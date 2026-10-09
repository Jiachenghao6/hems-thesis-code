"""
analyse_primary.py — the locked analysis of the main study.

Implements D:\\Claude\\Projects\\hems-thesis\\ANALYSIS_PLAN.md (locked 2026-09-30, commit 5214be9)
and nothing else. If the plan changes, the change goes into the plan's change log first,
then here — never the other way round.

    python analyse_primary.py backups/study-backup-20260930T200006Z.json [out.md]
    python analyse_primary.py <first-run backup> [out.md] --rerun-b <rerun backup>

`--rerun-b` implements change 1 of the plan (2026-10-06, written before the rerun data
existed): the analysed sample is condition A from the first run plus condition B from the
rerun; first-run condition B is dropped, and rerun participants flagged
`previous_run_participant` are dropped before any other rule is applied. Every other rule,
test and output is unchanged. Without the flag the script reproduces the first-run
analysis exactly.

Writes a Markdown report to stdout (and to out.md if given). The report contains no
Prolific IDs or participant ids.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

PAGES = {"demographics", "tlx", "tia_1", "tia_2", "checks"}
ATTENTION_CORRECT = "2"  # "Rather disagree"
N_DECISIONS = 12  # 3 scenarios x 4 appliances

TLX_ITEMS = ["tlx_mental", "tlx_physical", "tlx_temporal", "tlx_performance", "tlx_effort", "tlx_frustration"]
# Performance is anchored Perfect (0) -> Failure (100): higher already means more workload,
# the same direction as the other five. It is NOT reversed for the Raw TLX mean.

TIA_REVERSED = {5, 7, 10, 15, 16}
TIA_SUBSCALES = {
    "Trust": [9, 14],
    "Understanding/Predictability": [2, 7, 11, 16],
    "Reliability/Competence": [1, 6, 10, 13, 15, 19],
    "Propensity to Trust": [5, 12, 18],
}

POST_EXPOSURE_EVENTS = {"slider_move", "accept", "reject", "scenario_change", "task_complete"}


# ---------------------------------------------------------------- loading

def load(path: Path):
    files = json.loads(path.read_text(encoding="utf-8"))["files"]
    for name, f in files.items():
        if f.get("damaged"):
            raise SystemExit(f"{name}: server reported damaged lines — stop and inspect")
    return files["assignments"]["rows"], files["events"]["rows"], files["survey"]["rows"]


def combine_rerun(first, rerun):
    """Plan change 1: first-run A + rerun B (unflagged). Returns merged rows and the flag count."""
    a1, e1, s1 = first
    a2, e2, s2 = rerun
    keep1 = {r["participant_id"] for r in a1 if r["condition"] == "A"}
    keep2 = {r["participant_id"] for r in a2
             if r["condition"] == "B" and not r.get("previous_run_participant", False)}
    flagged = sum(1 for r in a2 if r.get("previous_run_participant", False))
    if keep1 & keep2:
        raise SystemExit("participant ids overlap between runs - stop and inspect")
    if any(r["condition"] != "B" for r in a2):
        raise SystemExit("rerun ledger contains a condition other than B - stop and inspect")
    merged = (
        [r for r in a1 if r["participant_id"] in keep1] + [r for r in a2 if r["participant_id"] in keep2],
        [e for e in e1 if e["participant_id"] in keep1] + [e for e in e2 if e["participant_id"] in keep2],
        [s for s in s1 if s["participant_id"] in keep1] + [s for s in s2 if s["participant_id"] in keep2],
    )
    return merged, flagged


def last_row_per_page(survey):
    """Plan §2: several rows for the same participant and page -> keep the latest."""
    out: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in sorted(survey, key=lambda r: r["timestamp"]):
        out[row["participant_id"]][row["page"]] = row["answers"]
    return out


def final_decisions(events):
    """Plan §3 P1: one decision per (participant, scenario, appliance), the latest one."""
    last: dict[tuple, str] = {}
    for e in sorted(events, key=lambda e: e["timestamp"]):
        if e["event_type"] in ("accept", "reject"):
            last[(e["participant_id"], e["scenario"], e["appliance_id"])] = e["event_type"]
    return last


def tia_score(answers: dict, item: int) -> float:
    raw = float(answers[f"tia{item:02d}"])
    return 6 - raw if item in TIA_REVERSED else raw


# ---------------------------------------------------------------- statistics

def rank_biserial(a, b) -> float:
    u_a = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    return 2 * u_a / (len(a) * len(b)) - 1


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def cohens_d(a, b) -> float:
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2))
    return float((np.mean(a) - np.mean(b)) / sp) if sp > 0 else float("nan")


def cronbach_alpha(matrix: np.ndarray) -> float:
    k = matrix.shape[1]
    if k < 2:
        return float("nan")
    item_var = matrix.var(axis=0, ddof=1).sum()
    total_var = matrix.sum(axis=1).var(ddof=1)
    return float(k / (k - 1) * (1 - item_var / total_var)) if total_var > 0 else float("nan")


def describe(x) -> str:
    x = np.asarray(x, dtype=float)
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    return f"{len(x)} | {x.mean():.2f} | {x.std(ddof=1):.2f} | {med:.2f} | {q1:.2f}–{q3:.2f}"


def compare(a, b) -> dict:
    mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    welch = stats.ttest_ind(a, b, equal_var=False)
    ci = welch.confidence_interval(0.95)
    return {
        "U": float(mw.statistic), "p_mw": float(mw.pvalue), "r_rb": rank_biserial(a, b),
        "t": float(welch.statistic), "df": float(welch.df), "p_welch": float(welch.pvalue),
        "d": cohens_d(a, b), "diff": float(np.mean(a) - np.mean(b)), "ci": (float(ci.low), float(ci.high)),
    }


# ---------------------------------------------------------------- main

def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    args = sys.argv[1:]
    rerun_src = None
    if "--rerun-b" in args:
        i = args.index("--rerun-b")
        rerun_src = Path(args[i + 1])
        del args[i:i + 2]
    src = Path(args[0])
    out_path = Path(args[1]) if len(args) > 1 else None
    assignments, events, survey = load(src)
    flagged = 0
    if rerun_src:
        (assignments, events, survey), flagged = combine_rerun(
            (assignments, events, survey), load(rerun_src))
    cond = {r["participant_id"]: r["condition"] for r in assignments}
    order = {r["participant_id"]: r["option_order"] for r in assignments}
    pages = last_row_per_page(survey)
    lines: list[str] = []
    w = lines.append

    # ---- sample (plan §2)
    completers = [p for p in cond if PAGES <= set(pages.get(p, {}))]
    excluded = [p for p in completers if str(pages[p]["checks"]["ac_instructed"]) != ATTENTION_CORRECT]
    sample = [p for p in completers if p not in excluded]
    non_completers = [p for p in cond if p not in completers]
    exposed = {e["participant_id"] for e in events if e["event_type"] in POST_EXPOSURE_EVENTS}
    post_exp_dropouts = [p for p in non_completers if p in exposed]

    grp = {c: [p for p in sample if cond[p] == c] for c in ("A", "B")}

    w(f"# Main study — locked analysis output\n")
    if rerun_src:
        w(f"Source: condition A from `{src.name}`, condition B from `{rerun_src.name}` · plan: "
          f"`ANALYSIS_PLAN.md` (commit 5214be9) with change 1 (2026-10-06) · rerun participants "
          f"excluded as previous-run participants: {flagged}\n")
    else:
        w(f"Source: `{src.name}` · plan: `ANALYSIS_PLAN.md` (commit 5214be9)\n")
    w("## 1. Sample\n")
    w(f"| | A | B | total |\n|---|---|---|---|")
    for label, ids in [("assigned", list(cond)), ("completed all survey pages", completers),
                       ("excluded (attention check)", excluded), ("analysed", sample)]:
        w(f"| {label} | {sum(cond[p]=='A' for p in ids)} | {sum(cond[p]=='B' for p in ids)} | {len(ids)} |")
    w("")
    w(f"Non-completers: {len(non_completers)} "
      f"(pre-exposure {len(non_completers) - len(post_exp_dropouts)}, post-exposure {len(post_exp_dropouts)}).")
    if post_exp_dropouts:
        a_drop = sum(cond[p] == "A" for p in post_exp_dropouts)
        b_drop = len(post_exp_dropouts) - a_drop
        a_exp = sum(cond[p] == "A" for p in exposed)
        b_exp = sum(cond[p] == "B" for p in exposed)
        _, p_f = stats.fisher_exact([[a_drop, a_exp - a_drop], [b_drop, b_exp - b_drop]])
        w(f"Post-exposure attrition Fisher exact p = {p_f:.3f}.")
    else:
        w("No post-exposure attrition, so the Fisher test is not needed.")
    w("")

    # ---- decisions
    dec = final_decisions(events)
    per_pid: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for (p, scen, _app), choice in dec.items():
        per_pid[p].append((scen, choice))
    bad = [p for p in sample if len(per_pid[p]) != N_DECISIONS]
    if bad:
        raise SystemExit(f"{len(bad)} analysed participants do not have exactly {N_DECISIONS} decisions — stop")

    def acceptance(p, scenario=None):
        ds = [c for s, c in per_pid[p] if scenario is None or s == scenario]
        return sum(c == "accept" for c in ds) / len(ds)

    def tlx(p):
        return float(np.mean([float(pages[p]["tlx"][k]) for k in TLX_ITEMS]))

    def sub(p, name):
        ans = {**pages[p]["tia_1"], **pages[p]["tia_2"]}
        return float(np.mean([tia_score(ans, i) for i in TIA_SUBSCALES[name]]))

    # ---- primary (plan §3)
    primary = [
        ("P1 Acceptance rate", lambda p: acceptance(p)),
        ("P2 Raw TLX", tlx),
        ("P3 TiA-Trust", lambda p: sub(p, "Trust")),
    ]
    res = []
    for name, fn in primary:
        a = [fn(p) for p in grp["A"]]
        b = [fn(p) for p in grp["B"]]
        res.append((name, a, b, compare(a, b)))
    adj_mw = holm([r[3]["p_mw"] for r in res])
    adj_w = holm([r[3]["p_welch"] for r in res])

    w("## 2. Primary outcomes (confirmatory)\n")
    w("Descriptives — n | mean | SD | median | IQR\n")
    w("| outcome | A | B |\n|---|---|---|")
    for name, a, b, _ in res:
        w(f"| {name} | {describe(a)} | {describe(b)} |")
    w("\nMain test: Mann-Whitney U, two-sided, Holm over the three outcomes. "
      "r = rank-biserial (positive = A higher).\n")
    w("| outcome | U | p | p (Holm) | r | significant |\n|---|---|---|---|---|---|")
    for (name, _, _, c), pa in zip(res, adj_mw):
        w(f"| {name} | {c['U']:.1f} | {c['p_mw']:.4f} | {pa:.4f} | {c['r_rb']:+.3f} | {'yes' if pa < .05 else 'no'} |")
    w("\nRobustness: Welch t, two-sided, Holm over the three outcomes.\n")
    w("| outcome | mean diff A−B [95% CI] | t | df | p | p (Holm) | d |\n|---|---|---|---|---|---|---|")
    for (name, _, _, c), pa in zip(res, adj_w):
        w(f"| {name} | {c['diff']:+.3f} [{c['ci'][0]:+.3f}, {c['ci'][1]:+.3f}] | {c['t']:.2f} | {c['df']:.1f} "
          f"| {c['p_welch']:.4f} | {pa:.4f} | {c['d']:+.2f} |")
    agree = all((pm < .05) == (pw < .05) for pm, pw in zip(adj_mw, adj_w))
    w(f"\nMann-Whitney and Welch agree on significance for every outcome: **{'yes' if agree else 'NO — report both, follow Mann-Whitney'}**.\n")

    # ---- secondary (plan §5)
    w("## 3. Secondary outcomes (exploratory, uncorrected)\n")
    w("| outcome | A median | B median | U | p | r |\n|---|---|---|---|---|---|")
    secondary = [
        ("TiA Understanding/Predictability", lambda p: sub(p, "Understanding/Predictability")),
        ("TiA Reliability/Competence", lambda p: sub(p, "Reliability/Competence")),
        *[(f"TLX {k.removeprefix('tlx_')}", (lambda k: lambda p: float(pages[p]["tlx"][k]))(k)) for k in TLX_ITEMS],
        *[(f"Acceptance {s}", (lambda s: lambda p: acceptance(p, s))(s)) for s in ("S1", "S2", "S3")],
    ]
    for name, fn in secondary:
        a = [fn(p) for p in grp["A"]]
        b = [fn(p) for p in grp["B"]]
        c = compare(a, b)
        w(f"| {name} | {np.median(a):.2f} | {np.median(b):.2f} | {c['U']:.1f} | {c['p_mw']:.4f} | {c['r_rb']:+.3f} |")
    w("\nOption-order check (acceptance rate, both conditions pooled):\n")
    w("| option order | n | median | mean |\n|---|---|---|---|")
    oo = {o: [acceptance(p) for p in sample if order[p] == o] for o in ("accept_first", "reject_first")}
    for o, v in oo.items():
        w(f"| {o} | {len(v)} | {np.median(v):.3f} | {np.mean(v):.3f} |")
    c = compare(oo["accept_first"], oo["reject_first"])
    w(f"\nMann-Whitney accept_first vs reject_first: U = {c['U']:.1f}, p = {c['p_mw']:.4f}, r = {c['r_rb']:+.3f}.\n")

    # ---- descriptive only (plan §6)
    w("## 4. Descriptive only\n")
    for item in ("mc_updates", "mc_modality"):
        w(f"**{item}**\n")
        vals = sorted({str(pages[p]['checks'][item]) for p in sample})
        w("| answer | A | B |\n|---|---|---|")
        for v in vals:
            w(f"| {v} | {sum(str(pages[p]['checks'][item]) == v for p in grp['A'])} "
              f"| {sum(str(pages[p]['checks'][item]) == v for p in grp['B'])} |")
        w("")
    w("**Demographics (balance check, no tests)**\n")
    for k in ("dem_age", "dem_gender", "dem_pays_bill", "dem_dynamic_tariff", "dem_smart_home", "dem_flexibility"):
        ca = Counter(str(pages[p]["demographics"][k]) for p in grp["A"])
        cb = Counter(str(pages[p]["demographics"][k]) for p in grp["B"])
        w(f"- `{k}`: A {dict(sorted(ca.items()))} · B {dict(sorted(cb.items()))}")
    w("")
    pa_ = [sub(p, "Propensity to Trust") for p in grp["A"]]
    pb_ = [sub(p, "Propensity to Trust") for p in grp["B"]]
    w(f"**Propensity to Trust** (n | mean | SD | median | IQR): A {describe(pa_)} · B {describe(pb_)}\n")
    moves = Counter(e["participant_id"] for e in events if e["event_type"] == "slider_move")
    w(f"**slider_move per participant, median**: A {np.median([moves[p] for p in grp['A']]):.0f} · "
      f"B {np.median([moves[p] for p in grp['B']]):.0f}\n")

    w("**Reliability (analysed sample, both conditions pooled)**\n")
    tlx_m = np.array([[float(pages[p]["tlx"][k]) for k in TLX_ITEMS] for p in sample])
    w(f"- Raw TLX (6 items): α = {cronbach_alpha(tlx_m):.2f}")
    for name, items in TIA_SUBSCALES.items():
        m = np.array([[tia_score({**pages[p]['tia_1'], **pages[p]['tia_2']}, i) for i in items] for p in sample])
        extra = ""
        if len(items) == 2:
            rho = stats.spearmanr(m[:, 0], m[:, 1]).statistic
            extra = f", Spearman ρ between the two items = {rho:.2f}"
        w(f"- TiA {name} ({len(items)} items): α = {cronbach_alpha(m):.2f}{extra}")

    report = "\n".join(lines) + "\n"
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    if out_path:
        out_path.write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
