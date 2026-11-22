"""Walk-forward backtest of all strategies; writes data/backtest.json for the dashboard."""
import json

import pandas as pd

from goldapp import backtest as bt
from goldapp import data
from goldapp.strategies import NAMES_TH, STRATEGIES, buy_hold

df = data.thai_gold()
print(f"Thai 96.5% bar gold, {df.index[0].date()} .. {df.index[-1].date()}, premium k={df.attrs['premium']:.4f}")

START = "2009-01-01"
oos_mask = df.index >= START
bh = bt.run(df[oos_mask], buy_hold(df[oos_mask]))
results = {"buy_hold": {"stats": bt.stats(bh), "equity": bh["equity"], "yearly": bt.yearly(bh)}}

for name in STRATEGIES:
    oos, chosen = bt.walk_forward(df, name, start=START)
    results[name] = {
        "stats": bt.stats(oos), "equity": oos["equity"], "yearly": bt.yearly(oos), "chosen": chosen,
        "robust": bt.robustness(df, name, df.index < START),  # judged on pre-OOS data only
    }

fmt = lambda x: f"{x * 100:6.1f}%"
print(f"\nOut-of-sample walk-forward {START} .. today (5y train / 1y test, 0.4% round-trip cost, 1-day delay)\n")
print(f"{'strategy':14} {'CAGR':>7} {'MaxDD':>7} {'Sharpe':>6} {'Calmar':>6} {'trd/yr':>6} {'win':>6} {'in mkt':>7}")
for k, v in results.items():
    s = v["stats"]
    print(f"{k:14} {fmt(s['cagr'])} {fmt(s['max_dd'])} {s['sharpe']:6.2f} {s['calmar']:6.2f} "
          f"{s['trades_per_year']:6.1f} {fmt(s['win_rate'])} {fmt(s['exposure'])}")
print("\nRobustness (2004-2008 grid, before OOS): median Sharpe / share of settings beating B&H Sharpe")
for k in STRATEGIES:
    r = results[k]["robust"]
    print(f"  {k:14} {r['median_sharpe']:.2f} / {r['share_beating_bh_sharpe']:.0%} of {r['n']}")
print("\nYearly returns")
print(pd.DataFrame({k: v["yearly"] for k, v in results.items()}).map(fmt).to_string())

out = {k: {"name_th": NAMES_TH[k], "stats": v["stats"],
           "yearly": {int(y): float(r) for y, r in v["yearly"].items()},
           "equity": [[d.strftime("%Y-%m-%d"), round(float(e), 4)] for d, e in v["equity"].resample("W").last().items()],
           "chosen": v.get("chosen"), "robust": v.get("robust")}
       for k, v in results.items()}
(data.CACHE / "backtest.json").write_text(json.dumps({"start": START, "results": out}, ensure_ascii=False), encoding="utf-8")
print("\nwrote data/backtest.json")
