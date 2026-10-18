"""Inject deliberate bugs ("mutants") into the engine and check that the test suite fails for each one.
A suite that lets a mutant survive has a blind spot. Writes docs/MUTATION.md."""
import pathlib, shutil, subprocess, sys
root = pathlib.Path(__file__).resolve().parents[1]; src = root / "os-engine" / "rohitos"
MUTANTS = [
    ("core.py", 'lambda i: P[i]["p"].priority}', 'lambda i: -P[i]["p"].priority}', "priority order reversed"),
    ("core.py", "run, qleft = pick, quantum", "run, qleft = pick, quantum + 1", "round-robin quantum off by one"),
    ("core.py", "if last != pick: switches += 1", "switches += 1", "context switches over-counted"),
    ("core.py", '"response": d["first"] - p.arrival', '"response": d["first"]', "response time ignores arrival"),
    ("core.py", 'qleft == 0 and P[run]["rem"] > 0', 'qleft == 1 and P[run]["rem"] > 0', "preempts one tick early"),
    ("core.py", 'key=lambda i: (key(i), P[i]["p"].arrival, i)', 'key=lambda i: (key(i), -P[i]["p"].arrival, i)', "tie-break prefers later arrival"),
    ("memory.py", "victim = min(mem, key=lambda x: last[x])", "victim = max(mem, key=lambda x: last[x])", "LRU evicts most recent page"),
    ("memory.py", "victim = order.pop(0)", "victim = order.pop()", "FIFO evicts newest page"),
    ("deadlock.py", "request[i][j] <= work[j]", "request[i][j] < work[j]", "detection too strict"),
    ("deadlock.py", "need[i][j] <= work[j]", "need[i][j] < work[j]", "Banker's safety too strict"),
    ("security.py", 'e["value"] > rules["cpu_limit"]["limit"]', 'e["value"] < rules["cpu_limit"]["limit"]', "cpu rule inverted"),
    ("evidence.py", "ok = [i < len(sim) and ker[i] == sim[i]", "ok = [True", "kernel validation always passes"),
]
def tests_pass():
    for cache in root.rglob("__pycache__"): shutil.rmtree(cache, ignore_errors=True)   # one-character mutants keep size and mtime: never trust stale bytecode
    env = {**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", "os-engine/tests", "-x", "-q", "--ignore=os-engine/tests/test_kernel_ws.py"], cwd=root, capture_output=True, text=True, env=env)
    return r.returncode == 0

assert tests_pass(), "baseline tests must pass before mutating"
rows, killed = [], 0
for fname, old, new, label in MUTANTS:
    path = src / fname; original = path.read_text()
    assert old in original, f"mutation target not found: {label}"
    backup = path.with_suffix(".bak"); shutil.copy(path, backup)
    try:
        path.write_text(original.replace(old, new, 1)); dead = not tests_pass()
    finally:
        shutil.move(backup, path)
    killed += dead; rows.append((label, fname, "killed" if dead else "SURVIVED")); print(f"{'killed  ' if dead else 'SURVIVED'} {fname}: {label}")
assert tests_pass(), "source was not restored cleanly"
md = ["# Mutation check", "", f"**{killed}/{len(MUTANTS)} injected bugs were caught by the test suite.**", "",
      "Each row is a deliberate bug put into the engine; the suite must fail for it to count as killed.", "", "| Injected bug | File | Result |", "|---|---|---|"]
md += [f"| {a} | {b} | {c} |" for a, b, c in rows]
(root / "docs" / "MUTATION.md").write_text("\n".join(md) + "\n"); print(f"\n{killed}/{len(MUTANTS)} mutants killed")
sys.exit(0 if killed == len(MUTANTS) else 1)
