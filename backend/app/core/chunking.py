"""
A small, explicit text splitter - intentionally simple so the chunking logic
that drives retrieval quality is visible and easy to reason about, rather
than hidden inside a framework.

Strategy: try to split on paragraph breaks, then sentence breaks, then
hard character limits, recombining pieces into chunks of roughly
`chunk_size` characters with `chunk_overlap` characters of overlap between
consecutive chunks.
"""

import re

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_into_sentences(text: str) -> list[str]:
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    sentences: list[str] = []
    for paragraph in paragraphs:
        sentences.extend(s.strip() for s in _SENTENCE_SPLIT.split(paragraph) if s.strip())
    return sentences


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 120) -> list[str]:
    """
    Split `text` into overlapping chunks of approximately `chunk_size` characters.

    Sentences are kept whole where possible. If a single sentence exceeds
    chunk_size, it is hard-split.
    """
    sentences = _split_into_sentences(text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > chunk_size:
            # Sentence itself is too long - hard split it.
            for i in range(0, len(sentence), chunk_size):
                piece = sentence[i : i + chunk_size]
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current)
            # Start the next chunk with the overlap tail of the previous one.
            overlap_tail = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{overlap_tail} {sentence}".strip()

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]
