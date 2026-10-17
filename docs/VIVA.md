# ROHIT OS: viva cheat sheet

Read this, then open the code beside each answer and trace it yourself. If you cannot trace an answer, you do not own it yet.

## One-minute summary
ROHIT OS is an educational operating-system platform with two separate tracks. Track A is a deterministic simulation engine with a web console: CPU scheduling,
page replacement, deadlock handling and rule-based security auditing, where every decision is a recorded event you can replay and compare under another policy.
Track B is a small bootable x86 kernel run in QEMU with paging, user mode, system calls and a RAM filesystem. They are connected by one experiment: the simulator
predicts the real kernel's scheduling order and matched all 59 recorded dispatches. We evaluate with hand-checked tests, fuzzing, and seeded benchmarks.

## Say this boundary out loud first
"The simulator models OS mechanisms; it does not control the host computer. The kernel is a separate program that runs only in an emulator."

## Three kernel explanations (code: `kernel/kernel.c`, `kernel/boot.S`)
**1. How the timer switches tasks.** The PIT is set to 100 Hz and raises IRQ0. The CPU looks up vector 32 in the IDT and jumps to `irq0_stub` (boot.S). The stub pushes
segment registers and general registers, so the interrupted task's whole state sits on its own stack, then calls `irq0_c(esp)`. That function saves the stack pointer in
the task table, counts the quantum (5 ticks), and when it expires picks the next task round-robin and returns *that* task's saved stack pointer. The stub loads it into ESP,
pops the registers and executes `iret`, so the CPU resumes the other task. New tasks start with a hand-built fake stack frame that looks like an interrupted task.

**2. How a page fault becomes a mapped page.** Paging is enabled with CR3 pointing at the page directory. Touching an unmapped address in the demand region (0x40000000+)
raises exception 14. The handler reads the faulting address from CR2 and the error code. If the address is in the demand region and the page was not present, it takes a free
physical page from the allocator, maps it with `map_page`, and returns. The CPU re-runs the same instruction, which now succeeds. Outside that region the fault is fatal.

**3. How a user program is kept out of the kernel.** User code runs in ring 3 using GDT segments with privilege level 3. Kernel pages have the supervisor-only flag, so a user read of
0x100000 raises a page fault (error code 5: user, present, read) and the kernel kills the program. Privileged instructions such as `cli` raise a general protection fault.
User programs reach the kernel only through `int 0x80`, whose IDT gate allows ring 3. The syscall handler validates every user pointer against the user region before touching it.

## Likely questions
- **Why simulate and also build a kernel?** The simulator lets you compare policies safely and repeatably; the kernel proves the mechanisms work on real (emulated) hardware. The validation experiment links them.
- **How do you know the scheduler is correct?** Hand-calculated metrics for the Appendix A workload, invariants (bursts conserved, nothing runs before arrival), 500+ fuzzed workloads, and the kernel trace match.
- **What does deterministic replay mean here?** The same workload and policy give the same ordered event list, shown by an identical hash. Time is a logical clock, not wall-clock time.
- **Why is response equal to waiting for FCFS/SJF/Priority?** Without preemption a process starts once and keeps the CPU, so first start minus arrival equals all its waiting. Only Round Robin separates them.
- **Why does Round Robin look bad for CPU-bound jobs?** It interleaves equal jobs, so all finish late; waiting rises while response improves. The benchmark chart shows this trade-off honestly.
- **Is the adaptive scheduler AI?** No. It measures the workload, ranks policies on a stated goal, and prints evidence. It advises; it does not switch automatically.
- **Is the security module real malware detection?** No. It applies rules to synthetic events and suggests simulated responses.
- **What is Belady's anomaly?** More frames can cause more faults under FIFO; the tests reproduce it (3 frames: 9 faults, 4 frames: 10).
- **Deadlock: detection vs avoidance?** Detection finds a stuck set after it happens (here, a victim is terminated). Banker's avoidance refuses a request that would leave an unsafe state.
- **What are the kernel's limits?** 32-bit, one address space, one user program at a time, 255-byte files, no disk, no multi-core.
- **What would you do next?** 64-bit mode, per-process address spaces, preemptive user tasks, a block device, and browser end-to-end tests.

## Demo order (five minutes)
1. Console: run FCFS then Round Robin on the default workload, step the Time Machine, read one decision aloud.
2. Evidence tab: validate against kernel (59/59), run the benchmark, point at one trade-off.
3. Terminal: `fuzz 300`, then `advise fairness`.
4. Kernel: `make run`, then `run`, `crash`, `fault`, `ps`. Explain which parts run in the kernel and which in the simulator.

## Things to say honestly if asked
Much of the code was developed with AI assistance. Be ready to explain any file you present; the traces above are the places to practise.
