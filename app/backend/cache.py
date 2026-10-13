"""Answers already paid for, kept so the same question is not paid for twice.

Every question costs tokens: one request to turn it into a standalone English question,
and one to answer it. Asked the same thing twice - which is exactly what happens while
demonstrating, or testing - the second time costs nothing here.

The whole of answer() is cached, which means a repeat costs **no** model requests at
all, not even the rewriting one. That works because the key is built before any request
is made: from the question as typed, the conversation it sits in, and everything else
that could change what comes back.

    WHAT IS IN THE KEY, AND WHY

    the question, as typed       obviously
    the conversation so far      "δηλαδή" means something different after each question
    the chat model               a different model gives a different answer
    chunking, TOP_K, MAX_DISTANCE  all of them change what the model is shown
    the corpus fingerprint       the names, sizes and times of every document

That last one is what makes this safe to use next to the upload feature. Add, replace
or delete a document and the fingerprint changes, so every answer cached against the
old corpus stops matching and is simply never served again. A cache that kept answering
from documents that have since changed would be worse than no cache.

Nothing is cached when the model fails: a rate-limit error is not an answer.
"""
import hashlib
import json

import config

from . import store

VERSION = 1          # raise this to abandon everything cached so far


def corpus_fingerprint():
    """What the documents are right now: name, size and last change of each."""
    marks = []
    for path in sorted(config.DATA_DIR.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            stat = path.stat()
            marks.append((path.name, stat.st_size, int(stat.st_mtime)))
    return marks


def key_for(question, history, chat_model):
    """One short string standing for "this question, asked under these conditions"."""
    material = {
        "version": VERSION,
        "question": " ".join(question.split()),      # spacing should not matter
        "history": history,
        "model": chat_model,
        "chunking": config.CHUNK_METHOD,
        "top_k": config.TOP_K,
        "max_distance": config.MAX_DISTANCE,
        "temperature": config.TEMPERATURE,
        "corpus": corpus_fingerprint(),
    }
    text = json.dumps(material, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get(key):
    """The stored answer for this key, or None. Counts the hit."""
    with store.connect() as connection:
        row = connection.execute(
            "SELECT value FROM answer_cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE answer_cache SET hits = hits + 1, used_at = ? WHERE key = ?",
            (store.now(), key),
        )
    return json.loads(row["value"])


def put(key, question, result):
    """Keep one answer. `question` is stored only so the table can be read by a human."""
    with store.connect() as connection:
        connection.execute("""
            INSERT INTO answer_cache (key, question, value, hits, created_at, used_at)
                 VALUES (?, ?, ?, 0, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (
            key,
            question,
            json.dumps(result, ensure_ascii=False),
            store.now(),
            store.now(),
        ))


def summary():
    """How much the cache is earning: how many answers it holds, and how often used."""
    with store.connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS entries, COALESCE(SUM(hits), 0) AS hits FROM answer_cache"
        ).fetchone()
    return {"entries": row["entries"], "hits": row["hits"]}


def clear():
    """Throw everything away. Returns how many answers were dropped."""
    with store.connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS n FROM answer_cache").fetchone()["n"]
        connection.execute("DELETE FROM answer_cache")
    return count
