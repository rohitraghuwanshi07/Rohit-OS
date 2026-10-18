SHELL=/bin/bash
# Use the i686-elf cross toolchain when installed (macOS: brew install i686-elf-gcc i686-elf-binutils);
# otherwise fall back to host gcc -m32 (Linux).
ifneq ($(shell command -v i686-elf-gcc 2>/dev/null),)
CC=i686-elf-gcc
LD=i686-elf-ld
ARCH=
else
CC=gcc
LD=ld
ARCH=-m32
endif
CFLAGS=$(ARCH) -ffreestanding -fno-pic -fno-pie -fno-stack-protector -O2 -Wall -nostdlib
LIMIT=perl -e 'alarm 30; exec @ARGV' --
QEMU=qemu-system-i386 -kernel kernel.elf -serial stdio -display none -no-reboot \
     -device isa-debug-exit,iobase=0xf4,iosize=0x04
all: kernel.elf
kernel.elf: boot.S kernel.c linker.ld Makefile
	$(CC) $(CFLAGS) -c boot.S -o boot.o
	$(CC) $(CFLAGS) -c kernel.c -o kernel.o
	$(LD) -m elf_i386 -T linker.ld -o kernel.elf boot.o kernel.o
run: all
	$(QEMU)
test: all
	$(LIMIT) $(QEMU) -append autotest </dev/null | tee boot.log; test $${PIPESTATUS[0]} -eq 33
shell-test: all
	(sleep 6; printf '\nhelp\nls\ncat motd\nwrite notes hello rohit\ncat notes\nmem\nps\nrun\ncrash\nfault\nmem\nexit\n') | $(LIMIT) $(QEMU) | tee shell.log; test $${PIPESTATUS[1]} -eq 33
clean:
	rm -f *.o kernel.elf *.log
