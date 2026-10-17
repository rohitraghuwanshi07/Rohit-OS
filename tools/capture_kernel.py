"""Boot the real kernel in QEMU (autotest mode) and save its scheduler trace for the simulator to validate against."""
import json, pathlib, re, subprocess
root = pathlib.Path(__file__).resolve().parents[1]
subprocess.run(["make", "-C", str(root / "kernel"), "clean"], check=True, capture_output=True)
subprocess.run(["make", "-C", str(root / "kernel"), "test"], check=True, capture_output=True)
log = (root / "kernel" / "boot.log").read_text()
ev = [{"t": int(m[1]), "from": m[2], "to": m[3]} for m in re.finditer(r"^KEV (\d+) (\S+) (\S+)$", log, re.M)]
assert ev and "ROHITOS SELFTEST PASS" in log, "kernel did not pass its self-test"
out = root / "workloads" / "kernel_trace.json"
out.write_text(json.dumps({"source": "qemu-system-i386 autotest boot", "quantum": 5, "total_ticks": 300, "events": ev}, indent=1))
print(f"saved {len(ev)} real kernel dispatch events to {out}")
