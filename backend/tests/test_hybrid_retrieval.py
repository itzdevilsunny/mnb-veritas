from __future__ import annotations

from datetime import date
import pytest
from app.models.schemas import SourceDoc
from app.pipeline.s2_retrieve import (
    cosine_similarity,
    extract_trigrams,
    reciprocal_rank_fusion,
    retrieve_relevant_sources,
    trigram_similarity,
)


def test_trigram_extraction_and_similarity():
    # Identical strings have similarity 1.0
    s1 = "National Green Hydrogen Mission"
    assert trigram_similarity(s1, s1) == 1.0

    # Overlapping strings have positive similarity
    s2 = "Green Hydrogen Outlay"
    sim = trigram_similarity(s1, s2)
    assert 0.1 < sim < 1.0

    # Completely disjoint strings have similarity 0.0
    s3 = "XYZ 123456"
    assert trigram_similarity(s1, s3) == 0.0


def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    v4 = [-1.0, 0.0, 0.0]

    assert pytest.approx(cosine_similarity(v1, v2)) == 1.0
    assert pytest.approx(cosine_similarity(v1, v3)) == 0.0
    assert pytest.approx(cosine_similarity(v1, v4)) == -1.0
    assert cosine_similarity(None, v1) == 0.0
    assert cosine_similarity(v1, []) == 0.0


def test_reciprocal_rank_fusion_k60_and_primary_boost():
    # 3 docs in 2 rankings:
    # Lexical rank: d1, d2, d3
    # Vector rank:  d2, d1, d3
    lex_ranks = ["d1", "d2", "d3"]
    vec_ranks = ["d2", "d1", "d3"]

    # Without primary boost, d1 and d2 have equal RRF scores: 1/(60+1) + 1/(60+2)
    fused_neutral = reciprocal_rank_fusion([lex_ranks, vec_ranks], k=60)
    scores = dict(fused_neutral)
    assert pytest.approx(scores["d1"]) == pytest.approx(scores["d2"])
    assert scores["d1"] > scores["d3"]

    # With primary boost on d1, d1 must strictly rank first
    fused_boosted = reciprocal_rank_fusion(
        [lex_ranks, vec_ranks],
        k=60,
        primary_doc_ids={"d1"},
        primary_boost=0.02,
    )
    assert fused_boosted[0][0] == "d1"
    assert fused_boosted[0][1] > fused_boosted[1][1]


def test_hybrid_retrieve_graceful_degradation_without_embeddings():
    docs = [
        SourceDoc(
            doc_id="doc_a",
            title="Solar Cell Subsidies FY26",
            text="Government approves capital subsidies for solar photovoltaics in FY 2025-26.",
            valid_from=date(2025, 4, 1),
            valid_until=date(2026, 3, 31),
            is_primary=True,
            embedding=None,  # No embedding generated yet
        ),
        SourceDoc(
            doc_id="doc_b",
            title="Coal Cess Guidelines",
            text="Guidelines for clean environment cess on coal shipments.",
            valid_from=date(2025, 1, 1),
            valid_until=date(2026, 12, 31),
            is_primary=False,
            embedding=None,
        ),
    ]

    valid, expired = retrieve_relevant_sources(
        sources=docs,
        query="What are the solar photovoltaics subsidies for FY 2025-26?",
        ref_date=date(2025, 6, 1),
        query_embedding=None,
    )

    assert len(valid) == 2
    assert valid[0].doc_id == "doc_a"  # Highly relevant + primary
    assert len(expired) == 0


def test_hybrid_retrieve_with_dense_vector_embeddings():
    # Dense mock embedding: [solar_dim, coal_dim]
    query_emb = [0.95, 0.05]
    doc_solar_emb = [0.92, 0.08]
    doc_coal_emb = [0.05, 0.95]

    docs = [
        SourceDoc(
            doc_id="doc_coal",
            title="Thermal Energy Policy",
            text="Coal combustion standards for thermal stations.",
            valid_from=date(2025, 1, 1),
            valid_until=date(2026, 12, 31),
            is_primary=False,
            embedding=doc_coal_emb,
        ),
        SourceDoc(
            doc_id="doc_solar",
            title="Renewable Transition Strategy",
            text="Solar cell manufacturing and rooftop incentives.",
            valid_from=date(2025, 1, 1),
            valid_until=date(2026, 12, 31),
            is_primary=True,
            embedding=doc_solar_emb,
        ),
    ]

    valid, expired = retrieve_relevant_sources(
        sources=docs,
        query="What are the solar power cell incentives?",
        ref_date=date(2025, 5, 1),
        query_embedding=query_emb,
    )

    assert len(valid) == 2
    assert valid[0].doc_id == "doc_solar"


def test_hybrid_retrieve_temporal_validity_partitioning():
    docs = [
        SourceDoc(
            doc_id="doc_active",
            title="Current FY26 Budget",
            text="Budget allocations for FY 2025-26 pilot electrolysers.",
            valid_from=date(2025, 4, 1),
            valid_until=date(2026, 3, 31),
            is_primary=True,
        ),
        SourceDoc(
            doc_id="doc_expired",
            title="Old FY24 Budget",
            text="Budget allocations for FY 2023-24 pilot electrolysers.",
            valid_from=date(2023, 4, 1),
            valid_until=date(2024, 3, 31),
            is_primary=True,
        ),
    ]

    # Evaluation date: 2025-08-01 -> doc_active is valid, doc_expired is expired
    valid, expired = retrieve_relevant_sources(
        sources=docs,
        query="pilot electrolysers budget allocations",
        ref_date=date(2025, 8, 1),
    )

    assert any(d.doc_id == "doc_active" for d in valid)
    assert any(d.doc_id == "doc_expired" for d in expired)
