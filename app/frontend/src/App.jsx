import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import Message from "./components/Message.jsx";
import SourcesPanel from "./components/SourcesPanel.jsx";
import Composer from "./components/Composer.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Documents from "./components/Documents.jsx";
import { api } from "./api.js";
import { useLanguage } from "./i18n.jsx";

export default function App() {
  const { strings } = useLanguage();
  const [view, setView] = useState("chat");
  const [settings, setSettings] = useState(null);
  // Bumped whenever the corpus changes, so the header's document count and the
  // dashboard are rebuilt from the server rather than showing a stale number.
  const [corpus, setCorpus] = useState(0);
  const [conversations, setConversations] = useState([]);
  const [openId, setOpenId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  // The two steps answering really goes through, so the wait says something true
  const [stage, setStage] = useState("searching");
  // A failure of the model is kept whole - what kind, which model, how long to wait -
  // because "502" tells somebody nothing they can act on.
  const [error, setError] = useState(null);
  const [cachedIds, setCachedIds] = useState(() => new Set());
  const [panel, setPanel] = useState({ message: null, focus: null });
  const bottom = useRef(null);

  // --- loading -----------------------------------------------------------------------

  const refreshList = useCallback(async () => {
    setConversations(await api.listConversations());
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [loadedSettings, list] = await Promise.all([
          api.settings(),
          api.listConversations(),
        ]);
        setSettings(loadedSettings);
        setConversations(list);
        if (list.length > 0) openConversation(list[0].id);
      } catch (problem) {
        setError({ message: strings.apiMissing(problem.message) });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function openConversation(id) {
    setView("chat");
    setOpenId(id);
    setPanel({ message: null, focus: null });
    try {
      const conversation = await api.getConversation(id);
      setMessages(conversation.messages);
    } catch (problem) {
      setError(problem);
    }
  }

  // --- actions -----------------------------------------------------------------------

  async function newConversation() {
    setView("chat");
    try {
      const conversation = await api.createConversation();
      await refreshList();
      setOpenId(conversation.id);
      setMessages([]);
      setPanel({ message: null, focus: null });
    } catch (problem) {
      setError(problem);
    }
  }

  async function ask(question) {
    setError(null);

    // Make sure there is a conversation to append to, so the first question of a fresh
    // session does not need a separate click.
    let id = openId;
    if (!id) {
      const conversation = await api.createConversation();
      id = conversation.id;
      setOpenId(id);
    }

    // Show the question at once, above everything already in the thread. Nothing is
    // replaced - the previous messages stay exactly where they are.
    const pending = {
      id: `pending-${Date.now()}`,
      role: "user",
      content: question,
      sources: [],
      chunks: [],
    };
    setMessages((earlier) => [...earlier, pending]);
    setAsking(true);
    setStage("searching");
    // Searching is the quick half; after it, the model is writing. Timed rather than
    // reported, because the request does not come back until both are finished.
    const movedOn = setTimeout(() => setStage("reading"), 1200);

    try {
      const result = await api.ask(id, question);
      setMessages((earlier) => [
        ...earlier.filter((message) => message.id !== pending.id),
        result.question,
        result.answer,
      ]);
      if (result.from_cache) {
        setCachedIds((known) => new Set(known).add(result.answer.id));
      }
      await refreshList();
    } catch (problem) {
      setMessages((earlier) => earlier.filter((message) => message.id !== pending.id));
      setError(problem);
    } finally {
      clearTimeout(movedOn);
      setAsking(false);
    }
  }

  async function rename(id, title) {
    await api.rename(id, title);
    refreshList();
  }

  async function remove(conversation) {
    const sure = window.confirm(strings.deleteConfirm(conversation.title));
    if (!sure) return;
    await api.remove(conversation.id);
    const list = await api.listConversations();
    setConversations(list);
    if (conversation.id === openId) {
      if (list.length > 0) openConversation(list[0].id);
      else {
        setOpenId(null);
        setMessages([]);
      }
    }
  }

  // --- rendering ---------------------------------------------------------------------

  const title = conversations.find((each) => each.id === openId)?.title;

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        openId={openId}
        view={view}
        onView={setView}
        onOpen={openConversation}
        onNew={newConversation}
        onRename={rename}
        onDelete={remove}
        busy={asking}
      />

      <main className="main">
        <header className="topbar">
          <div className="topbar-title">
            <h1>
              {view === "dashboard" && strings.dashboard}
              {view === "documents" && strings.documentsView}
              {view === "chat" && (title || strings.newChat)}
            </h1>
            {settings && (
              <p>
                {strings.documents(settings.documents.length)} · {settings.chat_model}
              </p>
            )}
          </div>
          {settings && (
            <div className="topbar-badges">
              <span className="badge" title={strings.chunkMethod}>
                {settings.chunk_method}
              </span>
              <span className="badge" title={strings.topK}>
                top {settings.top_k}
              </span>
              <span className="badge" title={strings.limit}>
                {strings.limitShort} {settings.max_distance}
              </span>
            </div>
          )}
        </header>

        {error && (
          <div className={`notice${error.kind === "rate_limit" ? " is-budget" : ""}`}
               role="alert">
            <div className="notice-icon" aria-hidden="true">
              {error.kind === "rate_limit" ? (
                <svg viewBox="0 0 16 16" width="16" height="16">
                  <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor"
                          strokeWidth="1.4" />
                  <path d="M8 4.6V8l2.4 1.6" fill="none" stroke="currentColor"
                        strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              ) : (
                <svg viewBox="0 0 16 16" width="16" height="16">
                  <path d="M8 2.5l6 11H2z" fill="none" stroke="currentColor"
                        strokeWidth="1.4" strokeLinejoin="round" />
                  <path d="M8 6.6v3.1M8 11.4v.1" stroke="currentColor" strokeWidth="1.4"
                        strokeLinecap="round" />
                </svg>
              )}
            </div>
            <div className="notice-text">
              <strong>
                {strings.errorTitle[error.kind] || strings.errorTitle.failed}
              </strong>
              <span>
                {/* Every kind the server names has its own wording here; the server's
                    own message is the fallback for anything unforeseen. */}
                {error.kind === "rate_limit"
                  ? strings.rateLimitBody(error.model, error.retryAfter)
                  : error.kind === "no_model"
                  ? strings.errorBody.no_model(error.model)
                  : strings.errorBody[error.kind] || error.message}
              </span>
              {error.kind === "rate_limit" && (
                <span className="notice-hint">{strings.rateLimitHint}</span>
              )}
            </div>
            <button className="icon-button" onClick={() => setError(null)}
                    title={strings.close}>
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6"
                      strokeLinecap="round" />
              </svg>
            </button>
          </div>
        )}

        {view === "documents" ? (
          <Documents
            onChanged={() => {
              setCorpus((count) => count + 1);
              api.settings().then(setSettings).catch(() => {});
            }}
          />
        ) : view === "dashboard" ? (
          <Dashboard key={`${conversations.length}-${corpus}`} />
        ) : (
        <>
        <div className="thread">
          {messages.length === 0 && !asking && (
            <div className="welcome">
              <h2>{strings.welcomeTitle}</h2>
              <p>{strings.welcomeText}</p>
              <div className="examples">
                {strings.examples.map((example) => (
                  <button key={example} onClick={() => ask(example)} disabled={asking}>
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <Message
              key={message.id}
              message={message}
              fromCache={cachedIds.has(message.id)}
              onShowSources={(target, focus) => setPanel({ message: target, focus })}
            />
          ))}

          {asking && (
            <div className="message is-assistant">
              <div className="avatar is-busy" aria-hidden="true" />
              <div className="working">
                <span className="working-line" />
                <span className="working-line is-short" />
                <span className="working-label">
                  {stage === "searching" ? strings.searching : strings.reading}
                </span>
              </div>
            </div>
          )}

          <div ref={bottom} />
        </div>

        <Composer onAsk={ask} busy={asking} />
        </>
        )}
      </main>

      <SourcesPanel
        message={panel.message}
        focus={panel.focus}
        onClose={() => setPanel({ message: null, focus: null })}
      />
    </div>
  );
}
