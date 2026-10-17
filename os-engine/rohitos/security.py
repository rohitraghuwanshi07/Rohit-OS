"""Rule-based audit over simulated events. A controlled demonstration, not malware detection."""
RULES = {"spawn_burst": {"limit": 5, "window": 10}, "file_attempts": {"limit": 8, "window": 10},
         "cpu_limit": {"limit": 90}, "forbidden": {"paths": ["/etc/shadow", "/sys/kernel"]}}

def audit(events, rules=RULES):
    """events: dicts with t, pid, kind in {spawn, file, cpu, syscall}, plus path/value."""
    alerts = []
    def add(rule, sev, t, pid, evidence, action): alerts.append({"rule": rule, "severity": sev, "t": t, "pid": pid, "evidence": evidence, "suggested_response": action + " (simulated)"})
    for e in events:
        if e["kind"] == "file" and e.get("path") in rules["forbidden"]["paths"]:
            add("forbidden", "high", e["t"], e["pid"], f"access to {e['path']}", f"deny and suspend {e['pid']}")
        if e["kind"] == "cpu" and e["value"] > rules["cpu_limit"]["limit"]:
            add("cpu_limit", "medium", e["t"], e["pid"], f"cpu {e['value']}% > {rules['cpu_limit']['limit']}%", f"throttle {e['pid']}")
    for kind, rule, label in (("spawn", "spawn_burst", "process spawns"), ("file", "file_attempts", "file access attempts")):
        cfg, seen = rules[rule], set()
        for pid in {e["pid"] for e in events if e["kind"] == kind}:
            ts = sorted(e["t"] for e in events if e["kind"] == kind and e["pid"] == pid)
            for i, t0 in enumerate(ts):
                inwin = [x for x in ts[i:] if x - t0 < cfg["window"]]
                if len(inwin) > cfg["limit"] and pid not in seen:
                    seen.add(pid); add(rule, "high", inwin[cfg["limit"]], pid, f"{len(inwin)} {label} within {cfg['window']} ticks", f"rate-limit {pid}")
    return sorted(alerts, key=lambda a: (a["t"], a["rule"]))

def attack_scenario():
    ev = [{"t": 1 + i, "pid": "forkbomb", "kind": "spawn"} for i in range(8)]
    ev += [{"t": 3, "pid": "snoop", "kind": "file", "path": "/etc/shadow"}, {"t": 4, "pid": "miner", "kind": "cpu", "value": 99},
           {"t": 5, "pid": "editor", "kind": "file", "path": "/home/notes.txt"}]
    return ev
