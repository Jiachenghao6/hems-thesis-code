/**
 * TradeoffSlider.tsx
 * Three trade-off sliders (Cost / Green / Convenience) constrained to sum to 100%.
 *
 * Rationale (supervisor feedback, 2026-06-16): with three independent 0–100 sliders
 * the percentage wording does not fit — the values could sum to 300%. A constrained
 * sum also matches the "trade-off" semantics: raising one priority must cost another.
 *
 * Redistribution rule: when one slider moves to `v`, the remaining budget (100 − v)
 * is split across the other two *in proportion to their current values*, so the user's
 * existing balance between them is preserved. If both are at 0, the budget is split evenly.
 * Rounding error is absorbed by the larger of the two so the total is always exactly 100.
 */
import type { SliderValues } from "../types";

interface Props {
  values: SliderValues;
  onChange: (next: SliderValues) => void;
  disabled?: boolean;
}

type Key = keyof SliderValues;

interface SliderCfg {
  key: Key;
  label: string;
  emoji: string;
  description: string;
}

const SLIDERS: SliderCfg[] = [
  { key: "cost",        label: "Cost",        emoji: "💶", description: "Shift appliances to cheapest hours" },
  { key: "green",       label: "Green",       emoji: "🌱", description: "Favour high renewable-energy windows" },
  { key: "convenience", label: "Convenience", emoji: "⏰", description: "Stay close to your usual routine" },
];

/**
 * Move `moved` to `target` and redistribute the remaining budget across the other
 * two keys proportionally. Guarantees the three values are integers summing to 100.
 */
export function redistribute(values: SliderValues, moved: Key, target: number): SliderValues {
  const v = Math.max(0, Math.min(100, Math.round(target)));
  const others = (["cost", "green", "convenience"] as Key[]).filter((k) => k !== moved);
  const [a, b] = others;
  const budget = 100 - v;
  const otherSum = values[a] + values[b];

  let va: number;
  if (otherSum === 0) {
    va = Math.round(budget / 2);
  } else {
    va = Math.round((values[a] / otherSum) * budget);
  }
  va = Math.max(0, Math.min(budget, va));
  const vb = budget - va;

  return { ...values, [moved]: v, [a]: va, [b]: vb } as SliderValues;
}

export default function TradeoffSlider({ values, onChange, disabled }: Props) {
  const total = values.cost + values.green + values.convenience;

  return (
    <div
      style={{
        background: "white",
        border: "1px solid #e2e8f0",
        borderRadius: 12,
        padding: "16px 18px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
          ⚖️ Your Priorities
        </h2>
        <span style={{ fontSize: 12, color: total === 100 ? "#94a3b8" : "#dc2626", fontWeight: 600 }}>
          {total}% of 100%
        </span>
      </div>
      <p style={{ margin: "0 0 14px", fontSize: 12, color: "#64748b" }}>
        These three always add up to 100%. Giving more weight to one priority takes weight away from the others.
      </p>

      {SLIDERS.map((cfg) => (
        <div key={cfg.key} style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
            <label htmlFor={`slider-${cfg.key}`} style={{ fontSize: 13, fontWeight: 600, color: "#334155" }}>
              <span aria-hidden="true" style={{ marginRight: 6 }}>{cfg.emoji}</span>
              {cfg.label}
            </label>
            <span style={{ fontSize: 13, fontWeight: 700, color: "#334155", fontVariantNumeric: "tabular-nums" }}>
              {values[cfg.key]}%
            </span>
          </div>

          <input
            id={`slider-${cfg.key}`}
            type="range"
            min={0}
            max={100}
            step={1}
            value={values[cfg.key]}
            disabled={disabled}
            aria-label={`${cfg.label} priority, ${values[cfg.key]} percent`}
            onChange={(e) => onChange(redistribute(values, cfg.key, Number(e.target.value)))}
            style={{
              width: "100%",
              accentColor: "#475569",
              cursor: disabled ? "not-allowed" : "pointer",
            }}
          />

          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{cfg.description}</div>
        </div>
      ))}
    </div>
  );
}
