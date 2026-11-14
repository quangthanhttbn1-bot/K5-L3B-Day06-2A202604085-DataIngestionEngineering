"""Load supported source files and normalize text without losing traceability."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import unicodedata
import hashlib

from pypdf import PdfReader

from .models import DocumentPage


_BLOCK_TAGS = {
    "address", "article", "blockquote", "br", "dd", "div", "dl", "dt",
    "figcaption", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ol",
    "p", "pre", "section", "table", "td", "th", "tr", "ul",
}
_IGNORED_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}


class _HTMLTextExtractor(HTMLParser):
    """Extract readable text while retaining headings and paragraph breaks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORED_TAGS:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORED_TAGS and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract physical PDF pages and warn explicitly for pages with no text.

    Scanned pages are not OCRed; their empty status is retained in metadata so
    the caller can decide whether to OCR or exclude them from the corpus.
    """
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = normalize_text(page.extract_text() or "")
        except Exception as exc:
            raise RuntimeError(f"Failed to extract {path}, physical page {page_number}: {exc}") from exc
        status = "ok" if text else "empty_no_extractable_text"
        pages.append(DocumentPage(
            document_id=document_id,
            source=source,
            page=page_number,
            text=text,
            metadata={"document_type": "pdf", "extraction_status": status},
        ))
    return pages


def load_html(
    path: Path,
    document_id: str,
    source: str,
    metadata: dict | None = None,
) -> list[DocumentPage]:
    """Load a local HTML file as one traceable source unit.

    For the lab's 1,500-character unit rule, a long HTML source can be split
    into ordered units later while keeping `source` and the unit number.
    """
    try:
        html = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        html = path.read_text(encoding="utf-8-sig", errors="replace")
    parser = _HTMLTextExtractor()
    parser.feed(html)
    parser.close()
    text = normalize_text("".join(parser.parts))
    if not text:
        raise ValueError(f"No extractable text in HTML source: {path}")
    # Exclude Project Gutenberg's legal boilerplate, contents and trailing license.
    start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
    end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker)) if start >= 0 else -1
    if start >= 0:
        body_start = text.find("\n", start)
        text = text[body_start + 1:end if end >= 0 else len(text)].strip()
    page_metadata = {"document_type": "html", "unit_id": f"{document_id}:unit-001",
                     "char_count": len(text), "language": "en"}
    if metadata:
        page_metadata.update(metadata)
    return [DocumentPage(
        document_id=document_id,
        source=source,
        page=1,
        text=text,
        metadata=page_metadata,
    )]


def split_html_units(page: DocumentPage, min_chars: int = 1500,
                    max_chars: int = 5000) -> list[DocumentPage]:
    """Split an unpaginated book into ordered, non-overlapping traceable units."""
    if min_chars < 1 or max_chars < min_chars:
        raise ValueError("Require 1 <= min_chars <= max_chars")
    units = []
    section = "Front matter"
    pending = []
    pending_len = 0
    current_section = section
    for paragraph in (p.strip() for p in page.text.split("\n\n")):
        if not paragraph:
            continue
        match = re.match(r"^(CHAPTER\s+[IVXLCDM]+|INTRODUCTION|CONCLUSION|APPENDIX.*)$", paragraph, re.I)
        if match and pending_len >= min_chars:
            units.append((current_section, "\n\n".join(pending)))
            pending, pending_len = [], 0
        if match:
            section = match.group(1).title()
            current_section = section
        if pending and pending_len + len(paragraph) + 2 > max_chars and pending_len >= min_chars:
            units.append((current_section, "\n\n".join(pending)))
            pending, pending_len = [], 0
        pending.append(paragraph)
        pending_len += len(paragraph) + 2
    if pending:
        tail = "\n\n".join(pending)
        if units and len(tail) < min_chars:
            prev_section, prev_text = units[-1]
            units[-1] = (prev_section, prev_text + "\n\n" + tail)
        else:
            units.append((current_section, tail))
    result = []
    source_offset = 0
    for index, (unit_section, text) in enumerate(units, start=1):
        text = normalize_text(text)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        result.append(DocumentPage(
            document_id=page.document_id, source=page.source, page=index, text=text,
            metadata={**page.metadata, "section": unit_section,
                      "unit_id": f"{page.document_id}:unit-{index:03d}",
                      "char_count": len(text), "char_start": source_offset,
                      "char_end": source_offset + len(text),
                      "content_sha256": digest},
        ))
        source_offset += len(text) + 2
    return result


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while preserving paragraph boundaries."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
