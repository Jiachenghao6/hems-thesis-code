/**
 * TradeoffSlider.tsx
 * Three independent sliders (0–100 each) for Cost / Green / Convenience.
 * Internal weights are normalised to sum=1 when sent to the API.
 */
import type { SliderValues } from "../types";

interface Props {
  values: SliderValues;
  onChange: (next: SliderValues) => void;
  disabled?: boolean;
}

interface SliderCfg {
  key: keyof SliderValues;
  label: string;
  emoji: string;
  color: string;
  trackColor: string;
  description: string;
}

const SLIDERS: SliderCfg[] = [
  {
    key: "cost",
    label: "Cost",
    emoji: "💶",
    color: "#2563eb",
    trackColor: "#dbeafe",
    description: "Shift appliances to cheapest hours",
  },
  {
    key: "green",
    label: "Green",
    emoji: "🌱",
    color: "#16a34a",
    trackColor: "#dcfce7",
    description: "Favour high renewable-energy windows",
  },
  {
    key: "convenience",
    label: "Convenience",
    emoji: "⏰",
    color: "#d97706",
    trackColor: "#fef3c7",
    description: "Stay close to your usual routine",
  },
];

function normalise(v: SliderValues): { cost: number; green: number; convenience: number } {
  const total = v.cost + v.green + v.convenience;
  if (total === 0) return { cost: 0.33, green: 0.33, convenience: 0.34 };
  return {
    cost: Math.round((v.cost / total) * 100),
    green: Math.round((v.green / total) * 100),
    convenience: Math.round((v.convenience / total) * 100),
  };
}

export default function TradeoffSlider({ values, onChange, disabled }: Props) {
  const pct = normalise(values);

  const handleReset = () => onChange({ cost: 33, green: 33, convenience: 34 });

  return (
    <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 12, padding: "18px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1e293b" }}>
          Trade-off Preferences
        </h3>
        <button
          onClick={handleReset}
          disabled={disabled}
          style={{
            fontSize: 12, padding: "3px 10px", border: "1px solid #cbd5e1",
            borderRadius: 6, background: "white", cursor: "pointer", color: "#475569",
          }}
        >
          Reset
        </button>
      </div>

      {SLIDERS.map((cfg) => {
        const val = values[cfg.key];
        const effectivePct = pct[cfg.key];
        return (
          <div key={cfg.key} style={{ marginBottom: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontWeight: 500, fontSize: 14, color: "#334155" }}>
                {cfg.emoji} {cfg.label}
                <span style={{ fontWeight: 400, color: "#94a3b8", fontSize: 12, marginLeft: 8 }}>
                  {cfg.description}
                </span>
              </span>
              <span style={{ fontWeight: 700, fontSize: 13, color: cfg.color, minWidth: 38, textAlign: "right" }}>
                {effectivePct}%
              </span>
            </div>
            <div style={{ position: "relative", height: 8 }}>
              {/* Track */}
              <div style={{ position: "absolute", top: 2, left: 0, right: 0, height: 4, borderRadius: 2, background: cfg.trackColor }} />
              {/* Fill */}
              <div
                style={{
                  position: "absolute", top: 2, left: 0, height: 4, borderRadius: 2,
                  background: cfg.color, width: `${val}%`, transition: "width 0.1s",
                }}
              />
              <input
                type="range"
                min={0}
                max={100}
                value={val}
                disabled={disabled}
                onChange={(e) => onChange({ ...values, [cfg.key]: Number(e.target.value) })}
                style={{
                  position: "absolute", top: 0, left: 0, width: "100%", height: 8,
                  opacity: 0, cursor: disabled ? "not-allowed" : "pointer", margin: 0,
                }}
              />
              {/* Thumb visual */}
              <div
                style={{
                  position: "absolute", top: -3, left: `calc(${val}% - 7px)`,
                  width: 14, height: 14, borderRadius: "50%", background: cfg.color,
                  border: "2px solid white", boxShadow: "0 1px 3px rgba(0,0,0,.25)",
                  pointerEvents: "none", transition: "left 0.1s",
                }}
              />
            </div>
          </div>
        );
      })}

      {/* Visual weight breakdown bar */}
      <div style={{ marginTop: 8 }}>
        <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden" }}>
          <div style={{ width: `${pct.cost}%`, background: "#2563eb", transition: "width 0.2s" }} />
          <div style={{ width: `${pct.green}%`, background: "#16a34a", transition: "width 0.2s" }} />
          <div style={{ width: `${pct.convenience}%`, background: "#d97706", transition: "width 0.2s" }} />
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 5, justifyContent: "center" }}>
          {SLIDERS.map((cfg) => (
            <span key={cfg.key} style={{ fontSize: 11, color: cfg.color }}>
              {cfg.emoji} {cfg.label} {pct[cfg.key]}%
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
