from __future__ import annotations

import math
import re
from datetime import date
from typing import Any
from app.models.schemas import SourceDoc


def extract_trigrams(text: str) -> set[str]:
    """Extracts character 3-grams for pg_trgm style fuzzy substring similarity."""
    clean = re.sub(r"\s+", " ", text.lower().strip())
    if len(clean) < 3:
        return {clean} if clean else set()
    return {clean[i : i + 3] for i in range(len(clean) - 2)}


def trigram_similarity(s1: str, s2: str) -> float:
    """
    Computes Jaccard trigram similarity matching PostgreSQL pg_trgm behavior.
    Range: 0.0 to 1.0.
    """
    t1 = extract_trigrams(s1)
    t2 = extract_trigrams(s2)
    if not t1 or not t2:
        return 0.0
    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / union if union > 0 else 0.0


def cosine_similarity(v1: list[float] | None, v2: list[float] | None) -> float:
    """Computes cosine similarity between two dense embedding vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


AUTHORITY_TIER_MULTIPLIERS: dict[str, float] = {
    "statutory": 1.25,
    "regulatory": 1.10,
    "advisory": 1.00,
    "draft": 0.85,
}


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    k: int = 60,
    primary_doc_ids: set[str] | None = None,
    primary_boost: float = 0.02,
    doc_authority_tiers: dict[str, str] | None = None,
) -> list[tuple[str, float]]:
    """
    Reciprocal Rank Fusion (RRF) with constant k (default 60).
    Fuses multiple ranked candidate lists into a single consolidated score,
    applying deterministic authority tier hierarchy multipliers (statutory > regulatory > advisory > draft)
    and primary-source precedence boosts.
    """
    scores: dict[str, float] = {}
    for r_list in ranked_lists:
        for rank, doc_id in enumerate(r_list, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank))

    # Deterministic authority hierarchy tier multiplier
    if doc_authority_tiers:
        for doc_id, base_score in list(scores.items()):
            tier = str(doc_authority_tiers.get(doc_id, "regulatory")).lower()
            multiplier = AUTHORITY_TIER_MULTIPLIERS.get(tier, 1.0)
            scores[doc_id] = base_score * multiplier

    if primary_doc_ids:
        for doc_id in scores:
            if doc_id in primary_doc_ids:
                scores[doc_id] += primary_boost

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def retrieve_relevant_sources(
    sources: list[SourceDoc],
    query: str,
    ref_date: date,
    source_ids: list[str] | None = None,
    max_count: int = 5,
    query_embedding: list[float] | None = None,
    rrf_k: int = 60,
) -> tuple[list[SourceDoc], list[SourceDoc]]:
    """
    Stage 2: Hybrid Retrieval (pgvector semantic similarity + pg_trgm lexical matching)
    fused with Reciprocal Rank Fusion (k=60), temporal validity partitioning,
    authority tier hierarchy (statutory > regulatory > advisory > draft),
    and primary-source authority precedence.

    Returns:
        tuple[list[SourceDoc], list[SourceDoc]]: (valid_active_docs, expired_docs)
    """
    filtered_pool = [
        s for s in sources
        if getattr(s, "is_active", True) is not False and (getattr(s, "metadata", {}) or {}).get("is_active", True) is not False
    ]
    if source_ids:
        filtered_pool = [s for s in filtered_pool if s.doc_id in source_ids]

    if not filtered_pool:
        return [], []

    docs_by_id = {s.doc_id: s for s in filtered_pool}
    primary_doc_ids = {s.doc_id for s in filtered_pool if s.is_primary}
    doc_authority_tiers = {
        s.doc_id: str(getattr(s, "authority_tier", "regulatory") or "regulatory")
        for s in filtered_pool
    }

    # 1. Lexical Scoring: character trigrams + token keyword overlap
    keywords = {w.lower() for w in re.findall(r"[a-zA-Z0-9]{3,}", query)}
    lexical_scored: list[tuple[float, str]] = []

    for doc in filtered_pool:
        haystack = f"{doc.title} {doc.text}".lower()
        tri_sim = trigram_similarity(query, haystack)
        kw_overlap = sum(1 for kw in keywords if kw in haystack)
        kw_norm = kw_overlap / max(1, len(keywords))
        combined_lex = tri_sim * 0.6 + kw_norm * 0.4
        lexical_scored.append((combined_lex, doc.doc_id))

    lexical_scored.sort(key=lambda x: x[0], reverse=True)
    lexical_rank_list = [doc_id for _, doc_id in lexical_scored]

    # 2. Vector Semantic Scoring (if query embedding is available and docs have embeddings)
    ranked_lists: list[list[str]] = [lexical_rank_list]

    if query_embedding:
        vec_scored: list[tuple[float, str]] = []
        for doc in filtered_pool:
            if doc.embedding:
                sim = cosine_similarity(query_embedding, doc.embedding)
                vec_scored.append((sim, doc.doc_id))
            else:
                # Neutral rank if embedding not yet generated
                vec_scored.append((0.0, doc.doc_id))

        vec_scored.sort(key=lambda x: x[0], reverse=True)
        vec_rank_list = [doc_id for _, doc_id in vec_scored]
        ranked_lists.append(vec_rank_list)

    # 3. Reciprocal Rank Fusion (k=60) with authority hierarchy and primary source boost
    fused = reciprocal_rank_fusion(
        ranked_lists=ranked_lists,
        k=rrf_k,
        primary_doc_ids=primary_doc_ids,
        primary_boost=0.02,
        doc_authority_tiers=doc_authority_tiers,
    )

    top_ids = [doc_id for doc_id, _ in fused[:max_count]]
    top_candidates = [docs_by_id[doc_id] for doc_id in top_ids if doc_id in docs_by_id]

    # Fallback to pool if candidates empty
    if not top_candidates and filtered_pool:
        top_candidates = filtered_pool[:max_count]

    # 4. Temporal Validity Partition against reference date
    valid_docs = [d for d in top_candidates if d.is_valid_on(ref_date)]
    expired_docs = [d for d in top_candidates if not d.is_valid_on(ref_date)]

    return valid_docs, expired_docs
