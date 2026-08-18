"""
explainer.py
Generates two types of explanation for a scheduling recommendation.

Group A — Interactive causal explanation (natural language, updates with slider)
Group B — Static SHAP-style feature importance data (fixed at recommendation time)

Design principles
-----------------
• No SHAP numbers or technical jargon in Group A explanations
• Group A uses counterfactual framing: "if you increase X, the system would..."
• Group B SHAP values are mock-computed from the optimiser's score breakdown —
  sufficient for the demo; a real deployment would call shap.TreeExplainer.
"""

from __future__ import annotations


def _fmt_hour(h: int) -> str:
    return f"{h:02d}:00"


def _cheapest_slot(prices: list[dict], duration: int) -> int:
    best_h, best_avg = 0, float("inf")
    for start in range(24 - duration + 1):
        avg = sum(prices[start + i]["price_eur_mwh"] for i in range(duration)) / duration
        if avg < best_avg:
            best_avg = avg
            best_h = start
    return best_h


def _most_convenient_slot(app_default: int, duration: int) -> int:
    """Closest valid start to the default habit."""
    return max(0, min(app_default, 24 - duration))


# ── Group A: Causal explanation (interactive) ───────────────────────────────

def generate_causal_explanation(
    rec: dict,
    weights: dict,      # already normalised to sum ≈ 1.0
    prices: list[dict],
) -> str:
    """
    Build a two-sentence causal explanation:
      1. Justification of the recommendation given the dominant weight
      2. Counterfactual: what would change if a different weight were raised
    """
    app = rec["appliance_name"]
    rec_start = rec["recommended_start"]
    rec_end = rec["recommended_end"]
    def_start = rec["default_start"]
    dur = rec["duration_hours"]
    avg_price = rec["avg_price_recommended_eur_mwh"]
    savings = abs(rec["savings_eur"])

    w_cost = weights.get("cost", 1 / 3)
    w_green = weights.get("green", 1 / 3)
    w_conv = weights.get("convenience", 1 / 3)

    # ── Sentence 1: reason based on dominant weight ──────────────────────
    dominant = max(weights, key=weights.get)

    if dominant == "cost":
        pct = round(w_cost * 100)
        sentence1 = (
            f"With your Cost priority at {pct}%, the system schedules your {app} "
            f"for {_fmt_hour(rec_start)}–{_fmt_hour(rec_end)}, when the price drops to "
            f"{avg_price:.1f} €/MWh — saving roughly "
            f"{savings * 100:.0f} ct compared to your usual {_fmt_hour(def_start)} slot."
        )
    elif dominant == "green":
        pct = round(w_green * 100)
        # Use the *measured* renewable share, not price as a proxy. The optimiser was
        # changed in Session 7 to score "green" from real ENTSO-E generation data; this
        # explanation previously still told participants that low prices indicate high
        # renewable generation, which no longer matches how the system actually decides.
        rec_renew = rec.get("renewable_share_recommended")
        def_renew = rec.get("renewable_share_default")

        if rec_renew is not None:
            share_txt = f"{rec_renew * 100:.0f}% of the electricity in that window comes from wind, solar and hydro"
            if def_renew is not None and rec_renew > def_renew:
                share_txt += f", against {def_renew * 100:.0f}% at your usual {_fmt_hour(def_start)} slot"
            sentence1 = (
                f"With your Green priority at {pct}%, the system targets "
                f"{_fmt_hour(rec_start)}–{_fmt_hour(rec_end)}, because {share_txt} — "
                f"the cleanest window available for your {app}."
            )
        else:
            # Renewable data unavailable for this scenario; state the basis honestly
            # rather than inventing a renewable claim.
            sentence1 = (
                f"With your Green priority at {pct}%, the system targets "
                f"{_fmt_hour(rec_start)}–{_fmt_hour(rec_end)} for your {app}, "
                f"the lowest-demand window available in today's data."
            )
    else:  # convenience dominant
        pct = round(w_conv * 100)
        if rec_start == def_start:
            sentence1 = (
                f"With your Convenience priority at {pct}%, the system keeps your {app} "
                f"at your usual {_fmt_hour(def_start)} slot — no change to your routine."
            )
        else:
            # "only slightly" was hard-coded, so a five-hour shift was described as slight.
            # An explanation that misdescribes what the system did is worse than no
            # explanation: it gives participants a reason to distrust everything else on
            # the screen, and that distrust would land in the trust scale as noise.
            shift = abs(rec_start - def_start)
            shift = min(shift, 24 - shift)          # wrap around midnight
            if shift <= 1:
                magnitude = f"by {shift} hour" if shift == 1 else "barely at all"
                sentence1 = (
                    f"With your Convenience priority at {pct}%, the system moves your {app} "
                    f"{magnitude} — from your usual {_fmt_hour(def_start)} to {_fmt_hour(rec_start)}, "
                    f"keeping close to your routine."
                )
            else:
                sentence1 = (
                    f"With your Convenience priority at {pct}%, the system still moves your {app} "
                    f"by {shift} hours — from your usual {_fmt_hour(def_start)} to {_fmt_hour(rec_start)} — "
                    f"because the saving over that window outweighs the change to your routine."
                )

    # ── Sentence 2: counterfactual ────────────────────────────────────────
    cheapest = _cheapest_slot(prices, dur)
    conv_slot = _most_convenient_slot(def_start, dur)

    if dominant != "cost" and cheapest != rec_start:
        sentence2 = (
            f"If you raise the Cost weight, the system would shift to "
            f"{_fmt_hour(cheapest)}–{_fmt_hour(cheapest + dur)} "
            f"(the cheapest window of the day)."
        )
    elif dominant != "convenience" and conv_slot != rec_start:
        sentence2 = (
            f"If you raise the Convenience weight, the system would move back towards "
            f"your usual {_fmt_hour(def_start)} slot."
        )
    elif dominant == "cost" and conv_slot != rec_start:
        sentence2 = (
            f"If you prioritise Convenience instead, the recommendation shifts "
            f"to {_fmt_hour(conv_slot)}, closer to your habitual run time."
        )
    else:
        sentence2 = (
            "The current schedule already balances all three priorities well — "
            "adjusting any single weight would only change the timing marginally."
        )

    return f"{sentence1} {sentence2}"


# ── Group B: Static SHAP-style data (generated once per recommendation) ─────

def generate_shap_data(rec: dict, weights: dict) -> list[dict]:
    """
    Produce mock SHAP feature-contribution data for a bar-chart display.

    Each entry:  {feature, label, value, direction}
    • value    : contribution magnitude (0–1 scale)
    • direction: 'positive' (supports recommendation) or 'negative' (works against)

    Values are derived from the optimiser's internal score breakdown so they
    are self-consistent without requiring a real SHAP explainer.
    """
    scores = rec.get("scores", {})
    cost_s = scores.get("cost_score", 0.5)
    green_s = scores.get("green_score", 0.5)
    conv_s = scores.get("convenience_score", 0.5)

    w_cost = weights.get("cost", 1 / 3)
    w_green = weights.get("green", 1 / 3)
    w_conv = weights.get("convenience", 1 / 3)

    features = [
        {
            "feature": "electricity_price",
            "label": "Electricity price level",
            "value": round(cost_s * w_cost, 3),
            "direction": "positive" if cost_s > 0.5 else "negative",
        },
        {
            "feature": "cost_weight",
            "label": "Cost priority (slider)",
            "value": round(w_cost * cost_s * 0.8, 3),
            "direction": "positive" if w_cost >= 1 / 3 else "negative",
        },
        {
            "feature": "green_weight",
            "label": "Green priority (slider)",
            "value": round(w_green * green_s * 0.8, 3),
            "direction": "positive" if w_green >= 1 / 3 else "negative",
        },
        {
            "feature": "convenience_weight",
            "label": "Convenience priority (slider)",
            "value": round(w_conv * conv_s * 0.8, 3),
            "direction": "positive" if w_conv >= 1 / 3 else "negative",
        },
        {
            "feature": "appliance_habit",
            "label": "Appliance run-time habit",
            "value": round(conv_s * 0.4, 3),
            "direction": "positive" if conv_s > 0.4 else "negative",
        },
        {
            "feature": "hour_of_day",
            "label": "Hour of day",
            "value": round(0.08 + cost_s * 0.12, 3),
            "direction": "positive",
        },
    ]

    # Sort by absolute value descending (most influential first)
    features.sort(key=lambda x: x["value"], reverse=True)
    return features
