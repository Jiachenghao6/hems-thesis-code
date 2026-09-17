/**
 * Consent.tsx — informed consent, shown before anything is recorded.
 *
 * Ordering matters and is the reason this component exists as its own phase:
 * requesting a session assigns a condition and writes a row to the assignment
 * ledger. That is data collection. It must not happen until consent is given, so
 * `App` does not call `createSession` until this page reports back.
 *
 * The purpose statement is deliberately unspecific ("how people use a system that
 * suggests when to run household appliances"). Naming the hypothesis — that
 * interactive causal explanations are expected to raise trust — would tell
 * participants what is being tested and invite them to confirm it.
 */
import { useState } from "react";
import { cardStyle, pageStyle } from "./ui";

const CONTACT_STUDENT = "jiacheng0411.hao@tum.de";
const CONTACT_SUPERVISOR = "woerndl@cit.tum.de";

export default function Consent({ onAccept }: { onAccept: () => void }) {
  const [checked, setChecked] = useState(false);

  const item: React.CSSProperties = { marginBottom: 12, lineHeight: 1.65 };

  return (
    <div style={{ ...pageStyle, padding: "32px 16px 64px" }}>
      <div style={cardStyle}>
        <h1 style={{ fontSize: 20, margin: "0 0 6px", fontWeight: 600 }}>Information and consent</h1>
        <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 22px" }}>
          Bachelor's thesis project · Chair of Connected Mobility · Technical University of Munich
        </p>

        <div style={{ fontSize: 14, color: "#334155" }}>
          <p style={item}>
            <strong>What this study is about.</strong> You will use a prototype that suggests when to run
            household appliances such as a dishwasher or a washing machine. We are interested in how people
            work with such a system and how they judge its suggestions.
          </p>
          <p style={item}>
            <strong>What you will do.</strong> You will set your priorities, look at the suggestions the system
            makes, and decide whether to accept them. Afterwards you will answer a short questionnaire. The
            whole study takes about 15 minutes.
          </p>
          <p style={item}>
            <strong>What is recorded.</strong> Your Prolific ID, the settings you choose, the suggestions you
            accept or reject, and your questionnaire answers. There is no audio or video recording, and we do
            not ask for your name or any contact details.
          </p>
          <p style={item}>
            <strong>How your data is handled.</strong> Your responses are stored under a randomly generated
            identifier. Your Prolific ID is kept separately and is used only to confirm your submission and
            your payment; it is not stored together with your answers. The data are analysed only in
            aggregate and are used solely for this thesis. No personal data are published.
          </p>
          <p style={item}>
            <strong>Voluntary participation.</strong> Participation is voluntary. You may stop at any point by
            closing the window. If you stop, please return the submission on Prolific so that you are not
            penalised. Data from unfinished sessions are not analysed.
          </p>
          <p style={item}>
            <strong>Questions.</strong> Jiacheng Hao (<a href={`mailto:${CONTACT_STUDENT}`}>{CONTACT_STUDENT}</a>),
            supervised by Dr. Wolfgang Wörndl (
            <a href={`mailto:${CONTACT_SUPERVISOR}`}>{CONTACT_SUPERVISOR}</a>).
          </p>
        </div>

        <label
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 11,
            marginTop: 24,
            padding: 15,
            border: "1px solid #e2e8f0",
            borderRadius: 9,
            background: "#f8fafc",
            fontSize: 14,
            cursor: "pointer",
            lineHeight: 1.5,
          }}
        >
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            style={{ accentColor: "#2563eb", width: 17, height: 17, marginTop: 2, flex: "none" }}
          />
          <span>
            I have read the information above, I am at least 18 years old, and I agree to take part in this
            study.
          </span>
        </label>

        <button
          onClick={onAccept}
          disabled={!checked}
          style={{
            marginTop: 22,
            background: checked ? "#2563eb" : "#cbd5e1",
            color: "white",
            border: "none",
            borderRadius: 8,
            padding: "11px 26px",
            fontSize: 14,
            fontWeight: 600,
            cursor: checked ? "pointer" : "not-allowed",
          }}
        >
          Start the study
        </button>
      </div>
    </div>
  );
}
