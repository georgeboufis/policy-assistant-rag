"""
Chat with the documents in the terminal. Run 1_build_database.py first, then:

    uv run python 2_chat.py

Every question goes to answer() in rag/answer.py. With SHOW_STEPS on in config.py, the chat
also prints the four steps it went through, numbered the same way as in rag/answer.py.
"""
import sys

import config
from rag.answer import answer
from rag.ai_models import CHAT_MODEL


def show_steps(question, result):
    """Print each of the four steps, so you can see why the bot answered the way it did."""
    # Step 1 - what was searched for, after translating and resolving any follow-up
    if result["searched"] == question:
        print(f"   1. Searching for: {question}")
    else:
        print(f"   1. Searching for: {result['searched']}")
        print("      (the question as typed was translated, or it was a follow-up that"
              " needed the conversation to make sense)")

    # Step 2 - the best chunks, and why each one is there. "meaning" and "keyword" are
    # its position in each of the two searches, so you can see which one found it.
    print("   2. Best chunks found (distance - smaller is closer):")
    for number, each_chunk in enumerate(result["chunks"], start=1):
        where = each_chunk["source"]
        if each_chunk["section"]:
            where += ", " + each_chunk["section"]
        found_by = f"meaning #{each_chunk['meaning_rank']}"
        if each_chunk["keyword_rank"]:
            found_by += f", keyword #{each_chunk['keyword_rank']}"
            found_by += f" on {'+'.join(each_chunk['matched_words'])}"
        print(f"        [{number}] {each_chunk['distance']:.2f}  {where}")
        print(f"            found by {found_by}")

    # Step 3 - answer or refuse
    closest = min(each_chunk["distance"] for each_chunk in result["chunks"])
    if not any(each_chunk["distance"] <= config.MAX_DISTANCE for each_chunk in result["chunks"]):
        rescued = config.KEYWORD_RESCUE and any(
            each_chunk["keyword_score"] >= config.MIN_KEYWORD_SCORE for each_chunk in result["chunks"])
        if not rescued:
            print(f"   3. The closest is {closest:.2f} away - over the {config.MAX_DISTANCE} limit,"
                  " so we refuse without asking the model.")
            return
        print(f"   3. The closest is {closest:.2f} away - over the {config.MAX_DISTANCE} limit, but the"
              " keywords match strongly enough, so we ask the model.")
    else:
        print(f"   3. The closest is {closest:.2f} away - within the {config.MAX_DISTANCE} limit, so we ask the model.")

    # Step 4 - the model's working
    if result["quote"]:
        print(f"   4. The model relied on: {result['quote']}")
    if result["check"] and result["check"].lower() != "nothing to compare":
        print(f"      and checked: {result['check']}")


def main():
    if not config.DB_PATH.exists():
        sys.exit("There is no database yet. Run 1_build_database.py first.")

    history = []     # the questions and answers so far, so follow-ups make sense
    print(f"Chat model: {CHAT_MODEL}. Chunks were cut with the {config.CHUNK_METHOD} method.")
    print("Ask a question about the documents. Type quit to stop.\n")

    while True:
        try:
            question = input("You: ").strip()
        except EOFError:
            break
        if question.lower() == "quit":
            break
        if not question:
            continue

        result = answer(question, history)
        if config.SHOW_STEPS:
            print()
            show_steps(question, result)
        if config.SHOW_PROMPT and "prompt" in result:
            print("\n----- The prompt sent to the model -----\n" + result["prompt"])
            print("\n----- The model's reply, as it came back -----\n" + result["reply"])
        print(f"\nBot: {result['answer']}\n")

        # Remember the exchange whatever came of it. Even a refusal carries the subject
        # of the question, which is exactly what a follow-up like "δηλαδή" needs in
        # order to be filled in. Only the last HISTORY_EXCHANGES of these are ever used.
        history.append((question, result["answer"]))


if __name__ == "__main__":
    main()
