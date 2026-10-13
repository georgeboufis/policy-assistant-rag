"""
Every setting for the demo, in one place. The models and the key are set in .env.

Change a setting, run 1_build_database.py again, and ask the same questions to see what changed.
"""
from pathlib import Path

# ---------------------------------------------------------------------------------------
# Where things are
# ---------------------------------------------------------------------------------------

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"               # the documents to answer from
DB_PATH = HERE / "db" / "chroma_db"    # where 1_build_database.py saves the chunks


# ---------------------------------------------------------------------------------------
# How to cut the documents into chunks - try changing these
# ---------------------------------------------------------------------------------------

# The six methods from day two. Pick one:
#   "fixed_size"       cut every few hundred characters, wherever that lands
#   "recursive"        cut at paragraphs, then sentences, then words
#   "structure_aware"  cut at the document's own headings
#   "semantic"         cut where the topic changes
#   "parent_child"     search single sentences, but show the model the whole section
#   "sentence_window"  search single sentences, but show the model the ones around it
#   "paragraph"        one chunk per paragraph, with its heading
CHUNK_METHOD = "structure_aware"

CHUNK_SIZE = 500             # the longest a chunk may be, in characters
OVERLAP = 50                 # characters repeated at the start of the next chunk
SEMANTIC_BREAKPOINT = 0.8    # semantic only: cut at the biggest 20% of topic changes
WINDOW = 2                   # sentence_window only: sentences shown either side

# A trick from day two: put the document name and heading at the start of every chunk
# before searching, so a chunk still makes sense on its own. Try False to compare.
ADD_CONTEXT = True


# ---------------------------------------------------------------------------------------
# Searching and answering
# ---------------------------------------------------------------------------------------

TOP_K = 4             # how many of the closest chunks the model gets to read

# How much of a conversation is remembered when a follow-up is filled in. Five exchanges
# is five questions and their answers - deep enough that "δηλαδή" four questions into a
# conversation still resolves, short enough that the prompt stays small. Each
# conversation is remembered on its own; nothing leaks between them.
HISTORY_EXCHANGES = 5

# How far away the closest chunk can be before we refuse to answer.
# 0 means identical meaning; the bigger the number, the less related.
# Measured for paraphrase-multilingual-MiniLM-L12-v2 with extra_find_refusal_line.py.
# Run that again after switching embedding model - every model spreads its distances
# differently. 0.68 is set a little above the worst answerable GREEK question (0.65):
# asked in Greek, the same question lands further away than in English, far enough that
# the English-only calibration in that script does not cover it. Some unanswerable
# questions get through this line - the model refuses those itself.
MAX_DISTANCE = 0.68

# ---------------------------------------------------------------------------------------
# Hybrid search: meaning AND keywords
# ---------------------------------------------------------------------------------------

# False goes back to the vector search on its own, to compare.
USE_KEYWORDS = True

# How the two rankings are merged. Each chunk scores 1/(RRF_K + its position) in each
# ranking. A small number makes the top few positions count for much more than the
# rest; a large one flattens the difference. 60 is the published default, for lists of
# thousands - with 52 chunks, 10 keeps first place meaningfully ahead of tenth.
RRF_K = 10

# How good a keyword match has to be, as a share of the best one for that question.
# 0.5 keeps chunks scoring at least half of the best and ignores the rest, so a chunk
# that matched one word, or only boilerplate, does not take a place in the prompt.
# Lower it to 0 and ask about a replacement monitor to see what gets in.
KEYWORD_MIN_SHARE = 0.5

# Should a strong keyword hit answer even when the chunk is too far away by meaning?
# Off, because it cannot be made to work with a threshold: "Who is Maria?" finds its
# chunk 0.78 away scoring 2.6, while "What is the capital of France?" finds the Paris
# row of travel_rates.csv 0.75 away scoring 2.9. The question the documents DO answer
# looks worse on both measures than the one they do not. Turn it on to watch France
# get answered from the model's own knowledge.
KEYWORD_RESCUE = False
MIN_KEYWORD_SCORE = 2.5

# How much the chat model is allowed to vary its wording. 1 is the model's own default.
# Set it to 0 while debugging a wrong answer: at 1, "How long does a replacement monitor
# take to arrive?" answers on roughly 4 runs in 10 and refuses on the rest, from
# identical chunks, so you cannot tell a fix from a lucky run. At 0 it refuses every
# time - the same failure, but one you can measure.
TEMPERATURE = 1

# Print what happens at each step while chatting. False shows only the answers.
SHOW_STEPS = True

# Also print the exact prompt sent to the model, and its reply exactly as it came back.
# Long - turn it on when you need to know why the model answered the way it did.
SHOW_PROMPT = False
