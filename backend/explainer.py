"""
explainer.py
Generates two types of explanation for a scheduling recommendation.

Group A — Interactive causal explanation (natural language, updates with slider)
Group B — Feature-attribution chart: exact per-factor contributions relative to the usual time (updates with slider)

Design principles
-----------------
• No SHAP numbers or technical jargon in Group A explanations
• Group A uses counterfactual framing: "if you increase X, the system would..."
• Group B values decompose the optimiser's weighted score exactly (see generate_shap_data);
  the first-run version used mock values and was replaced for the 2026-10 rerun.
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


# ── Group B: feature-attribution chart (exact decomposition, 2026-10 rerun) ──
#
# History. The chart used in the first run (20 Sep 2026) was mock data: cost and
# convenience each appeared twice, an "Hour of day" factor was shown although the
# optimiser does not use it, and bar colours came from fixed thresholds. A check of
# the 288 charts participants saw found at least one real factor with the wrong sign
# in 65% of them (analyse_shap_fidelity.py). Condition B is rerun with this version.
#
# What a bar means now. The optimiser picks the start hour with the highest weighted
# sum  w_cost*s_cost + w_green*s_green + w_conv*s_conv.  Taking the participant's
# usual start time as the baseline, the score difference between the recommended
# and the usual slot splits exactly into one term per factor:
#     contribution_i = w_i * (s_i(recommended) - s_i(usual))
# The three bars are these terms. Positive = the factor favoured the recommended
# time over the usual one (green); negative = it favoured the usual time (red).
# The bars sum to the total score difference, so nothing is invented or duplicated.
# (For an additive model with the usual slot as reference input this coincides with
# the SHAP value of each factor, but no SHAP library is involved.)

FACTOR_LABELS = {
    "cost": "Cost — electricity price",
    "green": "Green — renewable share",
    "convenience": "Convenience — usual time",
}


def generate_shap_data(rec: dict, weights: dict | None = None) -> list[dict]:
    """
    Exact per-factor contributions for the condition-B bar chart.

    Each entry: {feature, label, value, direction}
    • value     : |w_i * (s_i(recommended) - s_i(usual))|, rounded to 3 decimals
    • direction : 'positive' (favours the recommended time), 'negative'
                  (favours the usual time) or 'neutral' (exactly zero)

    `weights` is accepted for backwards compatibility but ignored: the unrounded
    weights the optimiser actually used are taken from the recommendation itself,
    so the chart decomposes exactly the decision that was made.
    """
    w = rec["weights_exact"]
    s_rec = rec["component_scores_recommended"]
    s_use = rec["component_scores_usual"]

    features = []
    for key in ("cost", "green", "convenience"):
        contrib = w[key] * (s_rec[key] - s_use[key])
        if abs(contrib) < 1e-9:
            direction = "neutral"
        else:
            direction = "positive" if contrib > 0 else "negative"
        features.append({
            "feature": key,
            "label": FACTOR_LABELS[key],
            "value": round(abs(contrib), 3),
            "signed_value": contrib,          # unrounded, for logging and fidelity checks
            "direction": direction,
        })

    # Largest contribution first; ties keep the fixed order cost, green, convenience.
    features.sort(key=lambda x: abs(x["signed_value"]), reverse=True)
    return features
