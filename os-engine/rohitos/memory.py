"""Page replacement: FIFO, LRU, and Optimal (offline baseline)."""
def replay(refs, frames, policy):
    if frames < 1: raise ValueError("frames must be >= 1")
    mem, order, last, steps, faults = [], [], {}, [], 0
    for i, pg in enumerate(refs):
        hit, victim = pg in mem, None
        if not hit:
            faults += 1
            if len(mem) == frames:
                if policy == "fifo": victim = order.pop(0)
                elif policy == "lru": victim = min(mem, key=lambda x: last[x])
                elif policy == "optimal":
                    nxt = lambda x: refs.index(x, i + 1) if x in refs[i + 1:] else 10**9
                    victim = max(mem, key=lambda x: (nxt(x), -mem.index(x)))
                else: raise ValueError(f"unknown policy {policy}")
                mem[mem.index(victim)] = pg; order = [o for o in order if o != victim]
            else: mem.append(pg)
            order.append(pg)
        last[pg] = i
        steps.append({"ref": pg, "hit": hit, "evicted": victim, "frames": list(mem)})
    return {"policy": policy, "faults": faults, "fault_rate": faults / len(refs) if refs else 0, "steps": steps}
