// ── Core domain types ────────────────────────────────────────────────────────

export interface PricePoint {
  hour: number;
  price_eur_mwh: number;
  price_eur_kwh: number;
  renewable_share: number;   // 0.0–1.0, fraction of generation from renewables
}

export interface ScenarioMeta {
  id: string;
  label: string;
  description: string;
  date_ref: string;
}

export interface ScoreBreakdown {
  cost_score: number;
  green_score: number;
  convenience_score: number;
  weighted_total: number;
}

export interface ShapFeature {
  feature: string;
  label: string;
  value: number;
  direction: "positive" | "negative" | "neutral";
  signed_value?: number;
}

export interface Recommendation {
  appliance_id: string;
  appliance_name: string;
  emoji: string;
  duration_hours: number;
  default_start: number;
  recommended_start: number;
  recommended_end: number;
  avg_price_default_eur_mwh: number;
  avg_price_recommended_eur_mwh: number;
  savings_eur: number;
  kwh_total: number;
  renewable_share_recommended: number | null;
  renewable_share_default: number | null;
  scores: ScoreBreakdown;
  weights_used: { cost: number; green: number; convenience: number };
  // Group A
  explanation?: string;
  // Group B
  shap_data?: ShapFeature[];
  explanation_type: "causal_interactive" | "static_shap";
  // UI state (client-side only)
  accepted?: boolean | null;
}

export interface RecommendResponse {
  condition: "A" | "B";
  scenario: string;
  weights: {
    cost_raw: number;
    green_raw: number;
    convenience_raw: number;
    normalised: { cost: number; green: number; convenience: number };
  };
  recommendations: Recommendation[];
}

export interface SliderValues {
  cost: number;
  green: number;
  convenience: number;
}

export type Condition = "A" | "B";
export type ScenarioId = "live" | "S1" | "S2" | "S3" | "S4" | "S5";
