from __future__ import annotations

import re
from dataclasses import dataclass
import pymupdf as fitz


@dataclass(frozen=True)
class PageChunk:
    chunk_index: int
    page_number: int
    doc_id: str
    title: str
    text: str
    char_count: int


def clean_page_text(raw_text: str) -> str:
    """
    Repair PDF extraction artefacts without altering numbers or years.
    Only joins a lowercase-letter hyphenation break ("alloca-\\ntion"); never touches "2025-\\n26".
    """
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_page_into_chunks(
    page_text: str,
    max_chars: int = 1800,
    overlap_chars: int = 200,
) -> list[str]:
    """
    Splits page text into overlapping chunks without breaking mid-sentence,
    ensuring each chunk maps cleanly to its originating page number.
    """
    if len(page_text) <= max_chars:
        return [page_text] if page_text else []

    chunks: list[str] = []
    start = 0
    text_len = len(page_text)

    while start < text_len:
        end = min(start + max_chars, text_len)
        if end < text_len:
            # Look for paragraph break, then sentence boundary, then space
            split_at = page_text.rfind("\n\n", start + max_chars // 2, end)
            if split_at == -1:
                split_at = max(
                    page_text.rfind(". ", start + max_chars // 2, end),
                    page_text.rfind("? ", start + max_chars // 2, end),
                    page_text.rfind("! ", start + max_chars // 2, end),
                )
                if split_at != -1:
                    split_at += 1  # include punctuation
            if split_at == -1:
                split_at = page_text.rfind(" ", start + max_chars // 2, end)
            if split_at != -1 and split_at > start:
                end = split_at

        chunk = page_text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(end - overlap_chars, start + 1)

    return chunks


def extract_pdf_chunks(
    pdf_bytes: bytes,
    base_doc_id: str,
    base_title: str,
    max_chars: int = 1800,
    overlap_chars: int = 200,
) -> tuple[int, list[PageChunk]]:
    """
    Parses PDF bytes with PyMuPDF and returns (total_pages, list[PageChunk]).
    Each chunk gets a deterministic doc_id: '{base_doc_id}:p{page}:c{idx}'.
    """
    chunks: list[PageChunk] = []
    global_idx = 0

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        total_pages = doc.page_count
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc.load_page(page_idx)
            raw_text = page.get_text("text", sort=True)
            cleaned = clean_page_text(raw_text)
            if not cleaned:
                continue

            page_splits = split_page_into_chunks(
                cleaned, max_chars=max_chars, overlap_chars=overlap_chars
            )
            for local_idx, chunk_text in enumerate(page_splits, start=1):
                global_idx += 1
                chunk_doc_id = f"{base_doc_id}:p{page_num}:c{local_idx}"
                chunk_title = f"{base_title} (p.{page_num} / chunk {local_idx})"
                chunks.append(
                    PageChunk(
                        chunk_index=global_idx,
                        page_number=page_num,
                        doc_id=chunk_doc_id,
                        title=chunk_title,
                        text=chunk_text,
                        char_count=len(chunk_text),
                    )
                )

    return total_pages, chunks


split_page = split_page_into_chunks

