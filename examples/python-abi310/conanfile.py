from pathlib import Path

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, download, mkdir, save, unzip


class PythonAbi310Conan(ConanFile):
    name = "python-abi310"
    version = "3.10.11"
    package_type = "shared-library"
    settings = "os", "arch", "build_type"

    _nuget_sha256 = "7c6f99b160a36a7e09492dfcff2b0a3a60bb5229ca44cdcc3ecb32871a6144d0"

    def validate(self):
        if self.settings.build_type != "Release":
            raise ConanInvalidConfiguration("python-abi310 only packages Release ABI artifacts")
        if self.settings.os == "Windows" and self.settings.arch != "x86_64":
            raise ConanInvalidConfiguration("python-abi310 currently packages Windows x64 only")

    def source(self):
        download(
            self,
            f"https://www.nuget.org/api/v2/package/python/{self.version}",
            "python.nupkg",
            sha256=self._nuget_sha256,
        )
        unzip(self, "python.nupkg", destination="python")

    def package(self):
        package_folder = Path(self.package_folder)
        if self.settings.os == "Windows":
            tools = Path(self.source_folder) / "python" / "tools"
            copy(self, "python3.lib", src=tools / "libs", dst=package_folder / "libs")
            copy(self, "python310.lib", src=tools / "libs", dst=package_folder / "libs")
            copy(self, "python3.dll", src=tools, dst=package_folder / "bin")
            copy(self, "python310.dll", src=tools, dst=package_folder / "bin")
            copy(self, "*", src=tools / "include", dst=package_folder / "include")
        else:
            mkdir(self, package_folder / "lib")

        save(
            self,
            package_folder / "manifest.txt",
            "Python ABI: abi3-py310\n"
            f"Version source: Python {self.version}\n"
            f"Platform: {self.settings.os}-{self.settings.arch}\n",
        )

    def package_info(self):
        if self.settings.os == "Windows":
            self.cpp_info.libs = ["python3"]
            self.cpp_info.libdirs = ["libs"]
            self.cpp_info.bindirs = ["bin"]
        else:
            self.cpp_info.libs = []
