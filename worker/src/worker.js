const ALLOWED_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp", "gif"]);
const CONTENT_TYPES = new Map([
  ["image/png", "png"],
  ["image/jpeg", "jpg"],
  ["image/webp", "webp"],
  ["image/gif", "gif"],
]);

export default {
  async fetch(request, env) {
    const cors = corsHeaders(env);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);
    try {
      if (request.method === "GET" && url.pathname === "/") {
        return jsonResponse({ ok: true, service: "ImageHost uploader" }, 200, cors);
      }
      if (request.method === "POST" && url.pathname === "/upload") {
        return await handleUpload(request, env, cors);
      }
      return jsonResponse({ ok: false, error: "Not found" }, 404, cors);
    } catch (error) {
      return jsonResponse({ ok: false, error: error.message || String(error) }, 500, cors);
    }
  },
};

async function handleUpload(request, env, cors) {
  assertEnv(env, ["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO", "GITHUB_BRANCH", "PUBLIC_BASE_URL"]);
  enforceUploadSecret(request, env);

  const contentType = request.headers.get("content-type") || "";
  if (!contentType.includes("multipart/form-data")) {
    return jsonResponse({ ok: false, error: "Use multipart/form-data with field name file" }, 400, cors);
  }

  const form = await request.formData();
  const files = form.getAll("file").filter((item) => item instanceof File);
  if (!files.length) {
    return jsonResponse({ ok: false, error: "No file field found" }, 400, cors);
  }

  const maxBytes = Number(env.MAX_IMAGE_BYTES || 10 * 1024 * 1024);
  const existingRows = await loadIndex(env);
  const knownSha = new Set(existingRows.map((row) => row.sha256).filter(Boolean));
  const createdRows = [];

  for (const file of files) {
    if (file.size > maxBytes) {
      throw new Error(`${file.name} is larger than ${maxBytes} bytes`);
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    const sha256 = await sha256Hex(bytes);
    if (knownSha.has(sha256)) {
      const duplicate = existingRows.find((row) => row.sha256 === sha256);
      createdRows.push({ ...duplicate, duplicate: true });
      continue;
    }

    const ext = detectExtension(file.name, file.type, bytes);
    const now = new Date();
    const id = sha256.slice(0, 16);
    const safeOriginalName = sanitizeName(file.name || `upload.${ext}`);
    const storedPath = buildStoredPath(now, id, ext);
    const uploadUrl = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${storedPath}`;
    const content = bytesToBase64(bytes);

    await githubJson(uploadUrl, env, {
      method: "PUT",
      body: {
        message: `Upload image ${safeOriginalName}`,
        content,
        branch: env.GITHUB_BRANCH,
      },
    });

    const row = {
      id,
      created_at: now.toISOString(),
      uploader: form.get("uploader") || "web",
      source_issue: "",
      original_name: safeOriginalName,
      stored_path: storedPath,
      url: `${env.PUBLIC_BASE_URL.replace(/\/$/, "")}/${storedPath}`,
      sha256,
      size_bytes: file.size,
      content_type: canonicalContentType(ext, file.type),
    };
    existingRows.unshift(row);
    knownSha.add(sha256);
    createdRows.push(row);
  }

  await saveIndex(env, existingRows);
  return jsonResponse({ ok: true, files: createdRows }, 200, cors);
}

function enforceUploadSecret(request, env) {
  if (!env.UPLOAD_SECRET) {
    return;
  }
  const provided = request.headers.get("x-upload-secret") || "";
  if (provided !== env.UPLOAD_SECRET) {
    throw new Error("Invalid upload secret");
  }
}

async function loadIndex(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/data/images.json?ref=${env.GITHUB_BRANCH}`;
  const response = await githubJson(url, env);
  if (!response.content) {
    return [];
  }
  const text = base64ToUtf8(response.content);
  return text.trim() ? JSON.parse(text) : [];
}

async function saveIndex(env, rows) {
  const jsonPath = "data/images.json";
  const csvPath = "data/images.csv";
  const jsonText = `${JSON.stringify(rows, null, 2)}\n`;
  const csvText = toCsv(rows);
  await upsertFile(env, jsonPath, jsonText, "Update image JSON index");
  await upsertFile(env, csvPath, csvText, "Update image CSV index");
}

async function upsertFile(env, path, text, message) {
  const getUrl = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}?ref=${env.GITHUB_BRANCH}`;
  let sha;
  try {
    const current = await githubJson(getUrl, env);
    sha = current.sha;
  } catch (error) {
    if (!String(error.message).includes("404")) {
      throw error;
    }
  }
  const putUrl = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}`;
  const body = {
    message,
    content: utf8ToBase64(text),
    branch: env.GITHUB_BRANCH,
  };
  if (sha) {
    body.sha = sha;
  }
  await githubJson(putUrl, env, { method: "PUT", body });
}

async function githubJson(url, env, options = {}) {
  const init = {
    method: options.method || "GET",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      "Content-Type": "application/json",
      "User-Agent": "imagehost-cloudflare-worker",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  };
  if (options.body) {
    init.body = JSON.stringify(options.body);
  }
  const response = await fetch(url, init);
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }
  }
  if (!response.ok) {
    throw new Error(`GitHub API ${response.status}: ${JSON.stringify(data).slice(0, 800)}`);
  }
  return data;
}

function detectExtension(name, contentType, bytes) {
  const fromType = CONTENT_TYPES.get((contentType || "").toLowerCase());
  if (fromType) {
    return fromType;
  }
  const fromName = (name.split(".").pop() || "").toLowerCase();
  if (ALLOWED_EXTENSIONS.has(fromName)) {
    return fromName === "jpeg" ? "jpg" : fromName;
  }
  if (startsWith(bytes, [0x89, 0x50, 0x4e, 0x47])) return "png";
  if (startsWith(bytes, [0xff, 0xd8, 0xff])) return "jpg";
  if (startsWithAscii(bytes, "GIF87a") || startsWithAscii(bytes, "GIF89a")) return "gif";
  if (startsWithAscii(bytes, "RIFF") && asciiAt(bytes, 8, 12) === "WEBP") return "webp";
  throw new Error(`Unsupported image type: ${name || contentType}`);
}

function canonicalContentType(ext, fallback) {
  if (ext === "jpg" || ext === "jpeg") return "image/jpeg";
  if (ext === "png") return "image/png";
  if (ext === "webp") return "image/webp";
  if (ext === "gif") return "image/gif";
  return fallback || "application/octet-stream";
}

function buildStoredPath(date, id, ext) {
  const yyyy = String(date.getUTCFullYear());
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const stamp = date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  return `images/${yyyy}/${mm}/${stamp}_${id}.${ext}`;
}

function sanitizeName(name) {
  return name.replace(/[^\w.\-()\u4e00-\u9fa5]+/g, "_").slice(0, 180);
}

async function sha256Hex(bytes) {
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function toCsv(rows) {
  const fields = [
    "id",
    "created_at",
    "uploader",
    "source_issue",
    "original_name",
    "stored_path",
    "url",
    "sha256",
    "size_bytes",
    "content_type",
  ];
  const lines = [fields.join(",")];
  for (const row of rows) {
    lines.push(fields.map((field) => csvEscape(row[field] ?? "")).join(","));
  }
  return `${lines.join("\n")}\n`;
}

function csvEscape(value) {
  const text = String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function jsonResponse(payload, status, headers) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: {
      ...headers,
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function corsHeaders(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOW_ORIGIN || "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Upload-Secret",
  };
}

function assertEnv(env, names) {
  const missing = names.filter((name) => !env[name]);
  if (missing.length) {
    throw new Error(`Missing environment variables: ${missing.join(", ")}`);
  }
}

function startsWith(bytes, signature) {
  return signature.every((value, index) => bytes[index] === value);
}

function startsWithAscii(bytes, text) {
  return asciiAt(bytes, 0, text.length) === text;
}

function asciiAt(bytes, start, end) {
  return String.fromCharCode(...bytes.slice(start, end));
}

function bytesToBase64(bytes) {
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.slice(i, i + chunkSize));
  }
  return btoa(binary);
}

function utf8ToBase64(text) {
  return bytesToBase64(new TextEncoder().encode(text));
}

function base64ToUtf8(base64) {
  const normalized = base64.replace(/\s/g, "");
  const binary = atob(normalized);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}
