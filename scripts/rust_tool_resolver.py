#!/usr/bin/env python3
"""Tier-0 resolver for soldr-toolchain v1 catalogues.

Only the standard library is used so this module can bootstrap cargo-binstall
itself. URL fallback is permitted only for URLs carrying the same digest;
checksum failures are terminal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def resolve(index_url: str, tool: str, version: str, platform: str) -> dict:
    index = json.loads(_get(index_url))
    descriptor = next((item for item in index.get("tools", []) if item.get("name") == tool), None)
    if not descriptor:
        raise ValueError(f"tool {tool!r} is not in the v1 index")
    descriptor_url = descriptor.get("descriptor", {}).get("url")
    descriptor_sha = descriptor.get("descriptor", {}).get("sha256")
    if not descriptor_url or not descriptor_sha:
        raise ValueError(f"tool {tool!r} has no verified descriptor")
    raw = _get(descriptor_url)
    if _sha(raw) != descriptor_sha:
        raise ValueError(f"descriptor sha256 mismatch for {tool}")
    catalog = json.loads(raw)
    release = next((r for r in catalog.get("releases", []) if r.get("version") == version), None)
    if not release:
        raise ValueError(f"exact version {version!r} is not catalogued for {tool}")
    candidates = [p for p in release.get("platforms", []) if p.get("platform") == platform]
    if len(candidates) != 1:
        raise ValueError(f"expected one {tool}/{version}/{platform} row, found {len(candidates)}")
    row = candidates[0]
    digest = row.get("sha256")
    urls = row.get("urls") or ([row["url"]] if row.get("url") else [])
    if not digest or len(digest) != 64 or not urls:
        raise ValueError("catalogue row must contain a sha256 and at least one URL")
    for url in urls:
        if urlparse(url).scheme != "https":
            raise ValueError(f"catalogue URL is not HTTPS: {url}")
    return {"tool": tool, "version": version, "platform": platform,
            "filename": row.get("filename") or Path(urlparse(urls[0]).path).name,
            "urls": urls, "sha256": digest, "size_bytes": row.get("size_bytes"),
            "source": release.get("source")}

def fetch(metadata: dict, output: Path) -> Path:
    expected = metadata["sha256"]
    with tempfile.TemporaryDirectory(prefix="forge-rust-") as temp:
        archive = Path(temp) / metadata["filename"]
        last: Exception | None = None
        for url in metadata["urls"]:
            try:
                data = _get(url)
                actual = _sha(data)
                if actual != expected:
                    raise ValueError(f"asset sha256 mismatch: expected {expected}, got {actual}")
                archive.write_bytes(data)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
                return output
            except urllib.error.URLError as exc:
                last = exc
        raise RuntimeError(f"all same-digest URLs failed: {last}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-url", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = resolve(args.index_url, args.tool, args.version, args.platform)
    print(json.dumps(result, sort_keys=True) if args.json else result["urls"][0])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
