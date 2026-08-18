import type { PricePoint, RecommendResponse, ScenarioMeta, ScenarioId, Condition, SliderValues } from "./types";

const BASE = "http://localhost:8000";

async function fetchJSON<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface SessionInfo {
  participant_id: string;
  condition: Condition;
  task_sequence: string[];
}

const SESSION_KEY = "hems_session";

/** Deduplicates concurrent calls — React StrictMode invokes mount effects twice in dev. */
let sessionInFlight: Promise<SessionInfo> | null = null;

/**
 * Ask the backend to assign this participant to a condition.
 * Assignment is block-randomised server-side so the two groups stay balanced;
 * the client must not choose its own condition.
 *
 * Cached in sessionStorage so a reload keeps the condition already assigned. Without
 * this, refreshing the page re-rolls the condition: the participant can end up seeing
 * both explanation types, which destroys their data and inflates the assignment ledger.
 * The backend is idempotent per Prolific ID for the same reason; this covers the case
 * where no Prolific ID is present.
 */
export async function createSession(prolificPid: string): Promise<SessionInfo> {
  const cached = sessionStorage.getItem(SESSION_KEY);
  if (cached) {
    try {
      return JSON.parse(cached) as SessionInfo;
    } catch {
      sessionStorage.removeItem(SESSION_KEY);   // 缓存坏了就重新分，不要静默用半个对象
    }
  }
  if (sessionInFlight) return sessionInFlight;

  sessionInFlight = fetchJSON<SessionInfo>(`${BASE}/api/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prolific_pid: prolificPid }),
  })
    .then((s) => {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(s));
      return s;
    })
    .finally(() => {
      sessionInFlight = null;
    });

  return sessionInFlight;
}

export async function getPrices(scenario: ScenarioId): Promise<PricePoint[]> {
  const data = await fetchJSON<{ prices: PricePoint[] }>(`${BASE}/api/prices/${scenario}`);
  return data.prices;
}

export async function getScenarios(): Promise<ScenarioMeta[]> {
  const data = await fetchJSON<{ scenarios: ScenarioMeta[] }>(`${BASE}/api/scenarios`);
  return data.scenarios;
}

export async function getRecommendations(
  sliders: SliderValues,
  scenario: ScenarioId,
  condition: Condition
): Promise<RecommendResponse> {
  return fetchJSON<RecommendResponse>(`${BASE}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cost: sliders.cost,
      green: sliders.green,
      convenience: sliders.convenience,
      scenario,
      condition,
    }),
  });
}

export async function logEvent(payload: {
  participant_id?: string;
  condition: Condition;
  event_type: string;
  appliance_id?: string;
  slider_values?: SliderValues;
  scenario?: string;
  extra?: Record<string, unknown>;
}): Promise<void> {
  try {
    await fetch(`${BASE}/api/log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ participant_id: "demo", ...payload }),
    });
  } catch {
    // Non-blocking — log failure should not break the UI
  }
}
