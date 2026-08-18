/**
 * App.tsx — HEMS Demo
 *
 * A/B experiment interface:
 *   Condition A — Trade-off Slider + Interactive Causal Explanations (updates with slider)
 *   Condition B — Trade-off Slider + Static SHAP feature-importance chart (fixed)
 *
 * Condition is currently taken from the URL param ?condition=A|B.
 * TODO (before the study): replace with server-side block randomisation via
 * /api/session, so assignment is random and balanced across the two groups.
 * See AB_COMPARABILITY.md §5.1 P4 in the thesis repo.
 *
 * Comparability (supervisor feedback 2026-06-16): nothing in the shared UI may
 * reveal which condition a participant is in, or that conditions exist at all.
 * The condition badge, the banner describing the manipulation, and the exposed
 * participant id / log-export link were removed for this reason.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import type { Condition, ScenarioId, SliderValues, PricePoint, Recommendation, ScenarioMeta } from "./types";
import { getPrices, getRecommendations, getScenarios, logEvent } from "./api";
import PriceCurve from "./components/PriceCurve";
import TradeoffSlider from "./components/TradeoffSlider";
import RecommendationCard from "./components/RecommendationCard";

// ── Helpers ──────────────────────────────────────────────────────────────────

function getConditionFromURL(): Condition {
  const p = new URLSearchParams(window.location.search).get("condition");
  return p === "B" ? "B" : "A";
}

function getParticipantId(): string {
  const p = new URLSearchParams(window.location.search).get("pid");
  return p || "demo-" + Math.random().toString(36).slice(2, 8);
}

const DEFAULT_SLIDERS: SliderValues = { cost: 33, green: 33, convenience: 34 };

const SCENARIO_OPTIONS: { id: ScenarioId; short: string }[] = [
  { id: "live", short: "Live (aWATTar DE)" },
  { id: "S1", short: "S1 · Extreme High" },
  { id: "S2", short: "S2 · Negative Prices" },
  { id: "S3", short: "S3 · High Volatility" },
  { id: "S4", short: "S4 · Low Stable" },
  { id: "S5", short: "S5 · Duck Curve" },
];

// ── Main component ────────────────────────────────────────────────────────────

export default function App() {
  const condition = getConditionFromURL();
  const participantId = getParticipantId();

  const [scenario, setScenario] = useState<ScenarioId>("S3");
  const [sliders, setSliders] = useState<SliderValues>(DEFAULT_SLIDERS);
  const [prices, setPrices] = useState<PricePoint[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [scenarioMeta, setScenarioMeta] = useState<ScenarioMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  // Debounce slider changes to avoid excessive API calls
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Data fetching ────────────────────────────────────────────────────────

  const fetchPrices = useCallback(async (sc: ScenarioId) => {
    try {
      const p = await getPrices(sc);
      setPrices(p);
    } catch (e) {
      setError(`Failed to fetch prices: ${(e as Error).message}`);
    }
  }, []);

  const fetchRecommendations = useCallback(
    async (sliderVals: SliderValues, sc: ScenarioId) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await getRecommendations(sliderVals, sc, condition);
        setRecommendations(resp.recommendations);
        setLastFetched(new Date());
      } catch (e) {
        setError(`Failed to fetch recommendations: ${(e as Error).message}`);
      } finally {
        setLoading(false);
      }
    },
    [condition]
  );

  // Load scenario metadata once
  useEffect(() => {
    getScenarios()
      .then(setScenarioMeta)
      .catch(() => {});
  }, []);

  // Re-fetch prices when scenario changes
  useEffect(() => {
    fetchPrices(scenario);
  }, [scenario, fetchPrices]);

  // Fetch recommendations on mount
  useEffect(() => {
    fetchRecommendations(sliders, scenario);
    logEvent({ participant_id: participantId, condition, event_type: "page_load", scenario });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch recommendations when scenario changes
  useEffect(() => {
    fetchRecommendations(sliders, scenario);
    logEvent({ participant_id: participantId, condition, event_type: "scenario_change", scenario });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario]);

  // Debounced re-fetch when sliders change
  const handleSliderChange = (next: SliderValues) => {
    setSliders(next);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      fetchRecommendations(next, scenario);
      logEvent({
        participant_id: participantId,
        condition,
        event_type: "slider_move",
        slider_values: next,
        scenario,
      });
    }, 400);
  };

  const handleAccept = (applianceId: string) => {
    logEvent({
      participant_id: participantId,
      condition,
      event_type: "accept",
      appliance_id: applianceId,
      slider_values: sliders,
      scenario,
    });
  };

  const handleReject = (applianceId: string) => {
    logEvent({
      participant_id: participantId,
      condition,
      event_type: "reject",
      appliance_id: applianceId,
      slider_values: sliders,
      scenario,
    });
  };

  const currentMeta = scenarioMeta.find((m) => m.id === scenario);

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", background: "#f8fafc", minHeight: "100vh" }}>
      {/* ── Header ── */}
      <header
        style={{
          background: "white",
          borderBottom: "1px solid #e2e8f0",
          padding: "12px 24px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          position: "sticky", top: 0, zIndex: 10,
          boxShadow: "0 1px 3px rgba(0,0,0,.04)",
        }}
      >
        <div>
          <span style={{ fontWeight: 700, fontSize: 16, color: "#1e293b" }}>⚡ HEMS Demo</span>
          <span style={{ fontSize: 12, color: "#94a3b8", marginLeft: 10 }}>
            Home Energy Management · European Day-Ahead Prices
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value as ScenarioId)}
            style={{
              fontSize: 12, padding: "4px 8px", border: "1px solid #e2e8f0",
              borderRadius: 6, background: "white", color: "#334155", cursor: "pointer",
            }}
          >
            {SCENARIO_OPTIONS.map((s) => (
              <option key={s.id} value={s.id}>{s.short}</option>
            ))}
          </select>
        </div>
      </header>

      <main style={{ maxWidth: 800, margin: "0 auto", padding: "20px 16px 48px" }}>

        {/* Scenario description banner */}
        {currentMeta && (
          <div style={{
            background: "white", border: "1px solid #e2e8f0", borderRadius: 10,
            padding: "10px 16px", marginBottom: 16, fontSize: 13, color: "#475569",
          }}>
            <strong style={{ color: "#1e293b" }}>{currentMeta.label}</strong>
            {" — "}{currentMeta.description}
            <span style={{ color: "#94a3b8", marginLeft: 8 }}>({currentMeta.date_ref})</span>
          </div>
        )}

        {/* ── Price Curve ── */}
        <section style={{
          background: "white", border: "1px solid #e2e8f0", borderRadius: 12,
          padding: "16px 18px", marginBottom: 16,
        }}>
          <h2 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
            📈 Today's Day-Ahead Electricity Prices
          </h2>
          <PriceCurve prices={prices} recommendations={recommendations} />
        </section>

        {/* ── Trade-off Slider ── */}
        <section style={{ marginBottom: 16 }}>
          <TradeoffSlider values={sliders} onChange={handleSliderChange} disabled={loading} />
        </section>

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: "center", color: "#64748b", padding: "24px 0", fontSize: 14 }}>
            ⏳ Optimising schedule…
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            background: "#fff1f2", border: "1px solid #fca5a5", borderRadius: 8,
            padding: "12px 16px", color: "#dc2626", fontSize: 13, marginBottom: 16,
          }}>
            ⚠️ {error}
            <br />
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              Make sure the backend is running: cd hems-demo/backend && uvicorn main:app --reload
            </span>
          </div>
        )}

        {/* ── Recommendations ── */}
        {!loading && recommendations.length > 0 && (
          <section>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: "#1e293b" }}>
                🏠 Appliance Scheduling Recommendations
              </h2>
              {lastFetched && (
                <span style={{ fontSize: 11, color: "#94a3b8" }}>
                  Updated {lastFetched.toLocaleTimeString()}
                </span>
              )}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {recommendations.map((rec) => (
                <RecommendationCard
                  key={rec.appliance_id}
                  rec={rec}
                  condition={condition}
                  onAccept={handleAccept}
                  onReject={handleReject}
                />
              ))}
            </div>
          </section>
        )}

        {/* Footer */}
        <div style={{ marginTop: 36, textAlign: "center", fontSize: 11, color: "#94a3b8" }}>
          Home Energy Management System
        </div>
      </main>
    </div>
  );
}
