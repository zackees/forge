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
        "cpython/*:with_bz2": False,
        "cpython/*:with_curses": False,
        "cpython/*:with_gdbm": False,
        "cpython/*:with_lzma": False,
        "cpython/*:with_sqlite3": False,
        "cpython/*:with_tkinter": False,
        "cpython/*:optimizations": False,
        "cpython/*:lto": False,
    }

    def requirements(self):
        self.requires(f"cpython/{self.version}")

    def package(self):
        cpython = self.dependencies["cpython"].package_folder
        copied = []
        copied += copy(self, "*.dll", src=cpython, dst=self.package_folder, keep_path=True)
        copied += copy(self, "*.so*", src=cpython, dst=self.package_folder, keep_path=True)
        copied += copy(self, "*.dylib", src=cpython, dst=self.package_folder, keep_path=True)
        if not copied:
            raise RuntimeError(f"No shared libraries found in {cpython}")
        save(
            self,
            Path(self.package_folder) / "manifest.txt",
            f"Packaged shared libraries from cpython/{self.version}\n",
        )

    def package_info(self):
        self.cpp_info.libs = []
