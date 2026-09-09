/**
 * Done.tsx — the last screen, and the hand-back to Prolific.
 *
 * Two rules this screen exists to enforce:
 *
 *  1. **The completion code appears only once the server has confirmed the write.**
 *     Showing it earlier would let a participant be marked complete for data that
 *     never arrived, and the submission would have to be paid without usable data.
 *
 *  2. **A failed save is stated plainly, not hidden behind a success screen.** If
 *     the final write fails after retries, the participant is told to contact us
 *     rather than being silently sent back with an unusable case.
 *
 * The redirect is automatic but delayed, and the code is always shown as well:
 * a blocked redirect (some browsers, some extensions) must not leave anyone
 * without a way to complete the submission manually.
 */
import { useEffect, useState } from "react";
import { cardStyle, pageStyle } from "./ui";

/**
 * Both come from the Prolific study page and are injected at build time.
 * See `.env.example`. Leaving them unset is fine in development — the screen
 * then simply omits the redirect.
 */
const COMPLETION_URL = import.meta.env.VITE_PROLIFIC_COMPLETION_URL ?? "";
const COMPLETION_CODE = import.meta.env.VITE_PROLIFIC_COMPLETION_CODE ?? "";

const REDIRECT_DELAY_MS = 6000;

export default function Done({ status }: { status: "saving" | "saved" | "failed" }) {
  const [seconds, setSeconds] = useState(Math.round(REDIRECT_DELAY_MS / 1000));

  useEffect(() => {
    if (status !== "saved" || !COMPLETION_URL) return;
    const tick = setInterval(() => setSeconds((s) => Math.max(0, s - 1)), 1000);
    const jump = setTimeout(() => {
      window.location.href = COMPLETION_URL;
    }, REDIRECT_DELAY_MS);
    return () => {
      clearInterval(tick);
      clearTimeout(jump);
    };
  }, [status]);

  return (
    <div style={{ ...pageStyle, padding: "72px 16px" }}>
      <div style={{ ...cardStyle, maxWidth: 560, textAlign: "center" }}>
        {status === "saving" && (
          <>
            <h1 style={{ fontSize: 19, fontWeight: 600, margin: "0 0 10px" }}>Saving your responses…</h1>
            <p style={{ fontSize: 14, color: "#64748b", margin: 0 }}>
              Please keep this window open for a moment.
            </p>
          </>
        )}

        {status === "saved" && (
          <>
            <div style={{ fontSize: 34, marginBottom: 10 }}>✓</div>
            <h1 style={{ fontSize: 19, fontWeight: 600, margin: "0 0 10px" }}>Thank you — you are finished.</h1>
            <p style={{ fontSize: 14, color: "#64748b", lineHeight: 1.6, margin: "0 0 22px" }}>
              Your responses have been saved. Your participation genuinely helps: this study is part of a
              bachelor's thesis at the Technical University of Munich.
            </p>

            {COMPLETION_CODE && (
              <div
                style={{
                  border: "1px solid #e2e8f0",
                  borderRadius: 9,
                  padding: 17,
                  background: "#f8fafc",
                  marginBottom: 18,
                }}
              >
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 7 }}>Your completion code</div>
                <div style={{ fontSize: 21, fontWeight: 700, letterSpacing: 1.5, fontFamily: "monospace" }}>
                  {COMPLETION_CODE}
                </div>
              </div>
            )}

            {COMPLETION_URL ? (
              <>
                <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 14px" }}>
                  Returning you to Prolific in {seconds}s…
                </p>
                <a
                  href={COMPLETION_URL}
                  style={{
                    display: "inline-block",
                    background: "#2563eb",
                    color: "white",
                    textDecoration: "none",
                    borderRadius: 8,
                    padding: "11px 26px",
                    fontSize: 14,
                    fontWeight: 600,
                  }}
                >
                  Return to Prolific now
                </a>
              </>
            ) : (
              <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>
                Please return to Prolific and enter the completion code above.
              </p>
            )}
          </>
        )}

        {status === "failed" && (
          <>
            <h1 style={{ fontSize: 19, fontWeight: 600, margin: "0 0 10px", color: "#b91c1c" }}>
              Your responses could not be saved
            </h1>
            <p style={{ fontSize: 14, color: "#475569", lineHeight: 1.6, margin: "0 0 8px" }}>
              You completed the study, but the final save did not go through. Please message us through
              Prolific so that we can approve your submission — you will be paid.
            </p>
            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>
              Nothing further is needed from you, and this is our fault, not yours.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
