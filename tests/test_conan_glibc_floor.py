import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import glibc_floor
from master_pull import DEFAULT_GLIBC_FLOOR, LINUX_CONTAINERS, PLATFORMS, glibc_floor as select_floor, worker_row

DIGEST = re.compile(r"^quay\.io/pypa/manylinux[0-9_]+_(x86_64|aarch64)@sha256:[0-9a-f]{64}$")


def test_default_floor_is_2_17():
    assert DEFAULT_GLIBC_FLOOR == "2.17"
    assert select_floor(None) == "2.17"
    assert select_floor("") == "2.17"


def test_unknown_floor_is_rejected():
    with pytest.raises(SystemExit):
        select_floor("2.39")


def test_containers_are_digest_pinned_and_match_floor_and_arch():
    assert set(LINUX_CONTAINERS) == {"2.17", "2.28"}
    for floor, images in LINUX_CONTAINERS.items():
        tag = "manylinux2014" if floor == "2.17" else "manylinux_2_28"
        assert images["x86_64"].startswith(f"quay.io/pypa/{tag}_x86_64@")
        assert images["armv8"].startswith(f"quay.io/pypa/{tag}_aarch64@")
        for image in images.values():
            assert DIGEST.match(image), image


@pytest.mark.parametrize("floor", ["2.17", "2.28"])
def test_gnu_lanes_are_containerised_and_musl_exempt(floor):
    for _, config in PLATFORMS:
        row = worker_row(config, floor)
        if config.get("libc") == "glibc":
            assert row["container"] == LINUX_CONTAINERS[floor][config["conan_arch"]]
            assert row["glibc_floor"] == floor
        else:
            assert row["container"] == ""
            assert row["glibc_floor"] == ""
    glibc = [c["platform"] for _, c in PLATFORMS if c.get("libc") == "glibc"]
    assert glibc == ["linux-x64", "linux-arm64"]


def test_workflow_default_matches_script():
    text = (ROOT / ".github" / "workflows" / "forge-conan.yml").read_text()
    assert text.count('default: "2.17"') == 2
    assert "matrix.container" in text
    assert "glibc_floor.py" in text


READELF_SAMPLE = """
Version needs section '.gnu.version_r' contains 1 entry:
 Addr: 0x0000000000000500  Offset: 0x000500  Link: 7 (.dynstr)
  000000: Version: 1  File: libc.so.6  Cnt: 3
  0x0010:   Name: GLIBC_2.28  Flags: none  Version: 4
  0x0020:   Name: GLIBC_2.17  Flags: none  Version: 3
  0x0030:   Name: GLIBC_2.2.5  Flags: none  Version: 2
"""


def test_floor_from_readelf_uses_version_order_not_string_order():
    assert glibc_floor.floor_from_readelf(READELF_SAMPLE) == "2.28"
    assert glibc_floor.floor_from_readelf("GLIBC_2.9 GLIBC_2.10") == "2.10"
    assert glibc_floor.floor_from_readelf("no versions") is None


def _fake_readelf(tmp_path: Path, output: str) -> str:
    script = tmp_path / "fake-readelf"
    script.write_text(f"#!/bin/sh\ncat <<'EOF'\n{output}\nEOF\n")
    script.chmod(0o755)
    return str(script)


def _package(tmp_path: Path) -> Path:
    root = tmp_path / "package"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "tool").write_bytes(b"\x7fELF" + b"\0" * 60)
    (root / "README.txt").write_text("not elf")
    return root


def test_main_fails_above_floor_and_writes_measurement(tmp_path):
    root = _package(tmp_path)
    readelf = _fake_readelf(tmp_path, READELF_SAMPLE)
    out = tmp_path / "floor.txt"
    assert glibc_floor.main([str(root), "--max", "2.17", "--readelf", readelf, "--output", str(out)]) == 1
    assert out.read_text().strip() == "2.28"
    assert glibc_floor.main([str(root), "--max", "2.28", "--readelf", readelf]) == 0


def test_only_elf_files_are_measured(tmp_path):
    root = _package(tmp_path)
    floors = glibc_floor.measure(root, _fake_readelf(tmp_path, "GLIBC_2.17"))
    assert [p.name for p in floors] == ["tool"]


@pytest.mark.skipif(not shutil.which("readelf"), reason="readelf not installed")
def test_real_elf_has_a_floor(tmp_path):
    host = Path(shutil.which("readelf")).resolve()
    root = tmp_path / "package"
    root.mkdir()
    shutil.copy(host, root / "readelf")
    floor = glibc_floor.package_floor(glibc_floor.measure(root))
    assert floor is None or floor.startswith("2.")
