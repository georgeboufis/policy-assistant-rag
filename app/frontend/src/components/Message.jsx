import { useLanguage } from "../i18n.jsx";
import Rating from "./Rating.jsx";

// One message in the thread, laid out answer-first with the evidence one layer behind
// it. Two patterns taken from how the best conversational-search tools present sources:
//
//   - the citation is a hover card. Resting on a [1] shows which file and section it
//     came from and the first words of the extract, so a claim can be checked without
//     looking away from the sentence being read.
//   - the sources strip. Under the answer each cited document is a card rather than a
//     bare file name, so the evidence is visible at a glance and clickable.
//
// The full panel - every extract, the sentence relied on, the comparison made - stays
// one more click away, so the page stays calm until somebody wants that detail.

const ICONS = {
  md: "M3 13V3h2.2l2.3 3.6L9.8 3H12v10h-2.1V6.8L7.5 10 5.1 6.8V13z",
  txt: "M3.5 3.5h9M8 3.5V13",
  pdf: "M4.5 13V3h4l3 3v7z",
  docx: "M4.5 13V3h4l3 3v7z",
  csv: "M3 5.5h10M3 8h10M3 10.5h10",
  eml: "M2.5 4h11v8h-11zM2.5 4l5.5 4.6L13.5 4",
  html: "M5.5 4L3 8l2.5 4M10.5 4L13 8l-2.5 4",
};

function fileIcon(name) {
  return ICONS[name.split(".").pop().toLowerCase()] || ICONS.txt;
}

function splitCitations(text) {
  // The answer ends in "[1]" or "[1][2]". Each one becomes its own piece so it can be
  // rendered as a button; everything else stays plain text.
  const pieces = [];
  const pattern = /\[(\d+)\]/g;
  let last = 0;
  let found;

  while ((found = pattern.exec(text)) !== null) {
    if (found.index > last) pieces.push({ text: text.slice(last, found.index) });
    pieces.push({ citation: Number(found[1]) });
    last = found.index + found[0].length;
  }
  if (last < text.length) pieces.push({ text: text.slice(last) });
  return pieces;
}

function body(chunk) {
  // Every chunk starts with the line saying where it came from; its text follows.
  const text = chunk?.model_text || "";
  const [, ...rest] = text.split("\n");
  return (rest.join(" ") || text).trim();
}

export default function Message({ message, fromCache, onShowSources }) {
  const { strings } = useLanguage();

  if (message.role === "user") {
    return (
      <div className="message is-user">
        <div className="bubble">{message.content}</div>
      </div>
    );
  }

  const refused = message.sources.length === 0;
  const pieces = splitCitations(message.content);
  const chunks = message.chunks || [];

  // One card per cited document, in the order the model cited them
  const cards = message.sources.map((file) => ({
    file,
    chunk: chunks.find((chunk) => chunk.source === file),
  }));

  return (
    <div className="message is-assistant">
      <div className="avatar" aria-hidden="true">
        <svg viewBox="0 0 20 20" width="13" height="13">
          <path d="M10 3l1.8 5.2L17 10l-5.2 1.8L10 17l-1.8-5.2L3 10l5.2-1.8z"
                fill="currentColor" />
        </svg>
      </div>

      <div className="answer">
        <div className={`answer-text${refused ? " is-refusal" : ""}`}>
          {pieces.map((piece, index) => {
            if (!piece.citation) return <span key={index}>{piece.text}</span>;
            const chunk = chunks[piece.citation - 1];
            return (
              <span className="citation-wrap" key={index}>
                <button
                  className="citation"
                  onClick={() => onShowSources(message, piece.citation)}
                  aria-label={strings.sourceTitle(piece.citation)}
                >
                  {piece.citation}
                </button>
                {chunk && (
                  <span className="citation-card" role="tooltip">
                    <span className="citation-card-file">{chunk.source}</span>
                    {chunk.section && (
                      <span className="citation-card-section">{chunk.section}</span>
                    )}
                    <span className="citation-card-text">
                      {body(chunk).slice(0, 170)}…
                    </span>
                  </span>
                )}
              </span>
            );
          })}
        </div>

        {fromCache && (
          <span className="cache-badge" title={strings.fromCacheTitle}>
            <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">
              <path d="M3 8a5 5 0 115 5" fill="none" stroke="currentColor"
                    strokeWidth="1.5" strokeLinecap="round" />
              <path d="M3 5v3h3" fill="none" stroke="currentColor" strokeWidth="1.5"
                    strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {strings.fromCache}
          </span>
        )}

        {/* Only a stored answer can be rated - a pending one has no id yet */}
        {typeof message.id === "number" && <Rating message={message} />}

        {refused ? (
          <p className="answer-note">{strings.refusalNote}</p>
        ) : (
          <div className="strip">
            <span className="strip-label">{strings.sourcesStrip}</span>
            <div className="strip-cards">
              {cards.map(({ file, chunk }) => (
                <button
                  className="source-card"
                  key={file}
                  onClick={() => onShowSources(message, null)}
                >
                  <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
                    <path d={fileIcon(file)} fill="none" stroke="currentColor"
                          strokeWidth="1.3" strokeLinejoin="round" strokeLinecap="round" />
                  </svg>
                  <span className="source-card-text">
                    <span className="source-card-file">{file}</span>
                    {chunk?.section && (
                      <span className="source-card-section">{chunk.section}</span>
                    )}
                  </span>
                </button>
              ))}
              <button
                className="source-card is-more"
                onClick={() => onShowSources(message, null)}
              >
                {strings.viewSources}
                <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
                  <path d="M6 4l4 4-4 4" fill="none" stroke="currentColor"
                        strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
