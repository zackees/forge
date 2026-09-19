import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import forge_rust
import rust_toolchain

WORKFLOW = ROOT / ".github" / "workflows" / "forge-rust.yml"


def test_default_is_exact():
    assert rust_toolchain.require_exact(rust_toolchain.DEFAULT_RUST_TOOLCHAIN)


@pytest.mark.parametrize("value", ["stable", "beta", "nightly", "1.98", "", "1.98.1-beta"])
def test_floating_or_partial_toolchains_are_refused(value):
    with pytest.raises(SystemExit, match="not an exact"):
        rust_toolchain.require_exact(value)


def test_rustc_version_must_match_toolchain():
    line = "rustc 1.98.1 (abcdef012 2026-09-01)\n"
    assert rust_toolchain.verify_rustc_version(line, "1.98.1") == line.strip()
    with pytest.raises(SystemExit, match="expected rustc 1.98.1"):
        rust_toolchain.verify_rustc_version("rustc 1.99.0 (x 2026-10-01)", "1.98.1")
    with pytest.raises(SystemExit, match="expected rustc 1.98.1"):
        rust_toolchain.verify_rustc_version("rustc 1.98.10 (x 2026-10-01)", "1.98.1")


def test_workflow_default_matches_script_and_never_floats():
    text = WORKFLOW.read_text(encoding="utf-8")
    defaults = re.findall(r'rust_toolchain: \{required: false, default: "([^"]+)"', text)
    # workflow_call and workflow_dispatch must agree with the script.
    assert defaults == [rust_toolchain.DEFAULT_RUST_TOOLCHAIN] * 2
    assert "dtolnay/rust-toolchain@stable" not in text
    assert "--default-toolchain stable" not in text
    assert "RUSTUP_TOOLCHAIN: ${{ inputs.rust_toolchain }}" in text


def _argv(tmp_path, *extra):
    return [
        "forge_rust.py",
        "--tool", "cargo-nextest",
        "--version", "0.9.140",
        "--binary", "cargo-nextest",
        "--target", "x86_64-unknown-linux-musl",
        "--platform", "linux-x64-musl",
        "--source-repo", "nextest-rs/nextest",
        "--source-ref", "a9fef2964e34f64ed4fceeee7c0c3559ce560920",
        "--output", str(tmp_path),
        *extra,
    ]


def test_manifest_records_compiler(tmp_path, monkeypatch):
    (tmp_path / "cargo-nextest").write_bytes(b"binary")
    version_file = tmp_path / "rustc-version.txt"
    version_file.write_text("rustc 1.98.1 (abcdef012 2026-09-01)\n")
    monkeypatch.setattr(
        sys, "argv",
        _argv(tmp_path, "--rust-toolchain", "1.98.1", "--rustc-version-file", str(version_file)),
    )
    assert forge_rust.main() == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["rust_toolchain"] == "1.98.1"
    assert manifest["rustc_version"] == "rustc 1.98.1 (abcdef012 2026-09-01)"


def test_manifest_refuses_mismatched_compiler(tmp_path, monkeypatch):
    (tmp_path / "cargo-nextest").write_bytes(b"binary")
    version_file = tmp_path / "rustc-version.txt"
    version_file.write_text("rustc 1.97.1 (abcdef012 2026-08-01)\n")
    monkeypatch.setattr(
        sys, "argv",
        _argv(tmp_path, "--rust-toolchain", "1.98.1", "--rustc-version-file", str(version_file)),
    )
    with pytest.raises(SystemExit, match="expected rustc 1.98.1"):
        forge_rust.main()
