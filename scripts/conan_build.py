#!/usr/bin/env python3
"""Pull or build one Conan package and stage it under ``forge-output/package``.

This replaces ``conan_build.sh``. The shell version died on macOS runners,
which ship bash 3.2: with ``set -u`` an empty expansion of an array
(``"${extra_args[@]}"``) is an *unbound variable* error there, so every
recipe whose lane passes no ``-o``/``-c`` arguments failed before Conan ever
ran (libuuid darwin-x64/arm64, forge runs 41853818603 / 41853869396). Bash
4.4+ fixed that expansion, which is why the same script passed on Linux — a
host-version difference no assertion in this repository could have caught.

Everything the shell did is expressible as typed values, so the arguments are
built as ``list[str]`` and executed without a shell: no arrays, no word
splitting, and no ``set -u``.

Environment contract (unchanged):
    FORGE_NAME FORGE_VERSION FORGE_RECIPE_PATH FORGE_BUILD_TYPE
    FORGE_CONAN_OS FORGE_CONAN_ARCH
    optional: FORGE_LIBC FORGE_HOST_TRIPLET FORGE_MINGW
              FORGE_CONAN_OPTIONS (whitespace-separated, each passed as -o)
              FORGE_IN_CONTAINER
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MUSL = "musl"
EXPORT_SCRIPT = Path("forge/scripts/export_conan_package.py")


@dataclass(frozen=True)
class BuildConfig:
    """One recipe build, resolved from the lane's environment."""

    name: str
    version: str
    recipe_path: str
    build_type: str
    conan_os: str
    conan_arch: str
    libc: str = ""
    host_triplet: str = ""
    mingw: bool = False
    in_container: bool = False
    options: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env: dict[str, str]) -> BuildConfig:
        def required(key: str) -> str:
            value = env.get(key, "")
            if not value:
                raise SystemExit(f"conan_build: {key} must be set")
            return value

        return cls(
            name=required("FORGE_NAME"),
            version=required("FORGE_VERSION"),
            recipe_path=required("FORGE_RECIPE_PATH"),
            build_type=required("FORGE_BUILD_TYPE"),
            conan_os=required("FORGE_CONAN_OS"),
            conan_arch=required("FORGE_CONAN_ARCH"),
            libc=env.get("FORGE_LIBC", ""),
            host_triplet=env.get("FORGE_HOST_TRIPLET", ""),
            mingw=env.get("FORGE_MINGW", "") == "true",
            in_container=env.get("FORGE_IN_CONTAINER", "") == "true",
            options=tuple(env.get("FORGE_CONAN_OPTIONS", "").split()),
        )

    def extra_args(self) -> list[str]:
        """The lane's ``-o``/``-c`` arguments, in the order the shell built them."""

        args: list[str] = []
        for option in self.options:
            args.extend(["-o", option])
        if self.libc == MUSL:
            args.extend(["-c", "tools.build:compiler_executables={'c':'musl-gcc'}"])
            args.extend(["-c", f"tools.gnu:host_triplet={self.host_triplet}"])
        if self.mingw:
            args.extend(["-c", "tools.build:compiler_executables={'c':'gcc','cpp':'g++'}"])
            # GCC 14/15 promote these legacy C diagnostics to hard errors by
            # default, breaking pre-C23 autotools deps (libx264's
            # _beginthreadex implicit declaration, for one). Relax them.
            cflags = (
                "tools.build:cflags=['-Wno-error=implicit-function-declaration',"
                "'-Wno-error=implicit-int','-Wno-error=incompatible-pointer-types',"
                "'-Wno-error=int-conversion']"
            )
            args.extend(["-c", cflags])
            # Statically link the MinGW runtime so the executables are
            # self-contained (no libgcc_s / libstdc++-6 / libwinpthread-1).
            args.extend(
                ["-c", "tools.build:exelinkflags=['-static','-static-libgcc','-static-libstdc++']"]
            )
        if self.in_container:
            # The floor image is root and disposable: let recipes that need
            # system packages install them with yum/dnf.
            args.extend(["-c", "tools.system.package_manager:mode=install"])
            args.extend(["-c", "tools.system.package_manager:sudo=False"])
        return args

    def common_args(self) -> list[str]:
        return [
            "-s",
            f"os={self.conan_os}",
            "-s",
            f"arch={self.conan_arch}",
            "-s",
            f"build_type={self.build_type}",
        ]


def run(argv: list[str]) -> None:
    """Run one command with inherited stdio, failing the build on non-zero."""

    result = subprocess.run(argv, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def probe(argv: list[str]) -> bool:
    """Run a command that is allowed to fail, without hiding its output."""

    return subprocess.run(argv, check=False).returncode == 0


def build(config: BuildConfig) -> None:
    if config.in_container:
        # Conan Center binaries are built against a newer glibc than the floor
        # image, so take only recipes from it and build every dependency here.
        run(["conan", "remote", "update", "conancenter", "--recipes-only"])

    run(["conan", "export", config.recipe_path, "--name", config.name, "--version", config.version])

    reference = f"{config.name}/{config.version}"
    if probe(
        [
            "conan",
            "install",
            "--requires",
            reference,
            *config.common_args(),
            "--build=never",
            *config.extra_args(),
        ]
    ):
        print(f"Pulled prebuilt {reference}")
        return

    run(
        [
            "conan",
            "create",
            config.recipe_path,
            "--name",
            config.name,
            "--version",
            config.version,
            *config.common_args(),
            "--build=missing",
            *config.extra_args(),
        ]
    )


def export_package(config: BuildConfig) -> None:
    run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--name",
            config.name,
            "--version",
            config.version,
            "--output",
            "forge-output/package",
        ]
    )


def main(env: dict[str, str] | None = None) -> int:
    config = BuildConfig.from_env(dict(os.environ if env is None else env))
    run(["conan", "profile", "detect", "--force"])
    build(config)
    export_package(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
