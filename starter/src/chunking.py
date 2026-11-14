"""Deterministic chunking strategies with source and section metadata."""
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and overlap must be between 0 and size")
    text = page.text
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(_make_chunk(page, len(chunks), chunk_text, start, end))
        if end == len(text):
            break
        start = end - overlap
    return chunks


def by_paragraph(page: DocumentPage, max_size: int = 1200) -> list[Chunk]:
    if max_size < 1:
        raise ValueError("max_size must be positive")
    paragraphs = []
    cursor = 0
    for paragraph in page.text.split("\n\n"):
        paragraph = paragraph.strip()
        if paragraph:
            paragraphs.append((paragraph, cursor, cursor + len(paragraph)))
        cursor += len(paragraph) + 2
    groups = []
    text_parts, first, last = [], 0, 0
    for paragraph, start, end in paragraphs:
        pieces = [paragraph[i:i + max_size] for i in range(0, len(paragraph), max_size)]
        for piece in pieces:
            if text_parts and sum(map(len, text_parts)) + len(piece) + 2 > max_size:
                groups.append(("\n\n".join(text_parts), first, last))
                text_parts = []
            if not text_parts:
                first = start
            text_parts.append(piece)
            last = min(end, start + len(piece))
            start = last
    if text_parts:
        groups.append(("\n\n".join(text_parts), first, last))
    return [_make_chunk(page, i, text, start, end) for i, (text, start, end) in enumerate(groups)]


def _make_chunk(page: DocumentPage, index: int, text: str, start: int, end: int) -> Chunk:
    metadata = {**page.metadata, "char_start": start, "char_end": end}
    return Chunk(
        chunk_id=f"{page.document_id}:{page.page}:{index:05d}",
        document_id=page.document_id, source=page.source, page=page.page,
        text=text, metadata=metadata,
    )
