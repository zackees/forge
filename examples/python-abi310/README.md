# Python ABI 3.10 import library

This Forge recipe packages the Python stable ABI 3.10 development files used by
maturin `abi3-py310` Windows releases. On Windows x64 it downloads the official
Python 3.10.11 NuGet package and exports `python3.lib`, `python310.lib`,
`python3.dll`, `python310.dll`, and headers without debug symbols.

Linux and macOS abi3 extension builds do not use a Windows-style import library,
so those platforms export a manifest only.
