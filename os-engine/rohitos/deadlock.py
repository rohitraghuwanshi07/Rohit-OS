"""Deadlock lab: detection, Banker's safety (avoidance), and victim-kill recovery. Multi-instance model."""
def detect(allocation, request, available):
    """Classic detection. Returns the set of deadlocked process indexes."""
    n, m = len(allocation), len(available)
    work, finish = list(available), [all(x == 0 for x in allocation[i]) for i in range(n)]
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(request[i][j] <= work[j] for j in range(m)):
                work = [work[j] + allocation[i][j] for j in range(m)]; finish[i] = True; progress = True
    return [i for i in range(n) if not finish[i]]

def banker_safe(maximum, allocation, available):
    """Returns (safe, sequence)."""
    n, m = len(maximum), len(available)
    need = [[maximum[i][j] - allocation[i][j] for j in range(m)] for i in range(n)]
    work, done, seq = list(available), [False] * n, []
    while len(seq) < n:
        for i in range(n):
            if not done[i] and all(need[i][j] <= work[j] for j in range(m)):
                work = [work[j] + allocation[i][j] for j in range(m)]; done[i] = True; seq.append(i); break
        else: return False, seq
    return True, seq

def request_allowed(maximum, allocation, available, pid, req):
    """Avoidance: grant only if the resulting state stays safe."""
    if any(req[j] > available[j] or allocation[pid][j] + req[j] > maximum[pid][j] for j in range(len(req))): return False
    a2 = [row[:] for row in allocation]; a2[pid] = [a2[pid][j] + req[j] for j in range(len(req))]
    return banker_safe(maximum, a2, [available[j] - req[j] for j in range(len(req))])[0]

def recover(allocation, request, available):
    """Recovery: repeatedly kill the deadlocked process holding the fewest resources until none remain."""
    alloc, req, avail, killed = [r[:] for r in allocation], [r[:] for r in request], list(available), []
    while True:
        dead = detect(alloc, req, avail)
        if not dead: return killed, avail
        v = min(dead, key=lambda i: (sum(alloc[i]), i)); killed.append(v)
        avail = [avail[j] + alloc[v][j] for j in range(len(avail))]
        alloc[v] = [0] * len(avail); req[v] = [0] * len(avail)

SCENARIOS = {  # P0 holds R0 wants R1, P1 holds R1 wants R0, P2 free to finish
    "classic_deadlock": {"allocation": [[1, 0], [0, 1], [0, 0]], "request": [[0, 1], [1, 0], [0, 0]], "available": [0, 0]},
    "no_deadlock": {"allocation": [[1, 0], [0, 1]], "request": [[0, 1], [0, 0]], "available": [0, 0]},
}
