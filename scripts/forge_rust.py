#!/usr/bin/env python3
"""Explicit Rust fetch/build state machine used by forge-rust.yml."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

STATES = ("validate", "catalogue", "cargo-binstall", "direct-upstream", "source-build", "smoke", "package")

def run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
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
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalogue-hit", action="store_true")
    parser.add_argument("--direct-upstream", action="store_true")
    args = parser.parse_args()
    if args.version.lower() in {"latest", "*"} or not args.source_ref or len(args.binary.strip()) == 0:
        raise SystemExit("exact version, immutable source ref, and binary are required")
    mode = choose_mode(catalogue=args.catalogue_hit, accelerator=args.tool != "cargo-binstall", direct=args.direct_upstream)
    manifest = {"schema_version": 1, "tool": args.tool, "version": args.version,
                "binary": args.binary, "target": args.target, "source_repo": args.source_repo,
                "source_ref": args.source_ref, "resolution_mode": mode,
                "quick_install": False, "telemetry": False}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
