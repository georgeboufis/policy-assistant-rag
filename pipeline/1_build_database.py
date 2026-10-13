"""
STEP ONE OF A RAG: prepare the documents. Run this once, before 2_chat.py.
Run it again whenever you change the documents or a setting in config.py.

    1. Read every document and cut it into chunks
    2. Turn every chunk into numbers that capture its meaning (an "embedding")
    3. Save the chunks and their numbers in a database on your laptop

    uv run python 1_build_database.py
"""
import logging

import chromadb

import config
from rag.cut_into_chunks import chunk
from rag.read_files import load
from rag.ai_models import EMBEDDING_MODEL, embed      # the only file that talks to the AI models

# Two of the PDFs print harmless warnings while being read. Hide them.
logging.getLogger("pypdf").setLevel(logging.ERROR)


def main():
    texts_to_search = []     # the text of every chunk, which is what gets searched
    chunk_details = []       # what else we want to remember about each chunk
    chunk_ids = []           # "expenses_policy.md-3" - the file it came from, and which
                             # chunk of it. Named rather than numbered, so one document
                             # can be re-indexed on its own without renumbering the rest
                             # (which is what rag_ui needs to add an uploaded file).

    # --- 1. Read every document and cut it into chunks ---------------------------------
    print(f"Embedding model: {EMBEDDING_MODEL}. Cutting the documents into chunks with the {config.CHUNK_METHOD} method:\n")

    for path in sorted(config.DATA_DIR.iterdir()):
        document_text = load(path)
        chunks = chunk(document_text, config.CHUNK_METHOD, embed)
        print(f"  {path.name:<28} {len(chunks):>3} chunks")

        # A readable title from the file name: "expenses_policy.md" becomes "Expenses policy"
        title = path.stem.replace("_", " ").capitalize()

        for number, each_chunk in enumerate(chunks):
            # Where the chunk came from, e.g. "Expenses policy › 4. Expenses"
            if each_chunk["section"]:
                where_from = f"{title} › {each_chunk['section']}"
            else:
                where_from = title

            # The trick from day two: put where the chunk came from at its start before
            # searching. On its own, "Receipts are required above EUR 25" does not say it
            # is about expenses - with the title in front of it, it does.
            if config.ADD_CONTEXT:
                texts_to_search.append(where_from + "\n" + each_chunk["search_text"])
            else:
                texts_to_search.append(each_chunk["search_text"])

            chunk_ids.append(f"{path.name}-{number}")
            chunk_details.append({
                "source": path.name,                                     # which file, for the answer
                "section": each_chunk["section"],                        # which heading, if known
                "model_text": where_from + "\n" + each_chunk["model_text"],  # what the model will read
            })

    # --- 2. Turn every chunk into numbers ---------------------------------------------------
    print(f"\nTurning {len(texts_to_search)} chunks into numbers (embeddings)...")
    embeddings = embed(texts_to_search)

    # --- 3. Save everything in the database -----------------------------------------------
    database = chromadb.PersistentClient(path=str(config.DB_PATH))

    # Throw away what an earlier run saved, so nothing is stored twice
    existing = [collection.name for collection in database.list_collections()]
    if "documents" in existing:
        database.delete_collection("documents")

    # "cosine" tells the database to compare chunks by meaning:
    # distance 0 means the same meaning, and bigger means less related
    collection = database.create_collection("documents", metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=chunk_ids,
        documents=texts_to_search,
        embeddings=embeddings,
        metadatas=chunk_details,
    )
    print(f"Saved {collection.count()} chunks. Now run 2_chat.py.")


if __name__ == "__main__":
    main()
