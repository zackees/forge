import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from rust_matrix import GLIBC_FLOOR, ROWS, matrix


def test_matrix_has_all_native_targets():
    assert len(ROWS) == 8
    assert len({row["target"] for row in ROWS}) == 8
    assert {row["runner"] for row in ROWS} >= {
        "macos-15-intel",
        "windows-11-arm",
        "ubuntu-24.04-arm",
    }


def test_matrix_selection_is_explicit():
    assert [row["platform"] for row in matrix({"linux-x64-musl"})] == ["linux-x64-musl"]


def test_glibc_builds_target_the_2_17_floor():
    """The floor comes from the build sysroot, not the runner.

    A previous revision chased this with runner labels (ubuntu-22.04 -> 2.35),
    which can only ever reach whatever glibc the newest available runner
    image ships. manylinux2014 is 2.17 and stays 2.17.
    """
    assert GLIBC_FLOOR == "2.17"
    glibc_rows = [row for row in ROWS if row["libc"] == "glibc"]
    assert glibc_rows, "the -gnu lanes must not disappear silently"
    assert all("manylinux2014" in row["container"] for row in glibc_rows)


def test_only_glibc_rows_are_containerised():
    # musl is static and darwin/windows have no glibc, so containerising them
    # would buy nothing and cost a pull.
    for row in matrix():
        assert bool(row["container"]) == (row["libc"] == "glibc"), row["platform"]


def test_every_matrix_row_defines_container():
    # `${{ matrix.container }}` is referenced unconditionally in the workflow;
    # a missing key there silently evaluates to empty and skips the container.
    assert all("container" in row for row in matrix())
