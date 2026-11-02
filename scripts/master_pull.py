#!/usr/bin/env python3
"""Pull prebuilt Conan packages when possible and plan worker builds."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path


# Linux -gnu lanes build inside a digest-pinned manylinux container so the
# package links against that image's glibc, not the runner's (README: "Linux
# glibc floor: 2.17, always"). 2.17 is the default and the rule; 2.28 is the
# documented exception for upstreams that cannot build against 2.17 (Qt 6).
DEFAULT_GLIBC_FLOOR = "2.17"
LINUX_CONTAINERS = {
    "2.17": {
        "x86_64": "quay.io/pypa/manylinux2014_x86_64@sha256:f6a6f153c9cf45470507ebbc27013e5db14ce21331b62fd2c540561f25e5f0a5",
        "armv8": "quay.io/pypa/manylinux2014_aarch64@sha256:c10b5d2ce68a4426011b5b9b8492f01037b9d0fd2187ed1956b346aa42faeb17",
    },
    "2.28": {
        "x86_64": "quay.io/pypa/manylinux_2_28_x86_64@sha256:4131ddd7acb9c6c966af02fe7e71edc51e078c2d41f475966697676430bfa2ae",
        "armv8": "quay.io/pypa/manylinux_2_28_aarch64@sha256:abd1230aa9e4058a74b89d27cd14ba18c0db036d7bfe6e6f219a29ea63c24eb6",
    },
}


PLATFORMS = [
    ("WINDOWS_X64", {
        "platform": "windows-x64",
        "runner": "windows-2022",
        "conan_os": "Windows",
        "conan_arch": "x86_64",
    }),
    ("WINDOWS_X64_GNU", {
        "platform": "windows-x64-gnu",
        "runner": "windows-2022",
        "conan_os": "Windows",
        "conan_arch": "x86_64",
        "mingw": True,
    }),
    ("WINDOWS_ARM64", {
        "platform": "windows-arm64",
        "runner": "windows-11-arm",
        "conan_os": "Windows",
        "conan_arch": "armv8",
    }),
    ("LINUX_X64", {
        "platform": "linux-x64",
        "runner": "ubuntu-24.04",
        "conan_os": "Linux",
        "conan_arch": "x86_64",
        "libc": "glibc",
    }),
    ("LINUX_ARM64", {
        "platform": "linux-arm64",
        "runner": "ubuntu-24.04-arm",
        "conan_os": "Linux",
        "conan_arch": "armv8",
        "libc": "glibc",
    }),
    ("LINUX_X64_MUSL", {
        "platform": "linux-x64-musl",
        "runner": "ubuntu-24.04",
        "conan_os": "Linux",
        "conan_arch": "x86_64",
        "libc": "musl",
        "host_triplet": "x86_64-linux-musl",
    }),
    ("LINUX_ARM64_MUSL", {
        "platform": "linux-arm64-musl",
        "runner": "ubuntu-24.04-arm",
        "conan_os": "Linux",
        "conan_arch": "armv8",
        "libc": "musl",
        "host_triplet": "aarch64-linux-musl",
    }),
    ("MACOS_X64", {
        "platform": "macos-x64",
        "runner": "macos-15-intel",
        "conan_os": "Macos",
        "conan_arch": "x86_64",
    }),
    ("MACOS_ARM64", {
        "platform": "macos-arm64",
        "runner": "macos-15",
        "conan_os": "Macos",
        "conan_arch": "armv8",
    }),
]


def enabled(name: str) -> bool:
    return os.environ.get(name, "").lower() == "true"


def glibc_floor(value: str | None) -> str:
    floor = (value or "").strip() or DEFAULT_GLIBC_FLOOR
    if floor not in LINUX_CONTAINERS:
        raise SystemExit(
            f"glibc_floor must be one of {sorted(LINUX_CONTAINERS)}, got {floor!r}"
        )
    return floor


def worker_row(config: dict, floor: str) -> dict:
    """Matrix row for a worker; every row carries container and glibc_floor."""
    row = dict(config)
    if row.get("libc") == "glibc":
        row["container"] = LINUX_CONTAINERS[floor][row["conan_arch"]]
        row["glibc_floor"] = floor
    else:
        row["container"] = ""
        row["glibc_floor"] = ""
    return row


def run(args: list[str], *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args), flush=True)
    return subprocess.run(args, check=check, text=True, env=env)


def tar_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    with tarfile.open(destination, "w:gz", compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            archive.add(path, arcname=path.relative_to(source))


def write_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--recipe-path", required=True)
    parser.add_argument("--build-type", required=True)
    parser.add_argument("--glibc-floor", default=os.environ.get("GLIBC_FLOOR"))
    parser.add_argument(
        "--options",
        default=os.environ.get("CONAN_OPTIONS", ""),
        help="whitespace-separated Conan options, each passed as -o",
    )
    args = parser.parse_args()
    floor = glibc_floor(args.glibc_floor)
    option_args = [arg for opt in args.options.split() for arg in ("-o", opt)]

    enabled_platforms = [config for env_name, config in PLATFORMS if enabled(env_name)]
    if not enabled_platforms:
        raise SystemExit("At least one platform must be enabled")

    missing = []
    artifact_root = Path("forge-prebuilt")
    shutil.rmtree(artifact_root, ignore_errors=True)
    artifact_root.mkdir(parents=True, exist_ok=True)

    for config in enabled_platforms:
        platform = config["platform"]
        if config.get("libc") == "musl":
            print(f"{platform}: musl targets are delegated to native workers")
            missing.append(config)
            continue
        if config.get("libc") == "glibc":
            # A cached or remote binary was built against an unknown glibc;
            # the worker pulls or builds inside the floor container and
            # measures the result.
            print(f"{platform}: glibc targets are delegated to containerised workers")
            missing.append(config)
            continue

        conan_home = Path(".conan-master") / platform
        env = os.environ.copy()
        env["CONAN_HOME"] = str(conan_home.resolve())

        run(["conan", "profile", "detect", "--force"], env=env)
        run([
            "conan",
            "export",
            args.recipe_path,
            "--name",
            args.name,
            "--version",
            args.version,
        ], env=env)

        install = run([
            "conan",
            "install",
            "--requires",
            f"{args.name}/{args.version}",
            "-s",
            f"os={config['conan_os']}",
            "-s",
            f"arch={config['conan_arch']}",
            "-s",
            f"build_type={args.build_type}",
            "--build=never",
            *option_args,
        ], env=env, check=False)

        if install.returncode != 0:
            print(f"{platform}: no prebuilt package available; delegating to worker")
            missing.append(config)
            continue

        package_output = artifact_root / platform / "package"
        run([
            "python",
            "forge/scripts/export_conan_package.py",
            "--name",
            args.name,
            "--version",
            args.version,
            "--output",
            str(package_output),
        ], env=env)

        archive_path = artifact_root / f"forge-{args.name}-{args.version}-{platform}.tar.gz"
        tar_directory(package_output.parent, archive_path)
        print(f"{platform}: uploaded from prebuilt package cache")

    matrix = {"include": [worker_row(config, floor) for config in missing]}
    write_output("matrix", json.dumps(matrix, separators=(",", ":")))
    write_output("has_builds", "true" if missing else "false")


if __name__ == "__main__":
    main()
