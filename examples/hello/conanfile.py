from conan import ConanFile
from conan.tools.files import copy, save

# On Linux the example also compiles a small executable so forge's glibc floor
# measurement has a real ELF file to read. It calls the newest libc function
# of the sysroot's glibc that forge supports as a floor (statx, GLIBC_2.28, or
# clock_gettime, GLIBC_2.17), so the measured floor equals the container's.
HELLO_C = r"""
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <sys/stat.h>
#include <time.h>

int main(void) {
    struct timespec now;
    clock_gettime(CLOCK_REALTIME, &now);
#if __GLIBC__ == 2 && __GLIBC_MINOR__ >= 28
    struct statx info;
    statx(AT_FDCWD, ".", 0, STATX_BASIC_STATS, &info);
#endif
#ifdef __GLIBC__
    printf("hello from glibc %d.%d\n", __GLIBC__, __GLIBC_MINOR__);
#else
    printf("hello\n");
#endif
    return 0;
}
"""


class HelloConan(ConanFile):
    name = "hello"
    version = "0.1.0"
    package_type = "application"
    settings = "os", "arch", "compiler", "build_type"

    def build(self):
        save(self, "hello.txt", f"hello from {self.settings.os}-{self.settings.arch}\n")
        if self.settings.os == "Linux":
            save(self, "hello.c", HELLO_C)
            compiler = self.conf.get("tools.build:compiler_executables", default={}).get("c", "cc")
            self.run(f"{compiler} -O2 hello.c -o hello")

    def package(self):
        copy(self, "hello.txt", src=self.build_folder, dst=self.package_folder)
        copy(self, "hello", src=self.build_folder, dst=self.package_folder + "/bin")
