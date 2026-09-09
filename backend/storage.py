"""
storage.py — where the study's data files live.

The three JSONL files (assignment ledger, event log, questionnaire responses) were
written next to the source code, which is correct on a laptop and wrong in a
container: a container's own filesystem is thrown away on every restart and every
redeploy. Data collected on Tuesday would disappear when a fix is deployed on
Wednesday, and nothing would announce that it had.

So the directory is configuration. `DATA_DIR` points at a mounted volume in
deployment and defaults to the backend folder locally, which keeps existing local
files exactly where they are.

**Single writer.** All three files assume one process appends to them. Running two
instances behind a load balancer would give each its own view of the assignment
ledger, and block randomisation — which works by counting the rows written so far —
would silently stop balancing the groups. Whatever this is deployed on must be
pinned to one instance with no autoscaling.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent)))


def data_file(name: str) -> Path:
    """Return the path for a data file, creating the directory if necessary."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / name
