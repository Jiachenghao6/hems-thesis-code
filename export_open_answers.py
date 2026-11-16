"""
export_open_answers.py — export the free-text answers for blind coding.

    python export_open_answers.py backups/study-backup-20260930T200006Z.json OUT_DIR

Writes two files:
  open_answers_blind.md  answers in a fixed random order under codes R01..Rnn, no condition
  open_answers_KEY.md    code -> condition, plus the closed-question counts by condition.
                         Open this only after every answer has been coded.

Uses the analysed sample of ANALYSIS_PLAN.md §2 (completers who passed the attention check).
No Prolific IDs or participant ids are written.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

PAGES = {"demographics", "tlx", "tia_1", "tia_2", "checks"}
SEED = 20260930  # fixed, so the R-codes are reproducible


def main() -> int:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = json.loads(src.read_text(encoding="utf-8"))["files"]
    cond = {r["participant_id"]: r["condition"] for r in files["assignments"]["rows"]}
    pages: dict[str, dict] = defaultdict(dict)
    for row in sorted(files["survey"]["rows"], key=lambda r: r["timestamp"]):
        pages[row["participant_id"]][row["page"]] = row["answers"]
    sample = sorted(p for p in cond
                    if PAGES <= set(pages[p]) and str(pages[p]["checks"]["ac_instructed"]) == "2")
    random.Random(SEED).shuffle(sample)
    code = {p: f"R{i + 1:02d}" for i, p in enumerate(sample)}

    def clean(s: str) -> str:
        return " ".join(str(s).split()).replace("|", "/")

    blind = [
        "# Open answers - for blind coding",
        "",
        f"> {len(sample)} answers (analysis sample). Random order, no condition. **Do not open `open_answers_KEY.md` before all labels are coded.**",
        "> Question: *In one sentence: what made you trust — or not trust — the recommendations?*",
        "> Labels are short phrases; one answer can have several labels, separated by ';'. Answers are kept verbatim, spelling errors included.",
        "",
        "| ID | Answer | Labels |",
        "|---|---|---|",
    ]
    for p in sample:
        blind.append(f"| {code[p]} | {clean(pages[p]['checks']['open_trust'])} | |")
    others = [(code[p], pages[p]["checks"].get("why_decide_other", "")) for p in sample]
    others = [(c, t) for c, t in others if str(t).strip()]
    if others:
        blind += ["", "## Appendix: text entered under 'Something else' (why_decide)", "",
                  "| ID | Text | Labels |", "|---|---|---|"]
        blind += [f"| {c} | {clean(t)} | |" for c, t in others]

    key = ["# Key: ID -> condition (open only after all coding is complete)", "", "| ID | Condition |", "|---|---|"]
    key += [f"| {code[p]} | {cond[p]} |" for p in sorted(sample, key=lambda p: code[p])]
    for item in ("why_decide", "what_confused"):
        counts = {c: Counter(v for p in sample if cond[p] == c for v in pages[p]["checks"][item]) for c in "AB"}
        n = {c: sum(cond[p] == c for p in sample) for c in "AB"}
        key += ["", f"## Closed item `{item}` counts by condition (A n={n['A']}, B n={n['B']}; in multi-select items one person can count more than once)", "",
                "| Option | A | B |", "|---|---|---|"]
        for v in sorted(set(counts["A"]) | set(counts["B"])):
            key.append(f"| {v} | {counts['A'][v]} | {counts['B'][v]} |")

    out.mkdir(parents=True, exist_ok=True)
    (out / "open_answers_blind.md").write_text("\n".join(blind) + "\n", encoding="utf-8")
    (out / "open_answers_KEY.md").write_text("\n".join(key) + "\n", encoding="utf-8")
    print(f"{len(sample)} answers, {len(others)} 'something else' texts -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
