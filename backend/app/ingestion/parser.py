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


def split_markdown_table_if_needed(table_md: str, max_chars: int = 1800) -> list[str]:
    """
    Splits a large markdown table across row boundaries while repeating headers on each split
    so that table chunks preserve column alignment and cell readability.
    """
    lines = [line.strip() for line in table_md.strip().split("\n") if line.strip()]
    if len(lines) < 3 or len(table_md) <= max_chars:
        return [table_md.strip()] if table_md.strip() else []

    header = lines[0]
    separator = lines[1]
    rows = lines[2:]

    chunks: list[str] = []
    current_rows: list[str] = []

    for r in rows:
        candidate = "\n".join([header, separator] + current_rows + [r])
        if len(candidate) > max_chars and current_rows:
            chunks.append("\n".join([header, separator] + current_rows))
            current_rows = [r]
        else:
            current_rows.append(r)

    if current_rows:
        chunks.append("\n".join([header, separator] + current_rows))

    return chunks


def extract_page_content(
    page: fitz.Page,
    max_chars: int = 1800,
    overlap_chars: int = 200,
) -> list[tuple[str, bool]]:
    """
    Extracts structured content from a PDF page.
    Returns a list of tuples: (chunk_text, is_table).
    Preserves tables as formatted Markdown with headers intact.
    Extracts non-table text blocks cleanly without scrambling.
    """
    results: list[tuple[str, bool]] = []

    # Attempt structured table discovery via PyMuPDF TableFinder
    table_finder = getattr(page, "find_tables", None)
    tables = []
    if callable(table_finder):
        try:
            found = table_finder()
            tables = getattr(found, "tables", []) or []
        except Exception:
            tables = []

    if not tables:
        # Standard prose page extraction
        raw_text = page.get_text("text", sort=True)
        cleaned = clean_page_text(raw_text)
        if cleaned:
            for piece in split_page_into_chunks(cleaned, max_chars=max_chars, overlap_chars=overlap_chars):
                results.append((piece, False))
        return results

    # When tables exist, separate table bboxes from prose text blocks
    tab_rects = [fitz.Rect(t.bbox) for t in tables if hasattr(t, "bbox")]

    # Extract non-tabular prose blocks
    blocks = page.get_text("blocks")
    prose_pieces: list[str] = []
    for b in blocks:
        r = fitz.Rect(b[:4])
        # Check if this block intersects any detected table bbox
        if not any(r.intersects(tr) for tr in tab_rects):
            text = b[4].strip()
            if text:
                prose_pieces.append(text)

    if prose_pieces:
        full_prose = clean_page_text("\n\n".join(prose_pieces))
        if full_prose:
            for piece in split_page_into_chunks(full_prose, max_chars=max_chars, overlap_chars=overlap_chars):
                results.append((piece, False))

    # Extract structured Markdown tables
    for tab in tables:
        try:
            md = tab.to_markdown()
            if md and md.strip():
                sub_tables = split_markdown_table_if_needed(md, max_chars=max_chars)
                for sub in sub_tables:
                    results.append((sub, True))
                continue
        except Exception:
            pass

        # Fallback to extracting table cell rows manually if to_markdown fails
        rows = getattr(tab, "extract", lambda: [])()
        if rows:
            lines = []
            for row in rows:
                clean_cells = [str(cell or "").strip().replace("\n", " ") for cell in row]
                lines.append("| " + " | ".join(clean_cells) + " |")
            if len(lines) >= 2:
                sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
                md_fallback = lines[0] + "\n" + sep + "\n" + "\n".join(lines[1:])
                for sub in split_markdown_table_if_needed(md_fallback, max_chars=max_chars):
                    results.append((sub, True))

    return results


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
    Extracts tabular schedules into clean Markdown tables with row/column headers intact.
    """
    chunks: list[PageChunk] = []
    global_idx = 0

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        total_pages = doc.page_count
        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc.load_page(page_idx)

            page_content = extract_page_content(
                page, max_chars=max_chars, overlap_chars=overlap_chars
            )
            for local_idx, (chunk_text, is_table) in enumerate(page_content, start=1):
                global_idx += 1
                chunk_doc_id = f"{base_doc_id}:p{page_num}:c{local_idx}"
                table_tag = " [Table]" if is_table else ""
                chunk_title = f"{base_title} (p.{page_num} / chunk {local_idx}{table_tag})"
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
