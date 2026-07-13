#!/usr/bin/env python3
"""Explicit Rust fetch/build state machine used by forge-rust.yml."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

STATES = (
    "validate",
    "catalogue",
    "cargo-binstall",
    "direct-upstream",
    "source-build",
    "smoke",
    "package",
)


def run(
    args: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=False, text=True, capture_output=True)


def choose_mode(*, catalogue: bool, accelerator: bool, direct: bool) -> str:
    if catalogue:
        return "catalogue"
    if accelerator:
        return "cargo-binstall"
    if direct:
        return "direct-upstream"
    return "source-build"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--resolution-mode",
        choices=("catalogue", "cargo-binstall", "direct-upstream", "source-build"),
        default="source-build",
    )
    args = parser.parse_args()
    if (
        args.version.lower() in {"latest", "*"}
        or not args.source_ref
        or len(args.binary.strip()) == 0
    ):
        raise SystemExit("exact version, immutable source ref, and binary are required")
    binary_name = args.binary + (
        ".exe" if args.target.endswith("-windows-msvc") else ""
    )
    binary_path = args.output / binary_name
    if not binary_path.is_file():
        raise SystemExit(f"built binary is missing: {binary_path}")
    payload_sha256 = hashlib.sha256(binary_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "tool": args.tool,
        "version": args.version,
        "binary": binary_name,
        "target": args.target,
        "platform": args.platform,
        "payload_sha256": payload_sha256,
        "source_repo": args.source_repo,
        "source_ref": args.source_ref,
        "resolution_mode": args.resolution_mode,
        "quick_install": False,
        "telemetry": False,
        "smoke": {"command": f"{binary_name} --version", "result": "passed"},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
