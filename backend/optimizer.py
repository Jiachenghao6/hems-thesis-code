"""
optimizer.py
Weighted multi-objective appliance scheduling algorithm.

Objective dimensions
--------------------
Cost        : minimise average electricity price in the assigned slot
Green       : maximise renewable energy share in the assigned slot
              (real data from ENTSO-E A75 generation mix, or scenario profiles)
Convenience : minimise deviation from the user's habitual run time

Weights are supplied at run-time by the Trade-off Slider and are normalised
internally so they always sum to 1.0 (supporting both the "three independent
sliders" and "ternary normalised" UI variants).
"""

from __future__ import annotations


# ── Appliance catalogue ─────────────────────────────────────────────────────

APPLIANCES: list[dict] = [
    {
        "id": "dishwasher",
        "name": "Dishwasher",
        "emoji": "🍽️",
        "duration_hours": 2,
        "default_start": 20,   # 20:00 after dinner
        "latest_finish": 24,   # must finish by midnight
        "typical_kwh_per_hour": 0.9,
    },
    {
        "id": "washing_machine",
        "name": "Washing Machine",
        "emoji": "🧺",
        "duration_hours": 2,
        "default_start": 10,   # mid-morning
        "latest_finish": 22,
        "typical_kwh_per_hour": 0.8,
    },
    {
        "id": "water_heater",
        "name": "Water Heater",
        "emoji": "🚿",
        "duration_hours": 1,
        "default_start": 6,    # before morning shower
        "latest_finish": 9,
        "typical_kwh_per_hour": 2.0,
    },
    {
        "id": "ev_charger",
        "name": "EV Charger",
        "emoji": "🔋",
        "duration_hours": 4,
        "default_start": 22,   # overnight charging
        "latest_finish": 24,
        "typical_kwh_per_hour": 7.2,
    },
]


# ── Core algorithm ──────────────────────────────────────────────────────────

def _normalise_weights(cost: float, green: float, convenience: float) -> dict:
    """Normalise slider values (0–100 each) to weights summing to 1.0."""
    total = cost + green + convenience
    if total == 0:
        return {"cost": 1 / 3, "green": 1 / 3, "convenience": 1 / 3}
    return {
        "cost": cost / total,
        "green": green / total,
        "convenience": convenience / total,
    }


def _slot_avg_price(prices: list[dict], start: int, duration: int) -> float:
    end = min(start + duration, 24)
    slot = prices[start:end]
    if not slot:
        return 0.0
    return sum(p["price_eur_mwh"] for p in slot) / len(slot)


def _slot_avg_renewable(renewable_shares: list[dict], start: int, duration: int) -> float:
    """Return average renewable share across a slot (0.0–1.0)."""
    end = min(start + duration, 24)
    slot = renewable_shares[start:end]
    if not slot:
        return 0.5
    return sum(r["renewable_share"] for r in slot) / len(slot)


def _price_range(prices: list[dict]) -> tuple[float, float]:
    vals = [p["price_eur_mwh"] for p in prices]
    lo, hi = min(vals), max(vals)
    return lo, hi if hi != lo else lo + 1.0   # avoid division by zero


def optimize_schedule(
    prices: list[dict],
    appliances: list[dict],
    cost_w: float,
    green_w: float,
    convenience_w: float,
    renewable_shares: list[dict] | None = None,
) -> list[dict]:
    """
    For each appliance, find the start hour that maximises the weighted score.

    Parameters
    ----------
    prices            : 24-hour list from price_service
    appliances        : appliance catalogue
    cost_w            : raw cost slider value (0–100)
    green_w           : raw green slider value (0–100)
    convenience_w     : raw convenience slider value (0–100)
    renewable_shares  : 24-hour list of {"hour": h, "renewable_share": float}.
                        If None, falls back to the cost-proxy heuristic.

    Returns a list of recommendation dicts, one per appliance.
    """
    weights = _normalise_weights(cost_w, green_w, convenience_w)
    price_lo, price_hi = _price_range(prices)
    price_span = price_hi - price_lo

    # Renewable range for normalisation (so green_score is also 0–1)
    if renewable_shares and len(renewable_shares) >= 24:
        renew_vals = [r["renewable_share"] for r in renewable_shares]
        renew_lo = min(renew_vals)
        renew_hi = max(renew_vals)
        renew_span = renew_hi - renew_lo if renew_hi != renew_lo else 0.01
        use_real_green = True
    else:
        use_real_green = False

    recommendations: list[dict] = []

    for app in appliances:
        dur = app["duration_hours"]
        # Only consider slots that finish by latest_finish
        max_start = min(app["latest_finish"] - dur, 24 - dur)
        if max_start < 0:
            max_start = 24 - dur

        best_start = app["default_start"]
        best_score = -1e9
        score_breakdown: dict = {}

        for start in range(0, max_start + 1):
            avg_price = _slot_avg_price(prices, start, dur)

            # Cost score: lower price → higher score  (0–1)
            cost_score = (price_hi - avg_price) / price_span

            # Green score: average renewable share of the slot, normalised to 0–1
            # relative to today's range so the score is sensitive to within-day
            # variation (not just the absolute level).
            if use_real_green:
                avg_renew = _slot_avg_renewable(renewable_shares, start, dur)
                green_score = (avg_renew - renew_lo) / renew_span
            else:
                # Fallback: low price as proxy for renewable surplus
                green_score = cost_score

            # Convenience score: 1 at default_start, falls off with deviation
            deviation = abs(start - app["default_start"])
            # Allow ±6 h full flexibility, harder penalty beyond that
            convenience_score = max(0.0, 1.0 - deviation / 8.0)

            total = (
                weights["cost"] * cost_score
                + weights["green"] * green_score
                + weights["convenience"] * convenience_score
            )

            if total > best_score:
                best_score = total
                best_start = start
                score_breakdown = {
                    "cost_score": round(cost_score, 3),
                    "green_score": round(green_score, 3),
                    "convenience_score": round(convenience_score, 3),
                    "weighted_total": round(total, 3),
                }

        # Default-slot economics
        default_avg = _slot_avg_price(prices, app["default_start"], dur)
        recommended_avg = _slot_avg_price(prices, best_start, dur)

        # Savings in € (price diff × energy consumption)
        kwh_total = app["typical_kwh_per_hour"] * dur
        savings_eur = (default_avg - recommended_avg) / 1000 * kwh_total

        # Renewable share at the recommended slot (absolute, for display)
        if use_real_green:
            rec_renew = _slot_avg_renewable(renewable_shares, best_start, dur)
            def_renew = _slot_avg_renewable(renewable_shares, app["default_start"], dur)
        else:
            rec_renew = None
            def_renew = None

        recommendations.append(
            {
                "appliance_id": app["id"],
                "appliance_name": app["name"],
                "emoji": app["emoji"],
                "duration_hours": dur,
                "default_start": app["default_start"],
                "recommended_start": best_start,
                "recommended_end": best_start + dur,
                "avg_price_default_eur_mwh": round(default_avg, 2),
                "avg_price_recommended_eur_mwh": round(recommended_avg, 2),
                "savings_eur": round(savings_eur, 4),
                "kwh_total": kwh_total,
                "renewable_share_recommended": round(rec_renew, 3) if rec_renew is not None else None,
                "renewable_share_default": round(def_renew, 3) if def_renew is not None else None,
                "scores": score_breakdown,
                "weights_used": {k: round(v, 3) for k, v in weights.items()},
            }
        )

    return recommendations
