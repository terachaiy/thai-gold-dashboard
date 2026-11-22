"""Gold dashboard server.  Run:  .venv\\Scripts\\python server.py   then open http://localhost:8765

Listens on all interfaces so the X4 can read /api/x4 over Wi-Fi.
"""
import json
import threading
import time
import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from goldapp import analysis, data, news

PORT = 8765
REFRESH_S = 15 * 60
WEB = Path(__file__).parent / "web"
app = FastAPI(title="Thai Gold Dashboard")
_state = {"a": None, "t": 0.0, "err": None}
_lock = threading.Lock()


def refresh():
    try:
        a = analysis.analyse()
        with _lock:
            _state.update(a=a, t=time.time(), err=None)
    except Exception as e:  # keep serving the last good analysis
        traceback.print_exc()
        _state["err"] = str(e)


def _loop():
    while True:
        refresh()
        time.sleep(REFRESH_S)


def current():
    if _state["a"] is None:
        refresh()
    return _state["a"]


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/summary")
def summary():
    a = current()
    return JSONResponse({**a, "error": _state["err"]} if a else {"error": _state["err"]})


@app.get("/api/news")
def news_list():
    return {"items": news.recent(72, 60), "daily": news.daily_index(60)}


@app.get("/api/backtest")
def backtest():
    p = data.CACHE / "backtest.json"
    return JSONResponse(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})


@app.get("/api/x4")
def x4():
    a = current()
    return analysis.x4_summary(a) if a else JSONResponse({"error": "no data"}, status_code=503)


def _port_in_use() -> bool:
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def _monthly_backtest():
    """Re-run the walk-forward backtest when its results are over 30 days old."""
    p = data.CACHE / "backtest.json"
    if p.exists() and time.time() - p.stat().st_mtime < 30 * 86400:
        return
    import os
    import subprocess
    import sys
    subprocess.run([sys.executable, str(Path(__file__).parent / "run_backtest.py")],
                   cwd=Path(__file__).parent, stdout=sys.stdout, stderr=sys.stderr,
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


if __name__ == "__main__":
    import sys
    if sys.stdout is None:  # started with pythonw (no console): log to a file instead
        log = open(data.CACHE / "server.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    if _port_in_use():
        print("gold server already running on port", PORT)
        sys.exit(0)
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "gold server starting on port", PORT)
    threading.Thread(target=_loop, daemon=True).start()
    threading.Thread(target=_monthly_backtest, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
