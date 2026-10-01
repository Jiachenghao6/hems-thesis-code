"""
analyse_shap_fidelity.py — how faithful was the condition-B chart participants actually saw?

    python analyse_shap_fidelity.py backups/study-backup-20260930T200006Z.json [out.md]

Background (2026-10-01): `explainer.generate_shap_data` is not a decomposition of the
optimiser's score. It draws the cost contribution twice ("Electricity price level" and
"Cost priority" = the same product x 0.8), adds an "Hour of day" factor that the optimiser
does not have, scales the other bars by unexplained constants, and sets each bar's sign
with threshold rules. This script measures how far the displayed charts were from a
faithful attribution. It reads stimulus data only (what was on screen), never outcomes.

Reference attribution. The card shows "your usual time -> recommended time", so the
faithful question is "why this time rather than my usual one". For the weighted-sum
optimiser that answer is exact, no estimation needed:

    delta_i = w_i * (score_i(recommended) - score_i(usual)),   i in {cost, green, convenience}

and the three deltas sum to the difference in total score.

Unit of analysis: the chart for one appliance at the moment a condition-B participant
accepted or rejected it (the last decision per participant, scenario and appliance).
Charts where recommended == usual are reported separately: every delta is zero there,
so any non-empty chart is unfaithful by construction.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from explainer import generate_shap_data  # noqa: E402
from optimizer import APPLIANCES, optimize_schedule  # noqa: E402
from price_service import get_scenario_prices, get_scenario_renewable  # noqa: E402

PAGES = {"demographics", "tlx", "tia_1", "tia_2", "checks"}
REAL = {"electricity_price": "cost", "green_weight": "green", "convenience_weight": "convenience"}


def slot_scores(prices, renew, app, start):
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


def main() -> int:
    src = Path(sys.argv[1])
    files = json.loads(src.read_text(encoding="utf-8"))["files"]
    cond = {r["participant_id"]: r["condition"] for r in files["assignments"]["rows"]}
    pages = defaultdict(dict)
    for row in sorted(files["survey"]["rows"], key=lambda r: r["timestamp"]):
        pages[row["participant_id"]][row["page"]] = row["answers"]
    sample = {p for p in cond if cond[p] == "B" and PAGES <= set(pages[p])
              and str(pages[p]["checks"]["ac_instructed"]) == "2"}

    last = {}
    for e in sorted(files["events"]["rows"], key=lambda e: e["timestamp"]):
        if e["participant_id"] in sample and e["event_type"] in ("accept", "reject"):
            last[(e["participant_id"], e["scenario"], e["appliance_id"])] = e

    apps = {a["id"]: a for a in APPLIANCES}
    cache = {}
    n = n_same = 0
    top_fake = top_dup_or_fake = sign_wrong_any = rank_wrong = 0
    sign_wrong_by = Counter()
    sign_checked_by = Counter()
    largest_real_wrong = 0
    for (pid, scen, app_id), e in last.items():
        sv = e["slider_values"]
        key = (scen, sv["cost"], sv["green"], sv["convenience"])
        if key not in cache:
            prices, renew = get_scenario_prices(scen), get_scenario_renewable(scen)
            recs = optimize_schedule(prices, APPLIANCES, sv["cost"], sv["green"], sv["convenience"], renewable_shares=renew)
            cache[key] = (prices, renew, {r["appliance_id"]: r for r in recs})
        prices, renew, recs = cache[key]
        rec = recs[app_id]
        w = rec["weights_used"]
        chart = generate_shap_data(rec, w)
        n += 1
        if rec["recommended_start"] == rec["default_start"]:
            n_same += 1
            continue
        s_rec = slot_scores(prices, renew, apps[app_id], rec["recommended_start"])
        s_def = slot_scores(prices, renew, apps[app_id], rec["default_start"])
        delta = {k: w[k] * (s_rec[k] - s_def[k]) for k in ("cost", "green", "convenience")}

        top = chart[0]["feature"]
        if top in ("hour_of_day", "appliance_habit"):
            top_fake += 1
        if top not in REAL:
            top_dup_or_fake += 1

        wrong_here = False
        for f in chart:
            if f["feature"] in REAL:
                k = REAL[f["feature"]]
                if abs(delta[k]) < 1e-9:
                    continue
                sign_checked_by[k] += 1
                shown_pos = f["direction"] == "positive"
                if shown_pos != (delta[k] > 0):
                    sign_wrong_by[k] += 1
                    wrong_here = True
        sign_wrong_any += wrong_here

        shown = {REAL[f["feature"]]: f["value"] for f in chart if f["feature"] in REAL}
        if sorted(shown, key=shown.get, reverse=True) != sorted(delta, key=lambda k: abs(delta[k]), reverse=True):
            rank_wrong += 1
        true_top = max(delta, key=lambda k: abs(delta[k]))
        shown_top_real = max(shown, key=shown.get)
        largest_real_wrong += shown_top_real != true_top

    m = n - n_same
    pct = lambda a, b: f"{a}/{b} ({100 * a / b:.0f}%)" if b else "—"
    lines = [
        "# Condition-B chart fidelity (stimulus check, no outcomes)",
        "",
        f"Source: `{src.name}` · condition-B analysed sample: {len(sample)} participants · "
        f"charts at decision time: {n}",
        "",
        "Reference: delta_i = w_i x (score_i(recommended) − score_i(usual)), exact for the weighted-sum optimiser.",
        "",
        "| check | result |",
        "|---|---|",
        f"| Charts where the recommended time equals the usual time (every true contribution is zero, chart still shows six bars) | {pct(n_same, n)} |",
        f"| Charts where Cost appears twice (price level + Cost priority) | {pct(n, n)} (by construction) |",
        f"| Charts containing 'Hour of day', a factor the optimiser does not use | {pct(n, n)} (by construction) |",
        f"| **Top bar is a factor the optimiser does not have** (Hour of day / run-time habit) | {pct(top_fake, m)} |",
        f"| Top bar is not one of the three real components (incl. the duplicated Cost bar) | {pct(top_dup_or_fake, m)} |",
        f"| **At least one real component shown with the wrong sign** (green vs red) | {pct(sign_wrong_any, m)} |",
        f"| Largest real component in the chart ≠ largest true contribution | {pct(largest_real_wrong, m)} |",
        f"| Ranking of the three real components differs from the true ranking | {pct(rank_wrong, m)} |",
        "",
        "Wrong sign, by component (charts where that component's true contribution is non-zero):",
        "",
        "| component | wrong sign |",
        "|---|---|",
    ]
    for k in ("cost", "green", "convenience"):
        lines.append(f"| {k} | {pct(sign_wrong_by[k], sign_checked_by[k])} |")
    report = "\n".join(lines) + "\n"
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
