"""
main.py — HEMS Demo API
FastAPI backend serving:
  GET  /api/prices/{scenario}   — fetch 24-hour price curve
  POST /api/recommend           — run optimizer + generate explanation
  POST /api/log                 — write experiment event to JSONL file
  POST /api/session             — assign condition + task sequence (block randomised)
  GET  /api/session/summary     — researcher-only assignment progress
  POST /api/survey              — store one page of questionnaire answers
  GET  /api/survey/summary      — researcher-only questionnaire progress
  GET  /health                  — uptime check

Run with:
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from price_service import fetch_live_prices, get_scenario_prices, SCENARIO_META, fetch_live_renewable, get_scenario_renewable
from optimizer import optimize_schedule, APPLIANCES
from explainer import generate_causal_explanation, generate_shap_data
from session_service import assign_session, assignment_summary, TASK_SEQUENCE
from survey_service import record_page, survey_summary
from storage import data_file

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HEMS Demo API",
    description="Home Energy Management System — A/B experiment backend",
    version="0.1.0",
)

# Allowed browser origins. During local development the frontend is on :5173 and
# the backend on :8000, which are already different origins, so this cannot simply
# be switched off. In deployment the frontend is served from its own host, and that
# host has to be named here — set ALLOWED_ORIGINS to a comma-separated list.
#
# The previous `["*"]` was not just loose but wrong: the CORS specification forbids
# a wildcard origin together with credentials, and browsers reject the combination,
# so it only ever worked because nothing sent credentials yet.
_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", ",".join(_DEV_ORIGINS)).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,   # no cookies or auth headers are used; see note above
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

LOG_FILE = data_file("experiment_log.jsonl")

# ── Researcher-only endpoints ────────────────────────────────────────────────
#
# The export and summary endpoints return participant data. On localhost that was
# harmless; on a public host it would let anyone download the entire dataset, which
# is both a GDPR incident and a way for a participant to see the study design.
#
# RESEARCHER_TOKEN must be set in the deployment environment. If it is unset the
# endpoints refuse to answer at all rather than falling open — a missing secret is a
# deployment mistake, and the safe reading of a deployment mistake is "deny".
RESEARCHER_TOKEN = os.environ.get("RESEARCHER_TOKEN", "")


def _require_researcher(token: str | None) -> None:
    """Gate an endpoint on the researcher token passed as ?token= or X-Researcher-Token."""
    if not RESEARCHER_TOKEN:
        raise HTTPException(status_code=503, detail="Researcher access is not configured on this deployment")
    # Constant-time comparison: these endpoints are reachable from the open internet
    # and a length-dependent early exit leaks the token a character at a time.
    import hmac

    if not token or not hmac.compare_digest(token, RESEARCHER_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid researcher token")


# ── Request / Response models ─────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    cost: float = Field(default=33.0, ge=0, le=100, description="Cost slider value 0–100")
    green: float = Field(default=33.0, ge=0, le=100, description="Green slider value 0–100")
    convenience: float = Field(default=34.0, ge=0, le=100, description="Convenience slider value 0–100")
    scenario: str = Field(default="live", description="Price scenario: live | S1 | S2 | S3 | S4 | S5")
    condition: str = Field(default="A", description="Experiment condition: A (causal) | B (SHAP)")


class SessionRequest(BaseModel):
    prolific_pid: str = Field(default="", description="Prolific ID, stored only in the assignment ledger")


class SurveyRequest(BaseModel):
    participant_id: str = Field(..., description="Anonymous participant id from /api/session — never a Prolific ID")
    condition: str = Field(default="A", description="A or B")
    page: str = Field(..., description="demographics | tlx | tia_1 | tia_2 | checks")
    answers: dict = Field(..., description="Raw answers keyed by item id; never recoded here")


class LogEvent(BaseModel):
    participant_id: str = Field(default="anon", description="Prolific participant ID or 'anon'")
    condition: str = Field(default="A", description="A or B")
    event_type: str = Field(..., description="accept | reject | slider_move | scenario_change | page_load")
    appliance_id: str = Field(default="", description="Appliance affected (for accept/reject)")
    slider_values: dict = Field(default_factory=dict, description="Current slider state at event time")
    scenario: str = Field(default="live")
    timestamp: str = Field(default="", description="ISO-8601; auto-filled if empty")
    extra: dict = Field(default_factory=dict, description="Any additional metadata")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/session")
async def create_session(req: SessionRequest):
    """
    Assign one participant to a condition and return the fixed task sequence.

    Condition assignment moved server-side (supervisor feedback 2026-06-16): it was
    previously a URL parameter defaulting to A, which was neither random nor balanced
    and was visible to the participant. Assignment now uses block randomisation so the
    two groups stay equal in size as recruitment proceeds.

    The response deliberately does NOT describe what the condition means — the client
    only needs the letter to pick which explanation component to render.
    """
    return assign_session(req.prolific_pid or None)


@app.get("/api/session/summary")
async def session_summary(token: str | None = None):
    """Recruitment progress. Researcher-only — see _require_researcher."""
    _require_researcher(token)
    return {**assignment_summary(), "task_sequence": list(TASK_SEQUENCE)}


@app.get("/api/scenarios")
async def list_scenarios():
    """Return metadata for all available price scenarios."""
    return {
        "scenarios": [
            {"id": k, **v}
            for k, v in SCENARIO_META.items()
        ]
    }


@app.get("/api/prices/{scenario}")
async def get_prices(scenario: str = "live"):
    """
    Return 24 hourly price points for the requested scenario.
    scenario: 'live' fetches aWATTar DE; 'S1'–'S5' use historical datasets.
    """
    try:
        if scenario == "live":
            prices = await fetch_live_prices()
        else:
            prices = get_scenario_prices(scenario)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Fetch renewable share and merge into price points
    if scenario == "live":
        renewable = await fetch_live_renewable()
    else:
        renewable = get_scenario_renewable(scenario)
    for p, r in zip(prices, renewable):
        p["renewable_share"] = r["renewable_share"]

    return {
        "scenario": scenario,
        "source": "aWATTar DE" if scenario == "live" else "Historical dataset",
        "prices": prices,
        "summary": {
            "min_eur_mwh": min(p["price_eur_mwh"] for p in prices),
            "max_eur_mwh": max(p["price_eur_mwh"] for p in prices),
            "avg_eur_mwh": round(
                sum(p["price_eur_mwh"] for p in prices) / len(prices), 2
            ),
        },
    }


@app.post("/api/recommend")
async def get_recommendations(req: RecommendRequest):
    """
    Run the multi-objective optimizer and return scheduling recommendations.
    Each recommendation includes either a causal explanation (condition=A)
    or static SHAP feature-importance data (condition=B).
    """
    try:
        if req.scenario == "live":
            prices = await fetch_live_prices()
        else:
            prices = get_scenario_prices(req.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Fetch renewable share for the chosen scenario
    if req.scenario == "live":
        renewable = await fetch_live_renewable()
    else:
        renewable = get_scenario_renewable(req.scenario)

    raw_recs = optimize_schedule(
        prices=prices,
        appliances=APPLIANCES,
        cost_w=req.cost,
        green_w=req.green,
        convenience_w=req.convenience,
        renewable_shares=renewable,
    )

    # Attach explanation data appropriate for the condition
    normalised_w = raw_recs[0]["weights_used"] if raw_recs else {"cost": 1/3, "green": 1/3, "convenience": 1/3}

    output = []
    for rec in raw_recs:
        item = {k: v for k, v in rec.items() if k != "scores"}  # don't expose raw scores
        item["scores"] = rec["scores"]  # but do include for debugging

        if req.condition == "A":
            item["explanation"] = generate_causal_explanation(rec, normalised_w, prices)
            item["explanation_type"] = "causal_interactive"
        else:
            item["shap_data"] = generate_shap_data(rec, normalised_w)
            item["explanation_type"] = "static_shap"

        output.append(item)

    return {
        "condition": req.condition,
        "scenario": req.scenario,
        "weights": {
            "cost_raw": req.cost,
            "green_raw": req.green,
            "convenience_raw": req.convenience,
            "normalised": normalised_w,
        },
        "recommendations": output,
    }


@app.post("/api/survey")
async def submit_survey(req: SurveyRequest):
    """Store one page of questionnaire answers.

    Unlike /api/log this endpoint reports failures to the client. Event logging is
    best-effort telemetry; questionnaire responses are the study's dependent
    variables, and the frontend must not show a completion code for answers that
    were never written.
    """
    if not req.participant_id or req.participant_id in {"pending", "demo"}:
        # 'demo' is the free-exploration build and must never write study data.
        raise HTTPException(status_code=400, detail="A real participant id is required")
    try:
        record = record_page(req.participant_id, req.condition, req.page, req.answers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "stored", "page": record["page"], "timestamp": record["timestamp"]}


@app.get("/api/survey/summary")
async def get_survey_summary(token: str | None = None):
    """Researcher-only: how many participants have finished each questionnaire page."""
    _require_researcher(token)
    return survey_summary()


@app.post("/api/log")
async def log_event(event: LogEvent):
    """Append one experiment event to the JSONL log file."""
    event_dict = event.model_dump()
    if not event_dict["timestamp"]:
        event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event_dict, ensure_ascii=False) + "\n")

    return {"status": "logged", "timestamp": event_dict["timestamp"]}


@app.get("/api/log/export")
async def export_log(token: str | None = None):
    """Return all logged events as a JSON array (for experiment download).

    Researcher-only: this returns every participant's behavioural data.
    """
    _require_researcher(token)
    if not LOG_FILE.exists():
        return {"events": []}
    events = []
    with LOG_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return {"count": len(events), "events": events}


@app.get("/api/export/all")
async def export_all(token: str | None = None):
    """Researcher-only: every data file at once, for backups.

    Exists so that backing up the study does not require shell access to the host.
    A study that can only be backed up by remembering to run a platform-specific
    command will not be backed up, and these three files are the entire dataset —
    there is no second copy anywhere.

    Lines that fail to parse are returned in `damaged` rather than dropped: a backup
    that silently omits broken records would make the loss invisible until analysis.
    """
    _require_researcher(token)

    def read_jsonl(path: Path) -> tuple[list, list]:
        if not path.exists():
            return [], []
        rows, damaged = [], []
        with path.open(encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    damaged.append({"line": n, "raw": line[:300]})
        return rows, damaged

    from session_service import ASSIGNMENT_LOG
    from survey_service import SURVEY_FILE

    out: dict = {"exported_at": datetime.now(timezone.utc).isoformat(), "files": {}}
    for name, path in (
        ("assignments", ASSIGNMENT_LOG),
        ("events", LOG_FILE),
        ("survey", SURVEY_FILE),
    ):
        rows, damaged = read_jsonl(path)
        out["files"][name] = {"count": len(rows), "rows": rows, "damaged": damaged}
    return out


# ── Serving the frontend ─────────────────────────────────────────────────────
#
# In deployment the built frontend is served by this same app. That is not just
# convenience: same origin means the browser makes no cross-origin requests at all,
# so the CORS configuration above stops mattering in production and one misconfigured
# environment variable can no longer take the study offline. It also means one
# deployment, one URL, and one certificate to keep valid for the whole data collection
# period — a URL that changes mid-study invalidates the link already live on Prolific.
#
# Locally nothing changes: `npm run dev` serves the frontend on :5173 and this block
# does nothing because dist/ does not exist.

_DIST = Path(os.environ.get("FRONTEND_DIST", str(Path(__file__).parent.parent / "frontend" / "dist")))

if _DIST.is_dir():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        """Serve the single-page app, falling back to index.html for client routes.

        Registered last so it cannot shadow the /api and /health routes above.
        A real file is served if it exists (favicon and friends); anything else gets
        index.html, which is what a refresh on a deep link needs.
        """
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
