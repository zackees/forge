# forge

Forge builds Conan recipes on native GitHub Actions runners and publishes the
resulting package folder as workflow artifacts.

The first workflow is intentionally small:

- manual `workflow_dispatch` trigger and reusable `workflow_call` trigger
- native matrix for Windows, Linux, and macOS on x64 and ARM64
- optional Linux musl targets for x64 and ARM64
- checks out a recipe repository at a requested ref
- has a master job try to pull prebuilt packages first
- delegates missing targets to native platform workers
- each worker tries to pull a prebuilt package before building locally
- runs `conan create` only when no matching binary package is available
- copies the generated Conan package folder into a deterministic artifact folder
- uploads one maximum-compression `.tar.gz` artifact per platform

## Runner Matrix

| Platform | Default | Runner label | Conan OS | Conan arch |
| --- | --- | --- | --- | --- |
| Windows x64 | On | `windows-2022` | `Windows` | `x86_64` |
| Windows ARM64 | Off | `windows-11-arm` | `Windows` | `armv8` |
| Linux x64 | On | `ubuntu-24.04` | `Linux` | `x86_64` |
| Linux ARM64 | Off | `ubuntu-24.04-arm` | `Linux` | `armv8` |
| Linux x64 musl | Off | `ubuntu-24.04` | `Linux` | `x86_64` |
| Linux ARM64 musl | Off | `ubuntu-24.04-arm` | `Linux` | `armv8` |
| macOS x64 | Off | `macos-15-intel` | `Macos` | `x86_64` |
| macOS ARM64 | On | `macos-15` | `Macos` | `armv8` |

## Usage

Open the **Forge Conan package** workflow and provide:

- `recipe_repo`: Git repository containing the Conan recipe
- `recipe_ref`: branch, tag, or commit to build
- `recipe_path`: path to the recipe directory inside that repository
- `name`: recipe name
- `version`: recipe version
- `build_type`: usually `Release`
- platform booleans, defaulting to Windows x64, Linux x64, and macOS ARM64

Forge can also be called from another workflow:

```yaml
jobs:
  forge:
    uses: zackees/forge/.github/workflows/forge-conan.yml@main
    with:
      recipe_repo: zackees/forge
      recipe_ref: main
      recipe_path: examples/hello
      name: hello
      version: 0.1.0
      linux_x64_musl: true
```

Forge runs:

```sh
conan export "$recipe_path" \
  --name "$name" \
  --version "$version"

conan install \
  --requires "$name/$version" \
  -s os="$conan_os" \
  -s arch="$conan_arch" \
  -s build_type="$build_type" \
  --build=never

conan create "$recipe_path" \
  --name "$name" \
  --version "$version" \
  -s os="$conan_os" \
  -s arch="$conan_arch" \
  -s build_type="$build_type" \
  --build=missing # only if the install step cannot pull a binary
```

Then it locates the generated package with `conan list`, copies the package
folder to `forge-output/package`, and uploads a gzip level 9 `.tar.gz` archive.

## Python ABI 3.10 Smoke Test

The `examples/python-abi310` recipe packages the Python stable ABI 3.10
development files used by maturin `abi3-py310` releases. It exports
`python3.lib`, `python310.lib`, the matching DLLs, and headers from the official
Python 3.10.11 NuGet package on Windows x64. Linux x64 and macOS ARM64 export
Python Build Standalone CPython 3.10.20 headers, `libpython3*`, `python3`,
`_sysconfigdata`, and Python config files so non-Windows maturin builds have a
real ABI payload instead of a manifest-only artifact. The same Python Build
Standalone payload flow is supported for Windows ARM64, Linux ARM64, Linux x64
musl, Linux ARM64 musl, and macOS x64. Windows ARM64 uses the stable ABI
`python3.lib` from Python Build Standalone CPython 3.11.15 because CPython 3.10
does not provide an official Windows ARM64 development package.

## Notes

Conan is not a remote build service. Forge supplies the machines by using
GitHub-hosted runners. The master job pulls prebuilt packages it can resolve and
delegates the rest to native workers. Workers also try to pull first, then build
missing packages locally when the recipe and toolchain support that target.

The matrix uses `fail-fast: false` so one unsupported platform does not cancel
the rest of the build.

The musl targets install `musl-tools` and pass a musl host triplet to Conan.
Conan does not expose musl as a default package-ID setting, so recipes that need
full musl behavior should make their toolchain support explicit.
