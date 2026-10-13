"""
STEP TWO OF A RAG: answer a question from the documents.

For every question, four things happen:

    1. Turn what was typed into one standalone question in English: translated, and
       with anything it referred to in the conversation filled back in
    2. Search the database for the chunks closest in meaning to that question
    3. If nothing is close enough, refuse - the documents do not cover it
    4. Otherwise, give the model those chunks and have it answer from them only,
       in the language the question was asked in

To chat, run 2_chat.py - it calls answer() below for every question you type.
"""
import json

import chromadb

import config
from rag.ai_models import ask_model, embed      # the only file that talks to the AI models
from rag.keyword_search import build_index, score_question

# What the bot says when the documents do not have the answer. The model writes its own
# refusal in the language of the question - but when step 3 refuses, no model is asked at
# all, so the sentence has to come from here. Greek questions are spotted by their own
# alphabet, which is enough for the two languages this demo is asked in; a third language
# would need either a language detector or a model call we are deliberately not making.
REFUSAL = "I could not find anything about that in the documents."
REFUSAL_GREEK = "Δεν βρήκα κάτι σχετικό στα έγγραφα."


def language_of(question):
    """The language to answer in, named for the model.

    The model is told outright instead of working it out. Asked a question in Greek
    written without accents - "Ποσες μερες ετησια αδεια δικαιουμαι" - it answered in
    English twice out of two, apparently not certain the question was Greek at all.
    We already know, from the alphabet, so there is no reason to let it guess.
    """
    return "Greek" if looks_greek(question) else "English"


def looks_greek(text):
    """True if the text contains Greek letters."""
    return any("\u0370" <= letter <= "\u03ff" or "\u1f00" <= letter <= "\u1fff"
               for letter in text)


def refusal_for(question):
    """The refusal sentence in the language the question looks like it is written in."""
    return REFUSAL_GREEK if looks_greek(question) else REFUSAL

# ---------------------------------------------------------------------------------------
# The standing brief: who the model is, what it is for, and how it should answer
# ---------------------------------------------------------------------------------------
# This goes in a "system" message, sent with every question. It holds what never
# changes. The question and its sources go in the "user" message, which changes every
# time. Keeping the two apart is what stops the rules reading like part of the question.

SYSTEM_PROMPT = f"""Your role
You are the assistant on an internal company help desk. You answer employees' questions
about their own company's documents: its policies, its contracts, and transcripts of its
support calls.

Your purpose
Every question reaches you with a few extracts from those documents, numbered as
sources, that a search picked out for it. Your job is to answer the question from those
extracts and from nothing else. An employee acts on what you tell them, so an invented
answer is worse than no answer.

How to answer
- Use only the numbered sources. Add nothing you know from elsewhere, however sure of it
  you are.
- The sources are extracts of real documents, so they seldom use the words of the
  question. A source answers the question when it states the fact asked for in its own
  words: when something ships tells an employee how long it takes to arrive, and a
  notice period tells them how much warning to give. Match the facts, not the wording.
- Read every source before you decide. The answer is often not in the first one.
- Before concluding that a question cannot be answered, look through the sources once
  more for the fact in different words. Only when no source states it, say in one short
  sentence that you cannot find it in the documents - in the language of the question.
- When the question mentions an amount, a date or a count, compare it with the one in
  the source and satisfy yourself which way round they go before you answer.
- Answer in one or two plain sentences. No preamble, no restating the question, no
  advice that the sources do not support.
- Answer in the language the question was asked in. The documents are in English, so a
  question in Greek is answered in Greek from English sources - translate what the
  source says, and never answer in English because that is what you read. That holds
  for saying you cannot find something too."""


# ---------------------------------------------------------------------------------------
# Step 1 - turn what was typed into one standalone question, in English
# ---------------------------------------------------------------------------------------

def looks_greek(text):
    """True if the text contains Greek letters."""
    return any("\u0370" <= letter <= "\u03ff" or "\u1f00" <= letter <= "\u1fff"
               for letter in text)


def language_of(question):
    """The language to answer in, named for the model.

    The model is told outright instead of working it out. Asked a question in Greek
    written without accents - "Ποσες μερες ετησια αδεια δικαιουμαι" - it answered in
    English twice out of two, apparently not certain the question was Greek at all.
    We already know, from the alphabet, so there is no reason to let it guess.
    """
    return "Greek" if looks_greek(question) else "English"


def document_list():
    """The documents, named the way a person would name them.

    This goes into the rewriting prompt. Without it the rewriting is correct but too
    literal to search with: asked "και για τους κωδικους;" it produced "what does the
    tech policy say about the codes?", and "codes" appears nowhere - the IT security
    policy calls them passwords. Knowing which documents exist is what lets it reach
    for the word those documents actually use.
    """
    names = sorted(
        path.stem.replace("_", " ") for path in config.DATA_DIR.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )
    return ", ".join(names)


def standalone_question(question, history):
    """What to actually search for: one complete question, in English.

    Two problems, one request. The documents are English, and a question that points
    back at the conversation ("and those?", "δηλαδή", "what about 20 euros?") means
    nothing to a search on its own - so both the translating and the filling-in happen
    here, together.

    This used to be two steps with a word list in between: a check for English pointing
    words like "it" or "those", and only then a rewrite. That list could never work
    once questions arrived in another language. Asked "τι ισχύει για το tech policy;"
    and then simply "δηλαδή", the second question matched no English pointing word, was
    never recognised as a follow-up, and was searched literally - so the assistant said
    it could not find anything, about a conversation it was in the middle of.

    Doing it in one request also costs less than the two it replaced, and there is no
    request at all for an English question that opens a conversation.
    """
    if not history:
        if not looks_greek(question):
            return question
        return ask_model(
            "Translate this question into English, as it would be worded in a company"
            f" document. The documents available are: {document_list()}.\n"
            "Reply with the translation only, nothing else.\n\n"
            f"{question}"
        )

    conversation = ""
    for earlier_question, earlier_answer in history[-config.HISTORY_EXCHANGES:]:
        conversation += f"Employee: {earlier_question}\nAssistant: {earlier_answer}\n"

    return ask_model(
        "Below is a conversation between an employee and an assistant that answers from"
        " company documents.\n\n"
        f"{conversation}\n"
        f"The employee now asks: {question}\n\n"
        f"The documents that can be searched are: {document_list()}.\n\n"
        "Write that last question as ONE complete question in English, understandable by"
        " somebody who has not seen the conversation.\n"
        "- Word it the way those documents would word it. They are written in plain"
        " company English, so prefer their term over a literal translation: an account's"
        " secret is a password, not a code.\n"
        "- If it refers back to the conversation in any way - a pronoun, a bare word like"
        " \"and?\" or \"δηλαδή\", a follow-up with no subject - put the subject back in,"
        " taking it from the conversation above.\n"
        "- If it already stands on its own, just translate it.\n"
        "- Keep it a question about the documents. Do not answer it.\n"
        "Reply with the question only."
    )


# ---------------------------------------------------------------------------------------
# Step 2 - search for the closest chunks
# ---------------------------------------------------------------------------------------

def search(question):
    """Find the chunks that best match the question, best first.

    Two searches run over the same chunks:

        by meaning   the embedding distance, which matches "ship" to "arrive" but is
                     weak on rare words like a name
        by keyword   BM25, which is blind to meaning but scores a rare word heavily

    Their two rankings are merged by position, not by score - a distance of 0.78 and a
    BM25 score of 4.1 are not on the same scale and cannot be added. What IS comparable
    is "second in one list, first in the other". So each chunk scores 1/(RRF_K + rank)
    in each list, and the two are added. A chunk both searches like beats a chunk that
    only one of them likes. This is called reciprocal rank fusion.

    Each chunk comes back as a dictionary with where it came from, what the model will
    read, its distance, its keyword score, and which words of the question it matched.
    """
    database = chromadb.PersistentClient(path=str(config.DB_PATH))
    collection = database.get_collection("documents")
    how_many = collection.count()

    # Rank EVERY chunk by meaning, not just the closest few - the keyword search needs a
    # position for each one to merge with. With 52 chunks this costs nothing.
    results = collection.query(
        query_embeddings=[embed([question])[0]],
        n_results=how_many,
        include=["metadatas", "distances", "documents"],
    )
    # The database can search for several questions at once, so each result is a list
    # with one entry per question. We asked one question, so we take entry [0].
    details_of_each = results["metadatas"][0]
    distance_of_each = results["distances"][0]
    text_of_each = results["documents"][0]        # the exact text that was searched

    # Rank the same chunks by keyword
    if config.USE_KEYWORDS:
        scores, matches = score_question(build_index(text_of_each), question)
    else:
        scores = [0.0] * how_many
        matches = [[] for _ in range(how_many)]

    found = []
    for position in range(len(details_of_each)):
        details = details_of_each[position]
        found.append({
            "source": details["source"],
            "section": details["section"],
            "model_text": details["model_text"],
            "distance": distance_of_each[position],
            "meaning_rank": position + 1,                 # 1 = closest in meaning
            "keyword_score": scores[position],
            "matched_words": matches[position],
            "keyword_rank": None,                         # filled in just below
        })

    # Where each chunk came in the keyword ranking. A chunk that matched no word of the
    # question has no keyword position at all - it must not be credited for one.
    by_keyword = sorted(found, key=lambda each: -each["keyword_score"])
    for rank, each_chunk in enumerate(by_keyword, start=1):
        if each_chunk["keyword_score"] > 0:
            each_chunk["keyword_rank"] = rank

    # Merge the two rankings
    for each_chunk in found:
        total = 1 / (config.RRF_K + each_chunk["meaning_rank"])
        if each_chunk["keyword_rank"]:
            total += 1 / (config.RRF_K + each_chunk["keyword_rank"])
        each_chunk["score"] = total

    found.sort(key=lambda each: -each["score"])

    # With parent_child, several sentences can lead to the same section. Keep each
    # piece of text only once, so the model does not read the same section twice.
    closest = []
    texts_already_found = set()
    for each_chunk in found:
        if each_chunk["model_text"] in texts_already_found:
            continue
        texts_already_found.add(each_chunk["model_text"])
        closest.append(each_chunk)

    return closest[:config.TOP_K]


# ---------------------------------------------------------------------------------------
# Step 3 - decide whether to answer at all
# ---------------------------------------------------------------------------------------

def close_enough(chunks):
    """True if the closest chunk is near enough to answer from.

    A chunk is near enough if it is within MAX_DISTANCE by meaning, OR if it matched the
    question's rare words strongly enough (MIN_KEYWORD_SCORE). If nothing passes either
    test, the documents do not cover the question, and we refuse without asking the
    model at all, so it gets no chance to make an answer up.
    """
    for each_chunk in chunks:
        if each_chunk["distance"] <= config.MAX_DISTANCE:
            return True
        # A strong keyword hit is reason enough on its own. "Who is Maria?" finds the
        # right chunk 0.78 away - too far by meaning, but the name is rare enough that
        # BM25 is certain. Without this, the keyword search could rank that chunk first
        # and still be refused by a limit measured for the vector search alone.
        if config.KEYWORD_RESCUE and each_chunk["keyword_score"] >= config.MIN_KEYWORD_SCORE:
            return True
    return False


# ---------------------------------------------------------------------------------------
# Step 4 - have the model answer from the chunks
# ---------------------------------------------------------------------------------------

def build_prompt(question, chunks, language="English"):
    """Write the prompt: the rules, the numbered chunks, and the question.

    `language` is the language to answer in. It is passed in rather than read off the
    question, because by this point the question has been translated into English - the
    language that matters is the one the person actually typed.

    The model replies in JSON, with the sentence it relied on and any comparison it
    made written out before the answer. Two of the rules fix real mistakes the model
    made while this demo was being built:
      - Showing its working. Without it, the model read "receipts are required above
        EUR 25" and said a 30 euro taxi needs no receipt.
      - Reading every source first. Without it, asked how long a monitor takes to
        "arrive", it missed the sentence saying monitors "ship" in five days.
    """
    numbered_chunks = ""
    for number, each_chunk in enumerate(chunks, start=1):
        numbered_chunks += f"[{number}] {each_chunk['model_text']}\n\n"

    return f"""Reply with only a JSON object with these four keys, in this order:
  "sources": the numbers of every source you used, in the order you used them, as a \
list - [1] for one, [1, 2] when the answer needed two. Leave out a source you did not use.
  "quote":  the sentence or sentences from those sources that answer the question
  "check":  if the question mentions an amount, date or count, compare it with the one in the source \
and write the comparison out, for example "30 is more than 25". Otherwise "nothing to compare".
  "answer": the answer in one or two sentences

If no source answers the question, set "sources" to [] and write in "answer", in the
language of the question, one short sentence saying it is not in the documents.

Sources:
{numbered_chunks.strip()}

Question: {question}

Write "answer" in {language}."""


def as_text(value):
    """What the model sent, as a string.

    "quote" is asked for as a sentence, but a model will now and then send a list of
    sentences instead, or a number. Anything that is not text has to become text here:
    further down the line it is printed, and in rag_ui it is written to a database
    column, which refused a list outright and turned the whole answer into an error.
    """
    if isinstance(value, list):
        return " ".join(as_text(item) for item in value if item not in (None, ""))
    return "" if value is None else str(value).strip()


def read_reply(reply):
    """Turn the model's JSON reply into "quote", "check", "answer" and "cited".

    The model gives the source numbers separately, and we add them to the end of the
    answer as [1][2] ourselves - that way the citations are always in the same place,
    and always match the numbers we handed it. "cited" is those numbers, which is how
    answer() knows which files were really used rather than merely shown.

    Some models put ```json ... ``` around their JSON, so that is removed first. If the
    reply is not JSON at all, the whole reply is treated as the answer.
    """
    cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        parts = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"quote": "", "check": "", "answer": reply, "cited": []}

    # Asked for a list, a model will now and then send one number, or a number as text
    given = parts.get("sources", parts.get("source", []))
    if not isinstance(given, list):
        given = [given]

    cited = []
    for number in given:
        try:
            number = int(number)
        except (TypeError, ValueError):
            continue                       # not a number at all - ignore it
        if number > 0 and number not in cited:
            cited.append(number)

    cited.sort()                       # [1][2] reads better than [2][1]

    answer_text = as_text(parts.get("answer", reply)) or reply
    if cited:
        answer_text += " " + "".join(f"[{number}]" for number in cited)

    return {
        "quote": as_text(parts.get("quote")),
        "check": as_text(parts.get("check")),
        "answer": answer_text,
        "cited": cited,
    }


# ---------------------------------------------------------------------------------------
# All four steps together
# ---------------------------------------------------------------------------------------

def answer(question, history=None):
    """Answer one question, and return everything that happened along the way.

    The dictionary returned holds:
        answer    the reply to show
        sources   the files the model cited - empty if it refused
        asked     the question exactly as it was typed
        searched  what was actually searched for: in English, standing on its own,
                  with any reference to the conversation resolved
        chunks    the closest chunks found (step 2)
        quote     the sentence the model relied on (step 4)
        check     the comparison the model wrote out, if any (step 4)
        prompt    exactly what was sent to the model - missing if it refused at step 3
        reply     exactly what the model sent back - missing if it refused at step 3
    """
    history = history or []
    result = {"answer": refusal_for(question), "sources": [], "quote": "", "check": ""}

    # Step 1: one complete question, in English, with anything it referred to filled in
    # from the conversation. This is where the thread is actually used.
    answer_in = language_of(question)
    result["asked"] = question
    result["searched"] = standalone_question(question, history)

    # Step 2: find the closest chunks
    result["chunks"] = search(result["searched"])

    # Step 3: refuse if nothing is close enough - the model is never asked
    if not close_enough(result["chunks"]):
        return result

    # Step 4: have the model answer from the chunks, showing its working.
    # It gets the rewritten question too - "and if it was 20 euros?" means nothing on its own.
    result["prompt"] = build_prompt(result["searched"], result["chunks"], answer_in)
    result["reply"] = ask_model(result["prompt"], json_reply=True, system=SYSTEM_PROMPT)
    reply = read_reply(result["reply"])
    result["answer"] = reply["answer"]
    result["quote"] = reply["quote"]
    result["check"] = reply["check"]

    # The model can still decide the chunks do not answer the question - that is a refusal
    # too, and it is the empty "sources" that tells us so. Matching the English refusal
    # sentence would miss a refusal written in the language the question was asked in.
    if reply["cited"]:
        # Only the files the model actually cited, each once, in the order it cited them.
        # Listing every chunk it was SHOWN would credit documents it never used.
        for number in reply["cited"]:
            if 1 <= number <= len(result["chunks"]):          # ignore a number we never gave it
                source = result["chunks"][number - 1]["source"]
                if source not in result["sources"]:
                    result["sources"].append(source)

    return result
