#!/usr/bin/env python3
"""Pinned Rust toolchain for every binary forge-rust.yml publishes.

Forge output is catalogued by zackees/soldr-toolchain and shipped inside the
zackees/soldr release archive, so the compiler that produced a published
binary must be reproducible from the run's inputs. A floating channel
(``stable``, ``beta``, ``nightly``) resolves to whatever rustup serves on the
day of the build, which makes two runs of the same source ref produce
binaries from different compilers. Only exact ``X.Y.Z`` releases are accepted.

``DEFAULT_RUST_TOOLCHAIN`` mirrors the ``rust_toolchain`` input default in
``.github/workflows/forge-rust.yml`` (a test keeps the two in lockstep) and
tracks the toolchain pinned by zackees/soldr's ``rust-toolchain.toml``.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_RUST_TOOLCHAIN = "1.98.1"

_EXACT = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def require_exact(toolchain: str) -> str:
    """Return ``toolchain`` if it is an exact ``X.Y.Z`` release, else exit."""
    if not _EXACT.fullmatch(toolchain.strip()):
        raise SystemExit(
            f"rust toolchain {toolchain!r} is not an exact X.Y.Z release; "
            "floating channels (stable/beta/nightly) are not reproducible"
        )
    return toolchain.strip()


def verify_rustc_version(rustc_version: str, toolchain: str) -> str:
    """Require ``rustc --version`` output to report exactly ``toolchain``."""
    line = rustc_version.strip()
    if not line.startswith(f"rustc {toolchain} "):
        raise SystemExit(
            f"compiler reported {line!r}, expected rustc {toolchain}; "
            "a rust-toolchain.toml or RUSTUP_TOOLCHAIN override leaked in"
        )
    return line


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="reject non-exact toolchain values")
    check.add_argument("toolchain")
    verify = sub.add_parser("verify", help="compare a rustc --version file")
    verify.add_argument("--toolchain", required=True)
    verify.add_argument("--rustc-version-file", type=Path, required=True)
    args = parser.parse_args()
    toolchain = require_exact(args.toolchain)
    if args.command == "verify":
        print(
            verify_rustc_version(
                args.rustc_version_file.read_text(encoding="utf-8"), toolchain
            )
        )
    else:
        print(toolchain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
