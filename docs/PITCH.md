# Interview pitch kit

## 30-second pitch
"I built an operating-system lab with two parts: a deterministic simulator that records every scheduling decision so I can replay and compare policies, and a small
real x86 kernel with paging, user mode and system calls that boots in QEMU. I connected them: the simulator predicts the kernel's scheduling order and matches
all 59 recorded switches. I also injected 12 bugs into the engine to check my tests catch them, and they did."

## Resume bullets (every number below is reproducible with the repo)
- Built a bootable 32-bit x86 kernel in C and assembly (GDT/TSS, IDT, paging with demand mapping, ring-3 user programs, `int 0x80` syscalls with pointer validation, RAM filesystem, serial shell), booted and tested in QEMU.
- Designed a deterministic OS simulation engine in Python (FCFS, SJF, Priority, Round Robin, FIFO/LRU/Optimal paging, deadlock detection and Banker's avoidance) with event replay hashing; exposed through a FastAPI service and a React/TypeScript console.
- Validated the simulator against the real kernel: it predicted 59 of 59 recorded task switches captured from QEMU.
- Verified correctness with 22 automated tests, a 500-workload fuzzer (thousands of invariant checks) and mutation testing (12 of 12 injected bugs detected); wired the browser to the live kernel over WebSocket and tested that path end to end.
- Added a GitHub Actions pipeline that runs the engine tests, builds the UI and boots the kernel.

## Questions a strong interviewer asks, and the honest answers
- **"Why should I believe the simulator is right?"** Four independent checks: hand-calculated cases, invariants under fuzzing, the real-kernel comparison, and mutation testing that proves the tests fail when the code is wrong.
- **"What was hard?"** Pick a real one from your own debugging. Good candidates from this build: user mode needs the TSS and careful segment handling on every interrupt; one-character code mutants hid behind stale Python bytecode; a test harness timing bug lost the first typed character.
- **"What would you change at scale?"** Per-process address spaces, 64-bit long mode, a block device, and replacing in-memory run state with the SQLite store; rate-limit and authenticate the live-kernel WebSocket before exposing it publicly.
- **"What is not done?"** The adaptive scheduler only advises; the kernel is single address space and 32-bit; benchmarks are synthetic; UI has no automated browser tests.
- **"Did you write this yourself?"** Be straight: AI assistance was used heavily. Then show you can explain and modify it: walk through `irq0_stub`, `exc_c` and `simulate()` live, and make a small change (for example a new scheduling policy) in front of them.

## Do before the interview
Push to a public GitHub repo (CI badge), add 4 to 5 screenshots and a 2-minute screen recording at the top of the README, and rehearse the kernel walkthroughs in `docs/VIVA.md` until you need no notes.
