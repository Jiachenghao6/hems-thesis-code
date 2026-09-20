"""
analyse_attrition.py — who was assigned, who finished, and does that differ by condition?

Block randomisation balances *assignments*. It cannot balance *completions*, because a
participant who walks away has already consumed a cell. This script is the reverse
reconciliation for that: it starts from the assignment ledger rather than from the
finished questionnaires, so somebody who was assigned and then vanished cannot go
unnoticed.

Two very different things get called "dropout", and the whole point of the script is to
keep them apart:

  **Pre-exposure** — assigned, but never reached a task screen. Consent, the tutorial
  and the situation card are all verbatim identical in both conditions, so these people
  left before anything that distinguishes the groups was on screen. They cost a cell and
  nothing else: their leaving cannot be caused by the condition, so it cannot bias the
  comparison. Report the count and move on.

  Note what the boundary is *not*: finishing the tutorial. The explanation first appears
  on the task screen, one transition later, and someone who read the tutorial and then
  closed the tab on the situation card has still seen nothing condition-specific. There
  is no event for arriving at a task, so first contact is inferred from the first thing a
  participant can only do there — moving the control, or deciding on a suggestion.

  **Post-exposure** — saw an explanation and then stopped. These are the dangerous
  ones. If one condition loses more of them, the people who remain in that group are a
  self-selected subset, and any difference between the groups is confounded with who
  stayed. That is an internal-validity problem, and no amount of over-recruiting fixes
  it — over-recruiting only restores the sample size.

So the number to watch during data collection is not "are the groups the same size"
(they will be close enough, and mild unevenness costs almost no power) but "do the two
conditions lose people at the same rate". Fisher's exact test on the post-exposure
dropouts is reported for that; with the numbers involved it is a monitoring aid, not a
confirmatory test.

The exclusion rule has to be fixed in the Study Design chapter BEFORE these numbers are
looked at, exactly like the attention check.

Usage:

    set DATA_DIR=C:\\path\\to\\data
    python analyse_attrition.py
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from fractions import Fraction
from math import comb
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent / "backend")))

#: The survey page that marks a finished run.
FINAL_PAGE = "checks"

#: Events that can only happen on a task screen, i.e. with an explanation on display.
#: `task_complete` alone would miss anyone who left a task without finishing it.
TASK_SCREEN_EVENTS = {"slider_move", "accept", "reject", "scenario_change", "task_complete"}

#: Ordered milestones, coarsest first. A participant's stage is the last one reached.
STAGES = [
    "assigned",
    "tutorial_complete",
    "saw_explanation",
    "task_1",
    "task_2",
    "task_3",
    "survey_demographics",
    "survey_tlx",
    "survey_tia_1",
    "survey_tia_2",
    "survey_checks",
]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # A half-written line is skipped, never counted as a participant.
                continue
    return out


def stage_of(pid: str, events: list[dict], survey: list[dict]) -> str:
    """The furthest milestone this participant reached."""
    reached = {"assigned"}
    if any(e.get("event_type") == "tutorial_complete" for e in events):
        reached.add("tutorial_complete")
    if any(e.get("event_type") in TASK_SCREEN_EVENTS for e in events):
        reached.add("saw_explanation")
    for n in range(1, len([e for e in events if e.get("event_type") == "task_complete"]) + 1):
        reached.add(f"task_{n}")
    for page in {r.get("page") for r in survey}:
        reached.add(f"survey_{page}")
    for stage in reversed(STAGES):
        if stage in reached:
            return stage
    return "assigned"


def fisher_exact_2x2(a: int, b: int, c: int, d: int) -> float:
    """
    Two-tailed Fisher's exact p for [[a, b], [c, d]].

    Hand-rolled rather than pulled from SciPy: this script has to run wherever a backup
    was unpacked, and a dependency that might not be installed is a script that silently
    does not get run.
    """
    n = a + b + c + d
    if n == 0:
        return 1.0
    row1, col1 = a + b, a + c

    # Exact rationals, not floats. The two-tailed p is the sum over every table whose
    # probability is *at most* the observed one, and on a symmetric table the mirror of
    # the observed table has exactly the same probability. In binary floating point the
    # two can differ in the last bit, and that table then falls out of the sum — a wrong
    # p value with nothing to indicate it. Fraction makes the comparison exact; the
    # counts here are small enough that the cost is irrelevant.
    def p_of(x: int) -> Fraction:
        return Fraction(comb(row1, x) * comb(n - row1, col1 - x), comb(n, col1))

    observed = p_of(a)
    lo = max(0, col1 - (n - row1))
    hi = min(row1, col1)
    total = sum((p for x in range(lo, hi + 1) if (p := p_of(x)) <= observed), Fraction(0))
    return min(1.0, float(total))


def main() -> int:
    assignments = read_jsonl(DATA_DIR / "assignments.jsonl")
    events = read_jsonl(DATA_DIR / "experiment_log.jsonl")
    survey = read_jsonl(DATA_DIR / "survey_responses.jsonl")

    if not assignments:
        print(f"No assignment ledger under {DATA_DIR} — nothing to reconcile.")
        return 1

    ev_by_pid: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        ev_by_pid[e.get("participant_id")].append(e)
    sv_by_pid: dict[str, list[dict]] = defaultdict(list)
    for s in survey:
        sv_by_pid[s.get("participant_id")].append(s)

    rows = []
    for a in assignments:
        pid = a["participant_id"]
        stage = stage_of(pid, ev_by_pid.get(pid, []), sv_by_pid.get(pid, []))
        finished = f"survey_{FINAL_PAGE}" in {
            f"survey_{r.get('page')}" for r in sv_by_pid.get(pid, [])
        }
        exposed = any(
            e.get("event_type") in TASK_SCREEN_EVENTS for e in ev_by_pid.get(pid, [])
        )
        rows.append(
            {
                "pid": pid,
                "condition": a.get("condition"),
                "option_order": a.get("option_order", "accept_first"),
                "stage": stage,
                "finished": finished,
                "exposed": exposed,
                "assigned_at": a.get("assigned_at", ""),
            }
        )

    print(f"Assignment ledger: {DATA_DIR / 'assignments.jsonl'}")
    print(f"{len(rows)} cells issued\n")

    # ── Per condition ───────────────────────────────────────────────────────
    print("condition   issued   pre-exposure   post-exposure   completed")
    per_cond = {}
    for cond in sorted({r["condition"] for r in rows}):
        sub = [r for r in rows if r["condition"] == cond]
        pre = [r for r in sub if not r["exposed"]]
        post = [r for r in sub if r["exposed"] and not r["finished"]]
        done = [r for r in sub if r["finished"]]
        per_cond[cond] = (len(post), len(done))
        print(f"  {cond:8} {len(sub):6} {len(pre):14} {len(post):15} {len(done):11}")

    total_done = sum(d for _, d in per_cond.values())
    print(f"\n  completions: {total_done}")

    # ── Cell balance among completers ───────────────────────────────────────
    cells = Counter((r["condition"], r["option_order"]) for r in rows if r["finished"])
    if cells:
        print("\ncompleted by cell (condition / option order):")
        for (c, o), n in sorted(cells.items()):
            print(f"  {c}/{o:13} {n}")

    # ── Differential attrition ──────────────────────────────────────────────
    if len(per_cond) == 2:
        (ca, (pa, da)), (cb, (pb, db)) = sorted(per_cond.items())
        print("\npost-exposure dropout by condition")
        print(f"  {ca}: {pa} of {pa + da}   {cb}: {pb} of {pb + db}")
        if pa + da and pb + db:
            p = fisher_exact_2x2(pa, da, pb, db)
            print(f"  Fisher's exact p = {p:.3f}")
            if p < 0.05:
                print("  ⚠ the two conditions are NOT losing people at the same rate —")
                print("    the completers are a self-selected subset and the group")
                print("    comparison is confounded. This belongs in the write-up.")
            elif pa + pb == 0:
                print("  no post-exposure dropouts yet.")
            else:
                print("  no evidence of differential attrition (underpowered — watch the trend).")

    # ── Where the post-exposure leavers stopped ─────────────────────────────
    leavers = [r for r in rows if r["exposed"] and not r["finished"]]
    if leavers:
        print("\nwhere post-exposure leavers stopped:")
        by_stage: dict[str, Counter] = defaultdict(Counter)
        for r in leavers:
            by_stage[r["stage"]][r["condition"]] += 1
        for stage in STAGES:
            if stage in by_stage:
                detail = "  ".join(f"{c}={n}" for c, n in sorted(by_stage[stage].items()))
                print(f"  {stage:22} {detail}")

    pre = [r for r in rows if not r["exposed"]]
    if pre:
        print(f"\n{len(pre)} cell(s) consumed before any explanation was on screen.")
        print("  These cannot bias the comparison — nothing condition-specific had")
        print("  appeared yet — but they do need over-recruiting to reach the target n.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
