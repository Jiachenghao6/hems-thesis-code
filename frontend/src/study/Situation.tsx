/**
 * Situation.tsx — the card shown before each of the three tasks.
 *
 * ── Why this screen exists ─────────────────────────────────────────────────
 *
 * The three tasks use three different price curves, but at a glance they look
 * identical: same four appliances, same control, same layout, with only a small
 * grey line naming the scenario. A timed walkthrough showed exactly what that
 * costs — 44s on the first situation, 25s on the second, 13s on the third. That
 * decay is not fatigue, it is a participant with no reason to re-engage, and on a
 * real run it would turn the acceptance rate on tasks two and three into a copy of
 * task one. Acceptance rate is the study's primary dependent variable, so this had
 * to be fixed before data collection rather than explained afterwards.
 *
 * ── The two constraints on the wording ─────────────────────────────────────
 *
 * 1. **Identical for both conditions.** Nothing here may hint at the explanation
 *    format or at the existence of another version.
 *
 * 2. **Descriptive, never directive.** It says what kind of day it is; it never
 *    suggests what to do about it. "Electricity is unusually expensive almost all
 *    day" is a fact the price chart shows anyway. "So you may want to prioritise
 *    cost" would be telling participants how to answer, and the acceptance rate
 *    would then measure compliance with the instruction.
 *
 * The framing is a deliberate departure from a bare repetition of the same task and
 * belongs in the study design chapter: it is identical across conditions, so it
 * cannot confound the comparison, but it does shape absolute acceptance levels and
 * should be reported as part of the procedure.
 */
import { cardStyle, pageStyle } from "./ui";

interface Framing {
  /** Plain-language name. No €/MWh, no market vocabulary. */
  title: string;
  /** One sentence of what kind of day it is. Descriptive only. */
  blurb: string;
}

/**
 * Keyed by scenario id so the framing follows the sequence the server hands out
 * (`TASK_SEQUENCE`), rather than being positional — if the order is ever changed,
 * the wrong blurb would otherwise be shown with the right chart.
 */
export const FRAMINGS: Record<string, Framing> = {
  S1: {
    title: "A very expensive day",
    blurb:
      "A cold snap has pushed demand up across the country, and electricity costs far more than usual for most of the day.",
  },
  S2: {
    title: "A day with a surplus of wind power",
    blurb:
      "So much wind power is being generated that for part of the day there is more electricity than the grid can use.",
  },
  S3: {
    title: "A day of big price swings",
    blurb:
      "Prices move sharply between the cheapest and the most expensive hours — a fairly ordinary day on the European market.",
  },
  S4: {
    title: "A calm, cheap day",
    blurb: "Mild demand and plenty of renewable generation keep prices low from morning to night.",
  },
  S5: {
    title: "A cheap morning and an expensive evening",
    blurb: "Solar generation makes the middle of the day cheap, and prices climb steeply once it drops away.",
  },
};

export default function Situation({
  scenarioId,
  index,
  total,
  onContinue,
}: {
  scenarioId: string;
  index: number;
  total: number;
  onContinue: () => void;
}) {
  const framing = FRAMINGS[scenarioId];

  return (
    <div style={{ ...pageStyle, padding: "72px 16px" }}>
      <div style={{ ...cardStyle, maxWidth: 560 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            letterSpacing: ".08em",
            textTransform: "uppercase",
            color: "#2563eb",
            marginBottom: 10,
          }}
        >
          Situation {index + 1} of {total}
        </div>

        <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 12px", lineHeight: 1.3 }}>
          {framing?.title ?? "A new day"}
        </h1>

        <p style={{ fontSize: 15, color: "#475569", lineHeight: 1.65, margin: "0 0 20px" }}>
          {framing?.blurb ?? "The electricity prices are different from the previous situation."}
        </p>

        <div
          style={{
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: 9,
            padding: "13px 15px",
            fontSize: 13.5,
            color: "#475569",
            lineHeight: 1.6,
          }}
        >
          {index === 0
            ? "Set your priorities however you like, then decide on each of the four suggestions."
            : "This is a different day with different prices, so your priorities start again from an even split. Set them however suits this day, then decide on each suggestion."}
        </div>

        <button
          onClick={onContinue}
          style={{
            marginTop: 22,
            background: "#2563eb",
            color: "white",
            border: "none",
            borderRadius: 8,
            padding: "11px 26px",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {index === 0 ? "Start" : "Continue"}
        </button>
      </div>
    </div>
  );
}
