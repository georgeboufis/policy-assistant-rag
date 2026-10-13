"""
The six ways to cut documents into chunks, from the day two slides.

Why cut documents up at all? A search works best on short pieces of text - a whole
document is about too many things to match any one question well. So every document
is cut into chunks, and the search looks for the chunks closest to the question.

Pick a method with CHUNK_METHOD in config.py, then run 1_build_database.py again.

Every method returns a list of chunks. Each chunk is a dictionary with three things:

    search_text   the words that get searched
    model_text    the words the model reads if this chunk is found
                  (the same as search_text, except for parent_child and sentence_window)
    section       the heading the chunk sits under, if the method knows it
"""
import math
import re

import config


def make_chunk(search_text, model_text=None, section=""):
    """Build one chunk. Unless told otherwise, the model reads the same words that were searched."""
    if model_text is None:
        model_text = search_text
    return {"search_text": search_text, "model_text": model_text, "section": section}


# ---------------------------------------------------------------------------------------
# Two helpers used by several of the methods
# ---------------------------------------------------------------------------------------

def split_sections(text):
    """Split a document at its headings.

    rag/read_files.py marks every heading with '#', so a line starting with '#' is a heading,
    and everything after it up to the next heading is that section.
    Returns a list of (heading, section text) pairs.
    """
    sections = []
    heading = ""
    lines_in_section = []

    for line in text.split("\n"):
        line = line.strip()

        if line.startswith("#"):
            # A new heading. Save the section we were collecting, then start the next one.
            if lines_in_section:
                sections.append((heading, "\n".join(lines_in_section)))
            heading = line.lstrip("#").strip()
            lines_in_section = []

        elif line:
            lines_in_section.append(line)

    # Save the last section
    if lines_in_section:
        sections.append((heading, "\n".join(lines_in_section)))
    return sections


def split_sentences(text):
    """Split text into sentences, leaving out the headings.

    A sentence ends with '.', '!' or '?' followed by a space. That is good enough
    here, though it would be fooled by abbreviations like "e.g." in real documents.
    """
    sentences = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split after every . ! or ? that is followed by a space
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            if sentence:
                sentences.append(sentence)
    return sentences


# ---------------------------------------------------------------------------------------
# 1. FIXED-SIZE
#    Good for:   huge amounts of plain text, or when you need something working today
#    Watch out:  it cuts mid-sentence, even mid-word
# ---------------------------------------------------------------------------------------

def fixed_size(text):
    """Cut the text every CHUNK_SIZE characters, ignoring what it says.

    Each chunk starts OVERLAP characters before the previous one ended, so a sentence
    cut at the edge of one chunk also appears at the start of the next.
    """
    chunks = []
    step = config.CHUNK_SIZE - config.OVERLAP
    for start in range(0, len(text), step):
        chunks.append(make_chunk(text[start:start + config.CHUNK_SIZE]))
    return chunks


# ---------------------------------------------------------------------------------------
# 2. RECURSIVE - the sensible default for ordinary text
#    Good for:   almost anything
#    Watch out:  it ignores headings, so a rule can be separated from its title
# ---------------------------------------------------------------------------------------

# Places to cut, from the most natural to the least:
# a blank line, a line break, the end of a sentence, a space between words
SEPARATORS = [r"\n\s*\n", r"\n", r"(?<=[.!?])\s+", r"\s+"]


def break_into_pieces(text, separators):
    """Break text into pieces no longer than CHUNK_SIZE.

    Cut at the most natural place first (blank lines). Only a piece that is still
    too long gets cut again at the next place on the list (line breaks), and so on.
    """
    if len(text) <= config.CHUNK_SIZE or not separators:
        return [text]

    pieces = []
    for part in re.split(separators[0], text):
        if part.strip():
            pieces += break_into_pieces(part, separators[1:])
    return pieces


def last_pieces_that_fit(pieces, limit):
    """The last few pieces, as many as fit in `limit` characters. Used for the overlap."""
    kept = []
    for piece in reversed(pieces):
        if len("\n".join([piece] + kept)) > limit:
            break
        kept.insert(0, piece)
    return kept


def recursive(text):
    """Cut the text at natural places, then put the pieces back together into chunks
    of up to CHUNK_SIZE characters."""
    chunks = []
    pieces_in_chunk = []

    for piece in break_into_pieces(text, SEPARATORS):
        chunk_if_added = "\n".join(pieces_in_chunk + [piece])

        # If adding this piece would make the chunk too long, finish the chunk here
        if pieces_in_chunk and len(chunk_if_added) > config.CHUNK_SIZE:
            chunks.append(make_chunk("\n".join(pieces_in_chunk)))
            # Start the next chunk with the end of this one - that is the overlap
            pieces_in_chunk = last_pieces_that_fit(pieces_in_chunk, config.OVERLAP)

        pieces_in_chunk.append(piece)

    if pieces_in_chunk:
        chunks.append(make_chunk("\n".join(pieces_in_chunk)))
    return chunks


# ---------------------------------------------------------------------------------------
# 3. STRUCTURE-AWARE
#    Good for:   policies, contracts, manuals - anything with headings
#    Watch out:  it needs readers that keep the headings, and sections vary in length
# ---------------------------------------------------------------------------------------

def structure_aware(text):
    """One chunk per section, and each chunk remembers its heading.

    A section longer than CHUNK_SIZE is cut further with the recursive method,
    and every piece still remembers the heading it came from.
    """
    chunks = []
    for heading, section_text in split_sections(text):
        for piece in recursive(section_text):
            chunks.append(make_chunk(piece["search_text"], section=heading))
    return chunks


# ---------------------------------------------------------------------------------------
# 4. SEMANTIC
#    Good for:   transcripts, interviews, long text with no headings
#    Watch out:  it has to turn every sentence into numbers first - slower, and it costs more
# ---------------------------------------------------------------------------------------

def distance(numbers_a, numbers_b):
    """How different two pieces of text are in meaning, once turned into numbers.
    0 means the same meaning. The bigger the number, the less related they are."""
    dot = sum(a * b for a, b in zip(numbers_a, numbers_b))
    length_a = math.sqrt(sum(a * a for a in numbers_a))
    length_b = math.sqrt(sum(b * b for b in numbers_b))
    return 1 - dot / (length_a * length_b)


def semantic(text, embed):
    """Start a new chunk wherever the topic changes.

    1. Turn every sentence into numbers.
    2. Measure how different each sentence is from the one before it.
    3. The biggest differences are where the topic changes - cut there.
    """
    sentences = split_sentences(text)
    if len(sentences) < 3:
        return [make_chunk(" ".join(sentences))]

    numbers = embed(sentences)

    # How much the meaning jumps between each sentence and the next one
    jumps = []
    for i in range(len(sentences) - 1):
        jumps.append(distance(numbers[i], numbers[i + 1]))

    # Only the biggest jumps count as a change of topic. With SEMANTIC_BREAKPOINT = 0.8
    # that means the top 20%: sort the jumps and read off the one 80% of the way up.
    position = min(len(jumps) - 1, int(len(jumps) * config.SEMANTIC_BREAKPOINT))
    big_jump = sorted(jumps)[position]

    chunks = []
    sentences_in_chunk = [sentences[0]]
    for i in range(1, len(sentences)):
        if jumps[i - 1] >= big_jump:
            # The topic changed before this sentence: finish the chunk here
            chunks.append(make_chunk(" ".join(sentences_in_chunk)))
            sentences_in_chunk = []
        sentences_in_chunk.append(sentences[i])

    chunks.append(make_chunk(" ".join(sentences_in_chunk)))
    return chunks


# ---------------------------------------------------------------------------------------
# 5. PARENT-CHILD
#    Good for:   when search finds the right place, but the answer comes out cut short
#    Watch out:  the model reads a lot more text for every chunk found
# ---------------------------------------------------------------------------------------

def parent_child(text):
    """Search single sentences (the children), but show the model the whole section
    each one belongs to (the parent). Search narrow, answer wide."""
    chunks = []
    for heading, section_text in split_sections(text):
        for sentence in split_sentences(section_text):
            chunks.append(make_chunk(sentence, model_text=section_text, section=heading))
    return chunks


# ---------------------------------------------------------------------------------------
# 6. SENTENCE-WINDOW
#    Good for:   looking up precise facts in dense text
#    Watch out:  poor when the answer is spread over several paragraphs
# ---------------------------------------------------------------------------------------

def sentence_window(text):
    """Search single sentences, but show the model each one together with the
    WINDOW sentences before and after it."""
    sentences = split_sentences(text)
    chunks = []
    for i, sentence in enumerate(sentences):
        first = max(0, i - config.WINDOW)
        last = i + config.WINDOW + 1
        surrounding = " ".join(sentences[first:last])
        chunks.append(make_chunk(sentence, model_text=surrounding))
    return chunks


# ---------------------------------------------------------------------------------------
# 7. PARAGRAPH
#    Good for:   documents whose paragraphs each make one point
#    Watch out:  an answer spread over two paragraphs ends up in two chunks
# ---------------------------------------------------------------------------------------

def paragraph(text):
    """One chunk per paragraph, and each chunk remembers the heading it sits under.

    Every reader in rag/read_files.py puts one paragraph on one line, so a line is a
    paragraph. That makes this the simplest method of the seven - and the finest-grained
    one that still keeps its heading, which is what tells you what the paragraph is about.
    """
    chunks = []
    for heading, section_text in split_sections(text):
        for line in section_text.split("\n"):
            if line.strip():
                chunks.append(make_chunk(line.strip(), section=heading))
    return chunks


# ---------------------------------------------------------------------------------------
# Picking a method by its name in config.py
# ---------------------------------------------------------------------------------------

METHODS = {
    "fixed_size": fixed_size,
    "recursive": recursive,
    "structure_aware": structure_aware,
    "semantic": semantic,
    "parent_child": parent_child,
    "sentence_window": sentence_window,
    "paragraph": paragraph,
}


def chunk(text, method, embed):
    """Cut `text` into chunks with the named method.

    `embed` is the function that turns text into numbers. Only the semantic method needs it.
    """
    if method == "semantic":
        return semantic(text, embed)
    return METHODS[method](text)
