/**
 * Survey.tsx — the post-task questionnaire, five pages.
 *
 * Design decisions worth keeping in mind when editing this file:
 *
 *  • **Each page is submitted as it is left, not all at once at the end.** A
 *    participant who drops out on the last page still leaves usable data for the
 *    pages they completed. Submitting once at the end means a dropped connection
 *    costs the entire questionnaire.
 *
 *  • **A failed submission does not block the participant.** The answers are kept
 *    in component state and retried with the next page, and again at the end. A
 *    network hiccup must not strand someone who has already done the work — they
 *    would return the submission and we would lose the whole case.
 *
 *  • **The scales are administered once, after all tasks**, not after each task.
 *    Per-task administration would turn NASA-TLX into 18 ratings and would keep
 *    reminding participants that their workload is being measured.
 *
 *  • Answers are stored raw. Reverse-coded items (TiA 5, 7, 10, 15, 16 and TLX
 *    Performance) are recoded in analysis, never here — storing recoded values
 *    makes the raw responses unrecoverable if the scoring is ever revised.
 */
import { useState } from "react";
import {
  CHECK_ITEMS,
  DEMOGRAPHIC_ITEMS,
  OPEN_ITEMS,
  TIA_ITEMS,
  TIA_LABELS,
  TIA_PAGE_BREAK,
  TLX_DIMENSIONS,
  TLX_STEPS,
  TLX_STEP_SIZE,
} from "./items";
import { LikertRow, OpenQuestion, RadioQuestion, SurveyPage, TlxScale } from "./ui";

export type SurveyAnswers = Record<string, string | number>;

const TOTAL_PAGES = 5;

export default function Survey({
  onPageComplete,
  onFinish,
}: {
  /** Called when a page is left. Persisting is fire-and-forget by design. */
  onPageComplete: (page: string, answers: SurveyAnswers) => void;
  onFinish: (all: SurveyAnswers) => void;
}) {
  const [page, setPage] = useState(0);
  const [answers, setAnswers] = useState<SurveyAnswers>({});
  const [showMissing, setShowMissing] = useState(false);

  const set = (id: string, v: string | number) => setAnswers((a) => ({ ...a, [id]: v }));
  const num = (id: string) => answers[id] as number | undefined;
  const str = (id: string) => answers[id] as string | undefined;

  /** Advance only when every required id on the page has an answer. */
  const advance = (pageName: string, requiredIds: string[]) => {
    const missing = requiredIds.filter((id) => answers[id] === undefined);
    if (missing.length > 0) {
      setShowMissing(true);
      // Bring the first unanswered question into view rather than leaving the
      // participant to hunt for the red marker on a long page.
      document.querySelector(`[name="${missing[0]}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
      return;
    }
    const pageAnswers: SurveyAnswers = {};
    for (const id of requiredIds) pageAnswers[id] = answers[id];
    onPageComplete(pageName, pageAnswers);
    setShowMissing(false);
    window.scrollTo({ top: 0 });
    setPage((p) => p + 1);
  };

  const countMissing = (ids: string[]) => (showMissing ? ids.filter((id) => answers[id] === undefined).length : 0);

  // ── Page 1 · Demographics ─────────────────────────────────────────────────

  if (page === 0) {
    const ids = DEMOGRAPHIC_ITEMS.map((i) => i.id);
    return (
      <SurveyPage
        title="A few questions about you"
        intro="These help us describe who took part. They are not linked to your identity."
        progress={[1, TOTAL_PAGES]}
        missing={countMissing(ids)}
        onNext={() => advance("demographics", ids)}
      >
        {DEMOGRAPHIC_ITEMS.map((q) => (
          <RadioQuestion
            key={q.id}
            id={q.id}
            text={q.text}
            options={q.options}
            value={str(q.id)}
            onChange={(v) => set(q.id, v)}
            showMissing={showMissing}
          />
        ))}
      </SurveyPage>
    );
  }

  // ── Page 2 · Raw NASA-TLX ─────────────────────────────────────────────────

  if (page === 1) {
    const ids = TLX_DIMENSIONS.map((d) => d.id);
    return (
      <SurveyPage
        title="How the task felt"
        intro="Think about the whole session you have just completed. For each aspect, click the point on the scale that matches your experience."
        progress={[2, TOTAL_PAGES]}
        missing={countMissing(ids)}
        onNext={() => advance("tlx", ids)}
      >
        {TLX_DIMENSIONS.map((d) => (
          <TlxScale
            key={d.id}
            id={d.id}
            title={d.title}
            question={d.question}
            lowAnchor={d.lowAnchor}
            highAnchor={d.highAnchor}
            steps={TLX_STEPS}
            stepSize={TLX_STEP_SIZE}
            value={num(d.id)}
            onChange={(v) => set(d.id, v)}
            showMissing={showMissing}
          />
        ))}
      </SurveyPage>
    );
  }

  // ── Pages 3–4 · TiA, split in two ─────────────────────────────────────────

  if (page === 2 || page === 3) {
    const slice = page === 2 ? TIA_ITEMS.slice(0, TIA_PAGE_BREAK) : TIA_ITEMS.slice(TIA_PAGE_BREAK);
    const ids = slice.map((i) => i.id);
    return (
      <SurveyPage
        title="Your view of the system"
        intro={
          page === 2
            ? "Please say how far you agree with each statement about the system you have just used. There are no right or wrong answers."
            : "A few more statements about the system."
        }
        progress={[page + 1, TOTAL_PAGES]}
        missing={countMissing(ids)}
        onNext={() => advance(page === 2 ? "tia_1" : "tia_2", ids)}
      >
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 9, overflow: "hidden" }}>
          {slice.map((it, i) => (
            <LikertRow
              key={it.id}
              id={it.id}
              index={i}
              text={it.text}
              labels={TIA_LABELS}
              value={num(it.id)}
              onChange={(v) => set(it.id, v)}
              showMissing={showMissing}
            />
          ))}
        </div>
        <p style={{ fontSize: 11, color: "#94a3b8", marginTop: 12, lineHeight: 1.5 }}>
          Trust in Automation (TiA) questionnaire · Körber (2019) · CC BY-SA 4.0
        </p>
      </SurveyPage>
    );
  }

  // ── Page 5 · Checks and open questions ────────────────────────────────────

  const checkIds = CHECK_ITEMS.map((c) => c.id);
  return (
    <SurveyPage
      title="Two last things"
      intro="Please answer from memory — there is no need to be exact."
      progress={[5, TOTAL_PAGES]}
      missing={countMissing(checkIds)}
      nextLabel="Finish and return to Prolific"
      onNext={() => {
        const missing = checkIds.filter((id) => answers[id] === undefined);
        if (missing.length > 0) {
          setShowMissing(true);
          document.querySelector(`[name="${missing[0]}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" });
          return;
        }
        // Open questions are optional on purpose: forcing prose produces "n/a".
        const final: SurveyAnswers = { ...answers };
        for (const o of OPEN_ITEMS) if (final[o.id] === undefined) final[o.id] = "";
        onPageComplete("checks", final);
        onFinish(final);
      }}
    >
      {CHECK_ITEMS.map((q) => (
        <RadioQuestion
          key={q.id}
          id={q.id}
          text={q.text}
          options={q.options}
          value={str(q.id)}
          onChange={(v) => set(q.id, v)}
          showMissing={showMissing}
        />
      ))}

      <hr style={{ border: "none", borderTop: "1px solid #e2e8f0", margin: "26px 0 22px" }} />
      <p style={{ fontSize: 13, color: "#64748b", marginTop: 0, marginBottom: 18 }}>
        Optional — but very helpful:
      </p>
      {OPEN_ITEMS.map((o) => (
        <OpenQuestion
          key={o.id}
          id={o.id}
          text={o.text}
          value={(answers[o.id] as string) ?? ""}
          onChange={(v) => set(o.id, v)}
        />
      ))}
    </SurveyPage>
  );
}
