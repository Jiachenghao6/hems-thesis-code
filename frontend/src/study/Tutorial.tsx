/**
 * Tutorial.tsx — what participants are shown before the first task.
 *
 * ── The constraint that shapes every sentence here ─────────────────────────
 *
 * Both conditions see this page, **word for word the same**. So nothing on it may
 * be true of only one of them. In particular it must not say that the explanation
 * responds to the control (true only in A), and it must not call the explanation
 * text or a chart (they differ). "Alongside each suggestion you will see an
 * explanation of why that time was chosen" holds in both, and is as specific as
 * this page is allowed to get.
 *
 * That is the same failure the condition badge and the banner represented: a
 * participant who learns that another version exists starts looking for what they
 * are missing, and the manipulation checks at the end stop measuring perception and
 * start measuring inference.
 *
 * The control is illustrated rather than demonstrated. A working control here would
 * have to be attached to something for its effect to be visible, and whatever it was
 * attached to would differ by condition — so it is a static picture, identical for
 * everyone, and the first real interaction happens inside task one.
 */
import { cardStyle, pageStyle } from "./ui";

/** Mirrors the segment colours and order of the real control, so it is recognisable. */
const SEGMENTS = [
  { label: "Cost", pct: 35, colour: "#2563eb", note: "cheapest hours" },
  { label: "Green", pct: 30, colour: "#16a34a", note: "high renewable share" },
  { label: "Convenience", pct: 35, colour: "#d97706", note: "close to your routine" },
];

export default function Tutorial({ onStart }: { onStart: () => void }) {
  const step: React.CSSProperties = { display: "flex", gap: 14, marginBottom: 20, alignItems: "flex-start" };
  const num: React.CSSProperties = {
    flex: "none",
    width: 25,
    height: 25,
    borderRadius: "50%",
    background: "#eff6ff",
    color: "#2563eb",
    fontSize: 13,
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 1,
  };

  return (
    <div style={{ ...pageStyle, padding: "32px 16px 64px" }}>
      <div style={cardStyle}>
        <h1 style={{ fontSize: 20, margin: "0 0 8px", fontWeight: 600 }}>Before you start</h1>
        <p style={{ fontSize: 14, color: "#64748b", lineHeight: 1.6, margin: "0 0 26px" }}>
          The system suggests when to run household appliances, based on what matters most to you. Here is how it
          works — it takes a minute to read.
        </p>

        <div style={step}>
          <div style={num}>1</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>You will see three situations.</strong> Each one is a different day, with its own electricity
            prices across the 24 hours. For each day the system suggests a time to run four appliances: a
            dishwasher, a washing machine, a water heater and an EV charger.
          </div>
        </div>

        <div style={step}>
          <div style={num}>2</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>You set the priorities.</strong> Three things can matter when choosing a time — saving money,
            using renewable electricity, and running the appliance close to when you normally would. They always
            add up to 100%, so giving more to one means giving less to another. That is the point: it is a
            trade-off, not a wish list.
          </div>
        </div>

        {/* Static illustration — identical in both conditions, see the file header. */}
        <div style={{ margin: "6px 0 24px", paddingLeft: 39 }}>
          <div
            style={{
              display: "flex",
              height: 38,
              borderRadius: 7,
              overflow: "hidden",
              border: "1px solid #e2e8f0",
            }}
            aria-hidden="true"
          >
            {SEGMENTS.map((s, i) => (
              <div
                key={s.label}
                style={{
                  width: `${s.pct}%`,
                  background: s.colour,
                  color: "white",
                  fontSize: 12,
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderLeft: i === 0 ? "none" : "3px solid white",
                }}
              >
                {s.pct}%
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 9, flexWrap: "wrap" }}>
            {SEGMENTS.map((s) => (
              <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#475569" }}>
                <span style={{ width: 11, height: 11, borderRadius: 3, background: s.colour, flex: "none" }} />
                <strong style={{ fontWeight: 600 }}>{s.label}</strong>
                <span style={{ color: "#94a3b8" }}>— {s.note}</span>
              </span>
            ))}
          </div>
          <p style={{ fontSize: 13, color: "#64748b", margin: "12px 0 0", lineHeight: 1.6 }}>
            Drag either of the two dividers to change the balance. You can also use the arrow keys once a divider is
            focused. Adjust it as often as you like — there is no single correct setting.
          </p>
        </div>

        <div style={step}>
          <div style={num}>3</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>You decide on each suggestion.</strong> Alongside each suggested time you will see an
            explanation of why the system picked it. Accept the ones you would actually follow and reject the ones
            you would not — rejecting is a perfectly good answer, and we are just as interested in those.
          </div>
        </div>

        <div style={step}>
          <div style={num}>4</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>Then a short questionnaire.</strong> A few questions about how the task felt and what you made
            of the system. There are no right or wrong answers anywhere in this study.
          </div>
        </div>

        <div
          style={{
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: 9,
            padding: "13px 15px",
            fontSize: 13,
            color: "#475569",
            lineHeight: 1.6,
            marginTop: 4,
          }}
        >
          Take your time — the study is not timed, and working through it at your normal pace is exactly what we
          need. Please stay in this window until the end so your submission is recorded.
        </div>

        <button
          onClick={onStart}
          style={{
            marginTop: 24,
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
          Start with the first situation
        </button>
      </div>
    </div>
  );
}
