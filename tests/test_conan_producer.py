"""Regression coverage for producer routing and argument plumbing."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("producer", ROOT / "scripts/master_pull.py")
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


@pytest.mark.parametrize("source", ["libuuid-darwin-x64", "libuuid-darwin-arm64"])
def test_routes_actual_sibling_per_lane(tmp_path, source):
    targets = ["libuuid-linux-x64-gnu", "libuuid-linux-arm64-gnu",
               "libuuid-darwin-x64", "libuuid-darwin-arm64"]
    for target in targets:
        directory = tmp_path / target
        directory.mkdir()
        (directory / "conanfile.py").touch()
    configs = [row for _, row in producer.PLATFORMS if row["conan_os"] != "Windows"
               and row.get("libc") != "musl"]
    for config, target in zip(configs, targets):
        assert producer.select_recipe(source, str(tmp_path / source), config) == {
            "recipe_name": target, "recipe_path": str(tmp_path / target)}
    with pytest.raises(SystemExit, match="missing platform recipe"):
        producer.select_recipe(source, str(tmp_path / source), producer.PLATFORMS[0][1])


def test_generic_recipe_keeps_path():
    assert producer.select_recipe("hello", "examples/hello", producer.PLATFORMS[0][1]) == {
        "recipe_name": "hello", "recipe_path": "examples/hello"}


@pytest.mark.parametrize("options", ["", "hello/*:shared=True hello/*:fPIC=False"])
@pytest.mark.parametrize("pull_fails", [False, True])
def test_python_builder_preserves_arguments(monkeypatch, options, pull_fails):
    spec = importlib.util.spec_from_file_location("producer_build", ROOT / "scripts/conan_build.py")
    builder = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, builder)
    spec.loader.exec_module(builder)
    calls = []
    monkeypatch.setattr(builder, "run", lambda argv: calls.append(argv))

    def probe(argv):
        calls.append(argv)
        return not pull_fails

    monkeypatch.setattr(builder, "probe", probe)
    builder.main({"FORGE_NAME": "hello", "FORGE_VERSION": "0.1.0",
                  "FORGE_RECIPE_PATH": "examples/hello", "FORGE_BUILD_TYPE": "Release",
                  "FORGE_CONAN_OS": "Macos", "FORGE_CONAN_ARCH": "armv8",
                  "FORGE_CONAN_OPTIONS": options})
    conan_calls = [call[1:] for call in calls if call[0] == "conan"]
    assert [call[0] for call in conan_calls] == ["profile", "export", "install"] + (["create"] if pull_fails else [])
    expected = [arg for opt in options.split() for arg in ("-o", opt)]
    assert conan_calls[2][conan_calls[2].index("--build=never") + 1:] == expected
    if pull_fails:
        assert conan_calls[3][conan_calls[3].index("--build=missing") + 1:] == expected


def test_linux_worker_matrix_uses_selected_recipe(tmp_path, monkeypatch, capsys):
    import sys

    source = tmp_path / "libuuid-darwin-x64"
    target = tmp_path / "libuuid-linux-x64-gnu"
    target.mkdir()
    (target / "conanfile.py").touch()
    monkeypatch.chdir(tmp_path)
    for flag, _ in producer.PLATFORMS:
        monkeypatch.setenv(flag, "true" if flag == "LINUX_X64" else "false")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setattr(sys, "argv", ["master_pull.py", "--name", source.name,
                                    "--version", "2.41.6", "--recipe-path", str(source),
                                    "--build-type", "Release"])
    monkeypatch.setattr(producer, "run", lambda *a, **kw: pytest.fail("Linux must run in worker"))
    producer.main()
    line = next(line for line in capsys.readouterr().out.splitlines() if line.startswith("matrix="))
    row, = json.loads(line.removeprefix("matrix="))["include"]
    assert row["recipe_name"] == target.name
    assert row["recipe_path"] == str(target)
    assert row["conan_os"] == "Linux"
    assert row["container"] == producer.LINUX_CONTAINERS["2.17"]["x86_64"]


def test_workflow_uses_shell_independent_pin_and_selected_worker_recipe():
    text = (ROOT / ".github/workflows/forge-conan.yml").read_text()
    assert text.count('"conan==${{ env.CONAN_VERSION }}"') == 3
    assert '"conan==${CONAN_VERSION}"' not in text
    assert text.count("FORGE_NAME: ${{ matrix.recipe_name }}") == 2
    assert text.count("FORGE_RECIPE_PATH: ${{ matrix.recipe_path }}") == 2
