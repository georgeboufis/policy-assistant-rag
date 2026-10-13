import { useEffect, useRef, useState } from "react";
import { api, uploadDocument } from "../api.js";
import { useLanguage } from "../i18n.jsx";

// Adding a document to the assistant's corpus. The file is stored in the data folder and
// indexed on its own - the other documents' chunks are already correct and are left
// alone. Chunking and embedding both run locally, so this costs no model requests: a
// client can hand over their own PDF mid-demo and ask about it twenty seconds later.

const ICON = {
  md: "M3 13V3h2.2l2.3 3.6L9.8 3H12v10h-2.1V6.8L7.5 10 5.1 6.8V13z",
  txt: "M3.5 3.5h9M8 3.5V13",
  pdf: "M4.5 13V3h4l3 3v7z",
  docx: "M4.5 13V3h4l3 3v7z",
  csv: "M3 5.5h10M3 8h10M3 10.5h10",
  eml: "M2.5 4h11v8h-11zM2.5 4l5.5 4.6L13.5 4",
  html: "M5.5 4L3 8l2.5 4M10.5 4L13 8l-2.5 4",
};

function bytes(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Documents({ onChanged }) {
  const { strings } = useLanguage();
  const [documents, setDocuments] = useState([]);
  const [supported, setSupported] = useState([]);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const [problem, setProblem] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [cache, setCache] = useState(null);
  const picker = useRef(null);

  async function refresh() {
    const loaded = await api.documents();
    setDocuments(loaded.documents);
    setSupported(loaded.supported);
    setCache(await api.cache());
  }

  useEffect(() => {
    refresh().catch((error) => setProblem(error.message));
  }, []);

  async function send(files) {
    setProblem(null);
    setNote(null);
    setBusy(true);
    try {
      for (const file of files) {
        const result = await uploadDocument(file);
        setNote(
          result.replaced
            ? strings.replacedDoc(result.name)
            : strings.uploaded(result.name, result.chunks)
        );
      }
      await refresh();
      onChanged?.();
    } catch (error) {
      setProblem(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(name) {
    if (!window.confirm(strings.deleteDocConfirm(name))) return;
    try {
      await api.removeDocument(name);
      await refresh();
      onChanged?.();
    } catch (error) {
      setProblem(error.message);
    }
  }

  return (
    <div className="dash">
      <header className="dash-head">
        <h2>{strings.documentsTitle}</h2>
        <p>{strings.documentsSubtitle}</p>
      </header>

      <div
        className={`dropzone${dragging ? " is-dragging" : ""}${busy ? " is-busy" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!busy) send([...event.dataTransfer.files]);
        }}
        onClick={() => !busy && picker.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => event.key === "Enter" && picker.current?.click()}
      >
        <input
          ref={picker}
          type="file"
          multiple
          hidden
          accept={supported.join(",")}
          onChange={(event) => {
            send([...event.target.files]);
            event.target.value = "";
          }}
        />
        <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
          <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 16v2.5A1.5 1.5 0 005.5 20h13a1.5 1.5 0 001.5-1.5V16"
                fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
                strokeLinejoin="round" />
        </svg>
        <strong>{busy ? strings.uploading : strings.dropHere}</strong>
        {!busy && <span>{strings.orBrowse}</span>}
        <span className="dropzone-types">
          {strings.supportedTypes(supported.join(" "))}
        </span>
        <span className="dropzone-types">{strings.noCost}</span>
      </div>

      {note && <p className="upload-note is-good">{note}</p>}
      {problem && <p className="upload-note is-bad">{problem}</p>}

      {cache && (
        <section className="card cache-card">
          <div>
            <h3>{strings.cacheTitle}</h3>
            <p className="card-note">{strings.cacheNote}</p>
            <p className="cache-figures">
              <strong>{strings.cacheEntries(cache.entries)}</strong>
              {cache.hits > 0 && <span>{strings.cacheHits(cache.hits)}</span>}
            </p>
          </div>
          <button
            className="quiet-button"
            disabled={cache.entries === 0}
            onClick={async () => {
              const { dropped } = await api.clearCache();
              setNote(strings.cacheCleared(dropped));
              refresh().catch(() => {});
            }}
          >
            {strings.clearCache}
          </button>
        </section>
      )}

      <section className="card">
        <h3>{strings.documentsView}</h3>
        <p className="card-note">{documents.length}</p>
        <ul className="documents">
          {documents.map((document) => {
            const kind = document.name.split(".").pop().toLowerCase();
            return (
              <li key={document.name}>
                <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                  <path d={ICON[kind] || ICON.txt} fill="none" stroke="currentColor"
                        strokeWidth="1.3" strokeLinejoin="round" strokeLinecap="round" />
                </svg>
                <span className="document-name">{document.name}</span>
                <span className="document-meta">
                  {document.chunks > 0
                    ? strings.chunksCount(document.chunks)
                    : strings.notIndexed}
                  {" · "}
                  {bytes(document.bytes)}
                </span>
                <button
                  className="icon-button"
                  title={strings.deleteDoc}
                  onClick={() => remove(document.name)}
                >
                  <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
                    <path d="M3.5 5h9M6 5V3.5h4V5M5 5l.6 8h4.8L11 5" stroke="currentColor"
                          strokeWidth="1.3" fill="none" strokeLinejoin="round" />
                  </svg>
                </button>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
