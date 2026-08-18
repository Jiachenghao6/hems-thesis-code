/**
 * RecommendationCard.tsx
 * Single appliance recommendation with accept/reject buttons.
 * Renders either the causal explanation (Group A) or SHAP chart (Group B).
 */
import { useState } from "react";
import type { Recommendation, Condition } from "../types";
import ShapChart from "./ShapChart";

interface Props {
  rec: Recommendation;
  condition: Condition;
  onAccept: (applianceId: string) => void;
  onReject: (applianceId: string) => void;
}

function fmtHour(h: number): string {
  return `${h.toString().padStart(2, "0")}:00`;
}

function fmtPrice(p: number): string {
  return `${p >= 0 ? "" : "−"}${Math.abs(p).toFixed(0)} €/MWh`;
}

function savingsColor(eur: number): string {
  if (eur > 0.01) return "#16a34a";
  if (eur < -0.001) return "#dc2626";
  return "#64748b";
}

export default function RecommendationCard({ rec, condition, onAccept, onReject }: Props) {
  const [decision, setDecision] = useState<"accepted" | "rejected" | null>(null);

  const isShifted = rec.recommended_start !== rec.default_start;
  const savings = rec.savings_eur;

  const handleAccept = () => {
    setDecision("accepted");
    onAccept(rec.appliance_id);
  };

  const handleReject = () => {
    setDecision("rejected");
    onReject(rec.appliance_id);
  };

  return (
    <div
      style={{
        border: `1.5px solid ${decision === "accepted" ? "#86efac" : decision === "rejected" ? "#fca5a5" : "#e2e8f0"}`,
        borderRadius: 12,
        padding: "16px 18px",
        background: decision === "accepted" ? "#f0fdf4" : decision === "rejected" ? "#fff1f2" : "white",
        transition: "border-color 0.2s, background 0.2s",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <span style={{ fontSize: 22 }}>{rec.emoji}</span>
          <span style={{ fontWeight: 600, fontSize: 15, color: "#1e293b", marginLeft: 8 }}>
            {rec.appliance_name}
          </span>
          <span style={{ fontSize: 12, color: "#94a3b8", marginLeft: 8 }}>
            ({rec.duration_hours}h • {rec.kwh_total} kWh)
          </span>
        </div>
        {decision && (
          <span
            style={{
              fontSize: 12, fontWeight: 600, padding: "2px 10px", borderRadius: 20,
              background: decision === "accepted" ? "#dcfce7" : "#fee2e2",
              color: decision === "accepted" ? "#16a34a" : "#dc2626",
            }}
          >
            {decision === "accepted" ? "✓ Accepted" : "✗ Rejected"}
          </span>
        )}
      </div>

      {/* Timing comparison */}
      <div style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 120, background: "#f1f5f9", borderRadius: 8, padding: "8px 12px" }}>
          <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>Your usual time</div>
          <div style={{ fontWeight: 600, fontSize: 14, color: "#475569" }}>
            {fmtHour(rec.default_start)} – {fmtHour(rec.default_start + rec.duration_hours)}
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8" }}>
            avg {fmtPrice(rec.avg_price_default_eur_mwh)}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", color: "#94a3b8", fontSize: 18 }}>
          {isShifted ? "→" : "="}
        </div>

        <div
          style={{
            flex: 1, minWidth: 120,
            background: isShifted ? "#eff6ff" : "#f1f5f9",
            border: isShifted ? "1px solid #bfdbfe" : "none",
            borderRadius: 8, padding: "8px 12px",
          }}
        >
          <div style={{ fontSize: 11, color: "#2563eb", marginBottom: 2, fontWeight: 500 }}>
            {isShifted ? "Recommended" : "No change needed"}
          </div>
          <div style={{ fontWeight: 700, fontSize: 14, color: "#1e293b" }}>
            {fmtHour(rec.recommended_start)} – {fmtHour(rec.recommended_end)}
          </div>
          <div style={{ fontSize: 11, color: "#64748b" }}>
            avg {fmtPrice(rec.avg_price_recommended_eur_mwh)}
          </div>
        </div>

        {/* Savings badge */}
        {Math.abs(savings) > 0.001 && (
          <div style={{ minWidth: 80, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
            <div style={{ fontSize: 11, color: "#94a3b8" }}>saving</div>
            <div style={{ fontWeight: 700, fontSize: 16, color: savingsColor(savings) }}>
              {savings > 0 ? "+" : ""}{(savings * 100).toFixed(1)} ct
            </div>
          </div>
        )}
      </div>

      {/* Explanation (condition-dependent) */}
      {condition === "A" && rec.explanation && (
        <div
          style={{
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 8,
            padding: "10px 13px",
            fontSize: 13,
            color: "#1e40af",
            lineHeight: 1.55,
            marginBottom: 14,
          }}
        >
          <span style={{ fontWeight: 600, marginRight: 6 }}>💡</span>
          {rec.explanation}
        </div>
      )}

      {condition === "B" && rec.shap_data && (
        <div style={{ marginBottom: 14 }}>
          <ShapChart features={rec.shap_data} />
        </div>
      )}

      {/* Accept / Reject buttons */}
      {!decision && (
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={handleAccept}
            style={{
              flex: 1, padding: "9px 0", borderRadius: 8,
              background: "#16a34a", color: "white",
              border: "none", fontWeight: 600, fontSize: 14,
              cursor: "pointer",
            }}
          >
            ✓ Accept
          </button>
          <button
            onClick={handleReject}
            style={{
              flex: 1, padding: "9px 0", borderRadius: 8,
              background: "white", color: "#dc2626",
              border: "1.5px solid #fca5a5", fontWeight: 600, fontSize: 14,
              cursor: "pointer",
            }}
          >
            ✗ Reject
          </button>
        </div>
      )}
    </div>
  );
}
