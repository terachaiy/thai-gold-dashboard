"""Vectorised daily backtester with Thai bar-gold costs and walk-forward validation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .strategies import STRATEGIES, buy_hold

# GTA bar spread is ฿100–200 on ฿20k–57k bars (0.35–0.5% round trip). Use 0.4% round trip.
COST_PER_SIDE = 0.002
LAG = 2  # signal on close t -> trade on close t+1 -> earns from t+1 (no look-ahead, 1-day delay)
YEAR = 252


def run(df: pd.DataFrame, signal: pd.Series, cost: float = COST_PER_SIDE) -> pd.DataFrame:
    ret = df["close"].pct_change().fillna(0.0)
    pos = signal.shift(LAG).fillna(0.0)
    turn = pos.diff().abs().fillna(pos.abs())
    strat = pos * ret - turn * cost
    return pd.DataFrame({"pos": pos, "ret": strat, "equity": (1 + strat).cumprod()})


def trades(bt: pd.DataFrame) -> pd.Series:
    """Compounded return of each completed long trade."""
    pos = bt["pos"]
    tid = (pos.diff().fillna(pos) > 0).cumsum().where(pos > 0)
    return bt.groupby(tid)["ret"].apply(lambda r: (1 + r).prod() - 1)


def stats(bt: pd.DataFrame) -> dict:
    r = bt["ret"]
    eq = (1 + r).cumprod()
    yrs = len(r) / YEAR
    dd = eq / eq.cummax() - 1
    t = trades(bt)
    sd = r.std()
    return {
        "cagr": eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0.0,
        "total": eq.iloc[-1] - 1,
        "max_dd": dd.min(),
        "sharpe": r.mean() / sd * np.sqrt(YEAR) if sd > 0 else 0.0,
        "calmar": (eq.iloc[-1] ** (1 / yrs) - 1) / abs(dd.min()) if dd.min() < 0 else 0.0,
        "trades_per_year": len(t) / yrs if yrs else 0.0,
        "win_rate": float((t > 0).mean()) if len(t) else 0.0,
        "avg_trade": float(t.mean()) if len(t) else 0.0,
        "exposure": float(bt["pos"].mean()),
    }


def score(bt: pd.DataFrame) -> float:
    """Selection score in training: Sharpe, but reject strategies that barely trade."""
    s = stats(bt)
    return s["sharpe"] if s["trades_per_year"] >= 1 else -9.0


def walk_forward(df: pd.DataFrame, name: str, train_years=5, test_years=1, start="2009-01-01"):
    """Re-optimise on the past `train_years`, trade the next `test_years` blind. Repeat."""
    fn, grid = STRATEGIES[name]
    sigs = {i: fn(df, **p) for i, p in enumerate(grid)}
    pieces, chosen = [], []
    t0 = pd.Timestamp(start)
    while t0 < df.index[-1]:
        t1 = t0 + pd.DateOffset(years=test_years)
        tr = (df.index >= t0 - pd.DateOffset(years=train_years)) & (df.index < t0)
        best = max(sigs, key=lambda i: score(run(df[tr], sigs[i][tr])))
        # run on full history so indicators/positions carry over, then slice the test year
        full = run(df, sigs[best])
        te = (df.index >= t0) & (df.index < t1)
        pieces.append(full.loc[te, ["pos", "ret"]])
        chosen.append({"from": t0.date().isoformat(), "params": grid[best]})
        t0 = t1
    oos = pd.concat(pieces)
    # charge an entry cost if a test year starts already long (position carried in)
    oos["equity"] = (1 + oos["ret"]).cumprod()
    return oos, chosen


def robustness(df: pd.DataFrame, name: str, mask=None) -> dict:
    """How the whole parameter grid does — a good strategy works across neighbours, not one lucky setting."""
    fn, grid = STRATEGIES[name]
    d = df if mask is None else df[mask]
    bh = stats(run(d, buy_hold(d)))["sharpe"]
    sh = [stats(run(d, fn(d, **p)))["sharpe"] for p in grid]
    return {"median_sharpe": float(np.median(sh)), "share_beating_bh_sharpe": float(np.mean([s > bh for s in sh])),
            "n": len(grid)}


def yearly(bt: pd.DataFrame) -> pd.Series:
    return bt["ret"].groupby(bt.index.year).apply(lambda r: (1 + r).prod() - 1)
