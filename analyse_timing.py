"""
analyse_timing.py — how long does a run actually take, and where does the time go?

Answers the question the Prolific study form asks: "How long will your study take to
complete?" Underestimating it triggers additional payments and participant complaints;
overestimating it raises the reward per participant. Either way the number should come
from measurement, not from a planning document.

No extra instrumentation was needed — every event already carries a timestamp, and the
questionnaire is written one page at a time, so the phase boundaries are already in the
data:

    start           first `page_load` event for that participant
    task 1..3       each `task_complete` event
    survey pages    each survey record's timestamp
    end             the `checks` survey record

Usage (point it at wherever the runs were recorded):

    set DATA_DIR=C:\\path\\to\\timing-runs
    python analyse_timing.py

Reports the median rather than the mean: Prolific compares against the median completion
time, and one participant who wanders off for ten minutes should not move the estimate.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent / "backend")))

#: Survey pages in the order participants meet them; the last one ends the run.
SURVEY_ORDER = ["demographics", "tlx", "tia_1", "tia_2", "checks"]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # Reported, not skipped quietly — a damaged line means data was lost.
                print(f"  ! unparseable line in {path.name}", file=sys.stderr)
    return out


def ts(rec: dict) -> datetime | None:
    raw = rec.get("timestamp") or ""
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def phases_for(pid: str, events: list[dict], survey: list[dict]) -> dict[str, float] | None:
    """Seconds spent in each phase for one participant, or None if the run is partial."""
    ev = sorted((e for e in events if e.get("participant_id") == pid and ts(e)), key=ts)
    sv = sorted((s for s in survey if s.get("participant_id") == pid and ts(s)), key=ts)
    if not ev or not sv:
        return None

    start = ts(ev[0])
    marks: list[tuple[str, datetime]] = []

    task_done = [e for e in ev if e.get("event_type") == "task_complete"]
    for i, e in enumerate(task_done, 1):
        marks.append((f"task {i}", ts(e)))

    seen = {s["page"]: ts(s) for s in sv if s.get("page") in SURVEY_ORDER}
    for page in SURVEY_ORDER:
        if page in seen:
            marks.append((page, seen[page]))

    if not marks or "checks" not in seen:
        return None   # run never finished; timing it would understate the real length

    marks.sort(key=lambda m: m[1])
    out: dict[str, float] = {}
    prev = start
    for name, when in marks:
        out[name] = (when - prev).total_seconds()
        prev = when
    out["TOTAL"] = (marks[-1][1] - start).total_seconds()
    return out


def main() -> int:
    events = read_jsonl(DATA_DIR / "experiment_log.jsonl")
    survey = read_jsonl(DATA_DIR / "survey_responses.jsonl")

    if not survey:
        print(f"No questionnaire records under {DATA_DIR}. Nothing to time yet.")
        return 1

    pids = sorted({s.get("participant_id") for s in survey if s.get("participant_id")})
    runs = {}
    for pid in pids:
        p = phases_for(pid, events, survey)
        if p:
            runs[pid] = p

    partial = len(pids) - len(runs)
    if not runs:
        print(f"{partial} participant(s) found, none finished. No complete run to time.")
        return 1

    print(f"Complete runs: {len(runs)}" + (f"   (unfinished, excluded: {partial})" if partial else ""))
    print()

    names = list(next(iter(runs.values())).keys())
    width = max(len(n) for n in names)

    print(f"{'phase'.ljust(width)}   median      range")
    print("-" * (width + 26))
    for name in names:
        vals = [r[name] for r in runs.values() if name in r]
        if not vals:
            continue
        med = statistics.median(vals)
        line = f"{name.ljust(width)}   {med:6.0f}s"
        if len(vals) > 1:
            line += f"    {min(vals):.0f}–{max(vals):.0f}s"
        if name == "TOTAL":
            print("-" * (width + 26))
        print(line)

    total_med = statistics.median(r["TOTAL"] for r in runs.values())
    minutes = total_med / 60
    estimate = max(1, round(minutes + 0.5))    # round up: undershooting costs more

    print()
    print(f"Median run: {minutes:.1f} min")
    print(f"Suggested Prolific estimate: {estimate} min")
    for rate in (9, 12, 16.80):
        per = rate * estimate / 60
        print(f"  at GBP {rate:>5.2f}/hr  ->  GBP {per:.2f} per participant"
              f"   |  45 people + 33.3% fee = GBP {per * 45 * 1.333:.2f}")
    if len(runs) < 5:
        print()
        print(f"Careful: {len(runs)} run(s) only. Treat this as a sighting shot, not the estimate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
