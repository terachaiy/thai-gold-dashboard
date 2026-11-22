"""Build a static copy of the dashboard for GitHub Pages (no server needed).

Writes site/index.html and site/api/{summary,news,backtest,x4,status}. The API files have no
extension so the same page and the X4 app work against either server.py or Pages:
    https://<user>.github.io/<repo>/api/x4
Exit code 1 if the analysis fails, so the workflow keeps the last good deployment.
"""
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from goldapp import analysis, data, news

ROOT = Path(__file__).parent
SITE = ROOT / "site"
API = SITE / "api"


def write(name: str, obj) -> None:
    txt = json.dumps(obj, ensure_ascii=False, default=str)
    (API / name).write_text(txt, encoding="utf-8")
    (API / f"{name}.json").write_text(txt, encoding="utf-8")


def main() -> int:
    API.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "web" / "index.html", SITE / "index.html")
    (SITE / ".nojekyll").write_text("")

    bt = data.CACHE / "backtest.json"
    if not bt.exists() or time.time() - bt.stat().st_mtime > 30 * 86400:
        import runpy
        runpy.run_path(str(ROOT / "run_backtest.py"), run_name="__main__")

    status = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        a = analysis.analyse()
    except Exception as e:  # noqa: BLE001 - report and keep the previous deployment
        print("analysis failed:", repr(e), file=sys.stderr)
        return 1
    status["gta_live"] = a["quote"] is not None
    status["last_bar"] = a["last_bar"]
    status["news_items"] = a["news"]["count"]
    status["premium"] = data.thai_gold().attrs["premium"]

    write("summary", a)
    write("x4", analysis.x4_summary(a))
    write("news", {"items": news.recent(72, 60), "daily": news.daily_index(60)})
    write("backtest", json.loads(bt.read_text(encoding="utf-8")) if bt.exists() else {})
    write("status", status)
    print(json.dumps(status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
