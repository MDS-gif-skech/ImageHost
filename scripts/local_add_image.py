from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
BASE_URL = "https://Ayayadaze.github.io/ImageHost"


def load_rows(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_indexes(rows: list[dict]) -> None:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    (data_dir / "images.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fields = [
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
    with (data_dir / "images.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/local_add_image.py path/to/image.png")
        return 2

    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.exists():
        print(f"File not found: {source}")
        return 1

    ext = source.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        print(f"Unsupported extension: {ext}")
        return 1

    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    now = datetime.now(timezone.utc)
    target_dir = Path("images") / f"{now:%Y}" / f"{now:%m}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{now:%Y%m%dT%H%M%SZ}_{digest[:16]}{ext}"
    shutil.copyfile(source, target)

    stored_path = target.as_posix()
    row = {
        "id": digest[:16],
        "created_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "uploader": "local",
        "source_issue": "",
        "original_name": source.name,
        "stored_path": stored_path,
        "url": f"{BASE_URL}/{stored_path}",
        "sha256": digest,
        "size_bytes": len(data),
        "content_type": mimetypes.types_map.get(ext, "application/octet-stream"),
    }

    rows = load_rows(Path("data/images.json"))
    rows.insert(0, row)
    write_indexes(rows)
    print(row["url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
