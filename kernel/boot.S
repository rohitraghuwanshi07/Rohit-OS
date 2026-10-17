.set MAGIC,0x1BADB002
.section .multiboot
.align 4
.long MAGIC, 0, -(MAGIC)
.section .bss
.align 16
stack_bottom: .skip 16384
stack_top:
.lcomm saved_ksp,4
.section .text
.global _start
_start:
    mov $stack_top, %esp
    push %ebx
    call kmain
    cli
1:  hlt
    jmp 1b

/* CPU exceptions 0-31: 16-byte stubs so stub n is isr_stubs + 16*n */
.macro ISRX n
.align 16
.if (\n==8)||(\n==10)||(\n==11)||(\n==12)||(\n==13)||(\n==14)||(\n==17)
    push $\n
.else
    push $0
    push $\n
.endif
    jmp isr_common
.endm
.align 16
.global isr_stubs
isr_stubs:
.irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    ISRX \n
.endr
.global isr128
isr128: push $0
    push $128
isr_common:
    push %ds
    push %es
    pusha
    mov $0x10,%ax
    mov %ax,%ds
    mov %ax,%es
    push %esp
    call exc_c
    add $4,%esp
    popa
    pop %es
    pop %ds
    add $8,%esp
    iret
.global irq0_stub
irq0_stub:
    push %ds
    push %es
    pusha
    mov $0x10,%ax
    mov %ax,%ds
    mov %ax,%es
    push %esp
    call irq0_c
    add $4,%esp
    mov %eax,%esp
    popa
    pop %es
    pop %ds
    iret
.global irq1_stub
irq1_stub:
    push %ds
    push %es
    pusha
    mov $0x10,%ax
    mov %ax,%ds
    mov %ax,%es
    call kbd_c
    popa
    pop %es
    pop %ds
    iret

.global enter_user
enter_user:
    mov 4(%esp),%eax
    mov 8(%esp),%ecx
    pusha
    mov %esp,saved_ksp
    mov $0x23,%dx
    mov %dx,%ds
    mov %dx,%es
    mov %dx,%fs
    mov %dx,%gs
    push $0x23
    push %ecx
    push $0x002
    push $0x1B
    push %eax
    iret
.global leave_user
leave_user:
    mov saved_ksp,%esp
    mov $0x10,%ax
    mov %ax,%ds
    mov %ax,%es
    mov %ax,%fs
    mov %ax,%gs
    popa
    ret

/* ---- user-mode programs (position independent, ring 3) ---- */
.global hello_start, hello_end, bad1_start, bad1_end, bad2_start, bad2_end
hello_start:
    call 1f
1:  pop %esi
    lea (hmsg-1b)(%esi), %ebx
    mov $1, %eax
    mov $(hmsg_end-hmsg), %ecx
    int $0x80
    lea (fname-1b)(%esi), %ebx
    sub $64, %esp
    mov %esp, %ecx
    mov $64, %edx
    mov $4, %eax
    int $0x80
    mov %esp, %ebx
    mov %eax, %ecx
    mov $1, %eax
    int $0x80
    mov $2, %eax
    xor %ebx, %ebx
    int $0x80
hmsg: .ascii "[user] hello from ring 3 via int 0x80; motd file says: "
hmsg_end:
fname: .asciz "motd"
hello_end:
bad1_start:
    cli
    jmp .
bad1_end:
bad2_start:
    mov 0x100000, %eax
    jmp .
bad2_end:
