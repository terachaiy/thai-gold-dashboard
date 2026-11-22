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


if __name__ == "__main__":
    threading.Thread(target=_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
