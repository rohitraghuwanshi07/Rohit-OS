"""Draw the report figures from real engine results and the captured kernel trace. Usage: python3 tools/make_figures.py <output_dir>"""
import json, pathlib, shutil, sys
root = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "os-engine"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rohitos import core, evidence, memory

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else root / "docs"); out.mkdir(parents=True, exist_ok=True)
for name in ("benchmark.png", "gantt_appendix_a.png"): shutil.copy(root / "docs" / name, out / name)
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
PAL = ["#4f46e5", "#12a37b", "#d9603b", "#1a8fb0"]

v = evidence.validate_kernel()
def segs(ev, total):
    o, prev, cur = [], 0, "kernel"
    for e in ev: o.append((prev, e["t"], cur)); prev, cur = e["t"], e["to"]
    o.append((prev, total, cur)); return o
fig, ax = plt.subplots(2, 1, figsize=(9, 2.4), sharex=True); col = {"kernel": PAL[0], "worker1": PAL[1], "worker2": PAL[2], "worker3": PAL[3]}
for a, (label, ev) in zip(ax, (("real kernel (QEMU)", v["kernel"]), ("simulator prediction", v["sim"]))):
    for s, e, p in segs(ev, v["total_ticks"]): a.barh(0, e - s, left=s, color=col[p], edgecolor="white", height=0.9)
    a.set_yticks([]); a.set_ylabel(label, rotation=0, ha="right", va="center"); a.spines["left"].set_visible(False)
ax[-1].set_xlabel("timer ticks (100 ticks = 1 second of kernel time)")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in col.values()]; fig.legend(handles, col, ncol=4, loc="upper center", frameon=False, fontsize=8)
fig.tight_layout(rect=(0, 0, 1, 0.88)); fig.savefig(out / "kernel_validation.png", dpi=170); plt.close(fig)

ref = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]; bel = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
for p, c, mk in zip(("fifo", "lru", "optimal"), PAL, ("o", "s", "^")): ax[0].plot(range(1, 8), [memory.replay(ref, f, p)["faults"] for f in range(1, 8)], mk + "-", label=p, color=c, markersize=6, alpha=0.9)
ax[0].set_xlabel("number of frames"); ax[0].set_ylabel("page faults"); ax[0].set_title("Classic reference string"); ax[0].legend(loc="upper right", frameon=True, fontsize=8)
ax[1].plot(range(1, 8), [memory.replay(bel, f, "fifo")["faults"] for f in range(1, 8)], "o-", color=PAL[2]); ax[1].set_xlabel("number of frames"); ax[1].set_title("FIFO on Belady's string"); ax[1].set_ylabel("page faults"); ax[1].set_ylim(4, 13)
ax[1].annotate("3 frames: 9\n4 frames: 10", xy=(4, 10), xytext=(4.8, 11.6), arrowprops=dict(arrowstyle="->"))
fig.tight_layout(w_pad=4); fig.savefig(out / "paging_curves.png", dpi=170); plt.close(fig)

fz = evidence.fuzz(500, seed=1); b = evidence.benchmark(seeds=30, quantum=3)
W = [core.Process("P1", 0, 8, 2), core.Process("P2", 1, 2, 1), core.Process("P3", 2, 4, 3), core.Process("P4", 3, 1, 1)]
numbers = {"validation": [v["matched"], v["total"]], "fuzz": {k: fz[k] for k in ("workloads", "runs", "checks", "failures")},
           "appendix": {p: core.simulate(W, p, 2)["metrics"] for p in core.POLICIES}, "bench": b["rows"]}
(out / "numbers.json").write_text(json.dumps(numbers, indent=1)); print(json.dumps({k: numbers[k] for k in ("validation", "fuzz")}))
