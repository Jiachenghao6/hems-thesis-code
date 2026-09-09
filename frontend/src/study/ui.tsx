/**
 * ui.tsx — the input widgets the questionnaire pages are built from.
 *
 * Two constraints shape everything here:
 *
 *  1. **Nothing may hint at the condition.** These pages are shown to both groups
 *     and are identical for both. No wording that presupposes a moving explanation.
 *
 *  2. **Unanswered must be visibly unanswered.** A self-hosted questionnaire has no
 *     platform validation behind it, so the page component refuses to advance and
 *     these widgets mark what is missing. Pre-selecting a default would silently turn
 *     a non-response into a data point, which is worse than an empty cell.
 *
 * Radio groups are real <input type="radio">, not styled divs: keyboard and screen
 * reader support comes for free, and the study is recruited online where some
 * participants will not be using a mouse.
 */
import type { ReactNode } from "react";

// ── Tokens, kept in step with App.tsx ───────────────────────────────────────

const INK = "#0f172a";
const MUTED = "#64748b";
const LINE = "#e2e8f0";
const ACCENT = "#2563eb";
const MISS = "#dc2626";

export const pageStyle: React.CSSProperties = {
  fontFamily: "'Inter', system-ui, sans-serif",
  background: "#f8fafc",
  minHeight: "100vh",
  color: INK,
};

export const cardStyle: React.CSSProperties = {
  background: "white",
  border: `1px solid ${LINE}`,
  borderRadius: 12,
  padding: 24,
  maxWidth: 780,
  margin: "0 auto",
};

// ── Page shell ──────────────────────────────────────────────────────────────

export function SurveyPage({
  title,
  intro,
  children,
  onNext,
  nextLabel = "Continue",
  missing,
  progress,
}: {
  title: string;
  intro?: ReactNode;
  children: ReactNode;
  onNext: () => void;
  nextLabel?: string;
  /** Number of required answers still missing; > 0 disables the button. */
  missing: number;
  /** [current, total] step counter shown above the title. */
  progress?: [number, number];
}) {
  return (
    <div style={{ ...pageStyle, padding: "32px 16px 64px" }}>
      <div style={cardStyle}>
        {progress && (
          <div style={{ fontSize: 12, color: MUTED, marginBottom: 8 }}>
            Step {progress[0]} of {progress[1]}
          </div>
        )}
        <h1 style={{ fontSize: 20, margin: "0 0 12px", fontWeight: 600 }}>{title}</h1>
        {intro && <div style={{ fontSize: 14, color: MUTED, lineHeight: 1.6, marginBottom: 20 }}>{intro}</div>}
        {children}
        <div style={{ marginTop: 28, display: "flex", alignItems: "center", gap: 14 }}>
          <button
            onClick={onNext}
            disabled={missing > 0}
            style={{
              background: missing > 0 ? "#cbd5e1" : ACCENT,
              color: "white",
              border: "none",
              borderRadius: 8,
              padding: "11px 26px",
              fontSize: 14,
              fontWeight: 600,
              cursor: missing > 0 ? "not-allowed" : "pointer",
            }}
          >
            {nextLabel}
          </button>
          {missing > 0 && (
            <span style={{ fontSize: 13, color: MISS }}>
              {missing} {missing === 1 ? "question is" : "questions are"} still unanswered.
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Single-choice question ──────────────────────────────────────────────────

export function RadioQuestion({
  id,
  text,
  options,
  value,
  onChange,
  showMissing,
}: {
  id: string;
  text: string;
  options: { value: string; label: string }[];
  value: string | undefined;
  onChange: (v: string) => void;
  showMissing: boolean;
}) {
  const unanswered = showMissing && value === undefined;
  return (
    <fieldset
      style={{
        border: "none",
        borderLeft: `3px solid ${unanswered ? MISS : "transparent"}`,
        padding: "0 0 0 12px",
        margin: "0 0 22px",
      }}
    >
      <legend style={{ fontSize: 14, fontWeight: 500, padding: 0, marginBottom: 10 }}>{text}</legend>
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {options.map((o) => (
          <label key={o.value} style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 14, cursor: "pointer" }}>
            <input
              type="radio"
              name={id}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              style={{ accentColor: ACCENT, width: 16, height: 16 }}
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// ── Closed question, single or multi-select, with an optional "other" box ───

/**
 * One component for both shapes because the only real difference is how many
 * answers may stand at once, and keeping them together stops the two drifting
 * apart in look — which would make the two closing items read as different kinds
 * of question when they are not.
 *
 * At the choice limit the remaining options are disabled rather than silently
 * ignoring the click: a control that does nothing when pressed reads as broken.
 */
export function ChoiceQuestion({
  id,
  text,
  hint,
  options,
  maxChoices,
  otherValue,
  exclusiveValue,
  value,
  otherText,
  onChange,
  onOtherText,
  showMissing,
}: {
  id: string;
  text: string;
  hint?: string;
  options: { value: string; label: string }[];
  maxChoices?: number;
  otherValue?: string;
  exclusiveValue?: string;
  value: string[];
  otherText: string;
  onChange: (next: string[]) => void;
  onOtherText: (v: string) => void;
  showMissing: boolean;
}) {
  const multi = (maxChoices ?? 1) > 1;
  const otherPicked = otherValue !== undefined && value.includes(otherValue);
  const unanswered = showMissing && (value.length === 0 || (otherPicked && otherText.trim() === ""));
  const atLimit = multi && value.length >= (maxChoices as number);

  const toggle = (v: string) => {
    if (!multi) {
      onChange([v]);
      return;
    }
    if (value.includes(v)) {
      onChange(value.filter((x) => x !== v));
      return;
    }
    // "Nothing in particular" cannot sit alongside a reason, in either direction.
    if (exclusiveValue !== undefined) {
      if (v === exclusiveValue) {
        onChange([v]);
        return;
      }
      if (value.includes(exclusiveValue)) {
        onChange([v]);
        return;
      }
    }
    if (value.length >= (maxChoices as number)) return;
    onChange([...value, v]);
  };

  return (
    <fieldset
      style={{
        border: "none",
        borderLeft: `3px solid ${unanswered ? MISS : "transparent"}`,
        padding: "0 0 0 12px",
        margin: "0 0 24px",
      }}
      data-q={id}
    >
      <legend style={{ fontSize: 14, fontWeight: 500, padding: 0, marginBottom: hint ? 4 : 10 }}>{text}</legend>
      {hint && <div style={{ fontSize: 13, color: MUTED, marginBottom: 10 }}>{hint}</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {options.map((o) => {
          const on = value.includes(o.value);
          const blocked = !on && atLimit && o.value !== exclusiveValue;
          return (
            <label
              key={o.value}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 9,
                fontSize: 14,
                lineHeight: 1.45,
                cursor: blocked ? "not-allowed" : "pointer",
                color: blocked ? "#94a3b8" : "inherit",
              }}
            >
              <input
                type={multi ? "checkbox" : "radio"}
                name={id}
                checked={on}
                disabled={blocked}
                onChange={() => toggle(o.value)}
                style={{ accentColor: ACCENT, width: 16, height: 16, marginTop: 2, flex: "none" }}
              />
              {o.label}
            </label>
          );
        })}
      </div>

      {otherPicked && (
        <input
          type="text"
          value={otherText}
          onChange={(e) => onOtherText(e.target.value)}
          placeholder="Please say briefly what it was"
          aria-label="Please say briefly what it was"
          style={{
            marginTop: 10,
            width: "100%",
            boxSizing: "border-box",
            border: `1px solid ${otherText.trim() === "" && showMissing ? MISS : LINE}`,
            borderRadius: 8,
            padding: "9px 11px",
            fontSize: 14,
            fontFamily: "inherit",
          }}
        />
      )}
    </fieldset>
  );
}

// ── Likert matrix row (TiA) ─────────────────────────────────────────────────

export function LikertRow({
  id,
  text,
  labels,
  value,
  onChange,
  showMissing,
  index,
}: {
  id: string;
  text: string;
  labels: string[];
  value: number | undefined;
  onChange: (v: number) => void;
  showMissing: boolean;
  index: number;
}) {
  const unanswered = showMissing && value === undefined;
  return (
    <fieldset
      style={{
        border: "none",
        borderLeft: `3px solid ${unanswered ? MISS : "transparent"}`,
        background: index % 2 === 0 ? "#fbfcfd" : "transparent",
        padding: "12px 0 12px 12px",
        margin: 0,
      }}
    >
      <legend style={{ fontSize: 14, padding: 0, marginBottom: 9 }}>{text}</legend>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {labels.map((label, i) => {
          const v = i + 1;
          const active = value === v;
          return (
            <label
              key={v}
              title={label}
              style={{
                flex: "1 1 90px",
                minWidth: 84,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 5,
                padding: "7px 4px",
                border: `1px solid ${active ? ACCENT : LINE}`,
                background: active ? "#eff6ff" : "white",
                borderRadius: 7,
                cursor: "pointer",
                fontSize: 11,
                color: active ? ACCENT : MUTED,
                textAlign: "center",
                lineHeight: 1.25,
              }}
            >
              <input
                type="radio"
                name={id}
                checked={active}
                onChange={() => onChange(v)}
                style={{ accentColor: ACCENT, margin: 0 }}
              />
              {label}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

// ── NASA-TLX 21-gradation scale ─────────────────────────────────────────────

/**
 * A row of 21 tick marks rather than a native range input. `<input type=range>`
 * always shows a thumb somewhere, so it cannot represent "not answered yet" — the
 * participant would have to be told to move it, and anyone who agreed with the
 * default would leave it untouched and be recorded as having answered.
 */
export function TlxScale({
  id,
  title,
  question,
  lowAnchor,
  highAnchor,
  steps,
  stepSize,
  value,
  onChange,
  showMissing,
}: {
  id: string;
  title: string;
  question: string;
  lowAnchor: string;
  highAnchor: string;
  steps: number;
  stepSize: number;
  value: number | undefined;
  onChange: (v: number) => void;
  showMissing: boolean;
}) {
  const unanswered = showMissing && value === undefined;
  return (
    <fieldset
      style={{
        border: "none",
        borderLeft: `3px solid ${unanswered ? MISS : "transparent"}`,
        padding: "0 0 0 12px",
        margin: "0 0 30px",
      }}
    >
      <legend style={{ padding: 0, marginBottom: 4 }}>
        <span style={{ fontSize: 14, fontWeight: 600 }}>{title}</span>
      </legend>
      <div style={{ fontSize: 14, marginBottom: 12 }}>{question}</div>
      <div style={{ display: "flex", gap: 2 }}>
        {Array.from({ length: steps }, (_, i) => {
          const score = i * stepSize;
          const active = value === score;
          return (
            <label
              key={score}
              title={String(score)}
              style={{
                flex: 1,
                height: 34,
                border: `1px solid ${active ? ACCENT : LINE}`,
                background: active ? ACCENT : "white",
                borderRadius: 3,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <input
                type="radio"
                name={id}
                checked={active}
                onChange={() => onChange(score)}
                aria-label={`${title}: ${score} out of 100`}
                style={{ position: "absolute", opacity: 0, width: 1, height: 1 }}
              />
            </label>
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: MUTED, marginTop: 6 }}>
        <span>{lowAnchor}</span>
        <span>{highAnchor}</span>
      </div>
    </fieldset>
  );
}

// ── Free text ───────────────────────────────────────────────────────────────

export function OpenQuestion({
  id,
  text,
  value,
  onChange,
  placeholder,
  showMissing,
}: {
  id: string;
  text: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  showMissing?: boolean;
}) {
  return (
    <div
      data-q={id}
      style={{
        marginBottom: 24,
        borderLeft: `3px solid ${showMissing ? MISS : "transparent"}`,
        paddingLeft: 12,
      }}
    >
      <label htmlFor={id} style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 9 }}>
        {text}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder={placeholder}
        style={{
          width: "100%",
          boxSizing: "border-box",
          border: `1px solid ${showMissing ? MISS : LINE}`,
          borderRadius: 8,
          padding: 11,
          fontSize: 14,
          fontFamily: "inherit",
          resize: "vertical",
        }}
      />
    </div>
  );
}
