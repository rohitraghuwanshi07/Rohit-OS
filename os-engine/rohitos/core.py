"""Deterministic scheduler simulation. Logical clock only; no wall-clock timing."""
import hashlib, json
from dataclasses import dataclass, asdict

POLICIES = ("fcfs", "sjf", "prio", "rr")

@dataclass
class Process:
    pid: str
    arrival: int
    burst: int
    priority: int = 0

def simulate(procs, policy, quantum=2):
    if policy not in POLICIES: raise ValueError(f"unknown policy {policy}")
    if policy == "rr" and quantum < 1: raise ValueError("quantum must be >= 1")
    P = {p.pid: {"p": p, "rem": p.burst, "first": None, "done": None} for p in procs}
    if len(P) != len(procs): raise ValueError("duplicate pid")
    for p in procs:
        if p.burst < 1 or p.arrival < 0: raise ValueError(f"invalid process {p.pid}")
    events, ticks = [], []
    t, ready, run, qleft, last, switches, busy, finished = 0, [], None, 0, None, 0, 0, 0
    def ev(kind, pid, why): events.append({"t": t, "type": kind, "pid": pid, "why": why})
    while finished < len(P):
        for p in procs:
            if p.arrival == t:
                ready.append(p.pid)
                ev("arrive", p.pid, f"{p.pid} arrived (burst {p.burst}, priority {p.priority}); ready={ready}")
        if run and policy == "rr" and qleft == 0 and P[run]["rem"] > 0:
            ev("preempt", run, f"quantum {quantum} used, {P[run]['rem']} left")
            ready.append(run); run = None
        if run is None and ready:
            key = {"fcfs": lambda i: 0, "rr": lambda i: 0,
                   "sjf": lambda i: P[i]["p"].burst, "prio": lambda i: P[i]["p"].priority}[policy]
            pick = min(ready, key=lambda i: (key(i), P[i]["p"].arrival, i)) if policy in ("sjf", "prio") else ready[0]
            why = {"fcfs": "earliest arrival", "rr": "head of queue",
                   "sjf": "smallest burst", "prio": "lowest priority number"}[policy]
            ready.remove(pick); run, qleft = pick, quantum
            if P[pick]["first"] is None: P[pick]["first"] = t
            if last != pick: switches += 1
            ev("dispatch", pick, f"{policy}: {why}; candidates before pick={[pick]+ready}")
        if run is None:
            if not any(p.arrival > t for p in procs): break
            ticks.append("idle"); t += 1; continue
        ticks.append(run); P[run]["rem"] -= 1; qleft -= 1; busy += 1; last = run; t += 1
        if P[run]["rem"] == 0:
            P[run]["done"] = t; finished += 1; ev("complete", run, f"{run} finished at t={t}"); run = None
    span = len(ticks); n = len(P)
    per = {}
    for i, d in P.items():
        p = d["p"]; ta = d["done"] - p.arrival
        per[i] = {"completion": d["done"], "turnaround": ta, "waiting": ta - p.burst, "response": d["first"] - p.arrival}
    avg = lambda k: sum(v[k] for v in per.values()) / n
    metrics = {"avg_waiting": avg("waiting"), "avg_turnaround": avg("turnaround"), "avg_response": avg("response"),
               "throughput": n / span, "cpu_utilization": busy / span, "context_switches": switches,
               "max_waiting": max(v["waiting"] for v in per.values())}
    return {"policy": policy, "quantum": quantum, "events": events, "gantt": ticks, "per_process": per,
            "metrics": metrics, "event_hash": stream_hash(events)}

def stream_hash(events):
    return hashlib.sha256(json.dumps(events, sort_keys=True).encode()).hexdigest()[:16]

def workload_from_dicts(rows): return [Process(r["pid"], int(r["arrival"]), int(r["burst"]), int(r.get("priority", 0))) for r in rows]
def workload_to_dicts(procs): return [asdict(p) for p in procs]
