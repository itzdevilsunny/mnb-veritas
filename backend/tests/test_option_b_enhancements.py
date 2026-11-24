from __future__ import annotations

import math
from datetime import date
import pytest
import pymupdf as fitz

from app.ingestion.parser import (
    extract_pdf_chunks,
    split_markdown_table_if_needed,
)
from app.models.schemas import AuthorityTier, SourceDoc
from app.pipeline.s2_retrieve import (
    AUTHORITY_TIER_MULTIPLIERS,
    cosine_similarity,
    reciprocal_rank_fusion,
    retrieve_relevant_sources,
)
from app.services.embeddings import (
    deterministic_local_embedding,
    generate_embedding,
    generate_embeddings_batch,
)


# =====================================================================
# 1. TABULAR PDF EXTRACTION TESTS
# =====================================================================

def test_tabular_pdf_extraction_to_structured_markdown():
    """Validates that PDF tables are extracted into clean Markdown tables with preserved headers."""
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)

    # Insert top prose
    page.insert_text((50, 40), "OFFICIAL GAZETTE: MINISTRY OF FINANCE OUTLAY SCHEDULE", fontsize=12)

    # Draw tabular grid lines
    page.draw_rect(fitz.Rect(50, 70, 500, 200))
    page.draw_line(fitz.Point(50, 110), fitz.Point(500, 110))
    page.draw_line(fitz.Point(280, 70), fitz.Point(280, 200))
    page.draw_line(fitz.Point(390, 70), fitz.Point(390, 200))

    # Column Headers
    page.insert_text((60, 95), "Expenditure Head / Scheme", fontsize=10)
    page.insert_text((290, 95), "Outlay FY 2025-26", fontsize=10)
    page.insert_text((400, 95), "Unit", fontsize=10)

    # Row 1
    page.insert_text((60, 145), "Capital Outlay Infrastructure", fontsize=10)
    page.insert_text((290, 145), "11,11,111", fontsize=10)
    page.insert_text((400, 145), "Crore", fontsize=10)

    # Bottom prose
    page.insert_text((50, 240), "Quarterly milestones shall be subject to statutory audit.", fontsize=10)

    pdf_bytes = doc.tobytes()
    total_pages, chunks = extract_pdf_chunks(
        pdf_bytes=pdf_bytes,
        base_doc_id="BUDGET_TEST_01",
        base_title="Union Budget Test Annexure",
    )

    assert total_pages == 1
    assert len(chunks) >= 1

    # Check deterministic chunk ID formatting
    assert any(c.doc_id.startswith("BUDGET_TEST_01:p1:c") for c in chunks)

    # Check that at least one chunk contains structured Markdown table syntax
    table_chunks = [c for c in chunks if "|" in c.text and "---" in c.text]
    assert len(table_chunks) >= 1, "Expected at least one chunk containing formatted Markdown table"

    matched_text = " ".join(c.text for c in chunks)
    assert "Capital Outlay" in matched_text
    assert "11,11,111" in matched_text
    assert "Crore" in matched_text


def test_split_markdown_table_repeats_headers():
    """Validates that large tables split across row boundaries repeat the header row."""
    header = "| Scheme | FY25 | FY26 |"
    sep = "| --- | --- | --- |"
    rows = [f"| Scheme_{i} | {i*10} | {i*20} |" for i in range(20)]
    full_table = "\n".join([header, sep] + rows)

    # Max chars 200 will force multiple sub-table chunks
    chunks = split_markdown_table_if_needed(full_table, max_chars=180)
    assert len(chunks) > 1

    for chunk in chunks:
        lines = chunk.strip().split("\n")
        assert lines[0] == header, "Each chunk must start with the table header"
        assert lines[1] == sep, "Each chunk must have the markdown separator row"
        assert len(lines) >= 3, "Each chunk must have at least one data row"


# =====================================================================
# 2. SOURCE AUTHORITY HIERARCHY & HYBRID RRF TESTS
# =====================================================================

def test_source_authority_tier_rrf_multipliers():
    """Validates that statutory > regulatory > advisory > draft tiers break ties in RRF."""
    doc_ids = ["stat_doc", "reg_doc", "adv_doc", "draft_doc"]
    tiers = {
        "stat_doc": "statutory",
        "reg_doc": "regulatory",
        "adv_doc": "advisory",
        "draft_doc": "draft",
    }

    # All documents have identical ranks across 2 rankers
    ranker1 = list(doc_ids)
    ranker2 = list(doc_ids)

    fused = reciprocal_rank_fusion(
        ranked_lists=[ranker1, ranker2],
        k=60,
        doc_authority_tiers=tiers,
    )
    scores = dict(fused)

    # Statutory (x1.25) > Regulatory (x1.10) > Advisory (x1.00) > Draft (x0.85)
    assert scores["stat_doc"] > scores["reg_doc"]
    assert scores["reg_doc"] > scores["adv_doc"]
    assert scores["adv_doc"] > scores["draft_doc"]

    ordered_doc_ids = [doc_id for doc_id, _ in fused]
    assert ordered_doc_ids == ["stat_doc", "reg_doc", "adv_doc", "draft_doc"]


def test_retrieve_relevant_sources_authority_and_temporal_partition():
    """Tests retrieve_relevant_sources with authority tiers, temporal bounds, and active flags."""
    ref = date(2025, 6, 1)

    s_statutory = SourceDoc(
        doc_id="src_stat",
        title="Union Budget Gazette (Statutory)",
        text="The capital outlay for green hydrogen electrolysers is ₹4,850 crore.",
        valid_from=date(2025, 1, 1),
        valid_until=date(2026, 12, 31),
        is_primary=True,
        authority_tier="statutory",
    )
    s_advisory = SourceDoc(
        doc_id="src_adv",
        title="Industry Guidance Note (Advisory)",
        text="The capital outlay for green hydrogen electrolysers is ₹4,850 crore.",
        valid_from=date(2025, 1, 1),
        valid_until=date(2026, 12, 31),
        is_primary=False,
        authority_tier="advisory",
    )
    s_expired = SourceDoc(
        doc_id="src_exp",
        title="Expired Circular",
        text="The capital outlay for green hydrogen electrolysers is ₹4,850 crore.",
        valid_from=date(2023, 1, 1),
        valid_until=date(2024, 12, 31),
        is_primary=True,
        authority_tier="statutory",
    )
    s_inactive = SourceDoc(
        doc_id="src_inact",
        title="Inactive Draft",
        text="The capital outlay for green hydrogen electrolysers is ₹4,850 crore.",
        valid_from=date(2025, 1, 1),
        valid_until=date(2026, 12, 31),
        is_primary=False,
        authority_tier="draft",
        metadata={"is_active": False},
    )

    sources = [s_advisory, s_statutory, s_expired, s_inactive]
    valid_docs, expired_docs = retrieve_relevant_sources(
        sources=sources,
        query="What is the capital outlay for green hydrogen electrolysers?",
        ref_date=ref,
    )

    # Inactive must be filtered out
    assert not any(d.doc_id == "src_inact" for d in valid_docs + expired_docs)

    # Expired must be partitioned to expired_docs
    assert any(d.doc_id == "src_exp" for d in expired_docs)
    assert not any(d.doc_id == "src_exp" for d in valid_docs)

    # Statutory must rank ahead of Advisory in valid_docs
    valid_ids = [d.doc_id for d in valid_docs]
    assert "src_stat" in valid_ids
    assert "src_adv" in valid_ids
    assert valid_ids.index("src_stat") < valid_ids.index("src_adv")


# =====================================================================
# 3. ENV-DRIVEN EMBEDDING PIPELINE TESTS
# =====================================================================

def test_deterministic_local_embedding_properties():
    """Validates properties of the deterministic local embedding generator."""
    v1 = deterministic_local_embedding("National Green Hydrogen Mission", dim=1536)
    v2 = deterministic_local_embedding("National Green Hydrogen Mission", dim=1536)
    v3 = deterministic_local_embedding("Completely unrelated text about astronomy", dim=1536)

    # Determinism
    assert v1 == v2
    assert len(v1) == 1536

    # Unit L2 Normalization (norm == 1.0)
    norm = math.sqrt(sum(x * x for x in v1))
    assert pytest.approx(norm, rel=1e-3) == 1.0

    # Similarity: identical text has cosine similarity 1.0
    sim_identical = cosine_similarity(v1, v2)
    assert pytest.approx(sim_identical, rel=1e-3) == 1.0

    # Dissimilar text has lower cosine similarity
    sim_dissimilar = cosine_similarity(v1, v3)
    assert sim_dissimilar < 0.6


@pytest.mark.asyncio
async def test_generate_embedding_and_batch_fallback():
    """Validates generate_embedding and concurrent batch fallback without external API keys."""
    text1 = "Capital expenditure outlay of ₹11,11,111 crore for FY 2025-26."
    text2 = "Standing deposit facility rate is 6.25% effective January 2025."

    emb1 = await generate_embedding(text1, model="text-embedding-3-small", dim=1536)
    assert len(emb1) == 1536
    norm = math.sqrt(sum(x * x for x in emb1))
    assert pytest.approx(norm, rel=1e-3) == 1.0

    # Batch concurrent embedding generation
    batch = await generate_embeddings_batch([text1, text2], dim=1536)
    assert len(batch) == 2
    assert len(batch[0]) == 1536
    assert len(batch[1]) == 1536
    assert batch[0] == emb1
