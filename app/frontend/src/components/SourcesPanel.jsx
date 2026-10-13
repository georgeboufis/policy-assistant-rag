// The panel that answers "πού το βρήκε;". It shows the chunks the model was given, in
// the order it was given them, which file and section each came from, and the sentence
// it said it relied on. Everything here was stored with the answer, so an old
// conversation can be checked without asking the model again.

import { useLanguage } from "../i18n.jsx";

export default function SourcesPanel({ message, focus, onClose }) {
  const { strings } = useLanguage();
  if (!message) return null;

  const chunks = message.chunks || [];

  return (
    <>
      <div className="panel-backdrop" onClick={onClose} />
      <aside className="panel" aria-label={strings.sources}>
        <header className="panel-head">
          <div>
            <h2>{strings.sources}</h2>
            <p>{strings.sourcesCount(chunks.length)}</p>
          </div>
          <button className="icon-button" onClick={onClose} title={strings.close}>
            <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6"
                    strokeLinecap="round" />
            </svg>
          </button>
        </header>

        {message.quote && (
          <section className="panel-block">
            <h3>{strings.quoteHeading}</h3>
            <blockquote>{message.quote}</blockquote>
          </section>
        )}

        {message.check && message.check.toLowerCase() !== "nothing to compare" && (
          <section className="panel-block">
            <h3>{strings.checkHeading}</h3>
            <p className="panel-check">{message.check}</p>
          </section>
        )}

        {message.searched && (
          <section className="panel-block">
            <h3>{strings.searchedHeading}</h3>
            <p className="panel-searched">{message.searched}</p>
          </section>
        )}

        <section className="panel-block">
          <h3>{strings.chunksHeading}</h3>
          <ol className="chunks">
            {chunks.map((chunk, index) => {
              const number = index + 1;
              const cited = (message.sources || []).includes(chunk.source);
              return (
                <li
                  key={number}
                  className={`chunk${focus === number ? " is-focus" : ""}`}
                  ref={(node) => focus === number && node?.scrollIntoView({ block: "center" })}
                >
                  <div className="chunk-head">
                    <span className="chunk-number">{number}</span>
                    <div className="chunk-where">
                      <span className="chunk-file">{chunk.source}</span>
                      {chunk.section && <span className="chunk-section">{chunk.section}</span>}
                    </div>
                    {cited && <span className="chunk-used">{strings.used}</span>}
                  </div>
                  <p className="chunk-text">
                    {(chunk.model_text || "").split("\n").slice(1).join(" ") ||
                      chunk.model_text}
                  </p>
                </li>
              );
            })}
          </ol>
        </section>
      </aside>
    </>
  );
}
