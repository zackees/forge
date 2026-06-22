from conan import ConanFile
from conan.tools.files import copy, save


class HelloConan(ConanFile):
    name = "hello"
    version = "0.1.0"
    package_type = "application"
    settings = "os", "arch", "compiler", "build_type"

    def build(self):
        save(self, "hello.txt", f"hello from {self.settings.os}-{self.settings.arch}\n")

    def package(self):
        copy(self, "hello.txt", src=self.build_folder, dst=self.package_folder)
