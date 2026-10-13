"""Keyword search, to run alongside the vector search.

The vector search finds chunks that MEAN the same as the question. It is bad at rare
words - a name, a ticket number, a product code. "Who is Maria?" is the example in
this demo: the one chunk that says "this is Maria" is 0.78 away, because the name is a
few characters in a chunk that is otherwise all about VPN timeouts. An embedding is one
vector for the whole chunk, so a word mentioned once barely moves it.

A keyword search has the opposite strengths. It knows nothing about meaning, so it
cannot match "ship" to "arrive" - but a rare word scores enormously, because it scores
words by how UNUSUAL they are. Run both and you cover each other's blind spots.

The scoring here is BM25, the standard for keyword search. For each word of the
question that appears in a chunk, it adds up:

    how rare the word is          a word in 1 chunk of 52 counts for far more than
    (idf)                         a word in 40 of them - "Maria" beats "is"
    how often it appears          twice is better than once, but not twice as good
    (term frequency)
    how long the chunk is         a word in a short chunk matters more than the same
    (length normalisation)        word in a long one

Nothing to install - it is about thirty lines of arithmetic.
"""
import math
import re

import config
from collections import Counter

# The two standard BM25 dials. K1 is how much repeating a word helps; B is how much a
# chunk's length counts against it. These values are the usual defaults.
K1 = 1.5
B = 0.75

# Words too common to carry meaning. Without this, "who is Maria" would score every
# chunk containing "is". BM25's idf already pushes them down - this just removes them.
TOO_COMMON = {
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "get", "have", "how", "i", "if", "in", "is", "it", "its", "long", "many",
    "me", "much", "my", "need", "of", "on", "or", "our", "that", "the", "their", "them",
    "there", "these", "this", "to", "was", "we", "what", "when", "where", "which",
    "who", "will", "with", "you", "your",
}


def words_in(text):
    """Every word of a text, lowercased. Numbers count as words - "25" matters here.

    Single letters are dropped: splitting "supplier's" leaves an "s" behind, and that
    stray letter turned up in 10 chunks of 54, scoring them all for nothing.
    """
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 1]


def build_index(texts):
    """Count the words in every chunk once, so scoring a question is quick afterwards."""
    counted = [Counter(words_in(text)) for text in texts]
    lengths = [sum(counts.values()) for counts in counted]

    # How many chunks each word appears in at all - this is what makes a word "rare"
    chunks_containing = Counter()
    for counts in counted:
        for word in counts:
            chunks_containing[word] += 1

    return {
        "counted": counted,
        "lengths": lengths,
        "average_length": sum(lengths) / len(lengths) if lengths else 0,
        "chunks_containing": chunks_containing,
        "total_chunks": len(texts),
    }


def score_question(index, question):
    """Score every chunk against the question.

    Returns a score for each chunk, and the question words each one actually matched -
    the second part is what lets you confirm an answer came from the right place.
    """
    asked = [word for word in set(words_in(question)) if word not in TOO_COMMON]

    scores = [0.0] * index["total_chunks"]
    matched = [[] for _ in range(index["total_chunks"])]

    for word in asked:
        appears_in = index["chunks_containing"].get(word, 0)
        if not appears_in:
            continue

        # How rare the word is. A word in every chunk scores near 0; a word in one
        # chunk out of 52 scores high.
        rarity = math.log(
            1 + (index["total_chunks"] - appears_in + 0.5) / (appears_in + 0.5)
        )

        for number, counts in enumerate(index["counted"]):
            times = counts.get(word, 0)
            if not times:
                continue
            length_penalty = 1 - B + B * index["lengths"][number] / index["average_length"]
            scores[number] += rarity * (times * (K1 + 1)) / (times + K1 * length_penalty)
            matched[number].append(word)

    # A chunk whose only match is a bare number is not a keyword hit. A number in a
    # question is nearly always a value to compare, not what the question is about:
    # asked "Do I need a receipt for a 30 euro taxi?", the word "30" matched "within 30
    # days" in the cleaning contract and a line of the supplier's email, and those two
    # took half the prompt. ("euro" and "taxi" match nothing at all - the documents say
    # EUR, and never say taxi, which is why so much rode on the number.)
    for number in range(index["total_chunks"]):
        if matched[number] and all(word.isdigit() for word in matched[number]):
            scores[number] = 0.0
            matched[number] = []

    # Keep only the chunks that scored a real share of the best score, and drop the
    # rest to 0 so they count as no keyword hit at all. Two reasons this is needed:
    #
    #   - a chunk matching one word of four was otherwise ranked alongside one matching
    #     all four. "How long does a replacement monitor take to arrive?" put two
    #     chunks in the prompt whose only word in common was "take".
    #   - counting matched words treats them all alike, so a chunk can qualify on
    #     boilerplate. Asked whether a price rise was allowed under the cleaning
    #     contract, the contract's liability clause matched five words - "contract",
    #     "under", "cleaning", "supplier" - while the clause about fees, which actually
    #     answers it, lost its place. Scoring by rarity instead, "price" and "rise"
    #     count for far more than "contract" in a file full of the word "contract".
    best = max(scores) if scores else 0.0
    if best:
        for number in range(index["total_chunks"]):
            if scores[number] < best * config.KEYWORD_MIN_SHARE:
                scores[number] = 0.0
                matched[number] = []

    return scores, matched
