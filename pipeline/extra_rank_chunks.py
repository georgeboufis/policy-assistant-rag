"""
Rank every chunk in the database by how close it is to a question.

The chat only shows the closest few. This shows all of them, in order of meaning, marks
which ones the model really gets, and draws the refusal line - so you can see where the
right chunk ended up, and how far from the question it was.

The list is ordered by meaning alone, but the chat searches by meaning AND keyword
(see rag/keyword_search.py), so the chunks it sends are not always the first TOP_K here.
The ">>" marks come from the real search, so a ">>" further down the list is a chunk the
keyword half pulled in - which is worth knowing before you blame the model for what it
was given.

    uv run python extra_rank_chunks.py "Who is Maria?"
    uv run python extra_rank_chunks.py "Who is Maria?" 50     (show the closest 50)

A Greek question is translated into English first, exactly as the chat does it, because
the documents are English. Otherwise it searches the question as you type it: for a
follow-up like "and if it was 20 euros?", paste in the full question the chat printed at
step 1 instead.
"""
import sys

import chromadb

import config
from rag.ai_models import embed
from rag.answer import close_enough, search, standalone_question

if len(sys.argv) < 2:
    sys.exit('Give a question in quotes, e.g.  uv run python extra_rank_chunks.py "Who is Maria?"')
if not config.DB_PATH.exists():
    sys.exit("There is no database yet. Run 1_build_database.py first.")

question = sys.argv[1]
how_many = int(sys.argv[2]) if len(sys.argv) > 2 else 20

# The chat searches in English whatever language you ask in, so do the same here - or
# this would rank the chunks against a question the chat never searched for. The empty
# history is what makes this honest: a question typed here has no conversation behind
# it, exactly like the first question of a chat. It is the one request this script
# makes to the chat model, and only for a question that is not already English.
searched = standalone_question(question, [])
if searched != question:
    print(f"Searched in English as: {searched}\n")
    question = searched

collection = chromadb.PersistentClient(path=str(config.DB_PATH)).get_collection("documents")
how_many = min(how_many, collection.count())
results = collection.query(
    query_embeddings=embed([question]),
    n_results=how_many,
    include=["documents", "metadatas", "distances"],
)
texts = results["documents"][0]
details = results["metadatas"][0]
distances = results["distances"][0]

# What the chat would really send to the model, so the marks below tell the truth
chunks_sent = search(question)
really_read = [each_chunk["model_text"] for each_chunk in chunks_sent]

print(f"The closest {how_many} of {collection.count()} chunks to: {question}\n")
print(f"  >> = one of the {config.TOP_K} the model reads (TOP_K in config.py),"
      " by meaning and keyword together\n")

line_drawn = False
for rank in range(how_many):
    # Draw the refusal line where the distances cross MAX_DISTANCE
    if distances[rank] > config.MAX_DISTANCE and not line_drawn:
        print(f"  ---------- MAX_DISTANCE = {config.MAX_DISTANCE} - further than this is too far ----------")
        line_drawn = True

    marker = ">>" if details[rank]["model_text"] in really_read else "  "
    where = details[rank]["source"]
    if details[rank]["section"]:
        where += ", " + details[rank]["section"]
    # The chunk's first line is where it came from, so show the start of its text instead
    text = texts[rank].split("\n", 1)[-1].replace("\n", " ")
    print(f"{marker} {rank + 1:>3}. {distances[rank]:.2f}  {where}")
    print(f"             {text[:90]}")

# Whether the chat answers is close_enough()'s decision, not ours - it also lets a
# strong keyword match through when KEYWORD_RESCUE is on, which the line above does not
# show. Ask it, rather than comparing distances here and getting a different answer.
if not close_enough(chunks_sent):
    print("\nThe closest chunk is past the line, so the chat refuses without asking the model.")
elif min(each_chunk["distance"] for each_chunk in chunks_sent) > config.MAX_DISTANCE:
    print("\nEvery chunk is past the line, but the keywords match strongly enough"
          " (KEYWORD_RESCUE in config.py), so the model is asked anyway.")
else:
    # Count over the chunks actually sent, not the rows printed above - a short list
    # would otherwise undercount the ones that are past the line.
    past_line = sum(1 for each_chunk in chunks_sent
                    if each_chunk["distance"] > config.MAX_DISTANCE)
    print(f"\nThe closest chunk is inside the line, so the model reads all {config.TOP_K}", end="")
    print(f" - {past_line} of them from past the line." if past_line else ".")
