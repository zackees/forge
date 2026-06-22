# Python ABI 3.10 import library

This Forge recipe packages the Python stable ABI 3.10 development files used by
maturin `abi3-py310` releases.

Windows x64 uses the official Python 3.10.11 NuGet package and exports
`python3.lib`, `python310.lib`, `python3.dll`, `python310.dll`, and headers.
Linux x64 and macOS ARM64 use Python Build Standalone CPython 3.10.20
install-only stripped archives and export `python3`, `include/python3.10`,
`libpython3*`, `_sysconfigdata`, and Python config files.
