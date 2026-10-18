import importlib, pathlib, shutil, signal, sys, time
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not shutil.which("qemu-system-i386") or not (shutil.which("i686-elf-gcc") or shutil.which("gcc")),
                                reason="needs qemu-system-i386 and a compiler")

def read_until(ws, needle, seconds=40):
    buf, end = "", time.time() + seconds
    while needle not in buf and time.time() < end: buf += ws.receive_text()
    assert needle in buf, f"never saw {needle!r}; got {buf[-300:]!r}"
    return buf

def test_browser_can_drive_the_real_kernel(tmp_path, monkeypatch):
    signal.alarm(120)
    monkeypatch.setenv("ROHITOS_DATA", str(tmp_path)); import app as appmod; importlib.reload(appmod)
    with TestClient(appmod.app).websocket_connect("/ws/kernel") as ws:
        boot = read_until(ws, "rohit> "); assert "SELFTEST PASS" in boot or "SELFTEST" in boot
        ws.send_text("crash\n"); out = read_until(ws, "kernel survives")
        assert "general protection" in out                               # ring 3 `cli` stopped by hardware
        read_until(ws, "rohit> "); ws.send_text("exit\n"); read_until(ws, "bye")
    signal.alarm(0)
