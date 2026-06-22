# forge

Forge builds Conan recipes on native GitHub Actions runners and publishes the
resulting package folder as workflow artifacts.

The first workflow is intentionally small:

- manual `workflow_dispatch` trigger
- native matrix for Windows, Linux, and macOS on x64 and ARM64
- checks out a recipe repository at a requested ref
- runs `conan create` for the requested recipe path
- copies the generated Conan package folder into a deterministic artifact folder
- uploads one compressed artifact per platform

## Runner Matrix

| Platform | Runner label | Conan OS | Conan arch |
| --- | --- | --- | --- |
| Windows x64 | `windows-2022` | `Windows` | `x86_64` |
| Windows ARM64 | `windows-11-arm` | `Windows` | `armv8` |
| Linux x64 | `ubuntu-24.04` | `Linux` | `x86_64` |
| Linux ARM64 | `ubuntu-24.04-arm` | `Linux` | `armv8` |
| macOS x64 | `macos-15-intel` | `Macos` | `x86_64` |
| macOS ARM64 | `macos-15` | `Macos` | `armv8` |

## Usage

Open the **Forge Conan package** workflow and provide:

- `recipe_repo`: Git repository containing the Conan recipe
- `recipe_ref`: branch, tag, or commit to build
- `recipe_path`: path to the recipe directory inside that repository
- `name`: recipe name
- `version`: recipe version
- `build_type`: usually `Release`

Forge runs:

```sh
conan create "$recipe_path" \
  --name "$name" \
  --version "$version" \
  -s os="$conan_os" \
  -s arch="$conan_arch" \
  -s build_type="$build_type" \
  --build=missing
```

Then it locates the generated package with `conan list`, copies the package
folder to `forge-output/package`, and uploads a `.tar.gz` archive.

## Notes

Conan is not a remote build service. Forge supplies the machines by using
GitHub-hosted runners. Conan will download prebuilt packages when available and
build missing packages locally on the active runner when the recipe and toolchain
support that target.

The matrix uses `fail-fast: false` so one unsupported platform does not cancel
the rest of the build.
