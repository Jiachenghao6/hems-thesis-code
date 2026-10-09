"""
verify_b_chart.py — pre-launch check of the corrected condition-B chart (2026-10 rerun).

    python verify_b_chart.py [--master-ref master]

Two questions, both answered exhaustively over every scenario, every appliance and every
priority setting a participant can produce (the single bar gives three weights that sum
to 100; checked in steps of 1):

1. Is the chart faithful? For each recommendation, an independent re-implementation of
   the optimiser's slot scores (copied from analyse_shap_fidelity.py, not imported from
   optimizer.py) gives the exact contributions
       delta_i = w_i * (score_i(recommended) - score_i(usual)).
   The chart must show exactly the three factors, with |delta_i| (rounded to 3 decimals),
   the sign of delta_i, ordered by |delta_i|, and all-neutral bars when recommended == usual.
   The signed values must sum to the difference in total weighted score.

2. Did anything else change? Condition A and the recommendations themselves must be
   identical to the version used in the first run. The optimiser and the causal text of
   `--master-ref` are loaded from git and compared output by output.

Exit code 0 only if every check passes. Reads no participant data.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))
from explainer import generate_causal_explanation, generate_shap_data  # noqa: E402
from optimizer import APPLIANCES, optimize_schedule  # noqa: E402
from price_service import SCENARIOS, get_scenario_prices, get_scenario_renewable  # noqa: E402

KEYS = ("cost", "green", "convenience")


def slot_scores(prices, renew, app, start):
    """Independent copy of the scoring (same as analyse_shap_fidelity.slot_scores)."""
    vals = [p["price_eur_mwh"] for p in prices]
    lo, hi = min(vals), max(vals)
    hi = hi if hi != lo else lo + 1.0
    dur = app["duration_hours"]
    seg = prices[start:min(start + dur, 24)]
    avg_price = sum(p["price_eur_mwh"] for p in seg) / len(seg)
    cost = (hi - avg_price) / (hi - lo)
    rv = [r["renewable_share"] for r in renew]
    rlo, rhi = min(rv), max(rv)
    rspan = rhi - rlo if rhi != rlo else 0.01
    rseg = renew[start:min(start + dur, 24)]
    green = (sum(r["renewable_share"] for r in rseg) / len(rseg) - rlo) / rspan
    conv = max(0.0, 1.0 - abs(start - app["default_start"]) / 8.0)
    return {"cost": cost, "green": green, "convenience": conv}


def load_master(ref: str):
    """Import optimizer.py and explainer.py as they are on `ref`, into a temp package."""
    tmp = Path(tempfile.mkdtemp(prefix="master_backend_"))
    for name in ("optimizer.py", "explainer.py", "price_service.py"):
        src = subprocess.run(["git", "show", f"{ref}:backend/{name}"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
        (tmp / name).write_text(src, encoding="utf-8")
    mods = {}
    sys.path.insert(0, str(tmp))
    for name in ("price_service", "optimizer", "explainer"):
        spec = importlib.util.spec_from_file_location(f"master_{name}", tmp / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod          # so master's own imports resolve to master copies
        spec.loader.exec_module(mod)
        mods[name] = mod
    sys.path.remove(str(tmp))
    for name in ("price_service", "optimizer", "explainer"):
        del sys.modules[name]
    return mods["optimizer"], mods["explainer"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master-ref", default="master")
    args = ap.parse_args()
    m_opt, m_expl = load_master(args.master_ref)

    apps = {a["id"]: a for a in APPLIANCES}
    settings = [(c, g, 100 - c - g) for c in range(0, 101) for g in range(0, 101 - c)]
    n = n_same = 0
    fails: list[str] = []
    rec_changed = text_changed = 0

    for scen in sorted(SCENARIOS):
        prices, renew = get_scenario_prices(scen), get_scenario_renewable(scen)
        for c, g, v in settings:
            recs = optimize_schedule(prices, APPLIANCES, c, g, v, renewable_shares=renew)
            old = {r["appliance_id"]: r for r in
                   m_opt.optimize_schedule(prices, m_opt.APPLIANCES, c, g, v, renewable_shares=renew)}
            for rec in recs:
                n += 1
                aid = rec["appliance_id"]
                o = old[aid]
                # 2. nothing else changed
                if (rec["recommended_start"], rec["scores"], rec["weights_used"]) != \
                   (o["recommended_start"], o["scores"], o["weights_used"]):
                    rec_changed += 1
                if generate_causal_explanation(rec, rec["weights_used"], prices) != \
                   m_expl.generate_causal_explanation(o, o["weights_used"], prices):
                    text_changed += 1

                # 1. faithful chart
                total = c + g + v
                w = {"cost": c / total, "green": g / total, "convenience": v / total} if total else \
                    {k: 1 / 3 for k in KEYS}
                s_rec = slot_scores(prices, renew, apps[aid], rec["recommended_start"])
                s_use = slot_scores(prices, renew, apps[aid], rec["default_start"])
                delta = {k: w[k] * (s_rec[k] - s_use[k]) for k in KEYS}
                chart = generate_shap_data(rec, rec["weights_used"])
                where = f"{scen} {aid} w=({c},{g},{v})"

                if [f["feature"] for f in chart if True] and sorted(f["feature"] for f in chart) != sorted(KEYS):
                    fails.append(f"{where}: factors {[f['feature'] for f in chart]}")
                    continue
                if rec["recommended_start"] == rec["default_start"]:
                    n_same += 1
                    if any(f["direction"] != "neutral" or f["value"] != 0 for f in chart):
                        fails.append(f"{where}: recommended == usual but chart not all neutral")
                    continue
                for f in chart:
                    d = delta[f["feature"]]
                    want_dir = "neutral" if round(abs(d), 3) == 0 else ("positive" if d > 0 else "negative")
                    if f["direction"] != want_dir:
                        fails.append(f"{where}: {f['feature']} shown {f['direction']}, true {d:+.4f}")
                    if f["value"] != round(abs(d), 3):
                        fails.append(f"{where}: {f['feature']} shown {f['value']}, true {abs(d):.4f}")
                    if abs(f["signed_value"] - d) > 1e-9:
                        fails.append(f"{where}: {f['feature']} signed {f['signed_value']}, true {d}")
                shown_order = [f["feature"] for f in chart]
                if [abs(delta[k]) for k in shown_order] != sorted((abs(delta[k]) for k in KEYS), reverse=True):
                    fails.append(f"{where}: order {shown_order}")
                tot_rec = sum(w[k] * s_rec[k] for k in KEYS)
                tot_use = sum(w[k] * s_use[k] for k in KEYS)
                if abs(sum(f["signed_value"] for f in chart) - (tot_rec - tot_use)) > 1e-9:
                    fails.append(f"{where}: bars do not sum to the score difference")

    print(f"scenarios: {sorted(SCENARIOS)} · priority settings: {len(settings)} · charts checked: {n}")
    print(f"recommended == usual (all bars neutral): {n_same}")
    print(f"chart faithfulness failures: {len(fails)}")
    for line in fails[:20]:
        print("  FAIL", line)
    print(f"recommendations differing from {args.master_ref}: {rec_changed}")
    print(f"condition-A texts differing from {args.master_ref}: {text_changed}")
    ok = not fails and rec_changed == 0 and text_changed == 0
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
