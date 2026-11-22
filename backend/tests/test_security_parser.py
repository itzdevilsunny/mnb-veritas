import hashlib

from app.core.security import hash_api_key, verify_api_key
from app.ingestion.parser import clean_page_text, split_page


def test_hash_and_verify_api_key():
    h = hash_api_key("secret-key")
    assert h == hashlib.sha256(b"secret-key").hexdigest()
    assert verify_api_key("secret-key", [h])
    assert verify_api_key("  secret-key  ", [h.upper()])
    assert not verify_api_key("wrong", [h])
    assert not verify_api_key(None, [h])
    assert not verify_api_key("", [h])
    assert not verify_api_key("secret-key", [])


def test_clean_page_text_joins_word_hyphenation_but_not_year_ranges():
    out = clean_page_text("grant alloca-\ntion for FY 2025-\n26")
    assert "allocation" in out
    assert "2025-" in out and "202526" not in out


def test_split_page_respects_limits_and_overlaps():
    text = " ".join(f"Sentence number {i} ends here." for i in range(200))
    chunks = split_page(text, max_chars=500, overlap_chars=80)
    assert len(chunks) > 5
    assert all(len(c) <= 500 for c in chunks)
    assert chunks[0][-20:] in chunks[1] or chunks[1][:20] in chunks[0]
    assert split_page("short", 500, 50) == ["short"]
    assert split_page("", 500, 50) == []
