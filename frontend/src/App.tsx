/**
 * App.tsx — HEMS Demo
 *
 * A/B experiment interface:
 *   Condition A — Trade-off Slider + Interactive Causal Explanations (updates with slider)
 *   Condition B — Trade-off Slider + Static SHAP feature-importance chart (fixed)
 *
 * Comparability (supervisor feedback 2026-06-16). Three things follow from it:
 *
 *  1. Condition is assigned by the server (/api/session, block randomised) — not by
 *     a URL parameter the participant can see or change, and not defaulting to A.
 *  2. The scenario sequence is fixed and identical for both groups. Participants do
 *     not pick scenarios, and the `live` scenario is excluded from the study, since
 *     it would show a different price curve on every day of data collection.
 *  3. Nothing in the shared UI reveals which condition a participant is in, or that
 *     conditions exist at all. The condition badge, the banner describing the
 *     manipulation, and the exposed participant id / log-export link were removed.
 *
 * `?mode=demo` restores free exploration for screenshots and live demos.
 *
 * ── Study phases ───────────────────────────────────────────────────────────
 *
 *   consent → tasks → survey → done
 *
 * Consent comes first for a reason that is easy to get wrong: asking the server
 * for a session assigns a condition and writes a row to the assignment ledger,
 * and that is already data collection. So `createSession` is not called until
 * consent has been given. Demo mode skips straight to the tasks.
 */
import { useState, useEffect, useCallback, useRef } from "react";
import type { Condition, ScenarioId, SliderValues, PricePoint, Recommendation, ScenarioMeta } from "./types";
import type { SessionInfo } from "./api";
import { createSession, getPrices, getRecommendations, getScenarios, logEvent, submitSurvey } from "./api";
import PriceCurve from "./components/PriceCurve";
import TradeoffSlider from "./components/TradeoffSlider";
import RecommendationCard from "./components/RecommendationCard";
import Consent from "./study/Consent";
import Tutorial from "./study/Tutorial";
import Survey from "./study/Survey";
import type { SurveyAnswers } from "./study/Survey";
import Done from "./study/Done";

type Phase = "consent" | "tutorial" | "tasks" | "survey" | "done";

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Study mode is the default. `?mode=demo` gives the old free-exploration build,
 * which is what the walkthrough screenshots and live demos use — it must never be
 * the URL handed to participants.
 */
function isDemoMode(): boolean {
  return new URLSearchParams(window.location.search).get("mode") === "demo";
}

/** Prolific appends PROLIFIC_PID to the study URL. Empty outside Prolific. */
function getProlificPid(): string {
  const q = new URLSearchParams(window.location.search);
  return q.get("PROLIFIC_PID") || q.get("prolific_pid") || "";
}

/** Demo mode only — study mode gets its condition from the server. */
function getDemoCondition(): Condition {
  return new URLSearchParams(window.location.search).get("condition") === "B" ? "B" : "A";
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
  const demoMode = isDemoMode();

  // In study mode both of these arrive from /api/session; until they do, nothing
  // is rendered, so a participant can never see a condition the server did not assign.
  const [session, setSession] = useState<SessionInfo | null>(
    demoMode
      ? { participant_id: "demo", condition: getDemoCondition(), task_sequence: ["S3"] }
      : null
  );
  const [sessionError, setSessionError] = useState<string | null>(null);

  const [phase, setPhase] = useState<Phase>(demoMode ? "tasks" : "consent");
  const [taskIndex, setTaskIndex] = useState(0);
  const [saveStatus, setSaveStatus] = useState<"saving" | "saved" | "failed">("saving");

  /**
   * Timing for the two phases that happen before any task.
   *
   * Every later boundary is already a timestamped row — task_complete events and
   * one survey record per page — so durations fall out of the log without extra
   * instrumentation. Consent and the tutorial are the exception: consent runs
   * before a participant id exists, and nothing is written between the tutorial
   * appearing and the first task ending, so the tutorial's reading time would be
   * silently added to task one. Both are measured here and reported once, when the
   * tutorial is left and there is an id to attach them to.
   */
  const phaseEnteredAt = useRef(performance.now());
  const consentMs = useRef<number | null>(null);

  const condition: Condition = session?.condition ?? "A";
  const participantId = session?.participant_id ?? "pending";

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

  // Ask the server for a condition and the task sequence (study mode only).
  // Runs once; demo mode already has a synthetic session.
  useEffect(() => {
    if (demoMode) return;
    // Not before consent: assignment writes a ledger row, which is data collection.
    if (phase === "consent") return;
    let cancelled = false;
    createSession(getProlificPid())
      .then((s) => {
        if (cancelled) return;
        setSession(s);
        // First task of the fixed sequence. Falls back to S3 only if the server
        // ever returns an empty sequence, which would be a deployment error.
        setScenario((s.task_sequence[0] as ScenarioId) ?? "S3");
      })
      .catch((e) => {
        if (!cancelled) setSessionError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [demoMode, phase]);

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

  // Fetch recommendations once a condition is known. Waiting on `session` matters:
  // firing before assignment would render condition A to everyone for a moment.
  useEffect(() => {
    if (!session) return;
    fetchRecommendations(sliders, scenario);
    logEvent({ participant_id: participantId, condition, event_type: "page_load", scenario });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  // Re-fetch recommendations when the scenario changes.
  // `loggedScenario` suppresses the spurious first run: in study mode the scenario is
  // set from the task sequence the moment the session arrives, which would otherwise
  // be recorded as a scenario_change the participant never made.
  const loggedScenario = useRef<string | null>(null);
  useEffect(() => {
    if (!session) return;
    if (loggedScenario.current === null) {
      loggedScenario.current = scenario;
      return;
    }
    if (loggedScenario.current === scenario) return;
    loggedScenario.current = scenario;
    fetchRecommendations(sliders, scenario);
    logEvent({ participant_id: participantId, condition, event_type: "scenario_change", scenario });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario, session]);

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

  // ── Task sequence ────────────────────────────────────────────────────────

  const taskCount = session?.task_sequence.length ?? 0;
  const isLastTask = taskIndex >= taskCount - 1;

  /**
   * Move to the next scenario in the fixed sequence, or hand over to the
   * questionnaire. Sliders are reset to the neutral starting point between tasks
   * so every task begins from the same state for everyone; carrying the previous
   * setting over would make the later tasks depend on the earlier ones.
   */
  const advanceTask = () => {
    logEvent({
      participant_id: participantId,
      condition,
      event_type: "task_complete",
      scenario,
      slider_values: sliders,
      extra: { task_index: taskIndex },
    });
    if (isLastTask) {
      setPhase("survey");
      window.scrollTo({ top: 0 });
      return;
    }
    const next = taskIndex + 1;
    setTaskIndex(next);
    setSliders(DEFAULT_SLIDERS);
    setScenario((session?.task_sequence[next] as ScenarioId) ?? scenario);
    window.scrollTo({ top: 0 });
  };

  // ── Questionnaire ────────────────────────────────────────────────────────

  /** Fire-and-forget per page; the final page decides whether the code is shown. */
  const handleSurveyPage = (page: string, answers: SurveyAnswers) => {
    submitSurvey({ participant_id: participantId, condition, page, answers }).catch(() => {
      // Swallowed on purpose: an intermediate page failing must not stop someone
      // mid-questionnaire. The full answer set is retried once at the end.
    });
  };

  const handleSurveyFinish = (all: SurveyAnswers) => {
    setPhase("done");
    setSaveStatus("saving");
    window.scrollTo({ top: 0 });
    // One final write of everything. This is the attempt that gates the completion
    // code, so its outcome is shown to the participant rather than swallowed.
    submitSurvey({ participant_id: participantId, condition, page: "checks", answers: all })
      .then(() => setSaveStatus("saved"))
      .catch(() => setSaveStatus("failed"));
  };

  const currentMeta = scenarioMeta.find((m) => m.id === scenario);

  // ── Phase routing ────────────────────────────────────────────────────────

  if (phase === "consent") {
    return (
      <Consent
        onAccept={() => {
          consentMs.current = performance.now() - phaseEnteredAt.current;
          phaseEnteredAt.current = performance.now();
          setPhase("tutorial");
        }}
      />
    );
  }

  // The session is requested the moment consent is given, so the assignment
  // arrives while the tutorial is being read and task one starts without a wait.
  if (phase === "tutorial") {
    return (
      <Tutorial
        onStart={() => {
          logEvent({
            participant_id: participantId,
            condition,
            event_type: "tutorial_complete",
            extra: {
              consent_ms: Math.round(consentMs.current ?? 0),
              tutorial_ms: Math.round(performance.now() - phaseEnteredAt.current),
            },
          });
          phaseEnteredAt.current = performance.now();
          setPhase("tasks");
        }}
      />
    );
  }

  if (phase === "survey") {
    return <Survey onPageComplete={handleSurveyPage} onFinish={handleSurveyFinish} />;
  }

  if (phase === "done") {
    return <Done status={saveStatus} />;
  }

  // ── Render ───────────────────────────────────────────────────────────────

  // Nothing is rendered before the condition is known. Showing a default condition
  // first and swapping it after assignment would expose some participants to both.
  if (!session) {
    return (
      <div
        style={{
          fontFamily: "'Inter', system-ui, sans-serif",
          background: "#f8fafc",
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: sessionError ? "#dc2626" : "#64748b",
          fontSize: 14,
          padding: 24,
          textAlign: "center",
        }}
      >
        {sessionError
          ? `The study could not be started: ${sessionError}. Please return the submission on Prolific so you are not penalised, and accept our apologies.`
          : "Preparing your session…"}
      </div>
    );
  }

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
        {/*
          Scenario picker is demo-only. During the study every participant works
          through the same fixed sequence, so the price data both groups see is
          identical; letting them choose would make the two groups incomparable.
        */}
        {demoMode && (
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value as ScenarioId)}
              aria-label="Price scenario"
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
        )}
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

        {/*
          Task advancement. Study mode only — in demo mode there is no sequence to
          walk through. The button is the participant's only way forward, so it is
          always enabled: gating it on "has accepted or rejected something" would
          make declining every suggestion an invalid answer, and declining is data.
        */}
        {!demoMode && taskCount > 0 && (
          <div
            style={{
              marginTop: 30,
              padding: "18px 20px",
              background: "white",
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <div style={{ fontSize: 13, color: "#64748b" }}>
              Situation {taskIndex + 1} of {taskCount}
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 3 }}>
                When you are done with this situation, continue.
              </div>
            </div>
            <button
              onClick={advanceTask}
              style={{
                background: "#2563eb",
                color: "white",
                border: "none",
                borderRadius: 8,
                padding: "11px 24px",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {isLastTask ? "Continue to the questions" : "Next situation"}
            </button>
          </div>
        )}

        {/* Footer */}
        <div style={{ marginTop: 36, textAlign: "center", fontSize: 11, color: "#94a3b8" }}>
          Home Energy Management System
        </div>
      </main>
    </div>
  );
}
