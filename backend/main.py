"""
main.py — HEMS Demo API
FastAPI backend serving:
  GET  /api/prices/{scenario}   — fetch 24-hour price curve
  POST /api/recommend           — run optimizer + generate explanation
  POST /api/log                 — write experiment event to JSONL file
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

# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="HEMS Demo API",
    description="Home Energy Management System — A/B experiment backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict to localhost in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE = Path(__file__).parent / "experiment_log.jsonl"


# ── Request / Response models ─────────────────────────────────────────────────

class RecommendRequest(BaseModel):
    cost: float = Field(default=33.0, ge=0, le=100, description="Cost slider value 0–100")
    green: float = Field(default=33.0, ge=0, le=100, description="Green slider value 0–100")
    convenience: float = Field(default=34.0, ge=0, le=100, description="Convenience slider value 0–100")
    scenario: str = Field(default="live", description="Price scenario: live | S1 | S2 | S3 | S4 | S5")
    condition: str = Field(default="A", description="Experiment condition: A (causal) | B (SHAP)")


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
async def export_log():
    """Return all logged events as a JSON array (for experiment download)."""
    if not LOG_FILE.exists():
        return {"events": []}
    events = []
    with LOG_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return {"count": len(events), "events": events}
