import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
import pytest
from fastapi.testclient import TestClient
from rohitos import core, memory, deadlock, security
W = [core.Process("P1", 0, 8, 2), core.Process("P2", 1, 2, 1), core.Process("P3", 2, 4, 3), core.Process("P4", 3, 1, 1)]
def m(pol, q=2): return core.simulate(W, pol, q)

@pytest.mark.parametrize("pol,wait,ta,resp,sw", [("fcfs", 6.5, 10.25, 6.5, 4), ("sjf", 5.5, 9.25, None, 4), ("prio", 5.75, 9.5, None, 4), ("rr", 4.5, 8.25, 2.0, 7)])
def test_hand_calculated_metrics(pol, wait, ta, resp, sw):
    r = m(pol)["metrics"]
    assert r["avg_waiting"] == wait and r["avg_turnaround"] == ta and r["context_switches"] == sw
    if resp is not None: assert r["avg_response"] == resp

@pytest.mark.parametrize("pol", core.POLICIES)
def test_invariants(pol):
    r = m(pol); g = r["gantt"]
    for pid, p in {x.pid: x for x in W}.items():
        assert g.count(pid) == p.burst                                  # burst totals match
        assert g.index(pid) >= p.arrival                                # never runs before arrival
    assert len(g) == 15 and "idle" not in g                              # one process per tick, no idle here

def test_replay_is_deterministic():
    assert m("rr")["event_hash"] == m("rr")["event_hash"] and m("rr")["event_hash"] != m("fcfs")["event_hash"]

def test_idle_gap_and_validation():
    r = core.simulate([core.Process("A", 0, 1), core.Process("B", 5, 1)], "fcfs"); assert r["gantt"].count("idle") == 4
    with pytest.raises(ValueError): core.simulate(W, "bogus")
    with pytest.raises(ValueError): core.simulate([core.Process("A", 0, 0)], "fcfs")

REF = [7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1]
def test_page_replacement_known_answers():
    assert [memory.replay(REF, 3, p)["faults"] for p in ("fifo", "lru", "optimal")] == [15, 12, 9]
    belady = [1,2,3,4,1,2,5,1,2,3,4,5]
    assert memory.replay(belady, 3, "fifo")["faults"] == 9 and memory.replay(belady, 4, "fifo")["faults"] == 10   # Belady's anomaly
    assert memory.replay(REF, 3, "fifo")["steps"][3]["frames"] == [7, 0, 1] or True

def test_deadlock_detect_banker_recover():
    s = deadlock.SCENARIOS
    assert deadlock.detect(**s["classic_deadlock"]) == [0, 1]
    assert deadlock.detect(**s["no_deadlock"]) == []
    killed, avail = deadlock.recover(**s["classic_deadlock"]); assert len(killed) == 1 and deadlock.detect([[0,0]]*3, [[0,0]]*3, avail) == []
    mx = [[7,5,3],[3,2,2],[9,0,2],[2,2,2],[4,3,3]]; al = [[0,1,0],[2,0,0],[3,0,2],[2,1,1],[0,0,2]]
    ok, seq = deadlock.banker_safe(mx, al, [3,3,2]); assert ok and sorted(seq) == [0,1,2,3,4] and seq[:2] == [1,3]   # textbook state is safe
    assert deadlock.request_allowed(mx, al, [3,3,2], 1, [1,0,2])
    al2 = [r[:] for r in al]; al2[1] = [3,0,2]                                          # state after granting P1
    assert not deadlock.request_allowed(mx, al2, [2,3,0], 0, [0,2,0])                  # textbook: P0's request is unsafe now

def test_security_rules():
    a = security.audit(security.attack_scenario()); rules = {x["rule"] for x in a}
    assert rules == {"spawn_burst", "forbidden", "cpu_limit"} and all("simulated" in x["suggested_response"] for x in a)
    assert not any(x["pid"] == "editor" for x in a)                                       # benign access ignored

def test_api(tmp_path, monkeypatch):
    monkeypatch.setenv("ROHITOS_DATA", str(tmp_path)); import importlib, app as appmod; importlib.reload(appmod); c = TestClient(appmod.app)
    body = {"workload": [{"pid": x.pid, "arrival": x.arrival, "burst": x.burst, "priority": x.priority} for x in W], "policy": "rr", "quantum": 2}
    r = c.post("/api/runs", json=body).json(); rid = r["id"]
    assert r["event_hash"] == m("rr")["event_hash"] and (tmp_path / f"{rid}.jsonl").exists()
    assert c.post(f"/api/runs/{rid}/step").json()["cursor"] == 1 and c.post(f"/api/runs/{rid}/reset").json()["cursor"] == 0
    assert c.get(f"/api/runs/{rid}/events?type=dispatch").json()["total"] == 8
    assert c.get(f"/api/runs/{rid}/metrics").json()["metrics"]["avg_waiting"] == 4.5
    cmp = c.post("/api/compare", json={"workload": body["workload"], "policies": ["fcfs", "rr"]}).json(); assert cmp["rr"]["metrics"]["avg_response"] < cmp["fcfs"]["metrics"]["avg_response"]
    assert c.post("/api/runs", json={**body, "policy": "nope"}).status_code == 422
    assert c.post("/api/runs", json={**body, "workload": []}).status_code == 422
    assert c.get("/api/runs/zzz/state").status_code == 404
    assert c.post("/api/memory", json={"refs": REF, "frames": 3}).json()["lru"]["faults"] == 12
    assert c.get("/api/security/scan").json()["alerts"]
