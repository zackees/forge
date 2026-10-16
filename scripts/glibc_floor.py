#!/usr/bin/env python3
"""Measure the glibc floor of every ELF file under a directory.

The floor of a package is the highest ``GLIBC_*`` symbol version any of its ELF
files needs, as reported by ``readelf -V`` (the README's rule). The script
prints every file's floor, writes the package floor to ``--output``, and exits
non-zero when that floor is above ``--max``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ELF_MAGIC = b"\x7fELF"
_GLIBC = re.compile(r"GLIBC_([0-9]+(?:\.[0-9]+)*)")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def floor_from_readelf(text: str) -> str | None:
    """Highest GLIBC_x.y version named in ``readelf -V`` output, or None."""
    versions = set(_GLIBC.findall(text))
    if not versions:
        return None
    return max(versions, key=version_key)


def is_elf(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    with path.open("rb") as handle:
        return handle.read(4) == ELF_MAGIC


def measure(root: Path, readelf: str = "readelf") -> dict[Path, str | None]:
    floors: dict[Path, str | None] = {}
    for path in sorted(root.rglob("*")):
        if not is_elf(path):
            continue
        result = subprocess.run(
            [readelf, "-V", "--wide", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        floors[path] = floor_from_readelf(result.stdout)
    return floors


def package_floor(floors: dict[Path, str | None]) -> str | None:
    measured = [floor for floor in floors.values() if floor]
    if not measured:
        return None
    return max(measured, key=version_key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--max", required=True, help="highest allowed glibc version, e.g. 2.17")
    parser.add_argument("--output", type=Path, help="file that receives the measured floor")
    parser.add_argument("--readelf", default="readelf")
    args = parser.parse_args(argv)

    floors = measure(args.root, args.readelf)
    for path, floor in floors.items():
        print(f"{floor or 'none':>8}  {path.relative_to(args.root).as_posix()}")
    floor = package_floor(floors)
    print(f"ELF files: {len(floors)}; package glibc floor: {floor or 'none'}; allowed: {args.max}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{floor or 'none'}\n", encoding="utf-8")

    if floor and version_key(floor) > version_key(args.max):
        offenders = [p for p, f in floors.items() if f and version_key(f) > version_key(args.max)]
        for path in offenders:
            print(
                f"::error::{path.relative_to(args.root).as_posix()} requires glibc "
                f"{floors[path]}, above the {args.max} floor",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
