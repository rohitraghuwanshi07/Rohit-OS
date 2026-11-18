import sys, pathlib, importlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
from fastapi.testclient import TestClient
W = [{"pid": "P1", "arrival": 0, "burst": 8, "priority": 2}, {"pid": "P2", "arrival": 1, "burst": 2, "priority": 1}]

def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ROHITOS_DATA", str(tmp_path)); import app as appmod; importlib.reload(appmod); return TestClient(appmod.app)

def test_evidence_endpoints(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    v = c.get("/api/validate/kernel").json(); assert v["matched"] == v["total"] == 59
    f = c.get("/api/fuzz?n=20").json(); assert f["failures"] == 0 and f["runs"] == 80
    assert len(c.get("/api/benchmark?seeds=3").json()["rows"]) == 12
    r = c.post("/api/recommend", json={"workload": W, "goal": "fairness"}).json(); assert r["recommended"] in ("fcfs", "sjf", "prio", "rr") and r["evidence"]

def test_bad_inputs_are_rejected_clearly(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.post("/api/recommend", json={"workload": W, "goal": "nope"}).status_code == 422
    assert c.post("/api/recommend", json={"workload": [], "goal": "response"}).status_code == 422
    assert c.post("/api/runs", json={"workload": [{"pid": "A", "arrival": 0, "burst": 0}], "policy": "fcfs"}).status_code == 422
    assert c.post("/api/runs", json={"workload": [{"pid": "A", "arrival": 0, "burst": 1}, {"pid": "A", "arrival": 1, "burst": 1}], "policy": "fcfs"}).status_code == 422
    assert c.post("/api/memory", json={"refs": [1, 2], "frames": 0}).status_code == 422
    assert c.post("/api/deadlock/analyze", json={"allocation": [[1]], "request": [[1, 1]], "available": [0]}).status_code == 422
