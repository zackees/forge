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


PLATFORMS = [
    ("WINDOWS_X64", {
        "platform": "windows-x64",
        "runner": "windows-2022",
        "conan_os": "Windows",
        "conan_arch": "x86_64",
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


def run(args: list[str], *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(args), flush=True)
    return subprocess.run(args, check=check, text=True, env=env)


def tar_directory(source: Path, destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    with tarfile.open(destination, "w:gz") as archive:
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
    args = parser.parse_args()

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

    matrix = {"include": missing}
    write_output("matrix", json.dumps(matrix, separators=(",", ":")))
    write_output("has_builds", "true" if missing else "false")


if __name__ == "__main__":
    main()
