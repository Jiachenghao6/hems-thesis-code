/**
 * TradeoffSlider.tsx
 * Single 100% bar split into three segments by two draggable dividers.
 *
 * Why a divider bar rather than three sliders
 * -------------------------------------------
 * The three priorities always sum to 100%, so the parameter space has only two
 * degrees of freedom. Three independent sliders offer three controls for those two
 * degrees, and the surplus has to be absorbed by moving the two sliders the user did
 * not touch. That is what made the earlier version feel arbitrary: the constraint was
 * real but invisible, and users could only infer it from the unexplained movement.
 *
 * Two dividers on one bar match the two degrees of freedom exactly, and make the
 * constraint visible instead of surprising — dragging a boundary between two adjacent
 * quantities is self-evidently a trade: what one gains, its neighbour loses.
 *
 * Dividers push rather than block: dragging the left divider all the way to the right
 * carries the right divider with it, giving Cost = 100%. Blocking would make some
 * settings unreachable without a two-step manoeuvre.
 *
 * Supervisor feedback (2026-06-16) asked for the three values to sum to 100% so the
 * percentage wording would fit. This satisfies that more directly than a constrained
 * three-slider design.
 */
import { useCallback, useRef } from "react";
import type { SliderValues } from "../types";

interface Props {
  values: SliderValues;
  onChange: (next: SliderValues) => void;
  disabled?: boolean;
}

// The hints are plain description, not jargon: "high renewable share" is a phrase from
// the energy literature, and a participant recruited off Prolific has no reason to know
// it — many of them are not native English speakers either. "More wind and solar" says
// the same thing and matches the wording the explanations already use.
//
// These must stay identical to the illustration in Tutorial.tsx.
const SEGMENTS = [
  { key: "cost" as const, label: "Cost", emoji: "💶", colour: "#2563eb", hint: "The cheapest hours" },
  { key: "green" as const, label: "Green", emoji: "🌱", colour: "#16a34a", hint: "More wind and solar" },
  { key: "convenience" as const, label: "Convenience", emoji: "⏰", colour: "#d97706", hint: "Close to your usual time" },
];

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

/** Boundary positions along the bar, derived from the three values. */
function toBoundaries(v: SliderValues): [number, number] {
  return [clamp(v.cost), clamp(v.cost + v.green)];
}

/** Boundaries back to values; the last segment absorbs rounding so the total is exactly 100. */
function toValues(c0: number, c1: number): SliderValues {
  const cost = clamp(c0);
  const green = clamp(c1) - cost;
  return { cost, green, convenience: 100 - cost - green };
}

export default function TradeoffSlider({ values, onChange, disabled }: Props) {
  const barRef = useRef<HTMLDivElement>(null);
  const [c0, c1] = toBoundaries(values);
  const total = values.cost + values.green + values.convenience;

  /** `which` 0 = Cost/Green divider, 1 = Green/Convenience divider. Pushes the other. */
  const moveDivider = useCallback(
    (which: 0 | 1, target: number) => {
      const t = clamp(target);
      let a = c0;
      let b = c1;
      if (which === 0) {
        a = t;
        if (a > b) b = a;          // push the right divider ahead
      } else {
        b = t;
        if (b < a) a = b;          // push the left divider back
      }
      onChange(toValues(a, b));
    },
    [c0, c1, onChange]
  );

  const startDrag = (which: 0 | 1) => (e: React.PointerEvent<HTMLButtonElement>) => {
    if (disabled) return;
    e.preventDefault();
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);

    const onMove = (ev: PointerEvent) => {
      const rect = barRef.current?.getBoundingClientRect();
      if (!rect || rect.width === 0) return;
      moveDivider(which, ((ev.clientX - rect.left) / rect.width) * 100);
    };
    const onUp = () => {
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
    };
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
  };

  const onKey = (which: 0 | 1) => (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;
    const step = e.shiftKey ? 10 : 1;
    const current = which === 0 ? c0 : c1;
    let next: number | null = null;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") next = current - step;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") next = current + step;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = 100;
    if (next === null) return;
    e.preventDefault();
    moveDivider(which, next);
  };

  const dividerStyle = (pos: number): React.CSSProperties => ({
    position: "absolute",
    top: -4,
    bottom: -4,
    left: `${pos}%`,
    width: 26,
    marginLeft: -13,
    padding: 0,
    border: 0,
    background: "transparent",
    cursor: disabled ? "not-allowed" : "ew-resize",
    touchAction: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 3,
  });

  const grip: React.CSSProperties = {
    width: 5,
    height: 42,
    borderRadius: 3,
    background: "#fff",
    boxShadow: "0 0 0 1.5px rgba(15,23,42,.35), 0 2px 6px rgba(0,0,0,.3)",
  };

  return (
    <div style={{ background: "white", border: "1px solid #e2e8f0", borderRadius: 12, padding: "16px 18px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#1e293b" }}>⚖️ Your Priorities</h2>
        <span style={{ fontSize: 12, color: total === 100 ? "#94a3b8" : "#dc2626", fontWeight: 600 }}>
          {total}% of 100%
        </span>
      </div>
      <p style={{ margin: "0 0 12px", fontSize: 12, color: "#64748b" }}>
        {/* Same words as the tutorial illustration: "the white lines between the
            colours" names something the participant can see, where "the dividers"
            names an interface part they have to identify first. And it is weight the
            bar splits, not attention. */}
        Drag the white lines between the colours to change the balance. Giving more to one always takes it from
        another.
      </p>

      {/*
        Legend stays visible at all times. A segment squeezed to 0% disappears from the
        bar, and without a legend the participant would have no way to see which one it
        was or that it still exists.
      */}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 9 }}>
        {SEGMENTS.map((s) => (
          <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, fontWeight: 600, color: "#334155" }}>
            <span aria-hidden="true" style={{ width: 12, height: 12, borderRadius: 3, background: s.colour, flex: "none" }} />
            {s.label}
            <span style={{ fontVariantNumeric: "tabular-nums", color: "#0f172a" }}>{values[s.key]}%</span>
          </span>
        ))}
      </div>

      <div
        ref={barRef}
        style={{
          position: "relative",
          height: 56,
          borderRadius: 9,
          display: "flex",
          userSelect: "none",
          border: "1px solid #cbd5e1",
          background: "#f8fafc",
          overflow: "hidden",
          opacity: disabled ? 0.6 : 1,
        }}
      >
        {SEGMENTS.map((s) => {
          const pct = values[s.key];
          return (
            <div
              key={s.key}
              style={{
                width: `${pct}%`,
                background: s.colour,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 12.5,
                fontWeight: 700,
                color: "#fff",
                textShadow: "0 1px 2px rgba(0,0,0,.35)",
                overflow: "hidden",
                whiteSpace: "nowrap",
              }}
            >
              {/* Only label the segment when it is wide enough to read; otherwise the legend carries it. */}
              {pct >= 22 ? `${s.emoji} ${pct}%` : pct >= 10 ? `${pct}%` : ""}
            </div>
          );
        })}

        <button
          type="button"
          role="slider"
          aria-label="Boundary between Cost and Green"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={c0}
          aria-valuetext={`Cost ${values.cost}%, Green ${values.green}%`}
          disabled={disabled}
          style={dividerStyle(c0)}
          onPointerDown={startDrag(0)}
          onKeyDown={onKey(0)}
        >
          <span aria-hidden="true" style={grip} />
        </button>

        <button
          type="button"
          role="slider"
          aria-label="Boundary between Green and Convenience"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={c1}
          aria-valuetext={`Green ${values.green}%, Convenience ${values.convenience}%`}
          disabled={disabled}
          style={dividerStyle(c1)}
          onPointerDown={startDrag(1)}
          onKeyDown={onKey(1)}
        >
          <span aria-hidden="true" style={grip} />
        </button>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
        {SEGMENTS.map((s) => (
          <div key={s.key} style={{ flex: 1, fontSize: 11, color: "#94a3b8", lineHeight: 1.5 }}>
            {s.hint}
          </div>
        ))}
      </div>
    </div>
  );
}
