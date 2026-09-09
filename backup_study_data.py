"""
backup_study_data.py — pull the study's three data files to this machine.

Run it daily while data collection is live. The deployed app holds the only copy of
the assignment ledger, the event log and the questionnaire responses; a lost volume
or a mistaken redeploy would end the study with nothing to analyse and no way to
reconstruct it. Prolific submissions would still have to be paid.

    set STUDY_URL=https://hems-study.fly.dev
    set RESEARCHER_TOKEN=...
    python backup_study_data.py

Each run writes a timestamped file and never overwrites an earlier one: a backup that
overwrites is one bad run away from being no backup at all. If the server ever returns
a truncated dataset, yesterday's file is still there.

Exit codes: 0 written, 1 failed, 2 written but the server reported damaged lines.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

STUDY_URL = os.environ.get("STUDY_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("RESEARCHER_TOKEN", "")
OUT_DIR = Path(os.environ.get("BACKUP_DIR", str(Path(__file__).parent / "backups")))
TIMEOUT_S = 60


def main() -> int:
    if not TOKEN:
        print("RESEARCHER_TOKEN is not set — refusing to run.", file=sys.stderr)
        return 1

    url = f"{STUDY_URL}/api/export/all?token={TOKEN}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as e:
        print(f"Server refused the export: HTTP {e.code}", file=sys.stderr)
        return 1
    except Exception as e:                                  # noqa: BLE001
        print(f"Backup failed: {e}", file=sys.stderr)
        return 1

    files = payload.get("files", {})
    counts = {k: v.get("count", 0) for k, v in files.items()}
    damaged = {k: len(v.get("damaged", [])) for k, v in files.items() if v.get("damaged")}

    # An empty dataset is almost always a wrong URL or a fresh volume, not a real
    # result. Writing it would leave a file that looks like a successful backup.
    if sum(counts.values()) == 0:
        print(f"Export from {STUDY_URL} contained no rows at all — not writing a backup.", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"study-backup-{stamp}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {out}")
    print("  rows: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    if damaged:
        # Reported loudly rather than folded into the success message: damaged lines
        # mean data has already been lost on the server and needs looking at today.
        print("  DAMAGED LINES: " + ", ".join(f"{k}={v}" for k, v in damaged.items()), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
