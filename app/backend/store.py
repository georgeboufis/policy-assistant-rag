"""Where the conversations live: one SQLite file next to this one.

Two tables. A conversation is a row with a title; every question and every answer is a
message row pointing at it. Nothing is ever overwritten - asking something new appends
two more rows, so the thread above it stays exactly as it was.

The answer rows also keep what the RAG found: the files it cited, the chunks it read,
the sentence it relied on. That is what the sources panel shows, and it means an old
conversation can still be checked months later, without asking the model again.

A new connection is opened per call. SQLite is quick enough for this, and it keeps the
server free of connections shared between threads, which SQLite dislikes.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "conversations.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,          -- 'user' or 'assistant'
    content         TEXT NOT NULL,
    sources         TEXT,                   -- JSON: the files the model cited
    chunks          TEXT,                   -- JSON: what it was given to read
    quote           TEXT,                   -- the sentence it relied on
    check_text      TEXT,                   -- the comparison it wrote out, if any
    searched        TEXT,                   -- what was actually searched for
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS messages_by_conversation
    ON messages (conversation_id, id);

-- Answers already paid for. The key stands for "this question under these conditions"
-- and is built in cache.py; see there for what goes into it and why.
CREATE TABLE IF NOT EXISTS answer_cache (
    key         TEXT PRIMARY KEY,
    question    TEXT NOT NULL,          -- kept so the table can be read by a person
    value       TEXT NOT NULL,          -- the whole answer, as JSON
    hits        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    used_at     TEXT NOT NULL
);

-- One row per rated answer. A separate table rather than two more columns on
-- messages: it needs no migration of the rows already there, and UNIQUE on
-- message_id means changing your mind replaces the rating instead of adding a second.
CREATE TABLE IF NOT EXISTS feedback (
    message_id  INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    verdict     TEXT NOT NULL,          -- 'up' or 'down'
    reason      TEXT,                   -- only for 'down', one of REASONS
    created_at  TEXT NOT NULL
);
"""

# Why an answer was not helpful. These are the failure modes this RAG actually has, so
# the answers group into something that can be acted on: "wrong_source" sends you to the
# chunking, "refused_wrongly" to MAX_DISTANCE, "language" to the prompt.
REASONS = [
    "not_answered",     # it did not answer what was asked
    "wrong",            # the information is wrong
    "incomplete",       # correct but too thin to use
    "wrong_source",     # it answered from the wrong document
    "refused_wrongly",  # it refused although the documents do cover it
    "language",         # answered in the wrong language, or badly worded
    "other",
]


def now():
    """The time, in a form that sorts correctly as text."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")      # so deleting a conversation
    connection.execute("PRAGMA journal_mode = WAL")     # takes its messages with it
    return connection


def setup():
    """Create the tables if this is the first run."""
    with connect() as connection:
        connection.executescript(SCHEMA)


# ---------------------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------------------

def create_conversation(title="New conversation"):
    stamp = now()
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
            (title, stamp, stamp),
        )
        return get_conversation(cursor.lastrowid, connection)


def list_conversations():
    """Every conversation, most recently used first, with its size and first line."""
    with connect() as connection:
        rows = connection.execute("""
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) AS message_count,
                   (SELECT content FROM messages
                     WHERE conversation_id = c.id AND role = 'user'
                     ORDER BY id DESC LIMIT 1) AS last_question
              FROM conversations c
         LEFT JOIN messages m ON m.conversation_id = c.id
          GROUP BY c.id
          ORDER BY c.updated_at DESC, c.id DESC
        """).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id, connection=None):
    close_after = connection is None
    connection = connection or connect()
    try:
        row = connection.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        if close_after:
            connection.close()


def rename_conversation(conversation_id, title):
    with connect() as connection:
        connection.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, now(), conversation_id),
        )
    return get_conversation(conversation_id)


def delete_conversation(conversation_id):
    with connect() as connection:
        connection.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor = connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------------------

def add_message(conversation_id, role, content, result=None):
    """Append one message. `result` is what rag.answer.answer() returned, for an answer."""
    result = result or {}
    stamp = now()
    with connect() as connection:
        connection.execute("""
            INSERT INTO messages (conversation_id, role, content, sources, chunks,
                                  quote, check_text, searched, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conversation_id, role, content,
            json.dumps(result.get("sources", []), ensure_ascii=False),
            json.dumps(result.get("chunks", []), ensure_ascii=False),
            result.get("quote", ""),
            result.get("check", ""),
            result.get("searched") or "",
            stamp,
        ))
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (stamp, conversation_id)
        )


def rate_message(message_id, verdict, reason=None):
    """Record what somebody thought of one answer, replacing any earlier rating."""
    if verdict not in ("up", "down"):
        raise ValueError("verdict must be 'up' or 'down'")
    if verdict == "up":
        reason = None                       # a reason only means something for a down
    elif reason is not None and reason not in REASONS:
        raise ValueError(f"unknown reason: {reason}")

    with connect() as connection:
        connection.execute("""
            INSERT INTO feedback (message_id, verdict, reason, created_at)
                 VALUES (?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE
                    SET verdict = excluded.verdict,
                        reason = excluded.reason,
                        created_at = excluded.created_at
        """, (message_id, verdict, reason, now()))


def clear_rating(message_id):
    """Take a rating back."""
    with connect() as connection:
        connection.execute("DELETE FROM feedback WHERE message_id = ?", (message_id,))


def list_messages(conversation_id):
    """Every message of one conversation, oldest first - the whole thread, always."""
    with connect() as connection:
        rows = connection.execute("""
            SELECT m.id, m.role, m.content, m.sources, m.chunks, m.quote, m.check_text,
                   m.searched, m.created_at, f.verdict, f.reason
              FROM messages m
         LEFT JOIN feedback f ON f.message_id = m.id
             WHERE m.conversation_id = ? ORDER BY m.id
        """, (conversation_id,)).fetchall()

    messages = []
    for row in rows:
        message = dict(row)
        message["sources"] = json.loads(message["sources"] or "[]")
        message["chunks"] = json.loads(message["chunks"] or "[]")
        message["check"] = message.pop("check_text") or ""
        messages.append(message)
    return messages


def history_for_model(conversation_id, how_many=None):
    """The thread as rag.answer.answer() wants it: [(question, answer), ...].

    Every exchange counts, including the ones that ended in a refusal: the QUESTION
    still says what the conversation was about, which is what a follow-up like
    "δηλαδή" needs in order to be filled in. Dropping refusals used to mean that one
    unanswered question wiped the thread's memory.

    Only the last few are returned - how_many, or whatever HISTORY_EXCHANGES in the
    RAG's own config.py says. The window is per conversation, because the rows are
    selected by conversation_id: two conversations never see each other's history.
    """
    if how_many is None:
        import config                      # the RAG's settings, next door
        how_many = config.HISTORY_EXCHANGES

    messages = list_messages(conversation_id)
    history = []
    for position, message in enumerate(messages):
        is_exchange = (
            message["role"] == "user"
            and position + 1 < len(messages)
            and messages[position + 1]["role"] == "assistant"
        )
        if is_exchange:
            history.append((message["content"], messages[position + 1]["content"]))
    return history[-how_many:]


def title_from(question, limit=60):
    """A conversation is named after its first question, shortened."""
    title = " ".join(question.split())
    return title if len(title) <= limit else title[:limit - 1].rstrip() + "…"
