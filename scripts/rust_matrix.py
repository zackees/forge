#!/usr/bin/env python3
"""Canonical native Rust producer matrix used by Forge and its tests."""
from __future__ import annotations

import argparse
import json

ROWS = (
    {
        "platform": "linux-x64-gnu",
        # Build against glibc 2.35 so the published binary also runs on
        # Debian 12 (glibc 2.36) and other supported older distributions.
        "runner": "ubuntu-22.04",
        "target": "x86_64-unknown-linux-gnu",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "glibc",
        "smoke": "native",
    },
    {
        "platform": "linux-arm64-gnu",
        "runner": "ubuntu-22.04-arm",
        "target": "aarch64-unknown-linux-gnu",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "glibc",
        "smoke": "native",
    },
    {
        "platform": "linux-x64-musl",
        "runner": "ubuntu-24.04",
        "target": "x86_64-unknown-linux-musl",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "musl",
        "smoke": "musl",
    },
    {
        "platform": "linux-arm64-musl",
        "runner": "ubuntu-24.04-arm",
        "target": "aarch64-unknown-linux-musl",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "musl",
        "smoke": "musl",
    },
    {
        "platform": "macos-x64",
        "runner": "macos-15-intel",
        "target": "x86_64-apple-darwin",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "darwin",
        "smoke": "native",
    },
    {
        "platform": "macos-arm64",
        "runner": "macos-15",
        "target": "aarch64-apple-darwin",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "darwin",
        "smoke": "native",
    },
    {
        "platform": "windows-x64-msvc",
        "runner": "windows-2022",
        "target": "x86_64-pc-windows-msvc",
        "archive_suffix": ".zip",
        "exe_suffix": ".exe",
        "libc": "msvc",
        "smoke": "native",
    },
    {
        "platform": "windows-arm64-msvc",
        "runner": "windows-11-arm",
        "target": "aarch64-pc-windows-msvc",
        "archive_suffix": ".zip",
        "exe_suffix": ".exe",
        "libc": "msvc",
        "smoke": "native",
    },
)


def matrix(enabled: set[str] | None = None) -> list[dict[str, str]]:
    selected = [
        dict(row) for row in ROWS if enabled is None or row["platform"] in enabled
    ]
    if not selected:
        raise ValueError("at least one Rust platform must be enabled")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", action="append", dest="platforms")
    args = parser.parse_args()
    print(
        json.dumps(
            {"include": matrix(set(args.platforms) if args.platforms else None)},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
