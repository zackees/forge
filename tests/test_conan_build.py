"""The Conan build entry point is typed Python, not shell.

Why this file exists: `conan_build.sh` passed on Linux and failed on every
macOS runner with `extra_args[@]: unbound variable` (bash 3.2 treats an empty
array expansion under `set -u` as unset). forge runs 41853818603 /
41853869396 died before Conan started, so libuuid darwin-x64/arm64 could never
produce a bundle. There is no shell left in this path to regress.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import conan_build  # noqa: E402  (path shim, matching the other tests here)

REPO = Path(__file__).parents[1]

BASE_ENV = {
    "FORGE_NAME": "libuuid-darwin-arm64",
    "FORGE_VERSION": "2.41.6",
    "FORGE_RECIPE_PATH": "recipe/recipes/libuuid-darwin-arm64",
    "FORGE_BUILD_TYPE": "Release",
    "FORGE_CONAN_OS": "Macos",
    "FORGE_CONAN_ARCH": "armv8",
}


def test_the_workflow_runs_the_python_build_entry_point() -> None:
    workflow = (REPO / ".github" / "workflows" / "forge-conan.yml").read_text(encoding="utf-8")

    assert "conan_build.py" in workflow
    assert "conan_build.sh" not in workflow, "the bash build path is gone on purpose; see this module's docstring"


def test_a_lane_with_no_options_yields_no_extra_arguments() -> None:
    # The exact shape that broke: no FORGE_CONAN_OPTIONS, no musl, no mingw.
    config = conan_build.BuildConfig.from_env(BASE_ENV)

    assert config.extra_args() == []
    assert config.common_args() == ["-s", "os=Macos", "-s", "arch=armv8", "-s", "build_type=Release"]


def test_conan_options_become_dash_o_pairs() -> None:
    env = dict(BASE_ENV, FORGE_CONAN_OPTIONS="qt/*:shared=True  zlib/*:static=True")
    config = conan_build.BuildConfig.from_env(env)

    assert config.extra_args() == [
        "-o",
        "qt/*:shared=True",
        "-o",
        "zlib/*:static=True",
    ]


def test_musl_and_mingw_lanes_add_their_compiler_settings() -> None:
    musl = conan_build.BuildConfig.from_env(
        dict(BASE_ENV, FORGE_LIBC="musl", FORGE_HOST_TRIPLET="aarch64-linux-musl")
    )
    assert "-c" in musl.extra_args()
    assert "tools.gnu:host_triplet=aarch64-linux-musl" in musl.extra_args()

    mingw = conan_build.BuildConfig.from_env(dict(BASE_ENV, FORGE_MINGW="true"))
    joined = " ".join(mingw.extra_args())
    assert "tools.build:compiler_executables={'c':'gcc','cpp':'g++'}" in joined
    assert "tools.build:exelinkflags=" in joined


def test_a_container_lane_allows_system_packages() -> None:
    config = conan_build.BuildConfig.from_env(dict(BASE_ENV, FORGE_IN_CONTAINER="true"))

    assert "tools.system.package_manager:mode=install" in config.extra_args()
    assert "tools.system.package_manager:sudo=False" in config.extra_args()


@pytest.mark.parametrize("missing", ["FORGE_NAME", "FORGE_VERSION", "FORGE_RECIPE_PATH", "FORGE_CONAN_OS"])
def test_a_missing_required_variable_fails_loudly(missing: str) -> None:
    env = {key: value for key, value in BASE_ENV.items() if key != missing}

    with pytest.raises(SystemExit) as excinfo:
        conan_build.BuildConfig.from_env(env)

    assert missing in str(excinfo.value)
