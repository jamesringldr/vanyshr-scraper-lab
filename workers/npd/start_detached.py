"""Detached uvicorn launcher for Windows OpenSSH sessions."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = Path(r"C:\Users\scraper\fps-scraper\venv\Scripts\python.exe")
PORT = os.environ.get("NPD_PORT", "8789")

CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def main() -> int:
    log_out = ROOT / "service.out.log"
    log_err = ROOT / "service.err.log"
    out_f = open(log_out, "a", encoding="utf-8")
    err_f = open(log_err, "a", encoding="utf-8")
    cmd = [
        str(PYTHON),
        "-m",
        "uvicorn",
        "service:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT),
    ]
    creationflags = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=out_f,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )
    print(f"started pid={proc.pid} port={PORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
