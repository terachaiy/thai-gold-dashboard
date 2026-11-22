"""Technical indicators on a daily OHLC frame (columns open/high/low/close)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    up = df["high"].diff()
    dn = -df["low"].diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = atr(df, n)
    pdi = 100 * pdm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / a
    ndi = 100 * ndm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def macd(s: pd.Series, fast=12, slow=26, sig=9) -> pd.DataFrame:
    m = ema(s, fast) - ema(s, slow)
    sg = ema(m, sig)
    return pd.DataFrame({"macd": m, "signal": sg, "hist": m - sg})


def bollinger(s: pd.Series, n=20, k=2.0) -> pd.DataFrame:
    mid = s.rolling(n).mean()
    sd = s.rolling(n).std()
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def swing_levels(df: pd.DataFrame, look: int = 5, keep: int = 120, tol: float = 0.012) -> dict:
    """Recent support/resistance from swing highs/lows, merged when within `tol`."""
    d = df.tail(keep)
    hi, lo = d["high"], d["low"]
    w = 2 * look + 1
    sh = hi[(hi == hi.rolling(w, center=True).max())].dropna()
    sl = lo[(lo == lo.rolling(w, center=True).min())].dropna()
    px = d["close"].iloc[-1]

    def merge(vals):
        out = []
        for v in sorted(vals):
            if out and abs(v - out[-1][0]) / v < tol:
                out[-1] = ((out[-1][0] * out[-1][1] + v) / (out[-1][1] + 1), out[-1][1] + 1)
            else:
                out.append((v, 1))
        return out

    levels = merge(list(sh.values) + list(sl.values))
    res = sorted([(v, n) for v, n in levels if v > px])[:3]
    sup = sorted([(v, n) for v, n in levels if v < px], reverse=True)[:3]
    if not sup:  # price at a fresh low: use the window low and the next round ฿1,000 below
        lowest = float(d["low"].min())
        sup = [(v, 1) for v in sorted({lowest, (px // 1000) * 1000, (px // 1000 - 1) * 1000}, reverse=True) if v < px][:3]
    r50 = lambda v: round(v / 50) * 50  # Thai prices move in ฿50 steps
    return {"support": [r50(v) for v, _ in sup], "resistance": [r50(v) for v, _ in res]}
