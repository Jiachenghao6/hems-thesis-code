/**
 * ShapChart.tsx — Group B (static SHAP explanation)
 * Horizontal bar chart showing feature contributions.
 * Fixed at recommendation time — does NOT update when the slider moves.
 */
import type { ShapFeature } from "../types";

interface Props {
  features: ShapFeature[];
}

const BAR_H = 22;
const GAP = 6;
const LABEL_W = 180;
const BAR_MAX_W = 160;
const VALUE_W = 40;
const CHART_W = LABEL_W + BAR_MAX_W + VALUE_W + 20;

export default function ShapChart({ features }: Props) {
  const maxVal = Math.max(...features.map((f) => Math.abs(f.value)), 0.01);

  const totalH = (BAR_H + GAP) * features.length + 24;

  return (
    <div>
      {/*
        This label used to read "Feature importance (SHAP) — fixed at recommendation
        time". That told condition-B participants their explanation would not update,
        which is precisely the manipulation and must not be disclosed — the same reason
        the condition badge and banner were removed from App.tsx. It also used jargon
        ("SHAP") that condition A never encounters, adding a comprehension asymmetry on
        top of the intended contrast.
      */}
      <div style={{ fontSize: 12, color: "#64748b", marginBottom: 10 }}>
        What influenced this recommendation
      </div>
      <svg
        viewBox={`0 0 ${CHART_W} ${totalH}`}
        style={{ width: "100%", maxWidth: CHART_W, display: "block", fontFamily: "inherit" }}
      >
        {/* Zero axis */}
        <line
          x1={LABEL_W + 5}
          y1={0}
          x2={LABEL_W + 5}
          y2={totalH}
          stroke="#e2e8f0"
          strokeWidth={1}
        />

        {features.map((feat, i) => {
          const y = i * (BAR_H + GAP) + 4;
          const isPos = feat.direction === "positive";
          const barW = (feat.value / maxVal) * BAR_MAX_W;
          const color = isPos ? "#16a34a" : "#dc2626";
          const barX = LABEL_W + 5;

          return (
            <g key={feat.feature}>
              {/* Feature label */}
              <text
                x={LABEL_W - 6}
                y={y + BAR_H / 2 + 4}
                textAnchor="end"
                fontSize={11}
                fill="#334155"
              >
                {feat.label}
              </text>

              {/* Bar */}
              <rect
                x={barX}
                y={y + 3}
                width={Math.max(barW, 2)}
                height={BAR_H - 6}
                fill={color}
                fillOpacity={0.7}
                rx={3}
              />

              {/* Value */}
              <text
                x={barX + Math.max(barW, 2) + 6}
                y={y + BAR_H / 2 + 4}
                fontSize={10}
                fill={color}
                fontWeight={600}
              >
                {isPos ? "+" : "−"}{feat.value.toFixed(3)}
              </text>
            </g>
          );
        })}

        {/* X axis labels */}
        <text x={LABEL_W + 5} y={totalH - 2} textAnchor="middle" fontSize={9} fill="#94a3b8">
          0
        </text>
        <text x={LABEL_W + 5 + BAR_MAX_W} y={totalH - 2} textAnchor="end" fontSize={9} fill="#94a3b8">
          +{maxVal.toFixed(2)}
        </text>
      </svg>
    </div>
  );
}
