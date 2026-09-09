/// <reference types="vite/client" />

/**
 * Build-time configuration. All three are injected by Vite at build time, so they
 * are baked into the bundle and visible to anyone who views source — which is fine
 * for these (a public API origin and the Prolific completion details) and must stay
 * true: never put a secret behind a VITE_ prefix.
 */
interface ImportMetaEnv {
  /** Backend origin, e.g. https://hems-api.example.eu. Defaults to localhost:8000. */
  readonly VITE_API_BASE?: string;
  /** Prolific completion URL used for the automatic redirect at the end. */
  readonly VITE_PROLIFIC_COMPLETION_URL?: string;
  /** Prolific completion code, shown as a fallback if the redirect is blocked. */
  readonly VITE_PROLIFIC_COMPLETION_CODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
