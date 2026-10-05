"""
analyse_a_fidelity.py — how faithful was the condition-A text participants actually saw?

    python analyse_a_fidelity.py backups/study-backup-20260930T200006Z.json [out.md]

Background (2026-10-05): the counterfactual endpoints of sentence 2 were checked on
2026-10-01 (12/12 consistent with the optimiser). Sentence 1 was not. Running the corrected
condition-B chart locally showed an EV-charger card where the text said "the price drops
to 195.0 €/MWh — saving roughly 158 ct compared to your usual 22:00 slot" while the usual
slot averaged 140 €/MWh and savings_eur was -1.58: `explainer.py` prints abs(savings).

This script regenerates, with the code of the first run, the text each condition-A
participant saw when making each final decision, and checks every factual claim in
sentence 1 against the optimiser's own numbers:

  cost branch        "the price drops to X — saving Y ct"   -> recommended avg price must be
                     below the usual slot's, and savings_eur > 0
  green branch       "the cleanest window available"        -> recommended window must have the
                     highest renewable share of all feasible windows
                     "X% … against Y% at your usual slot"   -> printed only if X > Y (checked)
  convenience branch "because the saving over that window   -> savings_eur > 0
                     outweighs the change to your routine"
                     "no change" / "by 1 hour" / "barely"   -> arithmetic only (not a claim)

Unit of analysis as in analyse_shap_fidelity.py: the last accept/reject per participant,
scenario and appliance, analysed sample only. Stimulus data only, never outcomes.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from explainer import generate_causal_explanation  # noqa: E402
from optimizer import APPLIANCES, optimize_schedule  # noqa: E402
from price_service import get_scenario_prices, get_scenario_renewable  # noqa: E402

PAGES = {"demographics", "tlx", "tia_1", "tia_2", "checks"}


def avg(xs):
    return sum(xs) / len(xs)


def main() -> int:
    src = Path(sys.argv[1])
    files = json.loads(src.read_text(encoding="utf-8"))["files"]
    cond = {r["participant_id"]: r["condition"] for r in files["assignments"]["rows"]}
    pages = defaultdict(dict)
    for row in sorted(files["survey"]["rows"], key=lambda r: r["timestamp"]):
        pages[row["participant_id"]][row["page"]] = row["answers"]
    sample = {p for p in cond if cond[p] == "A" and PAGES <= set(pages[p])
              and str(pages[p]["checks"]["ac_instructed"]) == "2"}

    last = {}
    for e in sorted(files["events"]["rows"], key=lambda e: e["timestamp"]):
        if e["participant_id"] in sample and e["event_type"] in ("accept", "reject"):
            last[(e["participant_id"], e["scenario"], e["appliance_id"])] = e

    apps = {a["id"]: a for a in APPLIANCES}
    n = 0
    branch = Counter()
    wrong = Counter()
    wrong_by_app = defaultdict(Counter)
    examples: dict[str, str] = {}
    participants_hit = defaultdict(set)

    for (pid, scen, app_id), e in last.items():
        sv = e["slider_values"]
        prices, renew = get_scenario_prices(scen), get_scenario_renewable(scen)
        recs = {r["appliance_id"]: r for r in optimize_schedule(
            prices, APPLIANCES, sv["cost"], sv["green"], sv["convenience"], renewable_shares=renew)}
        rec = recs[app_id]
        w = rec["weights_used"]
        text = generate_causal_explanation(rec, w, prices)
        n += 1
        app = apps[app_id]
        dur = app["duration_hours"]

        def flag(kind):
            wrong[kind] += 1
            wrong_by_app[kind][app_id] += 1
            participants_hit[kind].add(pid)
            examples.setdefault(kind, f"{scen} {app_id} w={sv} → {text}")

        if "when the price drops to" in text:
            branch["cost"] += 1
            if rec["recommended_start"] == rec["default_start"]:
                flag("cost: no move, yet says the price 'drops' and names a saving (of 0 ct)")
            elif rec["savings_eur"] <= 0:
                flag("cost: claims a saving, but the recommended slot is more expensive")
        elif "the cleanest window available" in text:
            branch["green"] += 1
            max_start = min(app["latest_finish"] - dur, 24 - dur)
            if max_start < 0:
                max_start = 24 - dur
            shares = {s: avg([r["renewable_share"] for r in renew[s:min(s + dur, 24)]])
                      for s in range(0, max_start + 1)}
            if shares[rec["recommended_start"]] < max(shares.values()) - 1e-9:
                flag("green: 'cleanest window available' but a cleaner feasible window exists")
        elif "because the saving over that window outweighs" in text:
            branch["convenience, moved >1 h"] += 1
            if rec["savings_eur"] <= 0:
                flag("convenience: attributes the move to a saving, but there is none")
        else:
            branch["other (no factual claim checked)"] += 1

    m = sum(wrong.values())
    pct = lambda a, b: f"{a}/{b} ({100 * a / b:.0f}%)" if b else "—"
    lines = [
        "# Condition-A text fidelity, sentence 1 (stimulus check, no outcomes)",
        "",
        f"Source: `{src.name}` · condition-A analysed sample: {len(sample)} participants · "
        f"texts at decision time: {n}",
        "",
        "| sentence-1 branch | texts |",
        "|---|---|",
    ] + [f"| {k} | {v} |" for k, v in branch.most_common()] + [
        "",
        "| problem | texts | participants affected | by appliance |",
        "|---|---|---|---|",
    ] + [f"| {k} | {pct(v, n)} | {len(participants_hit[k])}/{len(sample)} | "
         f"{', '.join(f'{a} {c}' for a, c in wrong_by_app[k].most_common())} |"
         for k, v in wrong.most_common()] + [
        "",
        f"Texts with at least one false claim in sentence 1: {pct(m, n)} "
        "(each text has one sentence-1 branch, so the rows do not overlap).",
        "",
        "## One example per problem",
        "",
    ] + [f"- **{k}**: {v}" for k, v in examples.items()]
    out = "\n".join(lines) + "\n"
    print(out)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
