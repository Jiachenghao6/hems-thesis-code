# HEMS Demo — Startup Guide

**Bachelor Thesis · Jiacheng Hao · TUM · 2026**

> Home Energy Management System with Trade-off Slider + A/B Explanation Experiment

---

## What this is

A full-stack demo implementing the system described in `SYSTEM_DESIGN_REQUIREMENTS.md`:

| Component | Technology | Status |
|-----------|-----------|--------|
| Backend API | Python FastAPI | ✅ ready |
| Price data | aWATTar DE (live) + 5 historical scenarios | ✅ ready |
| Scheduling optimizer | Weighted multi-objective (Cost / Green / Convenience) | ✅ ready |
| Frontend | React 19 + Vite 8 + TypeScript | ✅ ready |
| Group A explanation | Interactive causal NL (updates with slider) | ✅ ready |
| Group B explanation | Static SHAP feature-importance chart | ✅ ready |
| Experiment logging | JSONL file → `/api/log/export` | ✅ ready |

---

## Quick Start (2 terminals)

### Terminal 1 — Backend

```bash
cd D:\tehsis\hems-demo\backend

# Install dependencies (one-time)
pip install fastapi uvicorn httpx pydantic python-dotenv

# Start server
uvicorn main:app --reload --port 8000
```

Backend runs at: **http://localhost:8000**
API docs (auto-generated): **http://localhost:8000/docs**

### Terminal 2 — Frontend

```bash
cd D:\tehsis\hems-demo\frontend

# Install dependencies (one-time, already done)
npm install

# Start dev server
npm run dev
```

Frontend runs at: **http://localhost:5173**

---

## A/B Experiment URLs

| Condition | URL | Explanation type |
|-----------|-----|-----------------|
| **A** (interactive causal) | http://localhost:5173/?condition=A | Updates live with slider |
| **B** (static SHAP) | http://localhost:5173/?condition=B | Fixed at recommendation time |
| With Prolific participant ID | http://localhost:5173/?condition=A&pid=PROLIFIC_PID | Auto-logs participant |

---

## Price Scenarios

Select from the dropdown in the top-right corner:

| ID | Description | Historical reference |
|----|-------------|---------------------|
| **Live** | Real-time aWATTar Germany prices | Fetched fresh daily after 14:00 CET |
| **S1** | Extreme high-price day (peak 1,896 €/MWh) | Finland 2024-01-05 |
| **S2** | Negative-price day (floor −500 €/MWh) | Finland 2023-11-24 |
| **S3** | High-volatility day (swing >250 €/MWh) | Representative European |
| **S4** | Low stable day (all hours <50 €/MWh) | Representative European |
| **S5** | Duck-curve day (morning cheap, evening expensive) | Representative European |

---

## API Endpoints

```
GET  /health                   — server uptime check
GET  /api/scenarios            — list all scenario metadata
GET  /api/prices/{scenario}    — 24-hour price curve (scenario = live|S1–S5)
POST /api/recommend            — run optimizer + get explanations
POST /api/log                  — log experiment event (accept/reject/slider_move)
GET  /api/log/export           — download all logged events as JSON
```

### Example: POST /api/recommend

```json
{
  "cost": 80,
  "green": 10,
  "convenience": 10,
  "scenario": "S1",
  "condition": "A"
}
```

---

## Project Structure

```
hems-demo/
├── backend/
│   ├── main.py              ← FastAPI app + all endpoints
│   ├── price_service.py     ← aWATTar API + 5 scenario datasets
│   ├── optimizer.py         ← weighted multi-objective scheduler
│   ├── explainer.py         ← causal NL (Group A) + SHAP mock (Group B)
│   ├── requirements.txt
│   └── experiment_log.jsonl ← created automatically on first log event
│
└── frontend/
    ├── src/
    │   ├── App.tsx                        ← main app, A/B routing
    │   ├── types.ts                       ← TypeScript interfaces
    │   ├── api.ts                         ← fetch wrappers
    │   └── components/
    │       ├── PriceCurve.tsx             ← custom SVG 24-hour price chart
    │       ├── TradeoffSlider.tsx         ← Cost / Green / Convenience sliders
    │       ├── RecommendationCard.tsx     ← appliance card + accept/reject
    │       ├── ShapChart.tsx              ← Group B static SHAP bar chart
    │       └── (causal explanation is inline in RecommendationCard)
    ├── index.html
    ├── package.json
    └── vite.config.ts                     ← dev proxy to localhost:8000
```

---

## Appliances simulated

| Appliance | Duration | Default time | Reason |
|-----------|----------|-------------|--------|
| 🍽️ Dishwasher | 2h | 20:00 | after dinner |
| 🧺 Washing Machine | 2h | 10:00 | mid-morning |
| 🚿 Water Heater | 1h | 06:00 | before shower |
| 🔋 EV Charger | 4h | 22:00 | overnight |

---

## Experiment data export

After running sessions, export all logged events:

```bash
curl http://localhost:8000/api/log/export > experiment_data.json
```

Or open http://localhost:8000/api/log/export in the browser.

Each event contains: `participant_id`, `condition` (A/B), `event_type`, `appliance_id`, `slider_values`, `scenario`, `timestamp`.

---

## Next steps (post-demo development)

1. **ENTSO-E integration** — once token arrives, replace aWATTar in `price_service.py` with ENTSO-E Finland/Norway data
2. **Prolific integration** — pass `?pid={{%PROLIFIC_PID%}}` in the study URL
3. **NASA-TLX questionnaire** — embed post-task survey (can use Qualtrics iframe or in-app form)
4. **Ethics / consent screen** — add landing page before experiment starts
5. **Randomisation** — server-side random condition assignment keyed by `pid`
