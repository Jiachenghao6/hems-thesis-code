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
