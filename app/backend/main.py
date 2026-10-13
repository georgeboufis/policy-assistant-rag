"""The HTTP side of the RAG: the same answer() the terminal chat uses, over JSON.

    uv run uvicorn backend.main:app --reload --port 8000     (from Day_3/rag_ui)

Nothing about the retrieval lives here. This file only takes a question, hands it to
rag/answer.py in pipeline, stores both messages, and gives the answer back with the
sources it cited - so the React app can show where every sentence came from.

The endpoints are plain `def`, not `async def`, on purpose: answering blocks for a
second or two (embedding locally, then waiting on Groq), and FastAPI runs a plain `def`
in a thread, so one person asking does not freeze everyone else.
"""
import re
import sys
from pathlib import Path

# The RAG itself lives next door and imports its own modules by name ("import config"),
# so its folder has to be on the path before anything from it is imported.
RAG_DIR = Path(__file__).resolve().parent.parent.parent / "pipeline"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

import openai                                                    # noqa: E402
from fastapi import FastAPI, File, HTTPException, UploadFile    # noqa: E402
from fastapi.middleware.cors import CORSMiddleware              # noqa: E402
from pydantic import BaseModel, Field                           # noqa: E402

import config                                                   # noqa: E402
from rag.ai_models import CHAT_MODEL, EMBEDDING_MODEL           # noqa: E402
from rag.answer import answer                                   # noqa: E402

from . import cache, indexing, stats, store                     # noqa: E402

app = FastAPI(title="Policy Assistant API")

# In development the React app is served by Vite on another port. Vite proxies /api to
# here, so this is only a safety net for opening the app straight from a file.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store.setup()


WAIT = re.compile(r"try again in ((?:\d+m)?[\d.]+s)")


def model_problem(problem):
    """Turn a failure from the model into an HTTPException a person can act on.

    Three failures matter here and they need different words. The daily token limit is
    not an error in the usual sense - nothing is broken, the budget is spent - and
    telling somebody "502 Bad Gateway" when the answer is "come back in seven minutes"
    is the kind of message that makes people distrust a working system.
    """
    if isinstance(problem, openai.RateLimitError):
        found = WAIT.search(str(problem))
        return HTTPException(429, {
            "kind": "rate_limit",
            "model": CHAT_MODEL,
            "retry_after": found.group(1) if found else None,
            "message": "The model's token budget for today is spent.",
        })

    if isinstance(problem, openai.AuthenticationError):
        return HTTPException(401, {
            "kind": "auth",
            "message": "The API key was refused. Check GROQ_API_KEY in pipeline/.env.",
        })

    if isinstance(problem, (openai.APIConnectionError, openai.APITimeoutError)):
        return HTTPException(503, {
            "kind": "offline",
            "message": "The model could not be reached. Check the network.",
        })

    if isinstance(problem, openai.NotFoundError):
        return HTTPException(502, {
            "kind": "no_model",
            "model": CHAT_MODEL,
            "message": "That model is not available on this key.",
        })

    return HTTPException(502, {"kind": "failed", "message": str(problem)})


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class Rating(BaseModel):
    verdict: str = Field(pattern="^(up|down)$")
    reason: str | None = None


@app.get("/api/settings")
def settings():
    """What the assistant is running on, for the header of the app."""
    return {
        "chat_model": CHAT_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_method": config.CHUNK_METHOD,
        "top_k": config.TOP_K,
        "max_distance": config.MAX_DISTANCE,
        "documents": sorted(path.name for path in config.DATA_DIR.iterdir()
                            if path.is_file() and not path.name.startswith(".")),
    }


# ---------------------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------------------

@app.get("/api/documents")
def get_documents():
    return {"documents": indexing.list_documents(), "supported": indexing.supported()}


@app.post("/api/documents", status_code=201)
def post_document(file: UploadFile = File(...)):
    """Take one uploaded document, store it, and index it on its own.

    No model requests: the chunking is local and so is the embedding, so a document can
    be added during a demo without spending anything.
    """
    name = indexing.safe_name(file.filename or "document")
    ending = ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""
    if ending not in indexing.supported():
        raise HTTPException(
            415,
            f"There is no reader for {ending or 'a file with no extension'}."
            f" Supported: {', '.join(indexing.supported())}",
        )

    contents = file.file.read()
    if not contents:
        raise HTTPException(422, "The file is empty")
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "The file is larger than 10MB")

    path = config.DATA_DIR / name
    replaced = path.exists()
    path.write_bytes(contents)

    try:
        chunks = indexing.index_document(path)
    except Exception as problem:
        # A file that cannot be read must not be left behind pretending to be indexed
        path.unlink(missing_ok=True)
        indexing.remove_from_index(name)
        raise HTTPException(422, f"{name} could not be read: {problem}") from problem

    return {"name": name, "chunks": chunks, "replaced": replaced}


@app.delete("/api/documents/{name}", status_code=204)
def remove_document(name: str):
    if not indexing.delete_document(name):
        raise HTTPException(404, "No such document")


# ---------------------------------------------------------------------------------------
# What people thought of an answer
# ---------------------------------------------------------------------------------------

@app.get("/api/cache")
def get_cache():
    return cache.summary()


@app.delete("/api/cache")
def remove_cache():
    return {"dropped": cache.clear()}


@app.get("/api/reasons")
def get_reasons():
    """The reasons an answer can be marked unhelpful."""
    return {"reasons": store.REASONS}


@app.put("/api/messages/{message_id}/rating")
def put_rating(message_id: int, body: Rating):
    try:
        store.rate_message(message_id, body.verdict, body.reason)
    except ValueError as problem:
        raise HTTPException(422, str(problem)) from problem
    return {"message_id": message_id, "verdict": body.verdict, "reason": body.reason}


@app.delete("/api/messages/{message_id}/rating", status_code=204)
def remove_rating(message_id: int):
    store.clear_rating(message_id)


@app.get("/api/stats")
def get_stats():
    """Everything the dashboard shows, counted from the stored messages."""
    return stats.gather()


@app.get("/api/conversations")
def get_conversations():
    return store.list_conversations()


@app.post("/api/conversations", status_code=201)
def post_conversation():
    return store.create_conversation()


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: int):
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, "No such conversation")
    conversation["messages"] = store.list_messages(conversation_id)
    return conversation


@app.patch("/api/conversations/{conversation_id}")
def patch_conversation(conversation_id: int, body: Rename):
    if not store.get_conversation(conversation_id):
        raise HTTPException(404, "No such conversation")
    return store.rename_conversation(conversation_id, body.title.strip())


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def remove_conversation(conversation_id: int):
    if not store.delete_conversation(conversation_id):
        raise HTTPException(404, "No such conversation")


@app.post("/api/conversations/{conversation_id}/messages")
def post_message(conversation_id: int, body: Ask):
    """Ask one question inside a conversation, and append both messages to it."""
    if not store.get_conversation(conversation_id):
        raise HTTPException(404, "No such conversation")

    question = body.question.strip()
    if not question:
        raise HTTPException(422, "The question is empty")

    # The earlier exchanges, so that a follow-up like "and if it was 20 euros?" can be
    # rewritten into a question that stands on its own before it is searched.
    history = store.history_for_model(conversation_id)

    store.add_message(conversation_id, "user", question)

    # An unnamed conversation takes its name from its first question
    conversation = store.get_conversation(conversation_id)
    if conversation["title"] == "New conversation":
        store.rename_conversation(conversation_id, store.title_from(question))

    # Has this exact question, in this exact context, been answered already? The key is
    # built before any request is made, so a repeat costs nothing at all.
    key = cache.key_for(question, history, CHAT_MODEL)
    result = cache.get(key)
    from_cache = result is not None

    if not from_cache:
        try:
            result = answer(question, history)
        except Exception as problem:
            # The question is already stored; leave it there so the thread still reads
            # correctly, and say clearly what went wrong rather than "502".
            raise model_problem(problem) from problem
        cache.put(key, question, result)

    store.add_message(conversation_id, "assistant", result["answer"], result)

    messages = store.list_messages(conversation_id)
    return {
        "conversation": store.get_conversation(conversation_id),
        "question": messages[-2],
        "answer": messages[-1],
        "from_cache": from_cache,
    }
