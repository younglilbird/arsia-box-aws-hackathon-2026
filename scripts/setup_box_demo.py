#!/usr/bin/env python3
"""Seed the native Box annual-review folders without replacing existing files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.box_client import BoxClient, box_id, extract_text
from app.config import load_settings


ROOT_NAME = "Annual Review - Alex Chen - 2026"
CATEGORIES = ("Projects", "Peer Feedback", "Annual Plans")
MIME = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}


def ensure_folder(client: BoxClient, name: str, parent_id: str) -> str:
    parent = client.list_folder(parent_id)
    if parent.get("truncated"):
        raise RuntimeError("Folder listing is incomplete; choose a smaller dedicated parent folder.")
    for item in parent["entries"]:
        if item.get("name") == name:
            if item.get("type") != "folder":
                raise RuntimeError(f"A non-folder item already uses the name {name!r}; nothing was overwritten.")
            return box_id(item["id"])
    return box_id(client.create_folder(name, parent_id)["id"])


def save_config(path: Path, config: dict):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".native-config-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(config, output, indent=2)
            output.write("\n")
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def setup(client: BoxClient, root_folder_id: str | None = None, parent_folder_id: str = "0") -> dict:
    manifest = json.loads((ROOT / "demo-materials" / "manifest.json").read_text())
    for filename, category in manifest.items():
        path = ROOT / "demo-materials" / "files" / filename
        if Path(filename).name != filename or path.suffix not in MIME or not path.is_file() or category not in CATEGORIES:
            raise RuntimeError(f"The demo manifest contains an invalid document entry: {filename}")
    root = box_id(root_folder_id) if root_folder_id else ensure_folder(client, ROOT_NAME, box_id(parent_folder_id))
    category_folders = {category: ensure_folder(client, category, root) for category in CATEGORIES}
    reports = ensure_folder(client, "Reports", root)
    listings = {category: {item["name"]: item for item in client.list_folder(folder)["entries"]} for category, folder in category_folders.items()}
    for filename, category in manifest.items():
        path = ROOT / "demo-materials" / "files" / filename
        data = path.read_bytes()
        existing = listings[category].get(filename)
        if existing:
            if existing.get("type") != "file":
                raise RuntimeError(f"An existing folder uses the document name {filename}; nothing was overwritten.")
            remote = client.download(existing)
            same_content = data == remote or " ".join(extract_text(data, path.suffix[1:]).split()) == " ".join(extract_text(remote, path.suffix[1:]).split())
            if not same_content:
                raise RuntimeError(f"An existing document has different content: {filename}. It was left unchanged; use a new demo root.")
            print(f"Kept existing document: {category}/{filename}", file=sys.stderr)
        else:
            client.upload(category_folders[category], filename, data, MIME[path.suffix])
            print(f"Uploaded: {category}/{filename}", file=sys.stderr)
    return {
        "root_folder_id": root,
        "category_folders": category_folders,
        "reports_folder_id": reports,
        "employee_name": "Alex Chen",
        "year": 2026,
        "language": "en",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-folder-id", help="Reuse this existing Box folder and its matching category subfolders.")
    parser.add_argument("--parent-folder-id", default="0", help="Parent for a newly created demo root; defaults to the current Box user's root.")
    parser.add_argument("--config", type=Path, default=ROOT / ".local" / "native-config.json", help="Local configuration destination; contains no credentials.")
    arguments = parser.parse_args()
    client = BoxClient(load_settings())
    try:
        config = setup(client, arguments.root_folder_id, arguments.parent_folder_id)
        save_config(arguments.config, config)
        print(json.dumps(config, indent=2))
    finally:
        client.http.close()


if __name__ == "__main__":
    main()
