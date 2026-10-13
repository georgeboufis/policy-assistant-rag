"""Adding and removing one document at a time.

1_build_database.py rebuilds everything, which is right when a setting changed - every
chunk has to be cut and embedded again. Uploading a document is the other case: the
other fifty-four chunks are already correct, and only the new file needs doing.

That is possible because a chunk's id says which document it came from
("expenses_policy.md-3"), so one document's chunks can be deleted and written again
without touching anybody else's. Everything here uses the same chunking, the same
context line and the same embedding model as the full build - it calls the same
functions - so a document added this way is indistinguishable from one that was there
when the database was built.

Embedding happens on this machine, so adding a document costs no model requests at all.
"""
import logging
import re

import chromadb

import config
from rag.ai_models import embed
from rag.cut_into_chunks import chunk
from rag.read_files import READERS, load

logging.getLogger("pypdf").setLevel(logging.ERROR)

# A file name we are willing to write into the data folder: no directories, no leading
# dots, nothing clever. Whatever the browser sends gets reduced to this.
SAFE_NAME = re.compile(r"[^A-Za-z0-9._Ͱ-Ͽἀ-῿-]+")


def safe_name(name):
    """A plain file name, with any path the browser sent stripped off."""
    name = name.replace("\\", "/").split("/")[-1]
    name = SAFE_NAME.sub("_", name).lstrip(".")
    return name[:120] or "document"


def supported():
    """The file endings there is a reader for."""
    return sorted(READERS)


def collection():
    database = chromadb.PersistentClient(path=str(config.DB_PATH))
    try:
        return database.get_collection("documents")
    except Exception:
        # Nothing built yet: make the collection the same way the full build does, so
        # the first uploaded document does not land in a differently configured one.
        return database.create_collection("documents", metadata={"hnsw:space": "cosine"})


def list_documents():
    """Every document in the data folder, with how many chunks it became."""
    stored = collection().get(include=["metadatas"])
    counts = {}
    for details in stored["metadatas"]:
        counts[details["source"]] = counts.get(details["source"], 0) + 1

    documents = []
    for path in sorted(config.DATA_DIR.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        documents.append({
            "name": path.name,
            "bytes": path.stat().st_size,
            "chunks": counts.get(path.name, 0),
            "supported": path.suffix.lower() in READERS,
        })
    return documents


def remove_from_index(name):
    """Drop every chunk of one document. Safe to call for a document with none."""
    collection().delete(where={"source": name})


def index_document(path):
    """Cut one document into chunks, embed them, and store them. Returns the count.

    Any chunks the document already had are deleted first, so uploading a newer version
    of the same file replaces it instead of storing both.
    """
    document_text = load(path)
    chunks = chunk(document_text, config.CHUNK_METHOD, embed)
    if not chunks:
        return 0

    title = path.stem.replace("_", " ").capitalize()
    texts_to_search, chunk_details, chunk_ids = [], [], []

    for number, each_chunk in enumerate(chunks):
        where_from = f"{title} › {each_chunk['section']}" if each_chunk["section"] else title

        if config.ADD_CONTEXT:
            texts_to_search.append(where_from + "\n" + each_chunk["search_text"])
        else:
            texts_to_search.append(each_chunk["search_text"])

        chunk_ids.append(f"{path.name}-{number}")
        chunk_details.append({
            "source": path.name,
            "section": each_chunk["section"],
            "model_text": where_from + "\n" + each_chunk["model_text"],
        })

    remove_from_index(path.name)
    collection().add(
        ids=chunk_ids,
        documents=texts_to_search,
        embeddings=embed(texts_to_search),
        metadatas=chunk_details,
    )
    return len(chunk_ids)


def delete_document(name):
    """Remove a document from the data folder and from the database."""
    path = config.DATA_DIR / safe_name(name)
    if not path.is_file():
        return False
    remove_from_index(path.name)
    path.unlink()
    return True
