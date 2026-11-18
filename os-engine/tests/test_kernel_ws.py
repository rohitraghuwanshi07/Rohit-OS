import importlib, pathlib, shutil, signal, sys, time
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not shutil.which("qemu-system-i386") or not (shutil.which("i686-elf-gcc") or shutil.which("gcc")),
                                reason="needs qemu-system-i386 and a compiler")

class Terminal:
    """Reads the kernel's serial output. Keeps a persistent buffer so text that arrives together with a match is never lost."""
    def __init__(self, ws): self.ws, self.buf = ws, ""
    def until(self, needle, seconds=40):
        end = time.time() + seconds
        while needle not in self.buf:
            assert time.time() < end, f"never saw {needle!r}; last output: {self.buf[-300:]!r}"
            self.buf += self.ws.receive_text()
        i = self.buf.index(needle) + len(needle); out, self.buf = self.buf[:i], self.buf[i:]
        return out

def test_browser_can_drive_the_real_kernel(tmp_path, monkeypatch):
    def on_alarm(*_): raise AssertionError("live-kernel test timed out (a blocking read never returned)")
    old = signal.signal(signal.SIGALRM, on_alarm); signal.alarm(100)
    try:
        monkeypatch.setenv("ROHITOS_DATA", str(tmp_path)); import app as appmod; importlib.reload(appmod)
        with TestClient(appmod.app).websocket_connect("/ws/kernel") as ws:
            term = Terminal(ws)
            assert "SELFTEST PASS" in term.until("rohit> ")
            ws.send_text("crash\n")
            out = term.until("kernel survives")
            assert "general protection" in out                           # ring 3 `cli` stopped by the hardware
            term.until("rohit> "); ws.send_text("exit\n"); term.until("bye")
    finally:
        signal.alarm(0); signal.signal(signal.SIGALRM, old)
