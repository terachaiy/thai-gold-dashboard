"""Long-only swing strategies (physical Thai gold can't be shorted at a GTA dealer).

Each strategy maps (df, params) -> Series of 0/1 desired position, decided on that day's close.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from . import indicators as ta


def _hold(entry: pd.Series, exit_: pd.Series) -> pd.Series:
    """Latch: go long on entry, flat on exit."""
    sig = pd.Series(np.nan, index=entry.index)
    sig[entry] = 1.0
    sig[exit_ & ~entry] = 0.0
    return sig.ffill().fillna(0.0)


def ema_cross(df, fast=20, slow=50):
    c = df["close"]
    return (ta.ema(c, fast) > ta.ema(c, slow)).astype(float)


def donchian(df, entry=55, exit=20):
    c = df["close"]
    hi = df["high"].rolling(entry).max().shift()
    lo = df["low"].rolling(exit).min().shift()
    return _hold(c > hi, c < lo)


def rsi_pullback(df, n=5, lo=30, hi=70, trend=200):
    """Buy oversold dips inside an uptrend; sell on recovery or trend break."""
    c = df["close"]
    r = ta.rsi(c, n)
    up = c > ta.ema(c, trend)
    return _hold(up & (r < lo), (r > hi) | ~up)


def regime(df, adx_n=14, adx_th=25, fast=20, slow=50, n=5, lo=30):
    """ADX regime switch: follow the trend when ADX is high, buy dips when it is low."""
    a = ta.adx(df, adx_n)
    trend_sig = ema_cross(df, fast, slow)
    dip_sig = rsi_pullback(df, n, lo, 70, 200)
    return pd.Series(np.where(a >= adx_th, trend_sig, dip_sig), index=df.index)


def buy_hold(df):
    return pd.Series(1.0, index=df.index)


def _grid(**kw):
    keys = list(kw)
    return [dict(zip(keys, v)) for v in itertools.product(*kw.values())]


STRATEGIES = {
    "ema_cross": (ema_cross, [p for p in _grid(fast=[10, 20, 30, 50], slow=[50, 100, 150, 200]) if p["fast"] < p["slow"]]),
    "donchian": (donchian, [p for p in _grid(entry=[20, 40, 55, 80], exit=[10, 20, 30]) if p["exit"] < p["entry"]]),
    "rsi_pullback": (rsi_pullback, _grid(n=[2, 5, 14], lo=[20, 30, 40], hi=[60, 70], trend=[100, 200])),
    "regime": (regime, _grid(adx_th=[20, 25, 30], fast=[20, 50], slow=[100, 200], lo=[30, 40])),
}

NAMES_TH = {
    "ema_cross": "เส้นค่าเฉลี่ยตัดกัน (EMA)",
    "donchian": "เบรกกรอบราคา (Donchian)",
    "rsi_pullback": "ซื้อย่อในขาขึ้น (RSI)",
    "regime": "สลับตามสภาวะตลาด (ADX)",
    "buy_hold": "ซื้อแล้วถือ",
}
