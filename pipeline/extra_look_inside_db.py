"""
Look inside the database that 1_build_database.py built.

Shows how many chunks each document became, and what one chunk actually looks like.
Give a file name to see every chunk from that file, in order.

    uv run python extra_look_inside_db.py
    uv run python extra_look_inside_db.py support_call_transcript.txt
"""
import sys
from collections import Counter

import chromadb

import config

if not config.DB_PATH.exists():
    sys.exit("There is no database yet. Run 1_build_database.py first.")

collection = chromadb.PersistentClient(path=str(config.DB_PATH)).get_collection("documents")
everything = collection.get(include=["documents", "metadatas"])

# The chunks were saved with ids 0, 1, 2... in the order they were cut. Put them back in it.
order = sorted(range(len(everything["ids"])), key=lambda i: int(everything["ids"][i]))
chunks = [(everything["documents"][i], everything["metadatas"][i]) for i in order]


def show(searched_text, details):
    """Print one chunk as it gets searched, and what the model reads if that is different."""
    print(searched_text)
    # For parent_child and sentence_window, the model reads more than what was searched
    if details["model_text"] != searched_text:
        print("\n  What the model reads if this chunk is found:")
        print("  " + details["model_text"].replace("\n", "\n  "))


# --- One file: every chunk it became -------------------------------------------------------
if len(sys.argv) > 1:
    file_name = sys.argv[1]
    from_file = [(text, details) for text, details in chunks if details["source"] == file_name]
    if not from_file:
        sys.exit(f"No chunks from {file_name}. Check the name against the list without a file name.")

    print(f"{file_name} became {len(from_file)} chunks, cut with the {config.CHUNK_METHOD} method:")
    for number, (text, details) in enumerate(from_file, start=1):
        print(f"\n--- chunk {number} " + "-" * 60)
        show(text, details)
    sys.exit()

# --- No file given: how many chunks each file became, and one example ---------------------
print(f"{collection.count()} chunks in the database:\n")
for file_name, count in sorted(Counter(details["source"] for _, details in chunks).items()):
    print(f"  {count:>3}  {file_name}")

print("\nOne chunk, exactly as it gets searched:\n")
show(*chunks[0])
print("\nTo see every chunk from one file:  uv run python extra_look_inside_db.py <file name>")
