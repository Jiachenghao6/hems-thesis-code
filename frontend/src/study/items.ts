/**
 * items.ts — every questionnaire item used in the study, in one place.
 *
 * Why the items live in a data file rather than inside the page components:
 * the scoring code, the codebook in the appendix, and the questionnaire the
 * participant sees must not be able to drift apart. Subscale membership and
 * reverse-coding live next to the wording that they refer to.
 *
 * ── Provenance of the scales ───────────────────────────────────────────────
 *
 * TiA (Trust in Automation), 19 items, six subscales, 5-point rating scale.
 *   Wording, subscale assignment and the five inverse items are transcribed
 *   verbatim from the author's own English release:
 *     https://github.com/moritzkoerber/TiA_Trust_in_Automation_Questionnaire
 *   Licence: CC BY-SA 4.0 — attribution is required wherever the items appear,
 *   including the thesis appendix.
 *   Cite: Körber, M. (2019). Theoretical considerations and development of a
 *   questionnaire to measure trust in automation. In Proceedings of the 20th
 *   Congress of the IEA (Vol. VI, pp. 13–30). Springer.
 *
 * NASA-TLX, six dimensions, administered as Raw TLX (RTLX): the pairwise
 *   weighting procedure is omitted. That choice must be stated and justified in
 *   the Study Design chapter.
 *   ⚠️ The endpoint anchors and the 21-gradation scale below still need checking
 *   against Hart & Staveland (1988) — that PDF is not yet in the library.
 */

// ── Shared types ────────────────────────────────────────────────────────────

export type Likert5 = 1 | 2 | 3 | 4 | 5;

export interface LikertItem {
  /** Stable id used in the exported data. Never renumber these. */
  id: string;
  text: string;
  subscale: string;
  /** true → response must be recoded (6 − x) before analysis. */
  reverse: boolean;
}

export interface ChoiceItem {
  id: string;
  text: string;
  options: { value: string; label: string }[];
}

// ── TiA · Trust in Automation (Körber 2019) ─────────────────────────────────

export const TIA_SUBSCALES: Record<string, string> = {
  RC: "Reliability / Competence",
  UP: "Understanding / Predictability",
  F: "Familiarity",
  ID: "Intention of Developers",
  PRO: "Propensity to Trust",
  T: "Trust in Automation",
};

/**
 * Item order is the original 1–19 order. It is deliberately NOT grouped by
 * subscale: grouping would make the construct being measured obvious and invite
 * consistent-response bias.
 */
export const TIA_ITEMS: LikertItem[] = [
  { id: "tia01", subscale: "RC", reverse: false, text: "The system is capable of interpreting situations correctly." },
  { id: "tia02", subscale: "UP", reverse: false, text: "The system state was always clear to me." },
  { id: "tia03", subscale: "F", reverse: false, text: "I already know similar systems." },
  { id: "tia04", subscale: "ID", reverse: false, text: "The developers are trustworthy." },
  { id: "tia05", subscale: "PRO", reverse: true, text: "One should be careful with unfamiliar automated systems." },
  { id: "tia06", subscale: "RC", reverse: false, text: "The system works reliably." },
  { id: "tia07", subscale: "UP", reverse: true, text: "The system reacts unpredictably." },
  { id: "tia08", subscale: "ID", reverse: false, text: "The developers take my well-being seriously." },
  { id: "tia09", subscale: "T", reverse: false, text: "I trust the system." },
  { id: "tia10", subscale: "RC", reverse: true, text: "A system malfunction is likely." },
  { id: "tia11", subscale: "UP", reverse: false, text: "I was able to understand why things happened." },
  { id: "tia12", subscale: "PRO", reverse: false, text: "I rather trust a system than I mistrust it." },
  { id: "tia13", subscale: "RC", reverse: false, text: "The system is capable of taking over complicated tasks." },
  { id: "tia14", subscale: "T", reverse: false, text: "I can rely on the system." },
  { id: "tia15", subscale: "RC", reverse: true, text: "The system might make sporadic errors." },
  { id: "tia16", subscale: "UP", reverse: true, text: "It's difficult to identify what the system will do next." },
  { id: "tia17", subscale: "F", reverse: false, text: "I have already used similar systems." },
  { id: "tia18", subscale: "PRO", reverse: false, text: "Automated systems generally work well." },
  { id: "tia19", subscale: "RC", reverse: false, text: "I am confident about the system's capabilities." },
];

export const TIA_LABELS = [
  "Strongly disagree",
  "Rather disagree",
  "Neither disagree nor agree",
  "Rather agree",
  "Strongly agree",
];

/** Split across two pages: 19 statements on one screen depresses response quality. */
export const TIA_PAGE_BREAK = 10;

// ── NASA-TLX (Raw) ──────────────────────────────────────────────────────────

export interface TlxDimension {
  id: string;
  title: string;
  question: string;
  lowAnchor: string;
  highAnchor: string;
  /** Performance is anchored Perfect → Failure, i.e. reversed relative to the rest. */
  reverse: boolean;
}

export const TLX_DIMENSIONS: TlxDimension[] = [
  {
    id: "tlx_mental",
    title: "Mental Demand",
    question: "How mentally demanding was the task?",
    lowAnchor: "Very Low",
    highAnchor: "Very High",
    reverse: false,
  },
  {
    id: "tlx_physical",
    title: "Physical Demand",
    question: "How physically demanding was the task?",
    lowAnchor: "Very Low",
    highAnchor: "Very High",
    reverse: false,
  },
  {
    id: "tlx_temporal",
    title: "Temporal Demand",
    question: "How hurried or rushed was the pace of the task?",
    lowAnchor: "Very Low",
    highAnchor: "Very High",
    reverse: false,
  },
  {
    id: "tlx_performance",
    title: "Performance",
    question: "How successful were you in accomplishing what you were asked to do?",
    lowAnchor: "Perfect",
    highAnchor: "Failure",
    reverse: true,
  },
  {
    id: "tlx_effort",
    title: "Effort",
    question: "How hard did you have to work to accomplish your level of performance?",
    lowAnchor: "Very Low",
    highAnchor: "Very High",
    reverse: false,
  },
  {
    id: "tlx_frustration",
    title: "Frustration",
    question: "How insecure, discouraged, irritated, stressed and annoyed were you?",
    lowAnchor: "Very Low",
    highAnchor: "Very High",
    reverse: false,
  },
];

/** 21 gradations scored 0–100 in steps of 5, as in the original instrument. */
export const TLX_STEPS = 21;
export const TLX_STEP_SIZE = 5;

// ── Demographics and background ─────────────────────────────────────────────

export const DEMOGRAPHIC_ITEMS: ChoiceItem[] = [
  {
    id: "dem_age",
    text: "What is your age group?",
    options: [
      { value: "18-24", label: "18–24" },
      { value: "25-34", label: "25–34" },
      { value: "35-44", label: "35–44" },
      { value: "45-54", label: "45–54" },
      { value: "55-64", label: "55–64" },
      { value: "65plus", label: "65 or older" },
    ],
  },
  {
    id: "dem_gender",
    text: "What is your gender?",
    options: [
      { value: "female", label: "Female" },
      { value: "male", label: "Male" },
      { value: "diverse", label: "Non-binary / diverse" },
      { value: "na", label: "Prefer not to say" },
    ],
  },
  {
    id: "dem_pays_bill",
    text: "Do you pay the electricity bill for your household?",
    options: [
      { value: "yes", label: "Yes, I pay it" },
      { value: "shared", label: "I share it with others in the household" },
      { value: "no", label: "No, someone else pays it" },
    ],
  },
  {
    id: "dem_dynamic_tariff",
    text: "Does your household have an electricity contract with hourly or time-varying prices?",
    options: [
      { value: "yes", label: "Yes" },
      { value: "no", label: "No" },
      { value: "unknown", label: "I don't know" },
    ],
  },
  {
    id: "dem_smart_home",
    text: "Have you used a smart-home or energy-management app before?",
    options: [
      { value: "never", label: "Never" },
      { value: "tried", label: "I have tried one" },
      { value: "occasional", label: "I use one occasionally" },
      { value: "regular", label: "I use one regularly" },
    ],
  },
  {
    id: "dem_flexibility",
    text: "How freely can you choose when to run appliances such as the dishwasher or washing machine?",
    options: [
      { value: "1", label: "Not at all freely" },
      { value: "2", label: "Slightly freely" },
      { value: "3", label: "Moderately freely" },
      { value: "4", label: "Very freely" },
      { value: "5", label: "Completely freely" },
    ],
  },
];

// ── Manipulation and attention checks ───────────────────────────────────────

/**
 * The first two are manipulation checks and carry real weight: with a bundled
 * independent variable, evidence that group A actually perceived the interactivity
 * and the modality is what licenses the interpretation of any group difference.
 *
 * The third is an attention check. The exclusion rule based on it must be fixed in
 * the Study Design chapter BEFORE the data are seen.
 */
export const CHECK_ITEMS: ChoiceItem[] = [
  {
    id: "mc_updates",
    text: "When you moved the priority control, did the explanation on screen change as well?",
    options: [
      { value: "yes", label: "Yes, it changed" },
      { value: "no", label: "No, it stayed the same" },
      { value: "unsure", label: "I did not notice" },
    ],
  },
  {
    id: "mc_modality",
    text: "How was the explanation presented to you?",
    options: [
      { value: "text", label: "As written text" },
      { value: "chart", label: "As a chart" },
      { value: "both", label: "Both" },
      { value: "unsure", label: "I don't remember" },
    ],
  },
  {
    id: "ac_instructed",
    text: "This is a check that you are reading the questions. Please select \"Rather disagree\".",
    options: [
      { value: "1", label: "Strongly disagree" },
      { value: "2", label: "Rather disagree" },
      { value: "3", label: "Neither disagree nor agree" },
      { value: "4", label: "Rather agree" },
      { value: "5", label: "Strongly agree" },
    ],
  },
];

/** The single correct response to the attention check, kept next to the item. */
export const ATTENTION_CHECK_CORRECT = "2";

// ── Open questions ──────────────────────────────────────────────────────────

export const OPEN_ITEMS = [
  {
    id: "open_trust",
    text: "In one or two sentences: what made you trust — or not trust — the recommendations?",
  },
  {
    id: "open_confusing",
    text: "Was there anything about the explanations you found confusing?",
  },
];
