"""
The only file that talks to the AI models. It has two functions:

    embed(texts)        turn a list of texts into embeddings (lists of numbers)
    ask_model(prompt)   send a prompt to the chat model and get its reply

The models are reached through the bootcamp's LiteLLM proxy. It accepts the ordinary
OpenAI kind of request, so the plain OpenAI client works. See .env.example.
"""
import os
import sys
from pathlib import Path

import numpy
from dotenv import load_dotenv
from fastembed import TextEmbedding
from openai import OpenAI

import config

# The .env in the rag_demo folder - found by its exact path, so it works however the
# scripts are started (the VS Code debugger, for one, would otherwise look in the wrong folder)
ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE, override=True)


def setting(name):
    """Read a value from .env, and stop with a clear message if it is missing."""
    value = os.getenv(name)
    if not value:
        sys.exit(f"{name} is missing from {ENV_FILE}. Copy .env.example to .env in the rag_demo "
                 "folder and paste in your key.")
    return value


# ---------------------------------------------------------------------------------------
# Connect to the proxy
# ---------------------------------------------------------------------------------------

# Chat: Groq speaks the OpenAI protocol, so only the address changes
client = OpenAI(api_key=setting("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1")
CHAT_MODEL = setting("GROQ_MODEL")

# Embeddings: Groq serves none, so they are computed on this machine. Nothing is sent
# anywhere. This model understands many languages, including Greek, so a question asked
# in Greek still finds the right chunk of an English document - the earlier
# all-MiniLM-L6-v2 was English-only and put the same question 0.85 away instead of 0.28.
# 220MB, 384 numbers per chunk, downloaded once to ~/.cache/fastembed. It runs on
# onnxruntime, so there is no torch to install.
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_embedder = TextEmbedding(model_name="sentence-transformers/" + EMBEDDING_MODEL)


# ---------------------------------------------------------------------------------------
# The two functions everything else uses
# ---------------------------------------------------------------------------------------

def embed(texts):
    """Turn a list of texts into a list of embeddings - one list of numbers per text.

    Texts that mean similar things get similar numbers, which is what lets us search by
    meaning instead of by exact words. They are done 100 at a time to keep memory flat
    when a whole folder of documents is embedded at once.
    """
    embeddings = []
    for start in range(0, len(texts), 100):
        batch = texts[start:start + 100]
        # .tolist() gives plain Python floats - Chroma rejects numpy scalars
        embeddings.extend(numpy.asarray(list(_embedder.embed(batch))).tolist())
    return embeddings


def ask_model(prompt, json_reply=False, system=None):
    """Send a prompt to the chat model and return its reply as text.

    json_reply=True asks for a guarantee that the reply is valid JSON. Left to
    itself, the model sometimes forgets a quote mark and the reply cannot be read.

    system is the standing brief - who the model is and how it should answer. It goes
    in a message of its own, which models are trained to weigh more heavily than the
    question, and which stays the same for every question asked.
    """
    options = {}
    if json_reply:
        options["response_format"] = {"type": "json_object"}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=config.TEMPERATURE,
        **options,
    )
    return response.choices[0].message.content.strip()
