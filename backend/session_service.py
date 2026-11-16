"""
session_service.py — participant assignment and task sequence

Why this exists (supervisor feedback 2026-06-16, "conditions ... directly comparable"):
Previously the condition came from the frontend URL parameter ?condition=A, defaulting to A. Two problems:
assignment was not random and group sizes were unbalanced; participants could also see and change the parameter.

Assignment uses **block randomisation** rather than simple randomisation: with n=40, simple
randomisation has a real chance of imbalances like 24:16, which directly reduces statistical power. Block randomisation
guarantees equal groups within each block while keeping the order within a block random.

The ledger is append-only: each assignment writes one line, and counts are rebuilt from the ledger after a restart,
so a restart neither double-counts assigned participants nor loses the balance state.
"""
from __future__ import annotations

import json
import os
import random
import secrets
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from storage import data_file

ASSIGNMENT_LOG = data_file("assignments.jsonl")

CONDITIONS = ("A", "B")

# Left/right order of the response options, counterbalanced orthogonally to condition.
#
# Why counterbalance: Accept fixed on the left gives a slight primacy advantage, and acceptance rate is
# the main dependent variable. A fixed order would **not** confound the between-group comparison (it is the same
# constant for both groups and only shifts the absolute level). Counterbalancing does not make the position effect testable
# (10 per cell has no power), but it spreads the position effect instead of letting it accumulate systematically,
# and "the order was counterbalanced" is a complete answer.
#
# **Constant within a participant**: the same order for all three scenarios and four appliances. Changing it per card
# would make the interface feel jumpy and draw attention from content to layout.
OPTION_ORDERS = ("accept_first", "reject_first")

# One slot per cell, so the block size stays 4: A/left, A/right, B/left, B/right.
# n=40 -> 10 blocks -> exactly 20 A / 20 B, with 10 left / 10 right within each condition.
CELLS = tuple((c, o) for c in CONDITIONS for o in OPTION_ORDERS)
BLOCK_SIZE = len(CELLS)

# Fixed task sequence, identical in both conditions.
#
# Why fixed instead of letting participants choose: the frontend used to have a free dropdown including `live`
# (real prices of the current day). Different participants would see different price curves, and people on another day
# would see yet others, so group differences could not be attributed to the explanation. The sequence is fixed and excludes live.
#
# Why one order for everyone instead of a Latin square: order effects are then the **same** constant for both groups
# and do not confound the comparison; splitting n=40 across several orders would leave cells too small. The cost is that
# the order effect itself cannot be estimated (noted in the thesis limitations).
TASK_SEQUENCE = ["S3", "S1", "S2"]

_lock = Lock()


def _ensure_trailing_newline() -> None:
    """
    Make sure the ledger ends with a newline before appending.

    If a previous write was interrupted and left a partial line (no trailing newline), appending would join the new record
    to the partial line, producing one invalid JSON line that is skipped on parsing, so **the participant is assigned but
    not recorded** and the block balance drifts. Reproduced in simulation: 40 assignments, only 39 recorded.
    """
    if not ASSIGNMENT_LOG.exists():
        return
    try:
        with ASSIGNMENT_LOG.open("rb") as fh:
            if fh.seek(0, 2) == 0:          # empty file
                return
            fh.seek(-1, 2)
            if fh.read(1) == b"\n":
                return
    except OSError:
        return
    with ASSIGNMENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write("\n")


def _read_counts() -> dict[str, int]:
    """Rebuild per-condition counts from the append-only ledger. Missing file = all zero."""
    counts = {c: 0 for c in CONDITIONS}
    if not ASSIGNMENT_LOG.exists():
        return counts
    with ASSIGNMENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # skip partial lines (interrupted writes) so they do not corrupt the counts
                continue
            c = rec.get("condition")
            if c in counts:
                counts[c] += 1
    return counts


def _read_cell_counts() -> dict[tuple[str, str], int]:
    """Count ledger entries by (condition, option order).

    Records before 2026-09-12 have no option_order field; under the implementation at the time they were all
    Accept-left, so they are filled in as accept_first rather than dropped; dropping them would restart the block quota
    from the wrong base.
    """
    counts: dict[tuple[str, str], int] = {c: 0 for c in CELLS}
    if not ASSIGNMENT_LOG.exists():
        return counts
    with ASSIGNMENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cell = (rec.get("condition"), rec.get("option_order", "accept_first"))
            if cell in counts:
                counts[cell] += 1
    return counts


def _next_cell(cell_counts: dict[tuple[str, str], int]) -> tuple[str, str]:
    """
    Block randomisation: within the current block, pick one of the cells that are not yet full at random.
    A cell = (condition, option order); when a block is full, the next block starts automatically.
    """
    total = sum(cell_counts.values())
    filled_blocks = total // BLOCK_SIZE
    quota = filled_blocks + 1              # each cell has one slot per block

    available = [c for c in CELLS if cell_counts.get(c, 0) < quota]
    if not available:                      # should not happen; fall back to simple randomisation instead of failing silently
        available = list(CELLS)
    return random.choice(available)


def _pilot_cell(n_assigned: int) -> tuple[str, str] | None:
    """
    For the qualitative interviews only: assign the n-th person the cell given by PILOT_CELL_SEQUENCE, then fall back to block randomisation.

    Format "A:accept_first,B:accept_first,...". Only set by start-pilot.ps1 (separate DATA_DIR);
    the main study deployment never sets it, so the main assignment path is unaffected.

    Why: interviews n=6, 3 per group. With block size 4, the second block uses only two cells,
    with a 1/3 chance that both are the same condition (4:2). Choosing per person is worse, since the researcher might choose by
    "this person can read charts". A fixed sequence avoids both. It only decides who sees which version, not what anyone sees.
    """
    raw = os.environ.get("PILOT_CELL_SEQUENCE", "").strip()
    if not raw:
        return None
    seq = []
    for part in raw.split(","):
        cond, _, order = part.strip().partition(":")
        if cond not in CONDITIONS or order not in OPTION_ORDERS:
            raise ValueError(f"PILOT_CELL_SEQUENCE: bad entry {part!r}")
        seq.append((cond, order))
    return seq[n_assigned] if n_assigned < len(seq) else None


def _find_existing(prolific_pid: str) -> dict | None:
    """Return the existing assignment for an already assigned Prolific ID. See the idempotency note in assign_session."""
    if not prolific_pid or not ASSIGNMENT_LOG.exists():
        return None
    found = None
    with ASSIGNMENT_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("prolific_pid") == prolific_pid:
                found = rec          # only one record should exist; fall back to the last one
                break
    return found


def assign_session(prolific_pid: str | None = None) -> dict:
    """
    Assign a participant session. Returns participant_id / condition / option_order / task_sequence.

    **Idempotent**: a repeated request with the same Prolific ID returns the original assignment. Two reasons:
    first, otherwise a page refresh would switch the group, exposing the participant to both conditions and ruining their data;
    second, writing a ledger line per request would inflate counts and break the block balance. In testing, React strict mode
    called effects twice in development, so one page load produced two records.

    participant_id does not use the Prolific ID as key: the Prolific ID can be traced back to
    a person, so the experiment log stores only our own anonymous id; the Prolific ID is stored separately
    in the assignment ledger for payment, and the two are kept apart.
    """
    with _lock:
        if prolific_pid:
            existing = _find_existing(prolific_pid)
            if existing:
                return {
                    "participant_id": existing["participant_id"],
                    "condition": existing["condition"],
                    # old records lack this field; fill in accept_first as implemented at the time.
                    "option_order": existing.get("option_order", "accept_first"),
                    "task_sequence": list(TASK_SEQUENCE),
                }

        cell_counts = _read_cell_counts()
        condition, option_order = (_pilot_cell(sum(cell_counts.values()))
                                   or _next_cell(cell_counts))
        participant_id = "p_" + secrets.token_hex(6)

        record = {
            "participant_id": participant_id,
            "condition": condition,
            "option_order": option_order,
            "prolific_pid": prolific_pid or "",
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "seq": sum(cell_counts.values()) + 1,
        }
        _ensure_trailing_newline()
        with ASSIGNMENT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()          # flush immediately: an assignment without a ledger entry causes permanent imbalance

    return {
        "participant_id": participant_id,
        "condition": condition,
        "option_order": option_order,
        "task_sequence": list(TASK_SEQUENCE),
    }


def assignment_summary() -> dict:
    """Assignment progress for the researcher; not exposed to participants."""
    counts = _read_counts()
    cells = _read_cell_counts()
    return {
        "counts": counts,
        "cells": {f"{c}/{o}": n for (c, o), n in sorted(cells.items())},
        "total": sum(counts.values()),
        "block_size": BLOCK_SIZE,
    }
