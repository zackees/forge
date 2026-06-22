from pathlib import Path
import shutil
import tarfile

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, download, save, unzip


class PythonAbi310Conan(ConanFile):
    name = "python-abi310"
    version = "3.10.11"
    package_type = "shared-library"
    settings = "os", "arch", "build_type"

    _windows_url = "https://www.nuget.org/api/v2/package/python/3.10.11"
    _windows_sha256 = "7c6f99b160a36a7e09492dfcff2b0a3a60bb5229ca44cdcc3ecb32871a6144d0"
    _linux_url = (
        "https://github.com/indygreg/python-build-standalone/releases/download/20260610/"
        "cpython-3.10.20+20260610-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
    )
    _linux_sha256 = "b49c63cb009a04afb2809001e7934c6af83a3d5976ff9d8d4676617b6b90ab4d"
    _macos_url = (
        "https://github.com/indygreg/python-build-standalone/releases/download/20260610/"
        "cpython-3.10.20+20260610-aarch64-apple-darwin-install_only_stripped.tar.gz"
    )
    _macos_sha256 = "9e654af00e34614420818dabddff2d9051916393425262790c2cb18488db0944"
    _standalone_source = "Python Build Standalone CPython 3.10.20+20260610"

    def validate(self):
        if self.settings.build_type != "Release":
            raise ConanInvalidConfiguration("python-abi310 only packages Release ABI artifacts")
        if self.settings.os == "Windows":
            if self.settings.arch != "x86_64":
                raise ConanInvalidConfiguration("python-abi310 currently packages Windows x64 only")
        elif self.settings.os == "Linux":
            if self.settings.arch != "x86_64":
                raise ConanInvalidConfiguration("python-abi310 currently packages Linux x64 only")
        elif self.settings.os == "Macos":
            if self.settings.arch != "armv8":
                raise ConanInvalidConfiguration("python-abi310 currently packages macOS ARM64 only")
        else:
            raise ConanInvalidConfiguration(f"python-abi310 does not package {self.settings.os}")

    def build(self):
        if self.settings.os == "Windows":
            download(self, self._windows_url, "python.nupkg", sha256=self._windows_sha256)
            unzip(self, "python.nupkg", destination="python")
            return

        if self.settings.os == "Linux":
            url = self._linux_url
            sha256 = self._linux_sha256
        else:
            url = self._macos_url
            sha256 = self._macos_sha256

        download(self, url, "python.tar.gz", sha256=sha256)
        with tarfile.open("python.tar.gz", "r:gz") as archive:
            self._extract_selected_archive_members(archive, Path("python-standalone"))

    def package(self):
        package_folder = Path(self.package_folder)
        if self.settings.os == "Windows":
            tools = Path(self.build_folder) / "python" / "tools"
            copy(self, "python3.lib", src=tools / "libs", dst=package_folder / "libs")
            copy(self, "python310.lib", src=tools / "libs", dst=package_folder / "libs")
            copy(self, "python3.dll", src=tools, dst=package_folder / "bin")
            copy(self, "python310.dll", src=tools, dst=package_folder / "bin")
            copy(self, "*", src=tools / "include", dst=package_folder / "include")
        else:
            python = Path(self.build_folder) / "python-standalone" / "python"
            copy(self, "python3", src=python / "bin", dst=package_folder / "bin")
            copy(self, "*", src=python / "include" / "python3.10", dst=package_folder / "include" / "python3.10")
            copy(self, "libpython3*", src=python / "lib", dst=package_folder / "lib")
            copy(
                self,
                "_sysconfigdata*.py",
                src=python / "lib" / "python3.10",
                dst=package_folder / "lib" / "python3.10",
            )
            copy(
                self,
                "*",
                src=next((python / "lib" / "python3.10").glob("config-3.10*")),
                dst=package_folder / "lib" / "python3.10" / "config",
            )

        save(
            self,
            package_folder / "manifest.txt",
            "Python ABI: abi3-py310\n"
            f"Version source: {self._version_source()}\n"
            f"Platform: {self.settings.os}-{self.settings.arch}\n",
        )

    def package_info(self):
        if self.settings.os == "Windows":
            self.cpp_info.libs = ["python3"]
            self.cpp_info.libdirs = ["libs"]
            self.cpp_info.bindirs = ["bin"]
        else:
            self.cpp_info.libs = ["python3.10"]
            self.cpp_info.includedirs = ["include/python3.10"]
            self.cpp_info.libdirs = ["lib"]
            self.cpp_info.bindirs = ["bin"]

    def _version_source(self):
        if self.settings.os == "Windows":
            return f"Python {self.version} NuGet"
        return self._standalone_source

    def _extract_selected_archive_members(self, archive, destination):
        destination = destination.resolve()
        members_by_name = {member.name: member for member in archive.getmembers()}
        for member in archive.getmembers():
            if not self._should_extract(member.name):
                continue
            member_path = (destination / member.name).resolve()
            if destination not in (member_path, *member_path.parents):
                raise ConanInvalidConfiguration(f"Archive member escapes destination: {member.name}")
            self._extract_member(archive, members_by_name, member, member_path)

    def _should_extract(self, name):
        return (
            name in ("python/bin/python3", "python/bin/python3.10")
            or name.startswith("python/include/python3.10/")
            or (name.startswith("python/lib/libpython3") and "/" not in name.removeprefix("python/lib/"))
            or name.startswith("python/lib/python3.10/_sysconfigdata")
            or name.startswith("python/lib/python3.10/config-3.10")
        )

    def _extract_member(self, archive, members_by_name, member, member_path):
        if member.isdir():
            member_path.mkdir(parents=True, exist_ok=True)
            return
        if member.issym():
            target_name = str((Path(member.name).parent / member.linkname).as_posix())
            target = members_by_name.get(target_name)
            if target is None:
                raise ConanInvalidConfiguration(f"Archive symlink target is missing: {member.name} -> {member.linkname}")
            self._extract_file(archive, target, member_path)
            return
        if member.isfile():
            self._extract_file(archive, member, member_path)

    def _extract_file(self, archive, member, member_path):
        member_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile(member) as src, member_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        member_path.chmod(member.mode)
