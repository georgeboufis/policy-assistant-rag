import { useState } from "react";
import { api } from "../api.js";
import { useLanguage } from "../i18n.jsx";

// Two buttons under an answer, and on a thumbs-down a short list of reasons. The reasons
// are not generic: each one points at a different part of this RAG, so the dashboard's
// breakdown says where to look. "Answered from the wrong document" is a retrieval
// problem, "refused although the documents cover it" is the distance limit, "wrong
// language" is the prompt.

const REASONS = [
  "not_answered",
  "wrong",
  "incomplete",
  "wrong_source",
  "refused_wrongly",
  "language",
  "other",
];

export default function Rating({ message }) {
  const { strings } = useLanguage();
  const [verdict, setVerdict] = useState(message.verdict || null);
  const [reason, setReason] = useState(message.reason || null);
  const [asking, setAsking] = useState(false);

  async function set(next, why = null) {
    // Show it at once; a rating is not worth a spinner.
    setVerdict(next);
    setReason(why);
    setAsking(next === "down" && !why);
    try {
      if (next === null) await api.clearRating(message.id);
      else await api.rate(message.id, next, why);
    } catch {
      /* the rating is not worth interrupting the conversation over */
    }
  }

  return (
    <div className="rating">
      <div className="rating-buttons">
        <button
          className={`rating-button${verdict === "up" ? " is-on is-good" : ""}`}
          title={strings.helpful}
          aria-pressed={verdict === "up"}
          onClick={() => (verdict === "up" ? set(null) : set("up"))}
        >
          <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
            <path d="M5 14V7l3.2-5 .8.5a2 2 0 01.7 2.2L9 7h3.4a1.5 1.5 0 011.46 1.84l-.9 4A1.5 1.5 0 0111.5 14z"
                  fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            <path d="M5 7.5H3.2A.7.7 0 002.5 8.2v5.1a.7.7 0 00.7.7H5z" fill="none"
                  stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
          {strings.helpful}
        </button>

        <button
          className={`rating-button${verdict === "down" ? " is-on is-bad" : ""}`}
          title={strings.notHelpful}
          aria-pressed={verdict === "down"}
          onClick={() => (verdict === "down" ? set(null) : set("down"))}
        >
          <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
            <path d="M11 2v7l-3.2 5-.8-.5a2 2 0 01-.7-2.2L7 9H3.6A1.5 1.5 0 012.14 7.16l.9-4A1.5 1.5 0 014.5 2z"
                  fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            <path d="M11 8.5h1.8a.7.7 0 00.7-.7V2.7a.7.7 0 00-.7-.7H11z" fill="none"
                  stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          </svg>
          {strings.notHelpful}
        </button>

        {verdict && !asking && (
          <span className="rating-done">
            {reason ? strings.reason[reason] : strings.thanks}
          </span>
        )}
      </div>

      {asking && (
        <div className="reasons">
          <span className="reasons-label">{strings.whyNot}</span>
          <div className="reasons-chips">
            {REASONS.map((name) => (
              <button key={name} onClick={() => set("down", name)}>
                {strings.reason[name]}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
