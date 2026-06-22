import shutil
from pathlib import Path

from conan import ConanFile
from conan.tools.files import copy, save


class Python3SharedConan(ConanFile):
    name = "python3"
    version = "3.12.7"
    package_type = "shared-library"
    settings = "os", "arch", "compiler", "build_type"
    exports_sources = "README.md"

    default_options = {
        "cpython/*:shared": True,
        "cpython/*:optimizations": False,
        "cpython/*:lto": False,
    }

    def requirements(self):
        self.requires(f"cpython/{self.version}")

    def package(self):
        cpython = self.dependencies["cpython"].package_folder
        copy(self, "*", src=cpython, dst=self.package_folder, keep_path=True, excludes=("*.pdb", "*.dSYM/*"))

        package_folder = Path(self.package_folder)
        libs = list(package_folder.rglob("python*.lib"))
        if self.settings.os == "Windows" and libs:
            python3_lib = libs[0].with_name("python3.lib")
            if not python3_lib.exists():
                shutil.copy2(libs[0], python3_lib)

        save(
            self,
            package_folder / "manifest.txt",
            f"Packaged full Release CPython payload from cpython/{self.version}\n",
        )

    def package_info(self):
        self.cpp_info.libs = []
