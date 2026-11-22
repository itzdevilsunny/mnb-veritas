from __future__ import annotations

import pytest

from veritas_engine import (
    check_numeric_and_fy_consistency,
    extract_fy_tokens,
    extract_scaled_quantities,
    normalize_text,
    verify_verbatim_quote,
)


# =====================================================================
# VERBATIM QUOTE VERIFICATION ("NO PARAPHRASE PROOF")
# =====================================================================

def test_exact_verbatim_quote_matches_case_and_whitespace_normalized() -> None:
    source = (
        "Total verified grant allocation for FY 2025-26 stood at "
        "Rs 2.5 crore across 12 districts."
    )
    quote = "total verified grant allocation for fy 2025-26   stood at rs 2.5 crore"
    assert verify_verbatim_quote(quote, source) is True


def test_verbatim_quote_normalizes_unicode_quotes_and_dashes() -> None:
    source = "Scheme “Udaan–2026” cap is ₹1.25 crore for eligible MSMEs."
    quote = 'scheme "udaan-2026" cap is ₹1.25 crore'
    assert verify_verbatim_quote(quote, source) is True


def test_paraphrased_or_missing_quote_fails_verification() -> None:
    source = "The department approved ₹4.5 crore for rural road maintenance."
    paraphrase = "The department sanctioned 4.5 crore rupees for building village roads."
    assert verify_verbatim_quote(paraphrase, source) is False
    assert verify_verbatim_quote(None, source) is False
    assert verify_verbatim_quote("   ", source) is False


# =====================================================================
# LAKH / CRORE / SCALE UNIT NORMALIZATION & MISMATCH DETECTION
# =====================================================================

def test_equivalent_lakh_and_crore_values_match() -> None:
    # 2.5 crore == 250 lakh (25,000,000)
    claim = "Grant allocation is ₹2.5 crore."
    quote = "Allocation stands at 250 lakh."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert num_bad is False
    assert fy_bad is False
    assert reasons == []


def test_crore_vs_lakh_magnitude_mismatch_detected() -> None:
    # 4.5 crore (45,000,000) vs 45 lakh (4,500,000) is a 10x error
    claim = "Approved outlay is ₹4.5 crore."
    quote = "Approved outlay is ₹45 lakh."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert num_bad is True
    assert fy_bad is False
    assert any("Numeric value mismatch" in r for r in reasons)


def test_scaled_quantities_extract_indian_and_global_units() -> None:
    quants = dict(extract_scaled_quantities("Outlay of ₹1.5 cr, ₹75 lakh, 12%, and 500k units."))
    assert quants[15_000_000.0] == "base_number"
    assert quants[7_500_000.0] == "base_number"
    assert quants[12.0] == "percent"
    assert quants[500_000.0] == "base_number"


# =====================================================================
# PERCENTAGE & FINANCIAL YEAR (FY) MISMATCH DETECTION
# =====================================================================

def test_percentage_mismatch_detected() -> None:
    claim = "Interest subsidy is 8.5 percent under the scheme."
    quote = "Interest subsidy is 6.5 percent under the scheme."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert num_bad is True
    assert fy_bad is False
    assert any("Percentage mismatch" in r for r in reasons)


@pytest.mark.parametrize(
    ("claim_text", "quote_text", "expected_fy"),
    [
        ("Revenue in FY 2025-26 rose 10%.", "Revenue in FY26 rose 10%.", {"2025"}),
        ("Target for 2024-25 was met.", "Target for financial year 2024-25 was met.", {"2024"}),
    ],
)
def test_equivalent_fy_formats_match(
    claim_text: str, quote_text: str, expected_fy: set[str]
) -> None:
    assert extract_fy_tokens(claim_text) == expected_fy
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim_text, quote_text)
    assert num_bad is False
    assert fy_bad is False
    assert reasons == []


def test_financial_year_mismatch_detected() -> None:
    claim = "Budget allocation for FY 2026-27 was ₹10 crore."
    quote = "Budget allocation for FY 2025-26 was ₹10 crore."
    num_bad, fy_bad, reasons = check_numeric_and_fy_consistency(claim, quote)
    assert fy_bad is True
    assert num_bad is False
    assert any("FY mismatch" in r for r in reasons)


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  A   B\n\tC  ") == "a b c"
