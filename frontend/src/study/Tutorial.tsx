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

/**
 * Mirrors the segment colours, order and wording of the real control, so it is
 * recognisable. The notes have to match `TradeoffSlider` exactly — a participant who
 * meets one phrase here and a different one on the task screen has to work out
 * whether they mean the same thing, and that work has nothing to do with the study.
 */
const SEGMENTS = [
  { label: "Cost", pct: 35, colour: "#2563eb", note: "the cheapest hours" },
  { label: "Green", pct: 30, colour: "#16a34a", note: "more wind and solar" },
  { label: "Convenience", pct: 35, colour: "#d97706", note: "close to your usual time" },
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
        {/*
          Kept short on purpose. The three tasks themselves take around two and a half
          minutes, so a tutorial that takes two minutes to read is a third of the study,
          and a paid participant skims it — which shows up in the data as somebody who
          never touched the priority control.

          What was cut was whatever the screen already says: the three priorities are
          named in the legend a few centimetres below, and the four appliances appear by
          name seconds later. What was kept is the part that cannot be inferred from
          looking (the three always total 100%) and the two sentences that protect the
          measures — see the notes on each.
        */}
        <p style={{ fontSize: 14, color: "#64748b", lineHeight: 1.6, margin: "0 0 26px" }}>
          Electricity costs a different amount at each hour of the day, and at some hours more of it comes from
          wind and solar. This system uses that to suggest when to run your appliances.
        </p>

        <div style={step}>
          <div style={num}>1</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>Three days, one after another.</strong> On each one you see how the price changes through the
            day, and the system suggests a time for four household appliances.
          </div>
        </div>

        <div style={step}>
          <div style={num}>2</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>You choose what matters.</strong> The three priorities below always add up to 100%, so giving
            more to one means giving less to the others.
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
          {/*
            "Drag the white lines between the colours" rather than "drag either of the
            two dividers": a participant looking at the bar sees colours and gaps, not
            an interface element called a divider, and on a phone nothing says the bar
            can be touched at all unless the sentence points at something visible.

            It must not say what changes when the bar moves. The suggested times update
            in both conditions, so that part would be true either way — but a sentence
            telling people to watch for things updating turns the manipulation check at
            the end into a test of whether they followed an instruction.
          */}
          {/*
            The second sentence stays whatever else is cut. In the three pilot runs the
            control was moved between two and four times across all three situations —
            roughly once per situation. A participant who barely moves it sees almost the
            same screen in either condition, and the manipulation stops being a
            manipulation. This is the only place anything invites them to move it again.
          */}
          <p style={{ fontSize: 13, color: "#64748b", margin: "12px 0 0", lineHeight: 1.6 }}>
            Drag the white lines between the colours to change the balance — arrow keys work too. Change it as
            often as you like; there is no correct setting.
          </p>
        </div>

        <div style={step}>
          <div style={num}>3</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            {/*
              "Just as useful to us as accepting" also stays. Without it the agreeable
              answer is to accept everything, and acceptance rate is the primary
              dependent variable — the sentence costs eight words and protects it. The
              generic "no right or wrong answers" that used to sit in step 4 said less
              and said it further from the decision it was about.
            */}
            <strong>You accept or reject each suggestion.</strong> Next to each suggested time there is an
            explanation of why the system chose it. Reject the ones you would not actually use — that is just as
            useful to us as accepting.
          </div>
        </div>

        <div style={step}>
          <div style={num}>4</div>
          <div style={{ fontSize: 14, lineHeight: 1.6 }}>
            <strong>Then some questions</strong> about the system and how the task felt.
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
          Nothing here is timed. Please stay in this window until the end, so your submission is recorded.
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
