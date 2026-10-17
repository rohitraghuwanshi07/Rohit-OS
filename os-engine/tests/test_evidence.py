import json, sys, pathlib
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from rohitos import core, evidence
W = [core.Process("P1", 0, 8, 2), core.Process("P2", 1, 2, 1), core.Process("P3", 2, 4, 3), core.Process("P4", 3, 1, 1)]

def test_simulator_predicts_real_kernel_dispatches():
    v = evidence.validate_kernel()
    assert v["total"] == 59 and v["matched"] == v["total"]
    assert [e["to"] for e in v["kernel"][:4]] == ["worker1", "worker2", "worker3", "kernel"]

def test_validation_detects_a_wrong_model():
    t = json.loads(evidence.TRACE.read_text()); t["events"][3]["to"] = "worker1"
    assert evidence.validate_kernel(t)["matched"] == 58

def test_fuzz_finds_no_invariant_violations():
    r = evidence.fuzz(150, seed=7); assert r["failures"] == 0 and r["checks"] > 3000

def test_benchmark_shape_and_known_tradeoff():
    b = evidence.benchmark(seeds=5); rows = {(r["family"], r["policy"]): r for r in b["rows"]}
    assert len(b["rows"]) == 12
    assert rows[("interactive", "rr")]["avg_response"] < rows[("interactive", "fcfs")]["avg_response"]
    assert rows[("interactive", "rr")]["context_switches"] > rows[("interactive", "fcfs")]["context_switches"]

def test_recommendation_explains_itself():
    r = evidence.recommend(W, "response"); assert r["recommended"] == "rr" and r["ranking"][0]["value"] == 2.0
    assert any("convoy" in e for e in r["evidence"]) and "advice" in r["caveat"]
    with pytest.raises(ValueError): evidence.recommend(W, "nope")
