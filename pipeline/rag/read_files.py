"""
One reader per file type.

Every reader turns its file into plain text, and marks headings with '#' the way
Markdown does. That way the chunkers only ever deal with one shape of text, and the
structure-aware chunker can find the headings whatever the file type was.
"""
import csv
import email
import email.utils
import re
from email import policy

from bs4 import BeautifulSoup
from docx import Document
from pypdf import PdfReader


def read_text(path):
    """Markdown and plain text files are already text. Nothing to do."""
    return path.read_text(encoding="utf-8")


def read_pdf(path):
    """PDFs only store where letters go on the page, so structure has to be rebuilt."""
    # 1. Pull the text off every page
    pages = [page.extract_text() for page in PdfReader(path).pages]
    text = "\n".join(pages)

    # 2. Headings lose their bold and size. A short numbered line like "2. Eligibility"
    #    was a heading, so mark it as one again.
    text = re.sub(r"^(\d+\.\s+[A-Z][^.\n]{0,50})$", r"## \1", text, flags=re.MULTILINE)

    # 3. The PDF broke lines wherever the page edge was, often mid-sentence.
    #    If a line does not end a sentence, the next line belongs to it - join them.
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        previous_is_unfinished = (lines
                                  and not lines[-1].startswith("#")
                                  and not lines[-1].endswith((".", "!", "?", ":")))
        if previous_is_unfinished and not line.startswith("#"):
            lines[-1] = lines[-1] + " " + line
        else:
            lines.append(line)
    return "\n".join(lines)


def read_docx(path):
    """Word keeps headings as paragraph styles, so we can read them straight off."""
    lines = []
    for paragraph in Document(path).paragraphs:
        style = paragraph.style.name.lower()
        if style == "title":
            lines.append("# " + paragraph.text)
        elif style.startswith("heading"):
            lines.append("## " + paragraph.text)
        elif paragraph.text.strip():
            lines.append(paragraph.text)
    return "\n".join(lines)


def read_html(path):
    """Web pages are full of things that are not content - menus, footers, scripts."""
    page = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")

    # 1. Throw away the parts that are the same on every page. Left in, they would
    #    turn up in search results for every question.
    for boilerplate in page(["nav", "footer", "script", "style"]):
        boilerplate.decompose()

    # 2. Keep headings, paragraphs and list items, in the order they appear
    heading_marks = {"h1": "# ", "h2": "## ", "h3": "### "}
    lines = []
    for tag in page.find_all(["h1", "h2", "h3", "p", "li"]):
        mark = heading_marks.get(tag.name, "")
        lines.append(mark + tag.get_text(" ", strip=True))
    return "\n".join(lines)


def read_csv(path):
    """Never flatten a table into prose.

    Each row becomes one line that carries its own column names, e.g.
        City: London; Hotel nightly limit (EUR): 220
    so any chunk that holds the row still makes sense on its own.
    """
    with open(path, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    lines = []
    for row in rows:
        cells = [f"{column}: {value}" for column, value in row.items()]
        lines.append("; ".join(cells))
    return "\n".join(lines)


def read_eml(path):
    """An email arrives twice over, and with its lines broken in the middle.

    Three things have to be dealt with, and the standard library does all of them:

    1. The same message is sent as plain text AND as HTML, so reading the file as text
       would store everything twice - and the search would then find both copies.
       get_body() picks one part, preferring the plain text.
    2. Long lines are broken with a trailing "=" ("quoted-printable"), which splits
       words in half: "we are giving y=\nou notice". get_content() puts them back
       together and decodes the character set at the same time.
    3. Who sent it and when are only in the headers, never in the body. They go into
       the heading, because 1_build_database.py puts the heading at the start of every
       chunk - so even the last chunk of a long email still says who sent it and when.
    """
    message = email.message_from_bytes(path.read_bytes(), policy=policy.default)

    body = message.get_body(preferencelist=("plain", "html"))
    text = body.get_content()
    if body.get_content_subtype() == "html":      # an email with no plain-text part
        text = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)

    # "Fri, 19 Feb 2027 09:30:00 +0000" is how an email writes a date; nobody asks a
    # question in those words, so write it out the way a person would.
    sent = email.utils.parsedate_to_datetime(message["Date"]).strftime("%d %B %Y")
    heading = f"{message['Subject']} - email from {message['From']}, sent {sent}"

    paragraphs = [line.strip() for line in text.split("\n") if line.strip()]
    return "## " + heading + "\n" + "\n".join(paragraphs)


# Which reader to use for which file ending
READERS = {
    ".txt": read_text,
    ".md": read_text,
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".html": read_html,
    ".csv": read_csv,
    ".eml": read_eml,
}


def load(path):
    """Read any supported file into text."""
    return READERS[path.suffix.lower()](path)
