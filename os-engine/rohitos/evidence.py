"""Evidence tools: validate the simulator against the real kernel, fuzz invariants, benchmark, and explain a recommendation."""
import json, pathlib, random, statistics
from dataclasses import asdict
from . import core

TRACE = pathlib.Path(__file__).resolve().parents[2] / "workloads" / "kernel_trace.json"
NAMES = ["kernel", "worker1", "worker2", "worker3"]

def validate_kernel(trace=None):
    """Predict the kernel's round-robin dispatch order with the engine and compare with the captured QEMU trace."""
    trace = trace or json.loads(TRACE.read_text()); q, total = trace["quantum"], trace["total_ticks"]
    res = core.simulate([core.Process(n, 0, total // len(NAMES) + 5) for n in NAMES], "rr", q)
    sim, last = [], None
    for e in res["events"]:
        if e["type"] == "dispatch":
            if last is not None and e["t"] < total: sim.append({"t": e["t"], "from": last, "to": e["pid"]})
            last = e["pid"]
    ker = [e for e in trace["events"] if e["t"] < total]
    ok = [i < len(sim) and ker[i] == sim[i] for i in range(len(ker))]
    return {"source": trace["source"], "quantum": q, "total_ticks": total, "matched": sum(ok), "total": len(ker),
            "kernel": ker, "sim": sim, "ok": ok}

def _rand_workload(rng):
    return [core.Process(f"P{i}", rng.randint(0, 10), rng.randint(1, 12), rng.randint(0, 4)) for i in range(rng.randint(1, 8))]

def fuzz(n=200, seed=0):
    rng, fails, checks = random.Random(seed), [], 0
    for k in range(n):
        procs = _rand_workload(rng)
        for pol in core.POLICIES:
            q = rng.randint(1, 5); r = core.simulate(procs, pol, q); g = r["gantt"]
            def bad(msg):
                fails.append({"case": k, "policy": pol, "quantum": q, "problem": msg, "workload": [asdict(x) for x in procs]})
            for p in procs:
                checks += 3
                if g.count(p.pid) != p.burst: bad(f"{p.pid} ran {g.count(p.pid)} of {p.burst} units")
                if g.index(p.pid) < p.arrival: bad(f"{p.pid} ran before arrival")
                if r["per_process"][p.pid]["waiting"] < 0: bad(f"{p.pid} negative waiting")
            checks += 1
            if core.simulate(procs, pol, q)["event_hash"] != r["event_hash"]: bad("replay hash differs")
    return {"workloads": n, "runs": n * 4, "checks": checks, "failures": len(fails), "examples": fails[:3], "seed": seed}

FAMILIES = {
    "cpu_bound": lambda r: [core.Process(f"P{i}", r.randint(0, 3), r.randint(5, 30)) for i in range(6)],
    "interactive": lambda r: [core.Process("L", 0, 30)] + [core.Process(f"S{i}", r.randint(1, 15), r.randint(1, 3)) for i in range(6)],
    "mixed": lambda r: [core.Process(f"P{i}", r.randint(0, 10), r.randint(1, 15), r.randint(0, 4)) for i in range(8)]}

def benchmark(seeds=20, quantum=3):
    rows = []
    for fam, gen in FAMILIES.items():
        acc = {p: [] for p in core.POLICIES}
        for s in range(seeds):
            procs = gen(random.Random(s))
            for p in core.POLICIES: acc[p].append(core.simulate(procs, p, quantum)["metrics"])
        for p in core.POLICIES:
            m = {k: round(statistics.mean(x[k] for x in acc[p]), 3) for k in ("avg_waiting", "avg_turnaround", "avg_response", "max_waiting", "context_switches")}
            rows.append({"family": fam, "policy": p, **m})
    return {"seeds": seeds, "quantum": quantum, "rows": rows}

GOALS = {"response": "avg_response", "waiting": "avg_waiting", "fairness": "max_waiting", "switches": "context_switches"}

def recommend(procs, goal="response", q=2):
    if goal not in GOALS: raise ValueError(f"goal must be one of {sorted(GOALS)}")
    key, runs = GOALS[goal], {p: core.simulate(procs, p, q) for p in core.POLICIES}
    rank = sorted((runs[p]["metrics"][key], i, p) for i, p in enumerate(core.POLICIES))
    best, base = rank[0][2], runs["fcfs"]["metrics"]
    bursts = [p.burst for p in procs]; longest = max(procs, key=lambda p: p.burst)
    short = [p for p in procs if p is not longest and p.burst <= 0.25 * longest.burst and p.arrival >= longest.arrival]
    burst_of = {p.pid: p.burst for p in procs}
    wp = max(runs["fcfs"]["per_process"].items(), key=lambda kv: kv[1]["waiting"] / burst_of[kv[0]])
    ev = [f"{len(procs)} processes; burst spread (std/mean) {statistics.pstdev(bursts) / statistics.mean(bursts):.2f}; "
          f"{len(short)} short job(s) arrive while the longest ({longest.pid}, burst {longest.burst}) can be running."]
    if wp[1]["waiting"] >= 2 * burst_of[wp[0]]:
        ev.append(f"Under FCFS, {wp[0]} (burst {burst_of[wp[0]]}) waits {wp[1]['waiting']} units, {wp[1]['waiting'] / burst_of[wp[0]]:.1f}x its own burst: a convoy effect.")
    bm = runs[best]["metrics"]
    if best != "fcfs" and base[key]:
        ev.append(f"{best} improves {key} from {base[key]:.2f} (fcfs) to {bm[key]:.2f}, a {(1 - bm[key] / base[key]) * 100:.0f}% gain, "
                  f"with {bm['context_switches']} context switches versus {base['context_switches']}.")
    return {"goal": goal, "metric": key, "recommended": best, "ranking": [{"policy": p, "value": round(v, 3)} for v, _, p in rank],
            "evidence": ev, "caveat": f"Measured on this exact workload with quantum {q}; it is advice, not a universal ranking."}
