/**
 * DeviceCheck.tsx — the first thing anyone sees, shown instead of the study when the
 * window is too narrow to present both conditions fairly.
 *
 * ── Why a screen this study refuses to run on ──────────────────────────────
 *
 * The two conditions differ in how the explanation is presented: one is a paragraph
 * of text, the other a feature-importance chart. Those two do not shrink alike.
 * Measured at a 375px viewport, the chart is squeezed to 277px wide against the
 * 400px it gets from 520px upwards, while the text simply reflows and keeps its
 * 13px. A narrow screen therefore penalises one condition and not the other — and
 * since the comparison between them is the entire study, that is a difference
 * between groups caused by the device rather than by the manipulation. With around
 * forty participants there is no hope of estimating a device × condition
 * interaction, so the only clean answer is not to collect the cell at all.
 *
 * ── Why the check lives here and not on Prolific ───────────────────────────
 *
 * Prolific's device checkboxes look like a filter and are not one. Their own
 * documentation: the setting "is merely used as an indicator for participants and
 * ... do[es] not screen out participants based on the device options you select",
 * and they do not record which device was actually used either. So the study has to
 * check for itself, and their guidance is explicit that the check must run "at the
 * very start of your study, before participants invest significant time".
 *
 * ── Why it must come before consent ────────────────────────────────────────
 *
 * Consent is what triggers assignment, and assignment writes a row to the ledger
 * and consumes one cell of the block. Someone turned away here has not consented,
 * has not been assigned, and costs nothing. Running this check after consent would
 * burn a cell for every phone that ever opened the link.
 *
 * ── Returning rather than completing ───────────────────────────────────────
 *
 * The button sends them to a *different* Prolific completion path from the one at
 * the end of the study — an "Incompatible device" path configured as "Request a
 * return". The two must not be confused: one approves a submission for payment,
 * the other asks for it back so the place is freed for someone else. If that path
 * has not been configured yet the button is simply not shown, because sending a
 * participant to an empty URL is worse than telling them what to do in words.
 */
import { cardStyle, pageStyle } from "./ui";

/**
 * Minimum viewport width, in CSS pixels: the width at which the explanation chart
 * stops being squeezed, and therefore the width below which the two conditions stop
 * being comparable.
 *
 * Measured rather than picked, by stepping the viewport and reading the rendered
 * chart back:
 *
 *     375px → 277   420px → 322   480px → 382   520px → 400   560–1009px → 400
 *
 * So 520 is where it reaches full size and stays there. An earlier version of this
 * file said 768 on the strength of three data points — 375, 768 and 1009 — which
 * put the transition at the tablet breakpoint because that was the only place it had
 * been looked for. Turning away every window between 520 and 768 would have cost
 * participants for no reason.
 *
 * The comparison is against the *layout* width, which is what a media query reports
 * and what the chart is actually laid out in. `window.innerWidth` is the wrong number
 * here: it includes the scrollbar, so on a desktop browser it reads up to 15px wider
 * than the space the page really has.
 */
export const MIN_VIEWPORT_WIDTH = 520;

export default function DeviceCheck({
  returnUrl,
  width,
}: {
  /** Prolific's "Incompatible device" redirect; empty until the study is configured. */
  returnUrl: string;
  width: number;
}) {
  return (
    <div style={{ ...pageStyle, padding: "32px 16px 64px" }}>
      <div style={cardStyle}>
        <h1 style={{ fontSize: 20, margin: "0 0 12px", fontWeight: 600 }}>This study needs a wider screen</h1>

        <p style={{ fontSize: 14, color: "#334155", lineHeight: 1.65, margin: "0 0 14px" }}>
          Part of this study is a chart that does not fit on a narrow screen, so taking part on a phone held
          upright would not be a fair test of it. Your window is currently {width} pixels wide and the study
          needs at least {MIN_VIEWPORT_WIDTH}.
        </p>

        <p style={{ fontSize: 14, color: "#334155", lineHeight: 1.65, margin: "0 0 14px" }}>
          <strong>If you are on a computer or a tablet</strong>, widen this window or turn the device sideways —
          this page continues on its own as soon as there is room. Nothing has been recorded yet.
        </p>

        <p style={{ fontSize: 14, color: "#334155", lineHeight: 1.65, margin: "0 0 20px" }}>
          <strong>If you are on a phone</strong>, please return this submission on Prolific. Returning does not
          count against you, and the place will go to someone else. We are sorry for the wasted trip.
        </p>

        {returnUrl && (
          <a
            href={returnUrl}
            style={{
              display: "inline-block",
              background: "#2563eb",
              color: "white",
              textDecoration: "none",
              borderRadius: 8,
              padding: "11px 26px",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            Return this submission on Prolific
          </a>
        )}
      </div>
    </div>
  );
}
