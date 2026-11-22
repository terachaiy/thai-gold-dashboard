"""Price data: live GTA (สมาคมค้าทองคำ) quote + reconstructed Thai bar-gold history.

Thai 96.5% bar price per baht-weight (15.244 g) is derived from world gold and USD/THB:
    THB = XAUUSD * USDTHB * 0.965 * 15.244 / 31.1035 * k
where k (dealer premium, ~1%) is calibrated against the live GTA quote.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data"
CACHE.mkdir(exist_ok=True)
DB = CACHE / "gold.sqlite"

GRAMS_PER_BAHT = 15.244
GRAMS_PER_OZ = 31.1035
PURITY = 0.965
OZ_TO_BAHT = PURITY * GRAMS_PER_BAHT / GRAMS_PER_OZ
DEFAULT_PREMIUM = 1.011  # measured 2026-11-22; recalibrated from live quotes when available
UA = {"User-Agent": "Mozilla/5.0 (gold-dashboard)"}


# ---------------------------------------------------------------- live GTA quote
def fetch_gta() -> dict | None:
    """Latest GTA bar-gold buy/sell. Returns None if the page can't be parsed."""
    try:
        html = requests.get("https://www.goldtraders.or.th/", headers=UA, timeout=20).text
    except requests.RequestException:
        return None
    nums = re.findall(r'font-bold ">([\d,]+\.\d{2})</span>', html)
    stamp = re.search(r"ประจำวันที่ (\d+)/(\d+)/(\d{4}) เวลา (\d+):(\d+) \(ครั้งที่ (\d+)\)", html)
    if len(nums) < 2:
        return None
    buy, sell = (float(n.replace(",", "")) for n in nums[:2])
    q = {"bar_buy": buy, "bar_sell": sell, "round": None, "time": None}
    if stamp:
        d, m, y, hh, mm, rnd = map(int, stamp.groups())
        q["time"] = datetime(y - 543, m, d, hh, mm).isoformat()
        q["round"] = rnd
    _store_quote(q)
    return q


def _store_quote(q: dict) -> None:
    with sqlite3.connect(DB) as c:
        c.execute("create table if not exists gta (time text primary key, round int, bar_buy real, bar_sell real)")
        if q["time"]:
            c.execute("insert or replace into gta values (?,?,?,?)", (q["time"], q["round"], q["bar_buy"], q["bar_sell"]))


def gta_history() -> pd.DataFrame:
    """Real GTA quotes collected by this app so far (grows over time)."""
    with sqlite3.connect(DB) as c:
        c.execute("create table if not exists gta (time text primary key, round int, bar_buy real, bar_sell real)")
        return pd.read_sql("select * from gta order by time", c, parse_dates=["time"])


# ---------------------------------------------------------------- world data
def _yf(ticker: str, refresh: bool) -> pd.DataFrame:
    path = CACHE / f"{ticker.replace('=', '_').replace('^', '')}.csv"
    if path.exists() and not refresh:
        age_h = (datetime.now().timestamp() - path.stat().st_mtime) / 3600
        if age_h < 6:
            return pd.read_csv(path, index_col=0, parse_dates=True)
    d = yf.download(ticker, period="max", interval="1d", progress=False, auto_adjust=False)
    if d.empty:
        if path.exists():
            return pd.read_csv(path, index_col=0, parse_dates=True)
        raise RuntimeError(f"no data for {ticker}")
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    d = d[["Open", "High", "Low", "Close"]].dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None)
    d.to_csv(path)
    return d


def thai_gold(refresh: bool = False, premium: float | None = None) -> pd.DataFrame:
    """Daily OHLC of Thai 96.5% bar gold (THB / baht-weight), plus the world inputs."""
    xau = _yf("GC=F", refresh)
    fx = _yf("USDTHB=X", refresh)
    df = xau.join(fx[["Close"]].rename(columns={"Close": "usdthb"}), how="inner")
    # Yahoo FX history has occasional bad prints; clip implausible one-day jumps
    r = df["usdthb"].pct_change().abs()
    df.loc[r > 0.08, "usdthb"] = None
    df["usdthb"] = df["usdthb"].ffill()
    k = premium or calibrated_premium(df)
    f = df["usdthb"] * OZ_TO_BAHT * k
    out = pd.DataFrame({c.lower(): df[c] * f for c in ["Open", "High", "Low", "Close"]})
    out["xauusd"] = df["Close"]
    out["usdthb"] = df["usdthb"]
    out.attrs["premium"] = k
    return out.dropna()


def calibrated_premium(world: pd.DataFrame) -> float:
    """Ratio of real GTA mid price to the formula price, averaged over stored quotes."""
    h = gta_history()
    if h.empty:
        return DEFAULT_PREMIUM
    h["date"] = h["time"].dt.normalize()
    h = h.groupby("date")[["bar_buy", "bar_sell"]].last()
    j = h.join(world[["Close", "usdthb"]], how="inner")
    if j.empty:  # quotes from a weekend/today: compare with the last world close
        last = world.iloc[-1]
        mid = (h["bar_buy"].iloc[-1] + h["bar_sell"].iloc[-1]) / 2
        return float(mid / (last["Close"] * last["usdthb"] * OZ_TO_BAHT))
    mid = (j["bar_buy"] + j["bar_sell"]) / 2
    return float((mid / (j["Close"] * j["usdthb"] * OZ_TO_BAHT)).tail(60).mean())
