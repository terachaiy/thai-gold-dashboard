"""Gold news from RSS feeds, scored with a Thai + English keyword lexicon (no API key).

Score per headline is in [-1, 1]: + = bullish for Thai gold price, - = bearish.
A weaker baht is bullish for Thai gold (the price is quoted in THB).
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from .data import DB, UA

FEEDS = {
    "Google News (TH)": "https://news.google.com/rss/search?q=%E0%B8%A3%E0%B8%B2%E0%B8%84%E0%B8%B2%E0%B8%97%E0%B8%AD%E0%B8%87+when:2d&hl=th&gl=TH&ceid=TH:th",
    "Google News (EN)": "https://news.google.com/rss/search?q=gold+price+when:2d&hl=en-US&gl=US&ceid=US:en",
    "FXStreet": "https://www.fxstreet.com/rss/news",
    "Investing.com": "https://www.investing.com/rss/news_11.rss",
}

RELEVANT = re.compile(r"\bgold\b|xau|bullion|ทอง", re.I)

# (pattern, score, driver). Order matters: specific phrases are matched and removed first,
# so "ปรับขึ้นดอกเบี้ย" (rate hike, bearish) is not also counted as "ปรับขึ้น" (price up, bullish).
LEXICON: list[tuple[str, float, str]] = [
    # --- monetary policy
    (r"rate[- ]cuts?|cut(s|ting)? rates?|dovish|easing|ลดดอกเบี้ย|ปรับลดดอกเบี้ย|ผ่อนคลาย", +1.0, "fed"),
    (r"rate[- ]hikes?|hik(e|es|ing) rates?|hawkish|tightening|ขึ้นดอกเบี้ย|ปรับขึ้นดอกเบี้ย|คงดอกเบี้ยสูง|เข้มงวด", -1.0, "fed"),
    (r"yields? (rise|rises|climb|jump|surge)|bond yields? higher|บอนด์ยีลด์(พุ่ง|ขึ้น|เพิ่ม)", -0.7, "fed"),
    (r"yields? (fall|falls|drop|slide|retreat)|บอนด์ยีลด์(ลด|ร่วง|ลง)", +0.7, "fed"),
    # --- currencies
    (r"(dollar|usd|greenback|dxy) (weak|weakens|falls|slides|slips|drops|retreats)|weaker dollar|ดอลลาร์(อ่อน|ร่วง|ลด)", +0.8, "usd"),
    (r"(dollar|usd|greenback|dxy) (strong|strengthens|rises|climbs|gains|jumps|rallies)|stronger dollar|ดอลลาร์(แข็ง|พุ่ง)", -0.8, "usd"),
    (r"บาทอ่อน|เงินบาทอ่อน|baht weak", +0.6, "thb"),
    (r"บาทแข็ง|เงินบาทแข็ง|baht (strong|firm)", -0.6, "thb"),
    # --- risk / geopolitics
    (r"safe[- ]haven|geopolitic|war\b|conflict|tension|missile|attack|sanction|สงคราม|ตึงเครียด|ความขัดแย้ง|หลุมหลบภัย|สินทรัพย์ปลอดภัย", +0.7, "geopolitics"),
    (r"ceasefire|peace (deal|talks)|truce|risk[- ]on|หยุดยิง|เจรจาสันติภาพ", -0.6, "geopolitics"),
    (r"recession|crisis|slowdown|ถดถอย|วิกฤต", +0.5, "macro"),
    # --- flows
    (r"central banks? (buy|buying|purchases|add|demand)|reserves rise|pboc (buy|adds)|etf inflows?|ธนาคารกลาง.{0,10}ซื้อ|แรงซื้อ|ซื้อสะสม", +0.8, "flows"),
    (r"etf outflows?|profit[- ]taking|sell[- ]?off|liquidation|เทขาย|ขายทำกำไร|แรงขาย", -0.8, "flows"),
    (r"inflation (rises|jumps|hotter|accelerates)|เงินเฟ้อ(สูง|พุ่ง|เร่ง)", +0.3, "inflation"),
    # --- trend / tone words
    (r"bullish|uptrend|strength|supports? prices|ขาขึ้น|แนวโน้มบวก|มุมมองบวก", +0.5, "trend"),
    (r"bearish|downtrend|weakness|worst (week|month|day)|free[- ]fall|ขาลง|แนวโน้มลบ|มุมมองลบ", -0.5, "trend"),
    # --- price action words (weakest signal)
    (r"record high|all[- ]time high|นิวไฮ|สูงสุดเป็นประวัติการณ์|ทำสถิติ", +0.6, "price"),
    (r"\b(rall(y|ies)|surges?|soars?|jumps?|climbs?|gains?|rises?|rebounds?|higher)\b|พุ่ง|ทะยาน|ปรับขึ้น|เพิ่มขึ้น|ขึ้นต่อ|ดีดตัว|ฟื้นตัว|บวก", +0.4, "price"),
    (r"\b(slumps?|plunges?|tumbles?|slides?|falls?|drops?|declines?|sinks?|lower|crash(es)?)\b|ร่วง|ดิ่ง|ทรุด|ปรับลง|ลดลง|ลบ|ดิ่งลง|หลุด", -0.4, "price"),
]
_LEX = [(re.compile(p, re.I), s, d) for p, s, d in LEXICON]


def score_text(text: str) -> tuple[float, list[str]]:
    t = text
    total, drivers = 0.0, []
    for rx, s, d in _LEX:
        hits = rx.findall(t)
        if hits:
            total += s * min(len(hits), 2)
            drivers.append(d)
            t = rx.sub(" ", t)
    return max(-1.0, min(1.0, total / 1.5)), sorted(set(drivers))


def _init(c):
    c.execute("""create table if not exists news (id text primary key, time text, source text,
                 title text, link text, score real, drivers text)""")


def _norm(title: str) -> str:
    title = re.sub(r"\s+-\s+[^-]+$", "", title)  # Google News appends " - Publisher"
    return re.sub(r"\W+", "", title.lower())[:80]


def fetch_news() -> int:
    rows = []
    for src, url in FEEDS.items():
        try:
            f = feedparser.parse(requests.get(url, headers=UA, timeout=20).content)
        except requests.RequestException:
            continue
        for e in f.entries[:60]:
            title = (e.get("title") or "").strip()
            text = title + " " + re.sub("<[^>]+>", " ", e.get("summary", ""))[:300]
            if not RELEVANT.search(title):
                continue
            try:
                ts = parsedate_to_datetime(e.get("published")).astimezone(timezone.utc)
            except (TypeError, ValueError):
                ts = datetime.now(timezone.utc)
            s, drv = score_text(text)
            nid = hashlib.md5(_norm(title).encode()).hexdigest()
            rows.append((nid, ts.isoformat(), src, title, e.get("link", ""), s, ",".join(drv)))
    with sqlite3.connect(DB) as c:
        _init(c)
        c.executemany("insert into news values (?,?,?,?,?,?,?) on conflict(id) do update set "
                      "score=excluded.score, drivers=excluded.drivers", rows)
    return len(rows)


def recent(hours: int = 48, limit: int = 40) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(DB) as c:
        _init(c)
        cur = c.execute("select time, source, title, link, score, drivers from news where time >= ? "
                        "order by time desc limit ?", (since, limit))
        return [dict(zip(["time", "source", "title", "link", "score", "drivers"], r)) for r in cur]


def sentiment(hours: int = 48) -> dict:
    """Recency-weighted mean score (half-life 12 h) and driver breakdown."""
    items = recent(hours, 500)
    now = datetime.now(timezone.utc)
    num = den = 0.0
    drivers: dict[str, list[float]] = {}
    for it in items:
        age = (now - datetime.fromisoformat(it["time"])).total_seconds() / 3600
        w = 0.5 ** (age / 12)
        num += w * it["score"]
        den += w
        for d in filter(None, it["drivers"].split(",")):
            drivers.setdefault(d, []).append(it["score"])
    idx = num / den if den else 0.0
    return {"index": idx, "count": len(items),
            "drivers": {d: round(sum(v) / len(v), 2) for d, v in sorted(drivers.items(), key=lambda kv: -len(kv[1]))},
            "bull": sum(1 for i in items if i["score"] > 0.1), "bear": sum(1 for i in items if i["score"] < -0.1)}


def daily_index(days: int = 60) -> list[tuple[str, float, int]]:
    with sqlite3.connect(DB) as c:
        _init(c)
        cur = c.execute("select substr(time,1,10) d, avg(score), count(*) from news group by d order by d desc limit ?", (days,))
        return [(d, round(s, 3), n) for d, s, n in cur][::-1]
