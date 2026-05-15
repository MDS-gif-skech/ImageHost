from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    return int(raw)


MAX_IMAGE_BYTES = env_int("MAX_IMAGE_BYTES", 10 * 1024 * 1024)
DEFAULT_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
REPO = os.getenv("GITHUB_REPOSITORY", "Ayayadaze/ImageHost")
ISSUE_NUMBER = os.getenv("ISSUE_NUMBER", "")
UPLOADER = os.getenv("UPLOADER", "unknown")
SOURCE_URL = os.getenv("SOURCE_URL", "")


IMAGE_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\((https://[^)\s]+)\)")
IMAGE_URL_RE = re.compile(r"https://[^\s)]+")


@dataclass(frozen=True)
class UploadResult:
    id: str
    created_at: str
    uploader: str
    source_issue: str
    original_name: str
    stored_path: str
    url: str
    sha256: str
    size_bytes: int
    content_type: str


def public_base_url() -> str:
    if DEFAULT_BASE_URL:
        return DEFAULT_BASE_URL
    owner, repo_name = REPO.split("/", 1)
    return f"https://{owner}.github.io/{repo_name}"


def read_event_body() -> str:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        return ""
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    if "comment" in event:
        return event["comment"].get("body", "")
    if "issue" in event:
        return event["issue"].get("body", "")
    return ""


def extract_candidate_urls(text: str) -> list[str]:
    urls: list[str] = []
    urls.extend(IMAGE_MARKDOWN_RE.findall(text))
    for url in IMAGE_URL_RE.findall(text):
        if is_github_attachment_url(url):
            urls.append(url)
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        clean = url.strip().rstrip(".,;")
        if clean not in seen:
            deduped.append(clean)
            seen.add(clean)
    return deduped


def is_github_attachment_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in {
        "github.com",
        "user-images.githubusercontent.com",
        "private-user-images.githubusercontent.com",
        "repository-images.githubusercontent.com",
        "objects.githubusercontent.com",
    }


def request_with_retry(url: str, token: str | None = None, retries: int = 3) -> tuple[bytes, str]:
    headers = {
        "User-Agent": "github-image-host-action",
        "Accept": "image/png,image/jpeg,image/webp,image/gif,*/*;q=0.8",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=45) as resp:
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                data = resp.read(MAX_IMAGE_BYTES + 1)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError(f"image is larger than {MAX_IMAGE_BYTES} bytes")
                return data, content_type
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2 * attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def extension_from_content(url: str, content_type: str, data: bytes) -> str:
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext in ALLOWED_EXTENSIONS:
        return path_ext

    guessed = mimetypes.guess_extension(content_type or "")
    if guessed == ".jpe":
        guessed = ".jpg"
    if guessed in ALLOWED_EXTENSIONS:
        return guessed

    signatures = [
        (b"\x89PNG\r\n\x1a\n", ".png"),
        (b"\xff\xd8\xff", ".jpg"),
        (b"GIF87a", ".gif"),
        (b"GIF89a", ".gif"),
        (b"RIFF", ".webp"),
    ]
    for sig, ext in signatures:
        if data.startswith(sig):
            if ext == ".webp" and data[8:12] != b"WEBP":
                continue
            return ext
    raise ValueError(f"unsupported image type: content_type={content_type!r}, url={url}")


def safe_original_name(url: str, ext: str) -> str:
    raw = Path(urlparse(url).path).name
    if raw and "." in raw:
        return raw[:180]
    return f"upload{ext}"


def load_json_index(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def write_json_index(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv_index(path: Path, rows: list[dict]) -> None:
    fieldnames = [
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
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_upload(url: str, token: str | None) -> UploadResult:
    data, content_type = request_with_retry(url, token=token)
    ext = extension_from_content(url, content_type, data)
    digest = hashlib.sha256(data).hexdigest()
    now = datetime.now(timezone.utc)
    month_dir = Path("images") / f"{now:%Y}" / f"{now:%m}"
    month_dir.mkdir(parents=True, exist_ok=True)

    short = digest[:16]
    issue_part = f"issue{ISSUE_NUMBER}_" if ISSUE_NUMBER else ""
    filename = f"{now:%Y%m%dT%H%M%SZ}_{issue_part}{short}{ext}"
    stored = month_dir / filename
    stored.write_bytes(data)

    stored_path = stored.as_posix()
    image_url = f"{public_base_url()}/{stored_path}"
    return UploadResult(
        id=short,
        created_at=now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        uploader=UPLOADER,
        source_issue=SOURCE_URL,
        original_name=safe_original_name(url, ext),
        stored_path=stored_path,
        url=image_url,
        sha256=digest,
        size_bytes=len(data),
        content_type=content_type or mimetypes.types_map.get(ext, "application/octet-stream"),
    )


def main() -> int:
    body = read_event_body()
    urls = extract_candidate_urls(body)
    if not urls:
        Path("upload_results.md").write_text(
            "No supported GitHub image attachment URL was found.\n",
            encoding="utf-8",
        )
        print("No image URLs found.")
        return 0

    token = os.getenv("GITHUB_TOKEN")
    json_path = Path("data/images.json")
    csv_path = Path("data/images.csv")
    rows = load_json_index(json_path)
    known_sha = {row.get("sha256") for row in rows}

    results: list[UploadResult] = []
    skipped: list[str] = []
    for url in urls:
        result = save_upload(url, token=token)
        if result.sha256 in known_sha:
            image_path = Path(result.stored_path)
            if image_path.exists():
                image_path.unlink()
            skipped.append(result.sha256[:16])
            continue
        rows.append(result.__dict__)
        known_sha.add(result.sha256)
        results.append(result)

    rows.sort(key=lambda row: row["created_at"], reverse=True)
    write_json_index(json_path, rows)
    write_csv_index(csv_path, rows)

    lines = ["## ImageHost upload result", ""]
    if results:
        lines.append("Saved images:")
        lines.append("")
        for item in results:
            lines.append(f"- `{item.original_name}`")
            lines.append(f"  - URL: {item.url}")
            lines.append(f"  - Path: `{item.stored_path}`")
        lines.append("")
    if skipped:
        lines.append("Skipped duplicate images:")
        lines.append("")
        for digest in skipped:
            lines.append(f"- `{digest}`")
        lines.append("")
    if not results and not skipped:
        lines.append("No image was saved.")
        lines.append("")

    Path("upload_results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"saved={len(results)} skipped={len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
