#!/usr/bin/env python3
"""Canonical native Rust producer matrix used by Forge and its tests."""
from __future__ import annotations

import argparse
import json

# Every Linux -gnu binary Forge publishes must run on glibc 2.17 (RHEL 7 and
# newer, which covers RHEL 8 / Debian 10 at 2.28). The runner's own glibc is
# irrelevant to that: the floor comes from the sysroot the compile links
# against, so the -gnu lanes build inside a manylinux2014 container while the
# job itself stays on a modern runner.
#
# The container is applied to the *build step*, not the job. A job-level
# `container:` would make actions/checkout fail — its Node 20 runtime needs
# glibc 2.28 and manylinux2014 is 2.17 — so checkout and packaging run on the
# host and only the compile is containerised.
GLIBC_FLOOR = "2.17"
MANYLINUX_X64 = "quay.io/pypa/manylinux2014_x86_64"
MANYLINUX_ARM64 = "quay.io/pypa/manylinux2014_aarch64"

ROWS = (
    {
        "platform": "linux-x64-gnu",
        "runner": "ubuntu-24.04",
        "container": MANYLINUX_X64,
        "target": "x86_64-unknown-linux-gnu",
        "archive_suffix": ".tar.gz",
        "exe_suffix": "",
        "libc": "glibc",
        "smoke": "native",
    },
    {
        "platform": "linux-arm64-gnu",
        "runner": "ubuntu-24.04-arm",
        "container": MANYLINUX_ARM64,
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
    # Every row carries the key so `${{ matrix.container }}` is always defined;
    # empty means "build directly on the runner".
    for row in selected:
        row.setdefault("container", "")
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
