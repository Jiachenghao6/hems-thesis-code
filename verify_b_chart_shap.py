"""
verify_b_chart_shap.py — do the condition-B bars equal SHAP values from the shap library?

    python verify_b_chart_shap.py            # study scenarios S3, S1, S2; weights in steps of 5
    python verify_b_chart_shap.py --all      # all five scenarios, weights in steps of 1 (slow)

For one recommendation the optimiser's choice is explained by the model

    f(price, renewable, start) = w_cost * cost_score(price)
                               + w_green * green_score(renewable)
                               + w_conv * conv_score(start)

where `price` and `renewable` are the slot averages and `start` the start hour (the raw
inputs, not the scores). The instance to explain is the recommended slot; the background
(reference) is the participant's usual slot — the comparison the card shows.

shap.explainers.Exact computes the exact Shapley values of f for that instance against
that background. The script compares them with the bars the app shows
(`explainer.generate_shap_data`, field `signed_value`). Requires `pip install shap`;
the app itself does not depend on shap.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import shap

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))
from explainer import generate_shap_data  # noqa: E402
from optimizer import APPLIANCES, optimize_schedule  # noqa: E402
from price_service import get_scenario_prices, get_scenario_renewable  # noqa: E402

ORDER = ("cost", "green", "convenience")


def raw_features(prices, renew, app, start):
    dur = app["duration_hours"]
    seg = prices[start:min(start + dur, 24)]
    rseg = renew[start:min(start + dur, 24)]
    return [sum(p["price_eur_mwh"] for p in seg) / len(seg),
            sum(r["renewable_share"] for r in rseg) / len(rseg),
            float(start)]


def make_model(prices, renew, app, w):
    vals = [p["price_eur_mwh"] for p in prices]
    lo, hi = min(vals), max(vals)
    hi = hi if hi != lo else lo + 1.0
    rv = [r["renewable_share"] for r in renew]
    rlo, rhi = min(rv), max(rv)
    rspan = rhi - rlo if rhi != rlo else 0.01
    d = app["default_start"]

    def f(X):
        X = np.asarray(X, dtype=float)
        cost = (hi - X[:, 0]) / (hi - lo)
        green = (X[:, 1] - rlo) / rspan
        conv = np.maximum(0.0, 1.0 - np.abs(X[:, 2] - d) / 8.0)
        return w["cost"] * cost + w["green"] * green + w["convenience"] * conv
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    scenarios = ["S1", "S2", "S3", "S4", "S5"] if args.all else ["S3", "S1", "S2"]
    step = 1 if args.all else 5
    settings = [(c, g, 100 - c - g) for c in range(0, 101, step) for g in range(0, 101 - c, step)]

    n = 0
    max_err = 0.0
    sign_mismatch = 0
    worst = None
    for scen in scenarios:
        prices, renew = get_scenario_prices(scen), get_scenario_renewable(scen)
        for c, g, v in settings:
            for rec in optimize_schedule(prices, APPLIANCES, c, g, v, renewable_shares=renew):
                app = next(a for a in APPLIANCES if a["id"] == rec["appliance_id"])
                w = rec["weights_exact"]
                f = make_model(prices, renew, app, w)
                x = np.array([raw_features(prices, renew, app, rec["recommended_start"])])
                bg = np.array([raw_features(prices, renew, app, rec["default_start"])])
                sv = shap.explainers.Exact(f, bg)(x).values[0]          # library Shapley values
                bars = {b["feature"]: b["signed_value"] for b in generate_shap_data(rec)}
                for i, k in enumerate(ORDER):
                    err = abs(sv[i] - bars[k])
                    if err > max_err:
                        max_err, worst = err, (scen, rec["appliance_id"], (c, g, v), k, sv[i], bars[k])
                    if np.sign(round(sv[i], 9)) != np.sign(round(bars[k], 9)):
                        sign_mismatch += 1
                n += 1

    print(f"shap {shap.__version__} · scenarios {scenarios} · weight step {step} · recommendations {n}")
    print(f"largest |shap − bar| over all factors: {max_err:.2e}")
    print(f"sign mismatches: {sign_mismatch}")
    if worst:
        print("worst case:", worst)
    ok = max_err < 1e-9 and sign_mismatch == 0
    print("RESULT:", "PASS — the bars are the SHAP values" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
