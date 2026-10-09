"""
analyse_rerun_b_fidelity.py — were the charts the rerun participants actually saw faithful?

    python analyse_rerun_b_fidelity.py <rerun backup> [out.md]

Same unit of analysis as analyse_shap_fidelity.py (first run): the chart for one appliance
at each analysed participant's final accept/reject, regenerated with the deployed code from
the logged priority setting. Each chart is compared with an independent recomputation of
the exact contributions, and with the shap library (Exact explainer, usual slot as
background). Stimulus data only.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import shap

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "backend"))
import verify_b_chart_shap as vs  # noqa: E402
from explainer import generate_shap_data  # noqa: E402
from optimizer import APPLIANCES, optimize_schedule  # noqa: E402
from price_service import get_scenario_prices, get_scenario_renewable  # noqa: E402

PAGES = {"demographics", "tlx", "tia_1", "tia_2", "checks"}


def main() -> int:
    src = Path(sys.argv[1])
    f = json.loads(src.read_text(encoding="utf-8"))["files"]
    cond = {r["participant_id"]: r["condition"] for r in f["assignments"]["rows"]
            if not r.get("previous_run_participant", False)}
    pages = defaultdict(dict)
    for r in sorted(f["survey"]["rows"], key=lambda r: r["timestamp"]):
        pages[r["participant_id"]][r["page"]] = r["answers"]
    sample = {p for p in cond if cond[p] == "B" and PAGES <= set(pages[p])
              and str(pages[p]["checks"]["ac_instructed"]) == "2"}
    last = {}
    for e in sorted(f["events"]["rows"], key=lambda e: e["timestamp"]):
        if e["participant_id"] in sample and e["event_type"] in ("accept", "reject"):
            last[(e["participant_id"], e["scenario"], e["appliance_id"])] = e

    apps = {a["id"]: a for a in APPLIANCES}
    n = same = wrong_sign = wrong_value = wrong_order = sum_bad = 0
    max_shap = 0.0
    for (pid, scen, aid), e in last.items():
        sv = e["slider_values"]
        prices, renew = get_scenario_prices(scen), get_scenario_renewable(scen)
        rec = next(r for r in optimize_schedule(prices, APPLIANCES, sv["cost"], sv["green"],
                                                sv["convenience"], renewable_shares=renew)
                   if r["appliance_id"] == aid)
        chart = generate_shap_data(rec)
        n += 1
        w = rec["weights_exact"]
        s_rec = vs.raw_features(prices, renew, apps[aid], rec["recommended_start"])
        s_use = vs.raw_features(prices, renew, apps[aid], rec["default_start"])
        f_model = vs.make_model(prices, renew, apps[aid], w)
        phi = shap.explainers.Exact(f_model, np.array([s_use]))(np.array([s_rec])).values[0]
        delta = dict(zip(vs.ORDER, phi))
        if rec["recommended_start"] == rec["default_start"]:
            same += 1
        for b in chart:
            d = delta[b["feature"]]
            max_shap = max(max_shap, abs(d - b["signed_value"]))
            want = "neutral" if round(abs(d), 3) == 0 else ("positive" if d > 0 else "negative")
            if b["direction"] != want and abs(abs(d) - 0.0005) > 1e-12:
                wrong_sign += 1
            # Displayed to 3 decimals: correct if within half a unit of the last digit.
            # True values often end in exactly ...5 (convenience scores are multiples of
            # 1/8), where the library's and the closed form's last-bit difference (~1e-16)
            # decides between rounding up and down.
            if abs(b["value"] - abs(d)) > 0.0005 + 1e-12:
                wrong_value += 1
        if [abs(delta[b["feature"]]) for b in chart] != sorted((abs(v) for v in delta.values()), reverse=True):
            wrong_order += 1
        total = f_model(np.array([s_rec]))[0] - f_model(np.array([s_use]))[0]
        if abs(sum(b["signed_value"] for b in chart) - total) > 1e-9:
            sum_bad += 1

    lines = [
        "# Rerun condition-B chart fidelity (stimulus check, no outcomes)", "",
        f"Source: `{src.name}` · analysed rerun-B participants: {len(sample)} · charts at decision time: {n}", "",
        "| check | result |", "|---|---|",
        f"| Charts where recommended = usual (all bars zero, grey) | {same}/{n} |",
        f"| Bars with the wrong sign | {wrong_sign} |",
        f"| Bars whose displayed value is off by more than rounding (> 0.0005) | {wrong_value} |",
        f"| Charts with the wrong order | {wrong_order} |",
        f"| Charts whose bars do not sum to the score difference | {sum_bad} |",
        f"| Largest deviation from shap {shap.__version__} Exact | {max_shap:.1e} |",
    ]
    out = "\n".join(lines) + "\n"
    print(out)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
