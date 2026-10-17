"""FastAPI control API. Engine owns all logic; this layer validates, stores runs in SQLite, serves events as JSONL."""
import json, os, sqlite3, sys, uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "os-engine"))
from rohitos import core, memory, deadlock, security, evidence

DATA = Path(os.environ.get("ROHITOS_DATA", Path(__file__).parent / "data")); DATA.mkdir(exist_ok=True)
db = sqlite3.connect(DATA / "runs.db", check_same_thread=False)
db.execute("create table if not exists runs(id text primary key, policy text, quantum int, workload text, event_hash text, n_events int)")
RUNS = {}  # id -> {"result":..., "cursor":int, "running":bool}
app = FastAPI(title="ROHIT OS control API")

class Proc(BaseModel):
    pid: str; arrival: int = Field(ge=0); burst: int = Field(ge=1); priority: int = Field(0, ge=0)
class RunReq(BaseModel):
    workload: list[Proc] = Field(min_length=1); policy: str; quantum: int = Field(2, ge=1)
class CompareReq(BaseModel):
    workload: list[Proc] = Field(min_length=1); policies: list[str] = Field(min_length=2); quantum: int = Field(2, ge=1)
class MemReq(BaseModel):
    refs: list[int] = Field(min_length=1); frames: int = Field(ge=1, le=16)
class DLReq(BaseModel):
    allocation: list[list[int]]; request: list[list[int]]; available: list[int]

def _sim(w, policy, q):
    try: return core.simulate(core.workload_from_dicts([p.model_dump() for p in w]), policy, q)
    except ValueError as e: raise HTTPException(422, str(e))
def _run(rid):
    if rid not in RUNS: raise HTTPException(404, "unknown run")
    return RUNS[rid]

@app.post("/api/runs")
def create_run(r: RunReq):
    res = _sim(r.workload, r.policy, r.quantum); rid = uuid.uuid4().hex[:8]
    RUNS[rid] = {"result": res, "cursor": 0, "running": False}
    (DATA / f"{rid}.jsonl").write_text("\n".join(json.dumps(e) for e in res["events"]))
    db.execute("insert into runs values(?,?,?,?,?,?)", (rid, r.policy, r.quantum, json.dumps([p.model_dump() for p in r.workload]), res["event_hash"], len(res["events"]))); db.commit()
    return {"id": rid, "event_hash": res["event_hash"], "n_events": len(res["events"])}
@app.post("/api/runs/{rid}/start")
def start(rid: str):
    s = _run(rid); s["cursor"] = len(s["result"]["events"]); s["running"] = False; return state(rid)
@app.post("/api/runs/{rid}/pause")
def pause(rid: str): _run(rid)["running"] = False; return state(rid)
@app.post("/api/runs/{rid}/step")
def step(rid: str):
    s = _run(rid); s["cursor"] = min(len(s["result"]["events"]), s["cursor"] + 1); return state(rid)  # unit: one event
@app.post("/api/runs/{rid}/reset")
def reset(rid: str): s = _run(rid); s["cursor"] = 0; return state(rid)
@app.get("/api/runs/{rid}/state")
def state(rid: str):
    s = _run(rid); ev = s["result"]["events"]; c = s["cursor"]
    return {"cursor": c, "total": len(ev), "time": ev[c - 1]["t"] if c else 0, "last_event": ev[c - 1] if c else None,
            "gantt": s["result"]["gantt"]}
@app.get("/api/runs/{rid}/events")
def events(rid: str, type: str | None = None, pid: str | None = None, offset: int = 0, limit: int = 200):
    ev = [e for e in _run(rid)["result"]["events"] if (not type or e["type"] == type) and (not pid or e["pid"] == pid)]
    return {"total": len(ev), "events": ev[offset:offset + limit]}
@app.get("/api/runs/{rid}/metrics")
def metrics(rid: str):
    r = _run(rid)["result"]
    return {"definitions": {"turnaround": "completion - arrival", "waiting": "turnaround - burst", "response": "first CPU start - arrival",
            "throughput": "jobs / simulated time", "cpu_utilization": "busy / elapsed", "max_waiting": "fairness: longest single wait"},
            "metrics": r["metrics"], "per_process": r["per_process"]}
@app.post("/api/compare")
def compare(r: CompareReq):
    out = {}
    for p in r.policies:
        res = _sim(r.workload, p, r.quantum); out[p] = {"metrics": res["metrics"], "event_hash": res["event_hash"]}
    return out
@app.post("/api/memory")
def mem(r: MemReq): return {p: memory.replay(r.refs, r.frames, p) for p in ("fifo", "lru", "optimal")}
@app.post("/api/deadlock/analyze")
def dl(r: DLReq):
    m = len(r.available)
    if len(r.allocation) != len(r.request) or any(len(x) != m for x in r.allocation + r.request):
        raise HTTPException(422, "allocation, request and available must have matching shapes")
    try:
        dead = deadlock.detect(r.allocation, r.request, r.available); killed, avail = deadlock.recover(r.allocation, r.request, r.available)
    except IndexError: raise HTTPException(422, "matrix shapes do not match")
    return {"deadlocked": dead, "recovery_killed": killed, "available_after": avail}
@app.get("/api/deadlock/scenarios")
def dls(): return deadlock.SCENARIOS
@app.get("/api/security/scan")
def sec(): ev = security.attack_scenario(); return {"events": ev, "alerts": security.audit(ev)}

class RecReq(BaseModel):
    workload: list[Proc] = Field(min_length=1); goal: str = "response"; quantum: int = Field(2, ge=1)
@app.get("/api/validate/kernel")
def vk(): return evidence.validate_kernel()
@app.get("/api/fuzz")
def fz(n: int = 200, seed: int = 0): return evidence.fuzz(min(max(n, 1), 1000), seed)
@app.get("/api/benchmark")
def bm(seeds: int = 20): return evidence.benchmark(min(max(seeds, 1), 100))
@app.post("/api/recommend")
def rec(r: RecReq):
    try: return evidence.recommend(core.workload_from_dicts([p.model_dump() for p in r.workload]), r.goal, r.quantum)
    except ValueError as e: raise HTTPException(422, str(e))

fe = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if fe.exists(): app.mount("/", StaticFiles(directory=fe, html=True), name="ui")
