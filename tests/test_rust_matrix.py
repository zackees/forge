import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from rust_matrix import ROWS, matrix

def test_matrix_has_all_native_targets():
    assert len(ROWS) == 8
    assert len({row["target"] for row in ROWS}) == 8
    assert {row["runner"] for row in ROWS} >= {"macos-15-intel", "windows-11-arm", "ubuntu-24.04-arm"}

def test_matrix_selection_is_explicit():
    assert [row["platform"] for row in matrix({"linux-x64-musl"})] == ["linux-x64-musl"]
