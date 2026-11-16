import type { PricePoint, RecommendResponse, ScenarioMeta, ScenarioId, Condition, SliderValues } from "./types";

/**
 * Where the API lives.
 *
 * Only the Vite dev server needs an absolute origin: it serves the page on :5173
 * while the backend listens on :8000, so those really are different origins. In
 * every other case the page is served by the backend itself, and the right answer
 * is a relative URL — the API is wherever the page came from.
 *
 * Naming the host explicitly was a bug waiting to happen: a build that hard-codes
 * `http://localhost:8000` breaks the moment the page is opened as `127.0.0.1:8000`,
 * because the browser treats those as different origins and blocks the request. The
 * participant sees "the study could not be started" and nothing explains why.
 */
const BASE =
  import.meta.env.VITE_API_BASE ??
  (window.location.port === "5173" ? "http://localhost:8000" : "");

/**
 * Preview mode renders any screen directly from the URL so that screenshots of the
 * participant flow can be taken without walking through it. It must never write:
 * a screenshot run would otherwise assign conditions, append events and fill the
 * questionnaire file with fixture answers. The guard sits here, at the only two
 * functions that write, rather than at every call site — a call site added later
 * cannot forget it.
 */
export const IS_PREVIEW = new URLSearchParams(window.location.search).get("mode") === "preview";

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
  /**
   * Which response option is shown on the left, counterbalanced by the server and
   * crossed with the condition. Constant for a participant across every appliance
   * and every situation — a layout that moved between cards would pull attention
   * to the layout instead of the content.
   */
  option_order: "accept_first" | "reject_first";
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
      sessionStorage.removeItem(SESSION_KEY);   // if the cache is corrupt, request a new assignment instead of silently using a partial object
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

export interface StudyConfig {
  prolific_completion_url: string;
  prolific_completion_code: string;
  /** Where a participant on too small a screen is sent; a "Request a return" path. */
  prolific_incompatible_url: string;
  prolific_incompatible_code: string;
}

/**
 * Deployment settings fetched at run time. Falls back to the build-time variables
 * so local development and the preview screenshots keep working with no server
 * configuration at all.
 */
export async function getStudyConfig(): Promise<StudyConfig> {
  try {
    return await fetchJSON<StudyConfig>(`${BASE}/api/config`);
  } catch {
    return {
      prolific_completion_url: import.meta.env.VITE_PROLIFIC_COMPLETION_URL ?? "",
      prolific_completion_code: import.meta.env.VITE_PROLIFIC_COMPLETION_CODE ?? "",
      prolific_incompatible_url: "",
      prolific_incompatible_code: "",
    };
  }
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

/**
 * Persist one page of questionnaire answers.
 *
 * Unlike `logEvent`, this one throws: questionnaire responses are the study's
 * dependent variables, and a silent failure here would produce a participant who
 * looks complete but has no data. The caller decides what to do about it — the
 * survey retries with the next page and again at the end, and only the very last
 * attempt gates the completion code.
 *
 * Retries handle the common case (a transient network blip on a mobile connection)
 * without bothering the participant. Three attempts with a short backoff is enough
 * for that and short enough not to feel like a hang.
 */
export async function submitSurvey(payload: {
  participant_id: string;
  condition: Condition;
  page: string;
  /** Multi-select items store an array; the rest are scalars. */
  answers: Record<string, string | number | string[]>;
}): Promise<void> {
  if (IS_PREVIEW) return;
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await fetchJSON<{ status: string }>(`${BASE}/api/survey`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      return;
    } catch (e) {
      lastError = e;
      await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Survey submission failed");
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
  if (IS_PREVIEW) return;
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
