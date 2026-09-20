# forge

Forge builds Conan recipes on native GitHub Actions runners and publishes the
resulting package folder as workflow artifacts.

The first workflow is intentionally small:

- manual `workflow_dispatch` trigger and reusable `workflow_call` trigger
- native matrix for Windows, Linux, and macOS on x64 and ARM64
- GNU ABI Windows x64 builds through the soldr-toolchain managed
  MinGW-w64 GCC bundle
- optional Linux musl targets for x64 and ARM64
- checks out a recipe repository at a requested ref
- has a master job try to pull prebuilt packages first
- delegates missing targets to native platform workers
- each worker tries to pull a prebuilt package before building locally
- runs `conan create` only when no matching binary package is available
- copies the generated Conan package folder into a deterministic artifact folder
- uploads one maximum-compression `.tar.gz` artifact per platform

## Linux glibc floor: 2.17, always

**Every Linux `-gnu` recipe MUST build against glibc 2.17.** This is a hard
requirement, not a preference, and it applies to all future recipes.

Forge output feeds `zackees/soldr-toolchain`, which feeds the `zackees/soldr`
release archive. A recipe built on a modern runner links against that runner's
glibc, and that floor then propagates all the way to end users: an archive
bundling one 2.39 binary does not run on RHEL 8 or Debian 10, no matter how
carefully everything else was built. The floor of the whole chain is the
**highest** floor of any artifact in it, so a single recipe that ignores this
defeats the rest.

The floor is set by the **sysroot the compile links against**, not by the
runner label. Chasing it with older runner images tops out at whatever the
oldest available image ships (`ubuntu-22.04` → 2.35) and drifts upward every
time a label is retired. A `manylinux2014` container is 2.17 and stays 2.17.

### Rust producer — implemented

`forge-rust.yml` builds the two `-gnu` lanes inside `manylinux2014`
(`scripts/rust_matrix.py`, the `container` field) and then **measures** the
result with `readelf -V`, failing the job if anything imports a symbol above
`GLIBC_FLOOR`. Only the compile is containerised: `actions/checkout` runs on
the host because its Node 20 runtime cannot start under glibc 2.17.

### Rust compiler: pinned, never `stable`

`forge-rust.yml` takes a `rust_toolchain` input (default `1.98.1`, tracking
`zackees/soldr`'s `rust-toolchain.toml`). It must be an exact `X.Y.Z` release;
`scripts/rust_toolchain.py` rejects floating channels. The build exports
`RUSTUP_TOOLCHAIN` so a `rust-toolchain.toml` in the source repository cannot
override it, captures `rustc --version`, and refuses to write the manifest
unless the compiler matches. The manifest records `rust_toolchain` and
`rustc_version`. Bump the default in the workflow and in
`scripts/rust_toolchain.py` together (a test keeps them in lockstep).

Registered producers live in `rust-tools.json`: cargo-binstall, cargo-chef,
cargo-nextest, crgx and soldr-maturin. cargo-chef and crgx moved here from the
soldr-toolchain `rust-cli` Conan recipe, whose Linux `-gnu` lanes build on the
bare `ubuntu-24.04` runner and therefore link against glibc 2.39.

### Conan recipes — still required

`forge-conan.yml` builds on the bare runner, so its Linux `-gnu` lanes
currently inherit `ubuntu-24.04`'s glibc 2.39. They must move into a
2.17 environment the same way.

Notes:

- **musl targets are exempt.** They are statically linked; there is no glibc to
  floor.
- **Do not reach for zig or `cargo-zigbuild`.** Both are being purged across
  these repos in favour of the blessed toolchain. Getting to 2.17 here is a
  matter of *building in an old sysroot*, which is toolchain-agnostic and needs
  no zig involvement.
- **Verify, do not assume.** `readelf -V <binary> | grep -o 'GLIBC_[0-9.]*' |
  sort -Vu | tail -1` reports the real floor. A recipe is only compliant when
  that prints `GLIBC_2.17` or lower.

## Runner Matrix

The runner label is where the job is *scheduled*. For Linux `-gnu` it is not
where the build should ultimately link — see the glibc floor requirement above.

| Platform | Default | Runner label | Conan OS | Conan arch | glibc floor |
| --- | --- | --- | --- | --- | --- |
| Windows x64 | On | `windows-2022` | `Windows` | `x86_64` | n/a |
| Windows x64 GNU | Off | `windows-2022` | `Windows` | `x86_64` | n/a |
| Windows ARM64 | Off | `windows-11-arm` | `Windows` | `armv8` | n/a |
| Linux x64 | On | `ubuntu-24.04` | `Linux` | `x86_64` | **must be 2.17** |
| Linux ARM64 | Off | `ubuntu-24.04-arm` | `Linux` | `armv8` | **must be 2.17** |
| Linux x64 musl | Off | `ubuntu-24.04` | `Linux` | `x86_64` | n/a (static) |
| Linux ARM64 musl | Off | `ubuntu-24.04-arm` | `Linux` | `armv8` | n/a (static) |
| macOS x64 | Off | `macos-15-intel` | `Macos` | `x86_64` | n/a |
| macOS ARM64 | On | `macos-15` | `Macos` | `armv8` | n/a |

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
