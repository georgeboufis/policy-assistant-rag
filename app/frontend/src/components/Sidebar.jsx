import { useState } from "react";
import { useLanguage } from "../i18n.jsx";
import { useTheme } from "../theme.jsx";

// Conversations are grouped the way every chat tool groups them, because a flat list of
// thirty titles is unreadable: today first, then yesterday, then the rest.
function bucketOf(stamp) {
  const day = new Date(stamp);
  const today = new Date();
  const sameDay = (a, b) => a.toDateString() === b.toDateString();
  if (sameDay(day, today)) return "today";
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (sameDay(day, yesterday)) return "yesterday";
  return "earlier";
}

function when(stamp, language) {
  const then = new Date(stamp);
  const minutes = Math.round((Date.now() - then.getTime()) / 60000);
  const now = language === "el" ? "τώρα" : "now";
  if (minutes < 1) return now;
  if (minutes < 60) return `${minutes}${language === "el" ? "λ" : "m"}`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}${language === "el" ? "ώ" : "h"}`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}${language === "el" ? "μ" : "d"}`;
  return then.toLocaleDateString(language === "el" ? "el-GR" : "en-GB", {
    day: "numeric",
    month: "short",
  });
}

export default function Sidebar({
  conversations,
  openId,
  view,
  onView,
  onOpen,
  onNew,
  onRename,
  onDelete,
  busy,
}) {
  const { strings, language, setLanguage } = useLanguage();
  const { theme, setTheme } = useTheme();
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState("");

  function startRenaming(conversation, event) {
    event.stopPropagation();
    setEditing(conversation.id);
    setDraft(conversation.title);
  }

  function commit(event) {
    event?.preventDefault();
    const title = draft.trim();
    if (title) onRename(editing, title);
    setEditing(null);
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{strings.brand}</span>
        </div>

        <div className="views" role="tablist">
          <button
            role="tab"
            aria-selected={view === "chat"}
            className={view === "chat" ? "is-active" : ""}
            onClick={() => onView("chat")}
          >
            <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
              <path d="M2.5 3.5h11v7H6l-3.5 2.6z" fill="none" stroke="currentColor"
                    strokeWidth="1.3" strokeLinejoin="round" />
            </svg>
            {strings.chat}
          </button>
          <button
            role="tab"
            aria-selected={view === "documents"}
            className={view === "documents" ? "is-active" : ""}
            onClick={() => onView("documents")}
          >
            <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
              <path d="M4.5 13.5V2.5h4l3 3v8z" fill="none" stroke="currentColor"
                    strokeWidth="1.3" strokeLinejoin="round" />
            </svg>
            {strings.documentsView}
          </button>
          <button
            role="tab"
            aria-selected={view === "dashboard"}
            className={view === "dashboard" ? "is-active" : ""}
            onClick={() => onView("dashboard")}
          >
            <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
              <path d="M3 13V7M8 13V3.5M13 13v-4" stroke="currentColor" strokeWidth="1.6"
                    strokeLinecap="round" />
            </svg>
            {strings.dashboard}
          </button>
        </div>

        <button className="new-chat" onClick={onNew} disabled={busy}>
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6"
                  strokeLinecap="round" fill="none" />
          </svg>
          {strings.newChat}
        </button>
      </div>

      <nav className="conversations" aria-label={strings.conversationsHeading}>
        {conversations.length === 0 && (
          <p className="sidebar-empty">{strings.noConversations}</p>
        )}

        {["today", "yesterday", "earlier"].map((bucket) => {
          const inBucket = conversations.filter(
            (conversation) => bucketOf(conversation.updated_at) === bucket
          );
          if (inBucket.length === 0) return null;
          return (
            <section className="bucket" key={bucket}>
              <h2 className="bucket-label">{strings[bucket]}</h2>
              {inBucket.map((conversation) => {
                const isOpen = conversation.id === openId && view === "chat";
                return (
            <div
              key={conversation.id}
              className={`conversation${isOpen ? " is-open" : ""}`}
              onClick={() => onOpen(conversation.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => event.key === "Enter" && onOpen(conversation.id)}
            >
              {editing === conversation.id ? (
                <form onSubmit={commit} className="rename-form">
                  <input
                    autoFocus
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onBlur={commit}
                    onClick={(event) => event.stopPropagation()}
                    aria-label={strings.renameLabel}
                  />
                </form>
              ) : (
                <>
                  <div className="conversation-main">
                    <span className="conversation-title">{conversation.title}</span>
                    <span className="conversation-meta">
                      {when(conversation.updated_at, language)}
                      {conversation.message_count > 0 &&
                        ` · ${strings.messages(conversation.message_count)}`}
                    </span>
                  </div>
                  <div className="conversation-actions">
                    <button
                      title={strings.rename}
                      onClick={(event) => startRenaming(conversation, event)}
                    >
                      <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
                        <path d="M11.5 2.5l2 2L6 12l-2.5.5L4 10z" stroke="currentColor"
                              strokeWidth="1.3" fill="none" strokeLinejoin="round" />
                      </svg>
                    </button>
                    <button
                      title={strings.delete}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(conversation);
                      }}
                    >
                      <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
                        <path d="M3.5 5h9M6 5V3.5h4V5M5 5l.6 8h4.8L11 5" stroke="currentColor"
                              strokeWidth="1.3" fill="none" strokeLinejoin="round" />
                      </svg>
                    </button>
                  </div>
                </>
              )}
            </div>
                );
              })}
            </section>
          );
        })}
      </nav>

      <div className="sidebar-foot">
        <div className="switch" role="group" aria-label={strings.language}>
          {["el", "en"].map((code) => (
            <button
              key={code}
              className={language === code ? "is-active" : ""}
              onClick={() => setLanguage(code)}
              aria-pressed={language === code}
            >
              {code === "el" ? "Ελληνικά" : "English"}
            </button>
          ))}
        </div>
        <div className="switch" role="group" aria-label={strings.theme}>
          {[
            ["dark", strings.dark, "M8 2.6a5.4 5.4 0 100 10.8 4.4 4.4 0 010-10.8z"],
            ["light", strings.light, "M8 4.6a3.4 3.4 0 100 6.8 3.4 3.4 0 000-6.8zM8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15M3 3l1.2 1.2M11.8 11.8L13 13M13 3l-1.2 1.2M4.2 11.8L3 13"],
          ].map(([code, label, path]) => (
            <button
              key={code}
              className={theme === code ? "is-active" : ""}
              onClick={() => setTheme(code)}
              aria-pressed={theme === code}
              title={label}
            >
              <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">
                <path d={path} fill="none" stroke="currentColor" strokeWidth="1.3"
                      strokeLinecap="round" />
              </svg>
              {label}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
