import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import forge_rust


def test_manifest_records_ingest_contract(tmp_path, monkeypatch):
    payload = b"native-binary"
    (tmp_path / "cargo-nextest").write_bytes(payload)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "forge_rust.py",
            "--tool",
            "cargo-nextest",
            "--version",
            "0.9.140",
            "--binary",
            "cargo-nextest",
            "--target",
            "x86_64-unknown-linux-musl",
            "--platform",
            "linux-x64-musl",
            "--source-repo",
            "nextest-rs/nextest",
            "--source-ref",
            "a9fef2964e34f64ed4fceeee7c0c3559ce560920",
            "--output",
            str(tmp_path),
        ],
    )

    assert forge_rust.main() == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["version"] == "0.9.140"
    assert manifest["platform"] == "linux-x64-musl"
    assert manifest["payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert manifest["smoke"]["result"] == "passed"


def test_manifest_refuses_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "forge_rust.py",
            "--tool",
            "cargo-nextest",
            "--version",
            "0.9.140",
            "--binary",
            "cargo-nextest",
            "--target",
            "aarch64-pc-windows-msvc",
            "--platform",
            "windows-arm64-msvc",
            "--source-repo",
            "nextest-rs/nextest",
            "--source-ref",
            "a9fef2964e34f64ed4fceeee7c0c3559ce560920",
            "--output",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit, match="built binary is missing"):
        forge_rust.main()
