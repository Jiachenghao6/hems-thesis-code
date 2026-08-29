"""
price_service.py
Fetches day-ahead electricity prices.

Primary source:  ENTSO-E Transparency Platform REST API
                 Token: read at runtime from ENTSOE_TOKEN (env var, else
                 the ENTSOE_TOKEN= line in D:/Claude/.env). Never hard-coded.
                 Access granted: 2026-05-15
Fallback 1:      aWATTar DE API (free, no key required)
Fallback 2:      Five hard-coded historical/synthetic scenario datasets
"""

import os

import httpx
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

# ── API config ──────────────────────────────────────────────────────────────
# ENTSO-E token is never hard-coded. It is read at import time from the
# ENTSOE_TOKEN environment variable, else from the ENTSOE_TOKEN= line in
# D:\Claude\.env (same convention as scripts/notion.py; no dotenv dependency).
ENV_PATH = r"D:\Claude\.env"


def _load_entsoe_token() -> str:
    """Return the ENTSO-E token, or "" if it is not configured.

    Returning "" rather than exiting is deliberate: an unauthenticated request
    fails, and fetch_live_prices() / fetch_live_renewable() then fall through to
    aWATTar and the scenario datasets. A missing token degrades the demo, it
    does not crash the backend.
    """
    token = os.environ.get("ENTSOE_TOKEN", "").strip()
    if token:
        return token
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                if line.startswith("ENTSOE_TOKEN="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


ENTSOE_TOKEN = _load_entsoe_token()
ENTSOE_BASE  = "https://web-api.tp.entsoe.eu/api"
AWATTAR_URL  = "https://api.awattar.de/v1/marketdata"

# EIC bidding zone codes
ENTSOE_ZONES = {
    "FI":    "10YFI-1--------U",   # Finland — primary for thesis
    "NO_2":  "10YNO-2--------T",   # Norway NO2
    "NO_1":  "10YNO-1--------2",   # Norway NO1
    "DE_LU": "10Y1001A1001A82H",   # Germany-Luxembourg
}
DEFAULT_ZONE = "FI"   # Finland — main market for the thesis

ENTSOE_NS = {"ns": "urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"}


def _make_hour_list(raw_prices: list[float]) -> list[dict]:
    """Convert a list of 24 price values (€/MWh) into the standard format."""
    return [
        {
            "hour": h,
            "price_eur_mwh": round(raw_prices[h], 2),
            "price_eur_kwh": round(raw_prices[h] / 1000, 5),
        }
        for h in range(24)
    ]


# ── Five experimental price scenarios ──────────────────────────────────────

# S1: 2024-01-05 Finland — extreme cold-snap high prices
# Based on Nord Pool official data (Haakana et al., 2025; IET GTD)
S1_PRICES = [
    312, 280, 258, 241, 230, 245,     # 00-05
    390, 620, 895, 780, 560, 440,     # 06-11
    380, 320, 290, 310, 490, 720,     # 12-17
    1240, 1896, 1450, 980, 620, 410,  # 18-23
]

# S2: 2023-11-24 Finland — prolonged negative prices
# Based on Nord Pool official data (Haakana et al., 2025; IET GTD)
S2_PRICES = [
    -320, -480, -500, -500, -490, -450,   # 00-05
    -380, -260, -140,  -60,   10,   40,   # 06-11
      55,   60,   48,   30,   25,   60,   # 12-17
     110,  140,  120,   95,   75,   40,   # 18-23
]

# S3: High-volatility day
S3_PRICES = [
     42,  38,  30,  28,  25,  30,
     55,  90, 145, 190, 210, 180,
    160, 130,  95,  80,  85, 140,
    255, 290, 270, 230, 170, 110,
]

# S4: Low stable day
S4_PRICES = [
     22, 18, 15, 13, 12, 14,
     20, 28, 34, 38, 40, 42,
     45, 47, 48, 45, 42, 40,
     38, 35, 32, 30, 27, 24,
]

# S5: Duck-curve day
S5_PRICES = [
     30,  25,  22,  20,  22,  25,
     32,  40,  50,  58,  62,  68,
     80,  95, 115, 135, 155, 180,
    200, 195, 175, 150, 120,  85,
]

SCENARIOS = {
    "S1": _make_hour_list(S1_PRICES),
    "S2": _make_hour_list(S2_PRICES),
    "S3": _make_hour_list(S3_PRICES),
    "S4": _make_hour_list(S4_PRICES),
    "S5": _make_hour_list(S5_PRICES),
}

SCENARIO_META = {
    "S1": {
        "label": "Extreme High-Price Day",
        "description": "Cold-snap demand surge. Prices peak at 1,896 €/MWh (Finland 2024-01-05; Haakana et al., 2025).",
        "date_ref": "2024-01-05 Finland",
    },
    "S2": {
        "label": "Negative-Price Day",
        "description": "Wind energy surplus. Prices reach −500 €/MWh for six hours (Finland 2023-11-24; Haakana et al., 2025).",
        "date_ref": "2023-11-24 Finland",
    },
    "S3": {
        "label": "High-Volatility Day",
        "description": "Intra-day swing > 250 €/MWh — typical mid-season European day-ahead market.",
        "date_ref": "Synthetic (representative)",
    },
    "S4": {
        "label": "Low Stable Day",
        "description": "Mild demand and high renewable share — prices stay below 50 €/MWh all day.",
        "date_ref": "Synthetic (representative)",
    },
    "S5": {
        "label": "Price-Transition Day",
        "description": "Cheap morning, expensive evening — classic solar-heavy 'duck curve'.",
        "date_ref": "Synthetic (representative)",
    },
}


def get_scenario_prices(scenario_id: str) -> list[dict]:
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_id}'. Valid: {list(SCENARIOS.keys())}")
    return SCENARIOS[scenario_id]


# ── ENTSO-E live fetcher ─────────────────────────────────────────────────────

def _parse_entsoe_xml(xml_text: str) -> list[dict]:
    """Parse ENTSO-E Publication Document XML → 24-hour price list."""
    root  = ET.fromstring(xml_text)
    prices: dict[int, float] = {}

    for ts in root.findall(".//ns:TimeSeries", ENTSOE_NS):
        period = ts.find("ns:Period", ENTSOE_NS)
        if period is None:
            continue
        for pt in period.findall("ns:Point", ENTSOE_NS):
            pos  = pt.find("ns:position", ENTSOE_NS)
            pval = pt.find("ns:price.amount", ENTSOE_NS)
            if pos is None or pval is None:
                continue
            hour = int(pos.text) - 1   # ENTSO-E positions are 1-based
            prices[hour] = float(pval.text)

    if len(prices) < 24:
        raise ValueError(f"ENTSO-E XML contained only {len(prices)} price points (expected 24)")

    raw = [prices[h] for h in range(24)]
    return _make_hour_list(raw)


async def _fetch_entsoe(zone: str = DEFAULT_ZONE) -> list[dict]:
    """Fetch today's day-ahead prices from ENTSO-E Transparency Platform."""
    now = datetime.now(timezone.utc)
    # Request window: yesterday 23:00 UTC → tomorrow 23:00 UTC to ensure full day coverage
    period_start = (now - timedelta(days=1)).strftime("%Y%m%d2300")
    period_end   = (now + timedelta(days=1)).strftime("%Y%m%d2300")
    eic = ENTSOE_ZONES.get(zone, ENTSOE_ZONES[DEFAULT_ZONE])

    params = {
        "securityToken": ENTSOE_TOKEN,
        "documentType": "A44",          # Day-ahead prices
        "in_Domain":  eic,
        "out_Domain": eic,
        "periodStart": period_start,
        "periodEnd":   period_end,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(ENTSOE_BASE, params=params)
        resp.raise_for_status()
    return _parse_entsoe_xml(resp.text)


async def _fetch_awattar() -> list[dict]:
    """Fallback: fetch today's prices from aWATTar DE API (free, no key)."""
    now = datetime.now(timezone.utc)
    start_ts = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) * 1000
    end_ts   = start_ts + 86_400_000  # +24 h in ms

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(AWATTAR_URL, params={"start": start_ts, "end": end_ts})
        resp.raise_for_status()
    data = resp.json().get("data", [])
    if len(data) < 24:
        raise ValueError(f"aWATTar returned only {len(data)} price points")

    raw = [entry["marketprice"] for entry in sorted(data, key=lambda e: e["start_timestamp"])[:24]]
    return _make_hour_list(raw)


async def fetch_live_prices() -> list[dict]:
    """
    Try ENTSO-E → aWATTar → raise.
    Returns the standard 24-element list[dict] format.
    """
    try:
        return await _fetch_entsoe()
    except Exception:
        pass
    try:
        return await _fetch_awattar()
    except Exception:
        pass
    raise RuntimeError("All live price sources failed. Use a scenario (S1–S5) instead.")

# ── Renewable energy share data ─────────────────────────────────────────────
#
# Each scenario gets a 24-value renewable share profile (0.0–1.0) that is
# narratively consistent with the price scenario it accompanies.
#
# Source basis:
#   S1 (2024-01-05, cold-snap high prices):
#     Finland in deep winter — hydro + nuclear base, limited wind on a cold-snap
#     day. Demand spikes lower the renewable *share* even if absolute output is
#     similar. Peaks during overnight hours when hydro dominates.
#   S2 (2023-11-24, negative prices):
#     Negative prices were directly caused by wind surplus (Haakana et al., 2025).
#     Renewable share peaks 00-05 (wind storm overnight) — mirrors the -500 €/MWh
#     trough. Falls as demand rises mid-morning and wind eases.
#   S3 (high volatility, synthetic):
#     Mixed day — moderate wind with a midday solar bump.
#   S4 (low stable, synthetic — "high renewable share" explicitly):
#     High renewable throughout; broad solar plateau 09-16; scenario description
#     says "high renewable share" so all hours ≥ 55%.
#   S5 (duck curve, synthetic — solar-heavy):
#     Solar dominates 09-15, giving a pronounced midday green peak. Matches the
#     "cheap morning, expensive evening" price pattern.

def _make_renewable_list(raw_shares: list[float]) -> list[dict]:
    """Convert 24 renewable share values (0.0–1.0) into standard format."""
    return [
        {"hour": h, "renewable_share": round(raw_shares[h], 3)}
        for h in range(24)
    ]


# S1: cold-snap — moderate hydro/nuclear, low renewable share during demand peaks
S1_RENEWABLE = [
    0.52, 0.54, 0.55, 0.55, 0.53, 0.50,   # 00-05: hydro/nuclear base overnight
    0.42, 0.35, 0.30, 0.32, 0.34, 0.36,   # 06-11: demand surge, share drops
    0.37, 0.38, 0.37, 0.35, 0.30, 0.26,   # 12-17: still high demand
    0.22, 0.20, 0.24, 0.28, 0.33, 0.40,   # 18-23: evening peak, then recovery
]

# S2: wind surplus caused negative prices — very high renewable share early hours
S2_RENEWABLE = [
    0.88, 0.91, 0.93, 0.94, 0.93, 0.91,   # 00-05: storm wind, prices -500 €/MWh
    0.87, 0.82, 0.76, 0.70, 0.65, 0.62,   # 06-11: wind eases, demand rises
    0.60, 0.59, 0.60, 0.62, 0.63, 0.62,   # 12-17: stable afternoon
    0.60, 0.58, 0.60, 0.63, 0.67, 0.72,   # 18-23: slight wind pickup overnight
]

# S3: high volatility — moderate wind, small solar bump midday
S3_RENEWABLE = [
    0.38, 0.37, 0.36, 0.35, 0.35, 0.37,   # 00-05
    0.40, 0.44, 0.50, 0.57, 0.62, 0.60,   # 06-11: solar ramp
    0.57, 0.54, 0.52, 0.50, 0.46, 0.41,   # 12-17: solar fade
    0.36, 0.33, 0.32, 0.34, 0.36, 0.37,   # 18-23
]

# S4: low stable — "mild demand and high renewable share" (scenario description)
S4_RENEWABLE = [
    0.62, 0.60, 0.58, 0.57, 0.58, 0.61,   # 00-05: wind base
    0.65, 0.71, 0.77, 0.83, 0.87, 0.89,   # 06-11: solar + wind climb
    0.90, 0.91, 0.90, 0.88, 0.85, 0.80,   # 12-17: solar plateau
    0.75, 0.70, 0.67, 0.65, 0.63, 0.62,   # 18-23: wind remains
]

# S5: duck curve / solar-heavy — midday green spike, low morning & evening
S5_RENEWABLE = [
    0.32, 0.30, 0.28, 0.27, 0.28, 0.31,   # 00-05: wind overnight
    0.36, 0.44, 0.55, 0.66, 0.76, 0.84,   # 06-11: solar ramp
    0.89, 0.91, 0.89, 0.82, 0.70, 0.55,   # 12-17: solar peak then fade
    0.42, 0.35, 0.32, 0.30, 0.29, 0.30,   # 18-23: back to wind base
]

RENEWABLE_SCENARIOS: dict[str, list[dict]] = {
    "S1": _make_renewable_list(S1_RENEWABLE),
    "S2": _make_renewable_list(S2_RENEWABLE),
    "S3": _make_renewable_list(S3_RENEWABLE),
    "S4": _make_renewable_list(S4_RENEWABLE),
    "S5": _make_renewable_list(S5_RENEWABLE),
}

# Fallback profile used when live ENTSO-E generation data is unavailable.
# Representative Nordic day: steady wind base + modest solar 09-15.
_FALLBACK_RENEWABLE = [
    0.48, 0.47, 0.46, 0.45, 0.46, 0.48,   # 00-05
    0.51, 0.55, 0.60, 0.66, 0.70, 0.72,   # 06-11
    0.73, 0.74, 0.72, 0.68, 0.63, 0.57,   # 12-17
    0.52, 0.49, 0.48, 0.47, 0.47, 0.48,   # 18-23
]
_FALLBACK_RENEWABLE_LIST = _make_renewable_list(_FALLBACK_RENEWABLE)


def get_scenario_renewable(scenario_id: str) -> list[dict]:
    """Return 24-hour renewable share list for the given scenario."""
    if scenario_id not in RENEWABLE_SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_id}'. Valid: {list(RENEWABLE_SCENARIOS.keys())}")
    return RENEWABLE_SCENARIOS[scenario_id]


# ── ENTSO-E Generation (A75) live fetcher ────────────────────────────────────

# PSR types counted as renewable for the share calculation.
# Includes wind (onshore + offshore), solar, hydro run-of-river,
# hydro reservoir, and other renewables.
_RENEWABLE_PSR = {"B11", "B12", "B15", "B16", "B18", "B19"}

# Namespace used by GL_MarketDocument (A75); detected dynamically below.
_GENERATION_NS_URI = "urn:iec62325.351:tc57wg16:451-6:generationdocument:3:0"
_GENERATION_NS = {"ns": _GENERATION_NS_URI}


def _parse_generation_xml(xml_text: str) -> list[dict]:
    """
    Parse ENTSO-E A75 GL_MarketDocument XML into a 24-hour renewable share list.

    The document contains one TimeSeries per production type (psrType).
    We accumulate MW output per hour, then compute:
        renewable_share[h] = sum(renewable_types[h]) / sum(all_types[h])
    """
    root = ET.fromstring(xml_text)

    # Use wildcard namespace matching (Python ≥ 3.8) so we're resilient to
    # minor version differences in the ENTSO-E schema.
    hourly_total: dict[int, float] = {}
    hourly_renew: dict[int, float] = {}

    for ts in root.iter("{*}TimeSeries"):
        psr_elem = ts.find(".//{*}psrType")
        if psr_elem is None:
            continue
        psr_type = (psr_elem.text or "").strip()
        is_renewable = psr_type in _RENEWABLE_PSR

        period = ts.find("{*}Period")
        if period is None:
            continue

        for pt in period.findall("{*}Point"):
            pos_elem = pt.find("{*}position")
            qty_elem = pt.find("{*}quantity")
            if pos_elem is None or qty_elem is None:
                continue
            try:
                hour = int(pos_elem.text) - 1   # ENTSO-E is 1-based
                mw   = float(qty_elem.text)
            except (ValueError, TypeError):
                continue

            hourly_total[hour] = hourly_total.get(hour, 0.0) + mw
            if is_renewable:
                hourly_renew[hour] = hourly_renew.get(hour, 0.0) + mw

    if len(hourly_total) < 20:
        raise ValueError(
            f"ENTSO-E generation XML contained only {len(hourly_total)} hours (expected 24)"
        )

    shares: list[float] = []
    for h in range(24):
        total  = hourly_total.get(h, 0.0)
        renew  = hourly_renew.get(h, 0.0)
        share  = (renew / total) if total > 0 else _FALLBACK_RENEWABLE[h]
        shares.append(min(max(share, 0.0), 1.0))   # clamp to [0, 1]

    return _make_renewable_list(shares)


async def _fetch_entsoe_renewable(zone: str = DEFAULT_ZONE) -> list[dict]:
    """
    Fetch today's actual generation per production type from ENTSO-E (A75).
    Returns a 24-hour renewable share list.
    """
    now          = datetime.now(timezone.utc)
    period_start = (now - timedelta(days=1)).strftime("%Y%m%d2300")
    period_end   = now.strftime("%Y%m%d2300")
    eic          = ENTSOE_ZONES.get(zone, ENTSOE_ZONES[DEFAULT_ZONE])

    params = {
        "securityToken": ENTSOE_TOKEN,
        "documentType":  "A75",   # Actual generation per production type
        "processType":   "A16",   # Realised
        "in_Domain":     eic,
        "periodStart":   period_start,
        "periodEnd":     period_end,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(ENTSOE_BASE, params=params)
        resp.raise_for_status()
    return _parse_generation_xml(resp.text)


async def fetch_live_renewable() -> list[dict]:
    """
    Try ENTSO-E A75 → fallback to representative Nordic profile.
    Always returns a valid 24-element list[dict] with 'renewable_share'.
    Never raises — the fallback guarantees a usable result.
    """
    try:
        return await _fetch_entsoe_renewable()
    except Exception:
        pass
    # Fallback: static representative Nordic profile
    return _FALLBACK_RENEWABLE_LIST
