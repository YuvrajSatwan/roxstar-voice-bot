"""Runner script to launch STS Token Server and LiveKit Worker concurrently.

Usage:
    python sts_lab/run_sts.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

# Ensure sts_lab and its parent directory are on sys.path so "import sts_lab.xxx" always works
_current_dir = Path(__file__).resolve().parent
_parent_dir = _current_dir.parent
for _p in (str(_parent_dir), str(_current_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import sts_lab
except ImportError:
    import types
    _pkg = types.ModuleType("sts_lab")
    _pkg.__path__ = [str(_current_dir)]
    _pkg.__file__ = str(_current_dir / "__init__.py")
    sys.modules["sts_lab"] = _pkg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def main() -> None:
    print("=" * 60)
    print("  🚀 Starting Saraah Gemini 3.8 Live STS Lab")
    print("  Token Server: http://127.0.0.1:8001")
    print("  Model:        gemini-3.8-live (Multimodal Native Audio)")
    try:
        from sts_lab.config import StsSettings
        active_voice = StsSettings.load().voice
    except Exception:
        active_voice = "Leda"
    print(f"  Voice:        {active_voice}")
    print("  Persona:      Saraah (AI Sathi & Tech Consultant)")
    print("=" * 60)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{str(_parent_dir)}{os.pathsep}{str(_current_dir)}{os.pathsep}{existing_pythonpath}".rstrip(os.pathsep)

    def start_token_server() -> subprocess.Popen:
        print("[Supervisor] Launching STS Token Server...")
        return subprocess.Popen(
            [sys.executable, "-m", "sts_lab.token_server"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env,
        )

    def start_worker() -> subprocess.Popen:
        print("[Supervisor] Launching LiveKit STS Worker (prewarmed production mode)...")
        return subprocess.Popen(
            [sys.executable, "-m", "sts_lab.worker", "start"],
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env,
        )

    token_proc = start_token_server()
    time.sleep(1.0)
    worker_proc = start_worker()

    try:
        while True:
            time.sleep(2.0)
            if token_proc.poll() is not None:
                code = token_proc.returncode
                print(f"[Supervisor] STS Token Server exited with code {code}. Restarting in 2s...")
                time.sleep(2.0)
                token_proc = start_token_server()

            if worker_proc.poll() is not None:
                code = worker_proc.returncode
                print(f"[Supervisor] STS Worker exited with code {code}. Restarting in 2s...")
                time.sleep(2.0)
                worker_proc = start_worker()
    except KeyboardInterrupt:
        print("\nShutting down STS Lab...")
    finally:
        for p in (worker_proc, token_proc):
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
