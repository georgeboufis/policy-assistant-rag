"""
Find the right MAX_DISTANCE for your embedding model. Run 1_build_database.py first, then:

    uv run python extra_find_refusal_line.py

MAX_DISTANCE is the line between "the documents cover this" and "they do not". Every
embedding model spreads its distances differently, so the line that works for one model
is wrong for another. This asks some questions the documents DO answer and some they
DO NOT, prints how far away the closest chunk was for each, and suggests a value.
Put it in config.py.
"""
from rag.answer import search
from rag.ai_models import EMBEDDING_MODEL

COVERED = [
    "How many days of annual leave do I get?",
    "Do I need a receipt for a 30 euro taxi?",
    "How much notice do we need to give to end the cleaning contract?",
    "What is the hotel limit in London?",
    "How long is a temporary access code valid?",
    "When do new starters have to finish security training?",
    "How long does a replacement monitor take to arrive?",
]
NOT_COVERED = [
    "What is the capital of France?",
    "How do I cook pasta carbonara?",
    "Who won the last World Cup?",
    "What is the company's revenue this year?",
]

print(f"Embedding model: {EMBEDDING_MODEL}\n")

print("Questions the documents answer - distance of the closest chunk:")
covered = []
for question in COVERED:
    distance = search(question)[0]["distance"]
    covered.append(distance)
    print(f"  {distance:.2f}  {question}")

print("\nQuestions they do not answer:")
not_covered = []
for question in NOT_COVERED:
    distance = search(question)[0]["distance"]
    not_covered.append(distance)
    print(f"  {distance:.2f}  {question}")

furthest_answer = max(covered)
nearest_non_answer = min(not_covered)
print(f"\nThe furthest answerable question was {furthest_answer:.2f} away.")
print(f"The nearest unanswerable one was {nearest_non_answer:.2f} away.")

# Refusing a question the documents DO answer is the worse mistake - and anything
# unanswerable that slips past the line is still refused by the model, which is told to
# say so when the chunks do not answer. So set the line a little above the furthest
# answerable question, rather than halfway.
suggestion = round(furthest_answer + 0.1, 2)
print(f"\nSet MAX_DISTANCE = {suggestion} in config.py - a little above the furthest answerable question.")
if suggestion > nearest_non_answer:
    print("Some unanswerable questions will get past it - the model refuses those itself.")
