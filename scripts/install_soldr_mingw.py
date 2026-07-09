#!/usr/bin/env python3
"""Install the soldr-toolchain managed MinGW-w64 GCC bundle for forge."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

import zstandard


VERSION = "15.3.0posix-14.0.0-msvcrt-r1"
SHAPE = "windows-x64-gnu"
TOOL = "mingw-w64-gcc"
TARGET = "x86_64-pc-windows-gnu"
CATALOGUE_URL = "https://zackees.github.io/soldr-toolchain/catalogue.v1.json"
ASSET_URL = (
    "https://media.githubusercontent.com/media/zackees/soldr-toolchain/assets/"
    f"{TOOL}/{VERSION}/{SHAPE}/bundle.tar.zst"
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "forge-mingw-installer"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.read()


def catalogue_sha256() -> str:
    catalogue = json.loads(fetch(CATALOGUE_URL))
    for entry in catalogue.get("entries", []):
        if entry.get("url") == ASSET_URL:
            return entry["sha256"]
    raise SystemExit(f"catalogue does not contain {ASSET_URL}")


def extract_tar_zst(blob: bytes, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    dest_root = dest.resolve()
    dctx = zstandard.ZstdDecompressor()
    with dctx.stream_reader(io.BytesIO(blob)) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                normalized = PurePosixPath(member.name.replace("\\", "/"))
                if (
                    Path(member.name).is_absolute()
                    or normalized.is_absolute()
                    or ".." in normalized.parts
                    or member.issym()
                    or member.islnk()
                ):
                    raise SystemExit(f"unsafe archive entry in {ASSET_URL}: {member.name}")
                target = (dest / member.name).resolve()
                if target != dest_root and dest_root not in target.parents:
                    raise SystemExit(f"archive entry escapes destination: {member.name}")
                archive.extract(member, dest)


def append_line(path: str | None, line: str) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--github-env", default=os.environ.get("GITHUB_ENV"))
    parser.add_argument("--github-path", default=os.environ.get("GITHUB_PATH"))
    args = parser.parse_args()

    expected = catalogue_sha256()
    blob = fetch(ASSET_URL)
    actual = hashlib.sha256(blob).hexdigest()
    if actual != expected:
        raise SystemExit(f"sha256 mismatch for {ASSET_URL}: expected {expected}, got {actual}")

    install_root = args.target_dir / TOOL / VERSION / SHAPE
    complete = install_root / ".complete"
    package_root = install_root / "package"
    bin_dir = package_root / "bin"
    gcc = bin_dir / "gcc.exe"
    if not complete.is_file() or not gcc.is_file():
        if install_root.exists():
            import shutil

            shutil.rmtree(install_root)
        extract_tar_zst(blob, install_root)
        complete.write_text(actual + "\n", encoding="utf-8")

    if not gcc.is_file():
        raise SystemExit(f"managed MinGW bundle did not provide {gcc}")

    tools = {
        "CC": gcc,
        "CXX": bin_dir / "g++.exe",
        "AR": bin_dir / "ar.exe",
        "RANLIB": bin_dir / "ranlib.exe",
        "WINDRES": bin_dir / "windres.exe",
        "CMAKE_C_COMPILER": gcc,
        "CMAKE_CXX_COMPILER": bin_dir / "g++.exe",
    }
    make_program = bin_dir / "mingw32-make.exe"
    if make_program.is_file():
        tools["CMAKE_MAKE_PROGRAM"] = make_program

    # Emit forward-slash paths. These env vars (AR/CC/CXX/...) are consumed by
    # recipe builds that run under msys2 bash (autotools/libtool), where a
    # Windows backslash path like `D:\a\_temp\...\ar.exe` gets its backslashes
    # eaten by the shell -> `D:a_temp...ar.exe: command not found`. Forward
    # slashes (`D:/a/_temp/.../ar.exe`) are accepted by both Windows tools and
    # msys2/bash, so they survive the round-trip. CMake also accepts them.
    def _posix(value: Path) -> str:
        return value.as_posix()

    append_line(args.github_path, _posix(bin_dir))
    append_line(args.github_env, f"MINGW_W64_GCC_ROOT={_posix(package_root)}")
    append_line(args.github_env, f"MINGW_W64_GCC_BIN={_posix(bin_dir)}")
    append_line(args.github_env, f"FORGE_TARGET_TRIPLE={TARGET}")
    append_line(args.github_env, "CMAKE_GENERATOR=MinGW Makefiles")
    for key, value in tools.items():
        append_line(args.github_env, f"{key}={_posix(value)}")

    print(f"installed {TOOL} {VERSION} for {TARGET} at {package_root}")
    print(f"verified sha256={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
