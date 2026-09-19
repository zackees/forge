#!/usr/bin/env python3
"""Native smoke arguments for a Forge-built Rust binary.

Most tools answer ``--version``. Some do not: cargo-binstall's ``--version``
is its version-requirement option and needs a value, so it is smoked with
``-V``. Per-tool overrides live in ``rust-tools.json`` as ``smoke_args``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_SMOKE_ARGS = ("--version",)
MANAGED_PATH = Path(__file__).resolve().parents[1] / "rust-tools.json"


def smoke_args(tool: str, managed_path: Path = MANAGED_PATH) -> list[str]:
    tools = json.loads(managed_path.read_text(encoding="utf-8"))["tools"]
    args = (tools.get(tool) or {}).get("smoke_args", list(DEFAULT_SMOKE_ARGS))
    if not isinstance(args, list) or not args or not all(
        isinstance(item, str) and item for item in args
    ):
        raise SystemExit(f"{tool} smoke_args must be a non-empty list of strings")
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool", required=True)
    args = parser.parse_args()
    print(" ".join(smoke_args(args.tool)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
