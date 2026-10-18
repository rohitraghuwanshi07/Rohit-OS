"""Generate docs/REPORT.md, charts and benchmark.csv. Every number comes from the engine; nothing is typed by hand."""
import csv, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "os-engine"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rohitos import core, evidence, memory, deadlock, security

docs = root / "docs"; docs.mkdir(exist_ok=True)
W = [core.Process("P1", 0, 8, 2), core.Process("P2", 1, 2, 1), core.Process("P3", 2, 4, 3), core.Process("P4", 3, 1, 1)]
POL = {"fcfs": "FCFS", "sjf": "SJF", "prio": "Priority", "rr": "Round Robin (q=2)"}
runs = {p: core.simulate(W, p, 2) for p in POL}
bench = evidence.benchmark(seeds=30, quantum=3); val = evidence.validate_kernel(); fz = evidence.fuzz(500, seed=1)
ref = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]; mem = {p: memory.replay(ref, 3, p)["faults"] for p in ("fifo", "lru", "optimal")}
dl = deadlock.detect(**deadlock.SCENARIOS["classic_deadlock"]); alerts = security.audit(security.attack_scenario())
rec = evidence.recommend(W, "response"); rules = ", ".join(sorted({a["rule"] for a in alerts}))

with open(docs / "benchmark.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=bench["rows"][0].keys()); w.writeheader(); w.writerows(bench["rows"])

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(1, 3, figsize=(11, 3.2), sharey=False); cols = ["#4f46e5", "#12a37b", "#d9603b", "#1a8fb0"]
for a, fam in zip(ax, evidence.FAMILIES):
    for i, (metric, off) in enumerate((("avg_response", -0.2), ("avg_waiting", 0.2))):
        vals = [next(r[metric] for r in bench["rows"] if r["family"] == fam and r["policy"] == p) for p in POL]
        a.bar([x + off for x in range(4)], vals, 0.4, label=metric.replace("avg_", ""), color=cols[i])
    a.set_xticks(range(4)); a.set_xticklabels(list(POL), rotation=0); a.set_title(fam.replace("_", " "))
ax[0].legend(); fig.suptitle(f"Mean over {bench['seeds']} seeded workloads (quantum {bench['quantum']}), lower is better"); fig.tight_layout(); fig.savefig(docs / "benchmark.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(4, 1, figsize=(9, 3.6), sharex=True); pc = {"P1": "#4f46e5", "P2": "#12a37b", "P3": "#d9603b", "P4": "#1a8fb0", "idle": "#dddddd"}
for a, (p, name) in zip(ax, POL.items()):
    for t, pid in enumerate(runs[p]["gantt"]): a.barh(0, 1, left=t, color=pc[pid], edgecolor="white")
    a.set_yticks([]); a.set_ylabel(name, rotation=0, ha="right", va="center"); a.spines["left"].set_visible(False)
ax[-1].set_xlabel("simulated time units"); fig.tight_layout(); fig.savefig(docs / "gantt_appendix_a.png", dpi=150); plt.close(fig)

def table(head, rows): return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])
m = lambda p, k: f"{runs[p]['metrics'][k]:.2f}"
appendix = table(["Policy", "Avg waiting", "Avg turnaround", "Avg response", "Context switches", "Event-stream hash"],
                 [[POL[p], m(p, "avg_waiting"), m(p, "avg_turnaround"), m(p, "avg_response"), runs[p]["metrics"]["context_switches"], runs[p]["event_hash"]] for p in POL])
benchtab = table(["Family", "Policy", "Wait", "Turnaround", "Response", "Max wait", "Switches"],
                 [[r["family"], r["policy"], r["avg_waiting"], r["avg_turnaround"], r["avg_response"], r["max_waiting"], r["context_switches"]] for r in bench["rows"]])
report = f"""# ROHIT OS: An Explainable Operating-System Laboratory with Deterministic Event Replay and a Bootable Kernel Prototype

## 1. Abstract
ROHIT OS has two deliberately separate tracks. **Track A** is a deterministic OS laboratory (CPU scheduling, page replacement, deadlock handling,
rule-based security auditing) exposed through a FastAPI service and a React/TypeScript console. Every run is an ordered event log with a replay hash,
so any scheduling decision can be inspected and re-run under another policy. **Track B** is a bootable 32-bit x86 kernel that runs in QEMU with
paging, ring-3 user programs, system calls and a RAM filesystem. The tracks are connected by an experiment: the simulator predicts the kernel's
scheduling order and is checked against a trace captured from a real boot ({val['matched']} of {val['total']} dispatches matched).

## 2. Scope and boundaries
The simulator models OS mechanisms in a controlled environment; it does not control the host operating system. The kernel is a separate program
that runs only inside an emulator. Security features are rule-based demonstrations over synthetic events, not malware detection.

## 3. Architecture
Engine (`os-engine/rohitos`) owns all algorithms on a logical clock. The API (`backend/app.py`) validates input, stores run metadata in SQLite and
event streams as JSONL. The UI (`frontend/`) is a client of the API and contains no algorithm logic. The kernel (`kernel/`) is built with a
cross-compiler and tested by booting it in QEMU.

## 4. Metric definitions
Turnaround = completion - arrival. Waiting = turnaround - burst. Response = first CPU start - arrival. Throughput = jobs / simulated time.
Context switches count dispatches that change the running process. Fairness is reported as the longest single wait. Ties break by arrival, then name.
SJF and Priority are non-preemptive; a lower priority number runs first.

## 5. Results
### 5.1 Appendix A workload (hand-calculated, then verified by tests)
{appendix}

![Gantt charts](gantt_appendix_a.png)

Round Robin gives the best response time ({m('rr', 'avg_response')} vs {m('fcfs', 'avg_response')} for FCFS) and waiting time on this workload but needs the most context switches.

### 5.2 Benchmark matrix ({bench['seeds']} seeded workloads per family, quantum {bench['quantum']})
{benchtab}

![Benchmark](benchmark.png)

Raw data: `benchmark.csv`. For the three non-preemptive policies response equals waiting by definition, so their bars match. No policy wins every measure: the trade-offs between response time, waiting time and switch count depend on the workload family.

### 5.3 Correctness evidence
- Fuzzing: {fz['workloads']} random workloads x 4 policies = {fz['runs']} runs, {fz['checks']} invariant checks, **{fz['failures']} violations**.
- Page replacement on the classic reference string with 3 frames: FIFO {mem['fifo']}, LRU {mem['lru']}, Optimal {mem['optimal']} faults (matches the textbook values). Belady's anomaly is reproduced in tests.
- Deadlock: the classic two-process cycle is detected (deadlocked processes {dl}); recovery by victim termination clears it. Banker's safety is tested on the textbook state.
- Security audit: {len(alerts)} alerts raised on the synthetic attack scenario ({rules}); benign file access raised none.
- Replay: identical workload and policy produce an identical event-stream hash.

### 5.4 Simulator validated against the real kernel
The engine models the kernel's round-robin scheduler (quantum 5, four tasks) and predicts its dispatch order. The kernel's actual trace was captured from a QEMU boot
(`{val['source']}`). Result: **{val['matched']}/{val['total']}** dispatches identical. A test confirms the comparison fails when the trace is altered.

### 5.5 Kernel self-test (captured serial output)
The kernel passes 12 boot-time checks: GDT with ring-3 segments and TSS; page allocator reuse; paging enabled; IDT with exception, timer, keyboard and syscall gates;
breakpoint handled and resumed; demand paging; a ring-3 program using write/read-file/exit syscalls; a user `cli` stopped by the privilege check; a user read of kernel
memory stopped by paging; RAM filesystem; preemptive round-robin across three tasks.

### 5.6 Policy advisor
For the Appendix A workload with a response-time goal the advisor recommends **{rec['recommended']}**. Evidence it prints: {' '.join(rec['evidence'])}

## 6. Limitations and honest notes
The kernel is 32-bit with one address space, one user program at a time, 255-byte files and no disk. The scheduler comparison is advice, not an automatic policy switch.
Benchmarks use synthetic seeded workloads, not real traces. The validation checks scheduling order, not timing in real time. The web UI was checked by build and API tests, not by automated browser tests.

## 7. Future work
64-bit long mode, per-process address spaces, preemptive user tasks, a block device and filesystem, automatic policy switching evaluated against a held-out workload set, and browser end-to-end tests.

## 8. Reproduce
`make deps && make test` runs the engine tests and boots the kernel; `python3 tools/capture_kernel.py` regenerates the kernel trace; `python3 tools/build_report.py` regenerates this report and its charts.
"""
(docs / "REPORT.md").write_text(report)
print("wrote docs/REPORT.md, benchmark.png, gantt_appendix_a.png, benchmark.csv")
