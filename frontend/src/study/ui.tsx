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
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

/**
 * True while the viewport is too narrow to lay a response scale out horizontally.
 *
 * A media query rather than a one-off `window.innerWidth` read: the participant may
 * rotate the phone mid-questionnaire, and a layout that only reacts on mount would
 * leave a scale squeezed into a shape that was measured for the other orientation.
 */
function useNarrow(maxWidth = 560): boolean {
  const query = `(max-width: ${maxWidth}px)`;
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setNarrow(e.matches);
    setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [query]);
  return narrow;
}

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
  const narrow = useNarrow();
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
      {/*
        Grid, not wrapping flex. The previous layout was `flex: 1 1 90px` with
        `flexWrap`, which on a phone put two options per row and left the fifth
        alone on the last row, where `flex-grow` stretched it to the full width:
        measured at 375px, "Strongly agree" was 276px wide against 136px for the
        other four. The most extreme endpoint of the scale was also its largest
        and most isolated target — a response bias built into the layout, on the
        questionnaire that carries the trust measure.

        A grid cannot produce that: every column is `1fr`, so all five options are
        the same width at every viewport size. Below the breakpoint they become a
        single column instead, which keeps them in scale order — a five-point
        scale read as a 2×2×1 block is no longer an ordered line.
      */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: narrow ? "1fr" : `repeat(${labels.length}, 1fr)`,
          gap: 4,
        }}
      >
        {labels.map((label, i) => {
          const v = i + 1;
          const active = value === v;
          return (
            <label
              key={v}
              title={label}
              style={{
                display: "flex",
                flexDirection: narrow ? "row" : "column",
                alignItems: "center",
                justifyContent: narrow ? "flex-start" : "center",
                gap: narrow ? 10 : 5,
                minHeight: narrow ? 44 : undefined,
                padding: narrow ? "8px 12px" : "7px 4px",
                border: `1px solid ${active ? ACCENT : LINE}`,
                background: active ? "#eff6ff" : "white",
                borderRadius: 7,
                cursor: "pointer",
                fontSize: narrow ? 13 : 11,
                color: active ? ACCENT : MUTED,
                textAlign: narrow ? "left" : "center",
                lineHeight: 1.25,
              }}
            >
              <input
                type="radio"
                name={id}
                checked={active}
                onChange={() => onChange(v)}
                style={{ accentColor: ACCENT, margin: 0, flex: "none" }}
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
 * The raw NASA-TLX response format: one line divided into 21 gradations, scored
 * 0–100 in steps of 5. The number of gradations is part of the instrument, not a
 * design choice — scores are only comparable with the published TLX literature if
 * the response format is the same one those studies used.
 *
 * Not a native range input. `<input type=range>` always shows a thumb somewhere,
 * so it cannot represent "not answered yet": the participant would have to be told
 * to move it, and anyone who happened to agree with the default would leave it
 * untouched and be recorded as having answered. A thumb parked at the midpoint
 * also anchors the response toward the middle.
 *
 * The bar itself is the target, not the individual gradations. Twenty-one separate
 * hit boxes across a 375px phone measured 11.3px each — well under the 24px in
 * WCAG 2.5.8 — so an adjacent mis-tap was a silent ±5 error on a dependent
 * variable. Here a press anywhere on the bar picks the nearest gradation and a
 * drag adjusts it, which is how a mark on a paper TLX line works anyway; the
 * gradations stay visible because they are what makes the scale a TLX scale.
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
  const narrow = useNarrow();
  const barRef = useRef<HTMLDivElement>(null);

  /** Map a horizontal page position onto the gradation drawn under it. */
  const pick = (clientX: number) => {
    const bar = barRef.current;
    if (!bar) return;
    const rect = bar.getBoundingClientRect();
    if (rect.width === 0) return;
    const i = Math.floor(((clientX - rect.left) / rect.width) * steps);
    const clamped = Math.min(Math.max(i, 0), steps - 1);
    const next = clamped * stepSize;
    if (next !== value) onChange(next);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const max = (steps - 1) * stepSize;
    // No answer yet: the first key press starts at the end it points away from,
    // rather than silently seeding the midpoint.
    const current = value ?? (e.key === "ArrowLeft" || e.key === "ArrowDown" ? max : 0);
    const moves: Record<string, number> = {
      ArrowLeft: -stepSize,
      ArrowDown: -stepSize,
      ArrowRight: stepSize,
      ArrowUp: stepSize,
    };
    if (e.key in moves) {
      e.preventDefault();
      onChange(Math.min(Math.max(value === undefined ? current : current + moves[e.key], 0), max));
    } else if (e.key === "Home") {
      e.preventDefault();
      onChange(0);
    } else if (e.key === "End") {
      e.preventDefault();
      onChange(max);
    }
  };

  return (
    <fieldset
      data-q={id}
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
      <div
        ref={barRef}
        role="slider"
        tabIndex={0}
        aria-label={`${title}. ${question}`}
        aria-valuemin={0}
        aria-valuemax={(steps - 1) * stepSize}
        aria-valuenow={value}
        aria-valuetext={value === undefined ? "Not answered yet" : `${value} out of 100`}
        onKeyDown={onKeyDown}
        onPointerDown={(e) => {
          // Answer first, capture second. Pointer capture is only an improvement —
          // it keeps a drag tracking after the finger leaves the bar — and some
          // pointer ids cannot be captured. Doing it first meant a throw here
          // swallowed the answer entirely.
          pick(e.clientX);
          try {
            e.currentTarget.setPointerCapture(e.pointerId);
          } catch {
            /* drag still works while the pointer stays over the bar */
          }
        }}
        onPointerMove={(e) => {
          if (e.currentTarget.hasPointerCapture(e.pointerId)) pick(e.clientX);
        }}
        style={{
          display: "flex",
          height: narrow ? 44 : 34,
          border: `1px solid ${LINE}`,
          borderRadius: 5,
          overflow: "hidden",
          cursor: "pointer",
          // Sideways drags are ours, vertical ones stay with the browser. Six of
          // these scales sit on one page, so taking the whole gesture would make
          // a swipe that happens to start on a bar fail to scroll the page.
          touchAction: "pan-y",
        }}
      >
        {Array.from({ length: steps }, (_, i) => {
          const score = i * stepSize;
          return (
            <div
              key={score}
              title={String(score)}
              style={{
                flex: 1,
                borderLeft: i === 0 ? "none" : `1px solid ${LINE}`,
                background: value === score ? ACCENT : "white",
                // The gradations are drawn, not clicked — the bar handles pointers,
                // so each cell keeps its full share of the width as a hit region.
                pointerEvents: "none",
              }}
            />
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
