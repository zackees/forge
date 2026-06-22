# Python ABI 3.10 import library

This Forge recipe packages the Python stable ABI 3.10 development files used by
maturin `abi3-py310` releases.

Windows x64 uses the official Python 3.10.11 NuGet package and exports
`python3.lib`, `python310.lib`, `python3.dll`, `python310.dll`, and headers.
Windows ARM64 uses Python Build Standalone CPython 3.11.15 and exports the
stable ABI `python3.lib`, the matching runtime files, and headers.

Linux x64, Linux ARM64, Linux x64 musl, Linux ARM64 musl, macOS x64, and macOS
ARM64 use Python Build Standalone CPython 3.10.20 install-only stripped archives
and export `python3`, `include/python3.10`, `libpython3*`, `_sysconfigdata`, and
Python config files.
