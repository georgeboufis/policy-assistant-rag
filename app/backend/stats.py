"""What the dashboard shows, worked out from the messages already in the database.

Nothing extra is recorded to make this possible: every number here is counted from the
rows that answering a question writes anyway. An answer with an empty "sources" is a
refusal - that is the same signal the chat itself uses, so the two can never disagree.
"""
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from datetime import date, timedelta

from . import cache, store
from .departments import ORDER, department_of

CITATION = re.compile(r"\[\d+\]")


def plain(text):
    """A question reduced to what makes two askings of it the same question.

    Lowercased, accents removed, punctuation dropped, spaces collapsed - so that
    "Πόσες μέρες άδεια δικαιούμαι;" and "ποσες μερες αδεια δικαιουμαι" count as one.
    Accents matter to the embedding model, but not to "which question gets asked most".
    """
    without_accents = "".join(
        letter for letter in unicodedata.normalize("NFD", text.lower())
        if not unicodedata.combining(letter)
    )
    return " ".join(re.sub(r"[^\w\s]", " ", without_accents).split())


def gather(days=14):
    """Every number the dashboard needs, in one pass over the messages."""
    with store.connect() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT id, conversation_id, role, content, sources, chunks, created_at
              FROM messages ORDER BY id
        """).fetchall()
        conversations = connection.execute(
            "SELECT COUNT(*) AS total FROM conversations"
        ).fetchone()["total"]

    messages = [dict(row) for row in rows]
    messages_with_ids = messages                 # same rows; named for what the
                                                 # feedback section below needs them for

    questions = [m for m in messages if m["role"] == "user"]
    answers = [m for m in messages if m["role"] == "assistant"]

    answered, refused, with_citation = [], [], 0
    for message in answers:
        if json.loads(message["sources"] or "[]"):
            answered.append(message)
            if CITATION.search(message["content"]):
                with_citation += 1
        else:
            refused.append(message)

    # Which questions come up most. The first wording seen is kept as the label, so the
    # list reads like something a person typed rather than the flattened form.
    seen = Counter()
    label_for = {}
    for message in questions:
        key = plain(message["content"])
        if not key:
            continue
        seen[key] += 1
        label_for.setdefault(key, message["content"])

    top_questions = [
        {"question": label_for[key], "count": count}
        for key, count in seen.most_common(8)
    ]

    # The questions the documents could not answer, newest first. This is the most
    # useful list on the page: it is a reading list of what the documents are missing.
    refused_questions = []
    for position, message in enumerate(messages):
        is_refused_question = (
            message["role"] == "user"
            and position + 1 < len(messages)
            and messages[position + 1]["role"] == "assistant"
            and not json.loads(messages[position + 1]["sources"] or "[]")
        )
        if is_refused_question:
            refused_questions.append({
                "question": message["content"],
                "asked_at": message["created_at"],
            })
    refused_questions.reverse()

    # What people thought of the answers. A rating is on the answer row, so it is
    # joined back to the question above it to show what was being asked.
    with store.connect() as connection:
        rated = connection.execute("""
            SELECT f.message_id, f.verdict, f.reason, f.created_at, m.conversation_id
              FROM feedback f JOIN messages m ON m.id = f.message_id
          ORDER BY f.created_at DESC
        """).fetchall()
    rated = [dict(row) for row in rated]

    content_of = {message["id"]: message for message in messages_with_ids}
    questions_before = {}
    for position, message in enumerate(messages_with_ids):
        if message["role"] == "assistant" and position > 0:
            questions_before[message["id"]] = messages_with_ids[position - 1]["content"]

    liked = [row for row in rated if row["verdict"] == "up"]
    disliked = [row for row in rated if row["verdict"] == "down"]

    reason_counts = Counter(row["reason"] or "other" for row in disliked)
    total_disliked = len(disliked) or 1
    reasons = [
        {
            "reason": name,
            "count": count,
            "share": round(count / total_disliked, 3),
        }
        for name, count in reason_counts.most_common()
    ]

    flagged = [
        {
            "question": questions_before.get(row["message_id"], ""),
            "answer": content_of.get(row["message_id"], {}).get("content", "")[:160],
            "reason": row["reason"] or "other",
            "rated_at": row["created_at"],
            "conversation_id": row["conversation_id"],
        }
        for row in disliked[:12]
    ]

    # Which department each question was about, whether or not it got an answer. An
    # answered question counts once for every department it drew on - a question that
    # needed the cleaning contract AND the supplier email counts once for facilities,
    # not twice, because the set is deduplicated first.
    by_department = {name: {"answered": 0, "refused": 0} for name in ORDER}
    for position, message in enumerate(messages):
        is_question = (
            message["role"] == "user"
            and position + 1 < len(messages)
            and messages[position + 1]["role"] == "assistant"
        )
        if not is_question:
            continue

        reply = messages[position + 1]
        cited = json.loads(reply["sources"] or "[]")
        if cited:
            for name in {department_of(file_name) for file_name in cited}:
                by_department[name]["answered"] += 1
        else:
            # No answer, so attribute it to whatever the search came closest to. The
            # chunks are stored even for a refusal, which is what makes this possible.
            chunks = json.loads(reply["chunks"] or "[]")
            if chunks:
                by_department[department_of(chunks[0]["source"])]["refused"] += 1

    departments = [
        {
            "department": name,
            "answered": counts["answered"],
            "refused": counts["refused"],
            "questions": counts["answered"] + counts["refused"],
        }
        for name, counts in by_department.items()
        if counts["answered"] or counts["refused"]
    ]
    departments.sort(key=lambda row: -row["questions"])

    # Which documents actually earn their place in the corpus
    cited_files = Counter()
    for message in answered:
        for file_name in json.loads(message["sources"] or "[]"):
            cited_files[file_name] += 1

    # Questions per day, for the activity chart. Days with nothing asked are kept at
    # zero - leaving them out would make a quiet week look busy.
    per_day = Counter(message["created_at"][:10] for message in questions)
    today = date.today()
    activity = [
        {
            "day": (today - timedelta(days=offset)).isoformat(),
            "count": per_day.get((today - timedelta(days=offset)).isoformat(), 0),
        }
        for offset in range(days - 1, -1, -1)
    ]

    return {
        "conversations": conversations,
        "questions": len(questions),
        "answered": len(answered),
        "refused": len(refused),
        "with_citation": with_citation,
        "answer_rate": round(len(answered) / len(answers), 3) if answers else None,
        "citation_rate": round(with_citation / len(answered), 3) if answered else None,
        "top_questions": top_questions,
        "refused_questions": refused_questions[:12],
        "cache": cache.summary(),
        "rated": len(rated),
        "liked": len(liked),
        "disliked": len(disliked),
        "helpful_rate": round(len(liked) / len(rated), 3) if rated else None,
        "reasons": reasons,
        "flagged": flagged,
        "departments": departments,
        "cited_files": [
            {"file": file_name, "count": count} for file_name, count in cited_files.most_common(8)
        ],
        "activity": activity,
    }
