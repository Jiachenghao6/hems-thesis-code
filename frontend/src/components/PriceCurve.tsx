/**
 * PriceCurve.tsx
 * Custom SVG line chart showing 24 hourly day-ahead prices.
 * Overlays a green renewable-energy-share curve on a secondary right-hand axis.
 * Highlights recommended time slots as coloured bands.
 */
import type { PricePoint, Recommendation } from "../types";

interface Props {
  prices: PricePoint[];
  recommendations: Recommendation[];
}

const W = 680;
const H = 210;
const PAD = { top: 14, right: 48, bottom: 30, left: 54 };
const INNER_W = W - PAD.left - PAD.right;
const INNER_H = H - PAD.top - PAD.bottom;

const APPLIANCE_COLORS = [
  "rgba(37,99,235,0.18)",
  "rgba(16,163,74,0.18)",
  "rgba(234,88,12,0.18)",
  "rgba(147,51,234,0.18)",
];

function lerp(v: number, inMin: number, inMax: number, outMin: number, outMax: number): number {
  return outMin + ((v - inMin) / (inMax - inMin)) * (outMax - outMin);
}

export default function PriceCurve({ prices, recommendations }: Props) {
  if (prices.length === 0)
    return (
      <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center", color: "#94a3b8" }}>
        Loading prices…
      </div>
    );

  // ── Price axis (left) ──────────────────────────────────────────────────
  const vals = prices.map((p) => p.price_eur_mwh);
  const rawMin = Math.min(...vals);
  const rawMax = Math.max(...vals);
  const yMin = rawMin < 0 ? rawMin * 1.15 : rawMin * 0.85;
  const yMax = rawMax * 1.1;

  const xScale = (hour: number) => lerp(hour, 0, 23, 0, INNER_W);
  const yScale = (price: number) => lerp(price, yMin, yMax, INNER_H, 0);

  // Build price SVG path
  const pricePoints = prices.map(
    (p) => `${xScale(p.hour).toFixed(1)},${yScale(p.price_eur_mwh).toFixed(1)}`
  );
  const linePath = "M" + pricePoints.join("L");

  // Area fill path
  const zeroY = yScale(0).toFixed(1);
  const areaPath =
    linePath +
    `L${xScale(23).toFixed(1)},${zeroY}L${xScale(0).toFixed(1)},${zeroY}Z`;

  // Y-axis ticks (5 ticks)
  const yTicks: number[] = [];
  const step = (yMax - yMin) / 4;
  for (let i = 0; i <= 4; i++) yTicks.push(yMin + step * i);

  const hasNegative = rawMin < 0;

  // ── Renewable axis (right, 0–100%) ────────────────────────────────────
  const hasRenewable = prices.some((p) => p.renewable_share !== undefined);
  const renewScale = (share: number) => lerp(share, 0, 1, INNER_H, 0);

  // Build renewable SVG path (dashed green line)
  const renewPath = hasRenewable
    ? "M" +
      prices
        .map((p) => `${xScale(p.hour).toFixed(1)},${renewScale(p.renewable_share ?? 0).toFixed(1)}`)
        .join("L")
    : "";

  // Green axis ticks: 0%, 25%, 50%, 75%, 100%
  const renewTicks = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: "100%", height: "auto", display: "block", fontFamily: "inherit" }}
    >
      <defs>
        <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#2563eb" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="renewGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#16a34a" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#16a34a" stopOpacity="0.01" />
        </linearGradient>
        <clipPath id="chartClip">
          <rect x="0" y="0" width={INNER_W} height={INNER_H} />
        </clipPath>
      </defs>

      <g transform={`translate(${PAD.left},${PAD.top})`}>
        {/* ── Recommended slot bands ──────────────────────────────── */}
        {recommendations.map((rec, i) => {
          const x1 = xScale(rec.recommended_start);
          const x2 = xScale(Math.min(rec.recommended_end, 23));
          return (
            <rect
              key={rec.appliance_id}
              x={x1}
              y={0}
              width={x2 - x1}
              height={INNER_H}
              fill={APPLIANCE_COLORS[i % APPLIANCE_COLORS.length]}
              clipPath="url(#chartClip)"
            />
          );
        })}

        {/* ── Y-axis grid lines (price) ───────────────────────────── */}
        {yTicks.map((tick) => (
          <line
            key={tick}
            x1={0}
            y1={yScale(tick)}
            x2={INNER_W}
            y2={yScale(tick)}
            stroke="#e2e8f0"
            strokeWidth={1}
          />
        ))}

        {/* Zero line (negative price scenarios) */}
        {hasNegative && (
          <line
            x1={0}
            y1={yScale(0)}
            x2={INNER_W}
            y2={yScale(0)}
            stroke="#94a3b8"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
        )}

        {/* ── Renewable area fill ─────────────────────────────────── */}
        {hasRenewable && (
          <path
            d={
              renewPath +
              `L${xScale(23).toFixed(1)},${renewScale(0).toFixed(1)}` +
              `L${xScale(0).toFixed(1)},${renewScale(0).toFixed(1)}Z`
            }
            fill="url(#renewGrad)"
            clipPath="url(#chartClip)"
          />
        )}

        {/* ── Price area fill ─────────────────────────────────────── */}
        <path d={areaPath} fill="url(#priceGrad)" clipPath="url(#chartClip)" />

        {/* ── Price line (blue) ───────────────────────────────────── */}
        <path
          d={linePath}
          fill="none"
          stroke="#2563eb"
          strokeWidth={2}
          clipPath="url(#chartClip)"
        />

        {/* ── Renewable line (green, dashed) ──────────────────────── */}
        {hasRenewable && (
          <path
            d={renewPath}
            fill="none"
            stroke="#16a34a"
            strokeWidth={1.5}
            strokeDasharray="5 3"
            clipPath="url(#chartClip)"
          />
        )}

        {/* ── Left Y-axis labels (price) ──────────────────────────── */}
        {yTicks.map((tick) => (
          <text
            key={tick}
            x={-6}
            y={yScale(tick) + 4}
            textAnchor="end"
            fontSize={10}
            fill="#64748b"
          >
            {tick >= 1000 ? `${(tick / 1000).toFixed(1)}k` : Math.round(tick)}
          </text>
        ))}

        {/* ── Right Y-axis labels (renewable %) ───────────────────── */}
        {hasRenewable &&
          renewTicks.map((tick) => (
            <text
              key={tick}
              x={INNER_W + 6}
              y={renewScale(tick) + 4}
              textAnchor="start"
              fontSize={10}
              fill="#16a34a"
            >
              {Math.round(tick * 100)}%
            </text>
          ))}

        {/* ── X-axis labels every 3 hours ─────────────────────────── */}
        {[0, 3, 6, 9, 12, 15, 18, 21, 23].map((h) => (
          <text
            key={h}
            x={xScale(h)}
            y={INNER_H + 16}
            textAnchor="middle"
            fontSize={10}
            fill="#64748b"
          >
            {h.toString().padStart(2, "0")}h
          </text>
        ))}

        {/* ── Left axis unit label ─────────────────────────────────── */}
        <text
          x={-38}
          y={INNER_H / 2}
          textAnchor="middle"
          fontSize={9}
          fill="#94a3b8"
          transform={`rotate(-90, -38, ${INNER_H / 2})`}
        >
          €/MWh
        </text>

        {/* ── Right axis unit label ────────────────────────────────── */}
        {hasRenewable && (
          <text
            x={INNER_W + 42}
            y={INNER_H / 2}
            textAnchor="middle"
            fontSize={9}
            fill="#16a34a"
            opacity={0.8}
            transform={`rotate(90, ${INNER_W + 42}, ${INNER_H / 2})`}
          >
            Renewable
          </text>
        )}
      </g>

      {/* ── Legend: appliance slots + renewable line ─────────────────── */}
      {(recommendations.length > 0 || hasRenewable) && (
        <g transform={`translate(${PAD.left}, ${H - 4})`}>
          {recommendations.map((rec, i) => (
            <g key={rec.appliance_id} transform={`translate(${i * 155}, 0)`}>
              <rect
                x={0}
                y={-9}
                width={10}
                height={10}
                fill={APPLIANCE_COLORS[i % APPLIANCE_COLORS.length]}
                stroke={["#2563eb", "#16a34a", "#ea580c", "#9333ea"][i % 4]}
                strokeWidth={1}
              />
              <text x={14} y={0} fontSize={9} fill="#64748b">
                {rec.emoji} {rec.appliance_name} (
                {rec.recommended_start.toString().padStart(2, "0")}h–
                {rec.recommended_end.toString().padStart(2, "0")}h)
              </text>
            </g>
          ))}
          {hasRenewable && (
            <g transform={`translate(${recommendations.length * 155}, 0)`}>
              <line x1={0} y1={-4} x2={14} y2={-4} stroke="#16a34a" strokeWidth={1.5} strokeDasharray="4 2" />
              <text x={18} y={0} fontSize={9} fill="#16a34a">
                Renewable share
              </text>
            </g>
          )}
        </g>
      )}
    </svg>
  );
}
