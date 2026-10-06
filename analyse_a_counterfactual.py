"""
analyse_a_counterfactual.py — what did the condition-A counterfactual (sentence 2) promise,
and what would the optimiser actually have done?

    python analyse_a_counterfactual.py backups/study-backup-20260930T200006Z.json [out.md]

The 2026-10-01 check only compared the *endpoint* named in sentence 2 with the optimiser's
choice at a weight of 100%. Participants, however, read "If you raise the Cost weight, the
system would shift to X" while their Cost weight was, say, 30%. This script follows the
path a participant would take: raise the named weight step by step (1 percentage point),
keeping the other two weights in their current ratio, and records

  • the weight at which the recommendation first reaches the named slot,
  • whether other slots appear on the way (the text names only the end point),
  • for "already balances … would only change the timing marginally": the largest shift
    obtainable by raising any single weight, up to 100%.

Same unit of analysis as analyse_a_fidelity.py. Stimulus data only.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))
from explainer import _cheapest_slot, _most_convenient_slot, generate_causal_explanation  # noqa: E402
from optimizer import APPLIANCES, optimize_schedule  # noqa: E402
from price_service import get_scenario_prices, get_scenario_renewable  # noqa: E402

PAGES = {"demographics", "tlx", "tia_1", "tia_2", "checks"}


def path(prices, renew, app_id, sv, key):
    """Recommended start as weight `key` goes from its current share to 100%."""
    tot = sum(sv.values())
    cur = {k: v / tot for k, v in sv.items()}
    others = [k for k in cur if k != key]
    rest = sum(cur[k] for k in others)
    out = []
    start = round(cur[key] * 100)
    for t in range(start, 101):
        w = {key: t}
        for k in others:
            w[k] = (100 - t) * (cur[k] / rest) if rest > 0 else (100 - t) / 2
        rec = next(r for r in optimize_schedule(prices, APPLIANCES, w["cost"], w["green"],
                                                w["convenience"], renewable_shares=renew)
                   if r["appliance_id"] == app_id)
        out.append((t, rec["recommended_start"]))
    return out


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
    branch = Counter()
    gap = defaultdict(list)          # percentage points needed to reach the named slot
    detour = Counter()               # other slots appear before the named one
    never = Counter()                # named slot not reached even at 100%
    marginal_max = []
    example = {}

    for (pid, scen, app_id), e in last.items():
        sv = {k: float(e["slider_values"][k]) for k in ("cost", "green", "convenience")}
        prices, renew = get_scenario_prices(scen), get_scenario_renewable(scen)
        rec = next(r for r in optimize_schedule(prices, APPLIANCES, sv["cost"], sv["green"],
                                                sv["convenience"], renewable_shares=renew)
                   if r["appliance_id"] == app_id)
        text = generate_causal_explanation(rec, rec["weights_used"], prices)
        dur = apps[app_id]["duration_hours"]
        cur_start = rec["recommended_start"]

        if "If you raise the Cost weight" in text:
            kind, key, target = "raise Cost → cheapest window", "cost", _cheapest_slot(prices, dur)
        elif "If you raise the Convenience weight" in text:
            kind, key, target = "raise Convenience → back towards usual", "convenience", \
                _most_convenient_slot(apps[app_id]["default_start"], dur)
        elif "If you prioritise Convenience instead" in text:
            kind, key, target = "prioritise Convenience → named slot", "convenience", \
                _most_convenient_slot(apps[app_id]["default_start"], dur)
        else:
            kind = "already balances (no counterfactual)"
            branch[kind] += 1
            shifts = []
            for key in ("cost", "green", "convenience"):
                for _, s in path(prices, renew, app_id, sv, key):
                    shifts.append(abs(s - cur_start))
            marginal_max.append(max(shifts))
            if max(shifts) > 1:
                example.setdefault(kind, f"{scen} {app_id} w={sv}: raising one weight can move it "
                                         f"by {max(shifts)} h → {text}")
            continue

        branch[kind] += 1
        p = path(prices, renew, app_id, sv, key)
        cur_w = p[0][0]
        hit = next((t for t, s in p if s == target), None)
        if hit is None:
            never[kind] += 1
            example.setdefault(kind + " (never reached)", f"{scen} {app_id} w={sv} → {text}")
            continue
        gap[kind].append(hit - cur_w)
        visited = {s for t, s in p if t < hit} - {cur_start, target}
        if visited:
            detour[kind] += 1
            example.setdefault(kind + " (detour)", f"{scen} {app_id} w={sv}: passes "
                               f"{sorted(visited)} before {target} → {text}")

    lines = ["# Condition-A counterfactual (sentence 2): promise vs. optimiser along the path",
             "", f"Source: `{src.name}` · texts at decision time: {sum(branch.values())}", "",
             "| sentence-2 branch | texts | named slot reached | pp of weight needed: median [min–max] | "
             "share needing ≥ 30 pp | other slots on the way |",
             "|---|---|---|---|---|---|"]
    for kind, n in branch.most_common():
        if kind.startswith("already"):
            big = sum(1 for m in marginal_max if m > 1)
            lines.append(f"| {kind} | {n} | — | — | — | raising one weight shifts > 1 h in "
                         f"{big}/{n}; max {max(marginal_max) if marginal_max else 0} h |")
            continue
        g = gap[kind]
        reached = len(g)
        med = f"{statistics.median(g):.0f} [{min(g)}–{max(g)}]" if g else "—"
        big = f"{sum(1 for x in g if x >= 30)}/{reached}" if g else "—"
        lines.append(f"| {kind} | {n} | {reached}/{n} | {med} | {big} | {detour[kind]}/{reached} |")
    lines += ["", "## Examples", ""] + [f"- **{k}**: {v}" for k, v in example.items()]
    out = "\n".join(lines) + "\n"
    print(out)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
