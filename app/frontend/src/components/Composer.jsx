import { useEffect, useRef, useState } from "react";
import { useLanguage } from "../i18n.jsx";

// The box you type in. Enter sends, Shift+Enter makes a new line, and it grows with the
// text up to a few lines so a long question stays readable.

export default function Composer({ onAsk, busy }) {
  const { strings } = useLanguage();
  const [text, setText] = useState("");
  const box = useRef(null);

  useEffect(() => {
    if (!box.current) return;
    box.current.style.height = "auto";
    box.current.style.height = `${Math.min(box.current.scrollHeight, 160)}px`;
  }, [text]);

  function send() {
    const question = text.trim();
    if (!question || busy) return;
    setText("");
    onAsk(question);
  }

  return (
    <div className="composer">
      <div className="composer-box">
        <textarea
          ref={box}
          rows={1}
          value={text}
          placeholder={strings.placeholder}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          disabled={busy}
        />
        <button className="send" onClick={send} disabled={busy || !text.trim()} title={strings.send}>
          <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
            <path d="M2 8h11M9 4l4 4-4 4" stroke="currentColor" strokeWidth="1.7"
                  fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      <p className="composer-note">{strings.composerNote}</p>
    </div>
  );
}
