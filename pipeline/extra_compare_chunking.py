"""
Cut one document all six ways from day two, and print where each method makes its cuts.

    uv run python extra_compare_chunking.py expenses_policy.md
    uv run python extra_compare_chunking.py support_call_transcript.txt

Nothing is saved - this only shows the chunks, so you can compare the methods.
"""
import sys

import config
from rag.cut_into_chunks import METHODS, chunk
from rag.read_files import load
from rag.ai_models import embed

# Which document to cut: the one named after the command, or the expenses policy
file_name = sys.argv[1] if len(sys.argv) > 1 else "expenses_policy.md"
path = config.DATA_DIR / file_name
if not path.exists():
    sys.exit(f"There is no {file_name} in the data folder.")

text = load(path)
HOW_MANY_TO_SHOW = 4

for method in METHODS:
    chunks = chunk(text, method, embed)
    print(f"\n=== {method}: {len(chunks)} chunks")

    for number, each_chunk in enumerate(chunks[:HOW_MANY_TO_SHOW], start=1):
        heading = f"({each_chunk['section']}) " if each_chunk["section"] else ""
        searched = each_chunk["search_text"].replace("\n", " ")
        print(f"  [{number}] {heading}{searched[:90]}")

        # Parent-child and sentence-window show the model more than they search
        if each_chunk["model_text"] != each_chunk["search_text"]:
            shown = each_chunk["model_text"].replace("\n", " ")
            print(f"      model reads: {shown[:84]}")

    if len(chunks) > HOW_MANY_TO_SHOW:
        print(f"  ... and {len(chunks) - HOW_MANY_TO_SHOW} more")
