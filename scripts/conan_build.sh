#!/usr/bin/env bash
# Pull or build one Conan package and copy its package folder to
# forge-output/package. Runs the same on a runner host and inside a Linux
# glibc floor container (see forge-conan.yml); the caller provides conan.
#
# Environment: FORGE_NAME FORGE_VERSION FORGE_RECIPE_PATH FORGE_BUILD_TYPE
# FORGE_CONAN_OS FORGE_CONAN_ARCH, optional FORGE_LIBC FORGE_HOST_TRIPLET
# FORGE_MINGW FORGE_CONAN_OPTIONS (whitespace-separated, each passed as -o)
# FORGE_IN_CONTAINER PYTHON.
set -euo pipefail

python_bin="${PYTHON:-python}"

conan profile detect --force

extra_args=()
for option in ${FORGE_CONAN_OPTIONS:-}; do
  extra_args+=("-o" "$option")
done
if [[ "${FORGE_LIBC:-}" == "musl" ]]; then
  extra_args+=("-c" "tools.build:compiler_executables={'c':'musl-gcc'}")
  extra_args+=("-c" "tools.gnu:host_triplet=${FORGE_HOST_TRIPLET}")
fi
if [[ "${FORGE_MINGW:-}" == "true" ]]; then
  extra_args+=("-c" "tools.build:compiler_executables={'c':'gcc','cpp':'g++'}")
  # GCC 14/15 promote these legacy C diagnostics to hard errors by
  # default, breaking pre-C23 autotools deps (e.g. libx264's
  # _beginthreadex implicit declaration). Relax them to warnings.
  extra_args+=("-c" "tools.build:cflags=['-Wno-error=implicit-function-declaration','-Wno-error=implicit-int','-Wno-error=incompatible-pointer-types','-Wno-error=int-conversion']")
  # Statically link the MinGW runtime so produced executables are
  # self-contained (no libgcc_s / libstdc++-6 / libwinpthread-1 DLL
  # dependencies on end-user machines).
  extra_args+=("-c" "tools.build:exelinkflags=['-static','-static-libgcc','-static-libstdc++']")
fi
if [[ "${FORGE_IN_CONTAINER:-}" == "true" ]]; then
  # The container is root and disposable: let recipes that need system
  # packages (xorg/system, opengl/system, ...) install them with yum/dnf.
  extra_args+=("-c" "tools.system.package_manager:mode=install")
  extra_args+=("-c" "tools.system.package_manager:sudo=False")
fi

common_args=(
  -s os="$FORGE_CONAN_OS"
  -s arch="$FORGE_CONAN_ARCH"
  -s build_type="$FORGE_BUILD_TYPE"
)

conan export "$FORGE_RECIPE_PATH" --name "$FORGE_NAME" --version "$FORGE_VERSION"

if conan install --requires "$FORGE_NAME/$FORGE_VERSION" "${common_args[@]}" \
    --build=never "${extra_args[@]}"; then
  echo "Pulled prebuilt $FORGE_NAME/$FORGE_VERSION"
else
  conan create "$FORGE_RECIPE_PATH" --name "$FORGE_NAME" --version "$FORGE_VERSION" \
    "${common_args[@]}" --build=missing "${extra_args[@]}"
fi

"$python_bin" forge/scripts/export_conan_package.py \
  --name "$FORGE_NAME" \
  --version "$FORGE_VERSION" \
  --output forge-output/package
