#!/usr/bin/env python3
"""Explicit Rust fetch/build state machine used by forge-rust.yml."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from rust_smoke import smoke_args
from rust_toolchain import require_exact, verify_rustc_version

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
    parser.add_argument(
        "--rust-toolchain",
        help="exact X.Y.Z toolchain the binary was compiled with",
    )
    parser.add_argument(
        "--rustc-version-file",
        type=Path,
        help="captured `rustc --version` output; must match --rust-toolchain",
    )
    args = parser.parse_args()
    if (
        args.version.lower() in {"latest", "*"}
        or not args.source_ref
        or len(args.binary.strip()) == 0
    ):
        raise SystemExit("exact version, immutable source ref, and binary are required")
    toolchain = None
    rustc_version = None
    if args.rustc_version_file is not None and args.rust_toolchain is None:
        raise SystemExit("--rustc-version-file requires --rust-toolchain")
    if args.rust_toolchain is not None:
        toolchain = require_exact(args.rust_toolchain)
        if args.rustc_version_file is not None:
            rustc_version = verify_rustc_version(
                args.rustc_version_file.read_text(encoding="utf-8"), toolchain
            )
    managed_path = Path(__file__).resolve().parents[1] / "rust-tools.json"
    managed = json.loads(managed_path.read_text(encoding="utf-8"))["tools"].get(
        args.tool
    )
    if managed is not None:
        actual = {
            "version": args.version,
            "binary": args.binary,
            "source": args.source_repo,
            "source_ref": args.source_ref,
        }
        for field, expected in managed.items():
            if field == "smoke_args":
                continue
            if actual.get(field) != expected:
                raise SystemExit(
                    f"managed {args.tool} {field}={actual.get(field)!r}, "
                    f"expected {expected!r}"
                )
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
        "smoke": {
            "command": " ".join([binary_name, *smoke_args(args.tool)]),
            "result": "passed",
        },
    }
    if toolchain is not None:
        manifest["rust_toolchain"] = toolchain
    if rustc_version is not None:
        manifest["rustc_version"] = rustc_version
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
