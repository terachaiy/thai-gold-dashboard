"""Verdict engine. The core signal is the walk-forward-validated Donchian breakout;
trend, baht and news are shown as context (they were not validated as trading rules)."""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import data, news
from . import indicators as ta
from .strategies import donchian

DEFAULT_PARAMS = {"entry": 40, "exit": 30}


def current_params() -> dict:
    """Latest parameters picked by the walk-forward run (falls back to 40/30)."""
    p = data.CACHE / "backtest.json"
    if p.exists():
        chosen = json.loads(p.read_text(encoding="utf-8"))["results"]["donchian"]["chosen"]
        if chosen:
            return chosen[-1]["params"]
    return DEFAULT_PARAMS


def _with_live_bar(df: pd.DataFrame, q: dict | None) -> pd.DataFrame:
    """Append today's GTA mid as a bar if it is a newer weekday than the last world close."""
    if not q or not q.get("time"):
        return df
    t = pd.Timestamp(q["time"]).normalize()
    if t <= df.index[-1] or t.weekday() >= 5:
        return df
    mid = (q["bar_buy"] + q["bar_sell"]) / 2
    row = pd.DataFrame({"open": [df["close"].iloc[-1]], "high": [max(mid, df["close"].iloc[-1])],
                        "low": [min(mid, df["close"].iloc[-1])], "close": [mid],
                        "xauusd": [df["xauusd"].iloc[-1]], "usdthb": [df["usdthb"].iloc[-1]]}, index=[t])
    return pd.concat([df, row])


def analyse(refresh_news: bool = True) -> dict:
    q = data.fetch_gta()
    df = _with_live_bar(data.thai_gold(), q)
    c = df["close"]
    p = current_params()

    sig = donchian(df, **p)
    long_now = bool(sig.iloc[-1] > 0)
    changed = sig.diff().fillna(0) != 0
    last_change = sig.index[changed][-1] if changed.any() else sig.index[0]
    entry_lvl = round(float(df["high"].rolling(p["entry"]).max().iloc[-1]) / 50) * 50
    exit_lvl = round(float(df["low"].rolling(p["exit"]).min().iloc[-1]) / 50) * 50

    ema50, ema200 = ta.ema(c, 50).iloc[-1], ta.ema(c, 200).iloc[-1]
    adx = float(ta.adx(df).iloc[-1])
    rsi = float(ta.rsi(c, 14).iloc[-1])
    atr = float(ta.atr(df).iloc[-1])
    m = ta.macd(c).iloc[-1]

    # 20-day move split into world-gold and baht effects (log returns add up)
    n = 20
    lg = lambda s: float(np.log(s.iloc[-1] / s.iloc[-1 - n]))
    world, baht = lg(df["xauusd"]), lg(df["usdthb"])

    if refresh_news:
        news.fetch_news()
    sent = news.sentiment()

    # Context score: each factor in [-1, 1]
    factors = {
        "donchian": 1.0 if long_now else -1.0,
        "trend": 1.0 if c.iloc[-1] > ema200 and ema50 > ema200 else (-1.0 if c.iloc[-1] < ema200 and ema50 < ema200 else 0.0),
        "momentum": max(-1.0, min(1.0, (rsi - 50) / 20)),
        "news": max(-1.0, min(1.0, sent["index"] * 2)),
    }
    weights = {"donchian": 0.45, "trend": 0.25, "momentum": 0.15, "news": 0.15}
    bias = sum(factors[k] * weights[k] for k in factors)
    if bias >= 0.25:
        view, view_en = "ขาขึ้น", "BULLISH"
    elif bias <= -0.25:
        view, view_en = "ขาลง", "BEARISH"
    else:
        view, view_en = "ทรงตัว", "NEUTRAL"
    agree = sum(1 for k in factors if (factors[k] > 0) == (bias > 0) and abs(factors[k]) > 0.2)

    reasons = []
    if long_now:
        reasons.append(f"Donchian: ถือ ตั้งแต่ {last_change:%d/%m} จุดออกถ้าปิดต่ำกว่า ฿{exit_lvl:,.0f}")
    else:
        reasons.append(f"Donchian: รอ จะเข้าเมื่อปิดเหนือ ฿{entry_lvl:,.0f} (กรอบ {p['entry']} วัน)")
    reasons.append("แนวโน้มหลักเหนือ EMA200" if c.iloc[-1] > ema200 else "ราคาต่ำกว่า EMA200 (แนวโน้มหลักอ่อน)")
    reasons.append(f"20 วัน: ทองโลก {world*100:+.1f}% / ค่าบาท {baht*100:+.1f}%")
    reasons.append(f"ข่าว 48 ชม.: บวก {sent['bull']} / ลบ {sent['bear']} (ดัชนี {sent['index']:+.2f})")

    chg1 = float(c.iloc[-1] - c.iloc[-2])
    hist = df.tail(400)
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "quote": q,
        "price": round(float(c.iloc[-1]) / 50) * 50,
        "change_1d": round(chg1 / 50) * 50,
        "change_1d_pct": chg1 / c.iloc[-2],
        "last_bar": df.index[-1].date().isoformat(),
        "signal": {"position": "LONG" if long_now else "FLAT", "position_th": "ถือทอง" if long_now else "ถือเงินสด",
                   "since": last_change.date().isoformat(), "params": p,
                   "entry_level": round(entry_lvl / 50) * 50, "exit_level": round(exit_lvl / 50) * 50,
                   "atr": round(atr / 50) * 50},
        "view": view, "view_en": view_en, "bias": round(bias, 3),
        "confidence": round(abs(bias) * 100), "agree": agree,
        "factors": factors, "weights": weights, "reasons": reasons,
        "indicators": {"ema50": float(ema50), "ema200": float(ema200), "adx": adx, "rsi": rsi,
                       "macd": float(m["macd"]), "macd_signal": float(m["signal"])},
        "decomp_20d": {"world": world, "baht": baht},
        "levels": ta.swing_levels(df),
        "news": sent,
        "chart": {
            "candles": [{"time": d.strftime("%Y-%m-%d"), "open": round(r.open), "high": round(r.high),
                         "low": round(r.low), "close": round(r.close)} for d, r in hist.iterrows()],
            "ema50": _line(ta.ema(c, 50).tail(400)), "ema200": _line(ta.ema(c, 200).tail(400)),
            "upper": _line(df["high"].rolling(p["entry"]).max().tail(400)),
            "lower": _line(df["low"].rolling(p["exit"]).min().tail(400)),
            "markers": _markers(sig.tail(400)),
        },
    }


def _line(s: pd.Series) -> list:
    return [{"time": d.strftime("%Y-%m-%d"), "value": round(float(v))} for d, v in s.dropna().items()]


def _markers(sig: pd.Series) -> list:
    d = sig.diff().fillna(0)
    out = []
    for t, v in d[d != 0].items():
        out.append({"time": t.strftime("%Y-%m-%d"), "position": "belowBar" if v > 0 else "aboveBar",
                    "color": "#1a7f37" if v > 0 else "#cf222e", "shape": "arrowUp" if v > 0 else "arrowDown",
                    "text": "ซื้อ" if v > 0 else "ขาย"})
    return out


def x4_summary(a: dict) -> dict:
    """Compact, ASCII-safe payload for the X4 e-ink screen (small JSON, no Thai glyphs needed)."""
    q = a["quote"] or {}
    return {
        "buy": int(q.get("bar_buy") or a["price"]), "sell": int(q.get("bar_sell") or a["price"]),
        "chg": int(a["change_1d"]), "round": q.get("round") or 0, "time": (q.get("time") or "")[11:16],
        "date": (q.get("time") or a["last_bar"])[:10],
        "view": a["view_en"], "conf": a["confidence"],
        "pos": a["signal"]["position"], "since": a["signal"]["since"],
        "entry": a["signal"]["entry_level"], "exit": a["signal"]["exit_level"],
        "sup": a["levels"]["support"][:2], "res": a["levels"]["resistance"][:2],
        "rsi": round(a["indicators"]["rsi"]), "news": round(a["news"]["index"], 2),
        "nb": a["news"]["bull"], "ns": a["news"]["bear"],
        "world20": round(a["decomp_20d"]["world"] * 100, 1), "thb20": round(a["decomp_20d"]["baht"] * 100, 1),
        "spark": [round(x["close"]) for x in a["chart"]["candles"][-60:]],
    }
