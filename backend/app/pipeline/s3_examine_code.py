from __future__ import annotations

import re

# Indian and standard scale unit multipliers
UNIT_MULTIPLIERS: dict[str, float] = {
    "lakh": 1e5,
    "lakhs": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "crore": 1e7,
    "crores": 1e7,
    "cr": 1e7,
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "million": 1e6,
    "b": 1e9,
    "billion": 1e9,
}

NUMBER_UNIT_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr|\$)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(%|per\s*cent|percent|pct\.?|crores?|cr\.?|lakhs?|lacs?|lakh|million|billion|thousand|k|m|b)?",
    re.IGNORECASE,
)

# Pattern matching FY representations:
# 1) FY 2025-26, FY 2025/2026, financial year 2025-26
# 2) FY26, FY 26, FY 2026
# 3) Standalone 2025-26, 2024-25
FY_PATTERN = re.compile(
    r"\b(?:fy|f\.y\.|financial\s*year)\s*[-:]?\s*(20\d{2})[-/](\d{2,4})\b"
    r"|\b(?:fy|f\.y\.|financial\s*year)\s*[-:]?\s*(?:20)?(\d{2})\b"
    r"|\b(20\d{2})[-/](20\d{2}|\d{2})\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Collapses whitespace, normalizes Unicode quotes and hyphens for exact matching."""
    cleaned = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def verify_verbatim_quote(quote: str | None, source_text: str) -> bool:
    """
    Invariant 1: No Paraphrase Proof.
    Quote must be an exact substring of the cited source text after normalization.
    Tolerates optional terminal punctuation differences (. , ; :).
    """
    if not quote or not quote.strip():
        return False
    norm_quote = normalize_text(quote)
    norm_source = normalize_text(source_text)
    if norm_quote in norm_source:
        return True
    clean_quote = norm_quote.rstrip(".,;:")
    if clean_quote and clean_quote in norm_source:
        return True
    return False


def extract_fy_tokens(text: str) -> set[str]:
    """
    Normalizes financial years like 'FY 2025-26', 'FY26', or '2025-26' into canonical base start years.
    For example:
      - 'FY 2025-26' -> start year '2025'
      - '2024-25'    -> start year '2024'
      - 'FY26'       -> ending in 2026, start year '2025'
    """
    canonical_start_years: set[str] = set()

    for m in FY_PATTERN.finditer(text):
        g1, g2 = m.group(1), m.group(2)  # (20\d{2})[-/](\d{2,4})
        g3 = m.group(3)                  # single year: (\d{2})
        g4, g5 = m.group(4), m.group(5)  # standalone (20\d{2})[-/](\d{2,4})

        if g1:
            canonical_start_years.add(g1)
        elif g4:
            canonical_start_years.add(g4)
        elif g3:
            # Single FY like FY26: end year is 2026, start year is 2025
            end_yr = int(g3)
            start_yr = 2000 + end_yr - 1
            canonical_start_years.add(str(start_yr))

    return canonical_start_years


def mask_fy_tokens(text: str) -> str:
    """Replaces FY tokens with placeholders so year numbers don't pollute financial quantities."""
    return FY_PATTERN.sub(" [FY_MASKED] ", text)


def extract_scaled_quantities(text: str) -> list[tuple[float, str]]:
    """Extracts numeric values normalized to base units (e.g. ₹2.5 crore -> 25,000,000, 6.50 per cent -> 6.5%)."""
    results: list[tuple[float, str]] = []
    for match in NUMBER_UNIT_PATTERN.finditer(text):
        raw_num, raw_unit = match.group(1), (match.group(2) or "").lower().strip()
        try:
            val = float(raw_num.replace(",", ""))
        except ValueError:
            continue

        clean_unit = re.sub(r"\s+", "", raw_unit).rstrip(".")
        if clean_unit in {"%", "percent", "pct"}:
            results.append((val, "percent"))
        elif clean_unit in UNIT_MULTIPLIERS:
            results.append((val * UNIT_MULTIPLIERS[clean_unit], "base_number"))
        else:
            results.append((val, "raw_number"))
    return results


def check_numeric_and_fy_consistency(
    claim_text: str, quote_text: str
) -> tuple[bool, bool, list[str]]:
    """
    Invariant 2: Code Outvotes Models on Numbers & Dates.
    Deterministic Python validation for quantities, percentages, and financial years.
    Returns: (numeric_mismatch, fy_mismatch, reasons)
    """
    reasons: list[str] = []
    numeric_mismatch = False
    fy_mismatch = False

    # Financial Year consistency
    claim_fy = extract_fy_tokens(claim_text)
    quote_fy = extract_fy_tokens(quote_text)
    if claim_fy and quote_fy and claim_fy != quote_fy:
        fy_mismatch = True
        reasons.append(
            f"FY mismatch: claim references {sorted(claim_fy)}, source quote has {sorted(quote_fy)}"
        )

    # Mask FY before extracting financial numbers so year digits don't create false numeric mismatches
    claim_clean = mask_fy_tokens(claim_text)
    quote_clean = mask_fy_tokens(quote_text)

    claim_quants = extract_scaled_quantities(claim_clean)
    quote_quants = extract_scaled_quantities(quote_clean)

    # Compare percentages
    claim_pcts = [v for v, u in claim_quants if u == "percent"]
    quote_pcts = {v for v, u in quote_quants if u == "percent"}
    for pct in claim_pcts:
        if pct not in quote_pcts:
            numeric_mismatch = True
            reasons.append(f"Percentage mismatch: {pct}% not found in source quote")

    # Compare scaled financial numbers (e.g. ₹2.5 crore vs 250 lakh)
    claim_vals = [v for v, u in claim_quants if u in {"base_number", "raw_number"}]
    quote_vals = [v for v, u in quote_quants if u in {"base_number", "raw_number"}]

    for c_val in claim_vals:
        # Check if equivalent within 0.001% relative tolerance
        if quote_vals and not any(
            abs(c_val - q_val) <= 1e-5 * max(1.0, abs(q_val)) for q_val in quote_vals
        ):
            numeric_mismatch = True
            reasons.append(
                f"Numeric value mismatch: {c_val:g} does not match source quantities {[round(x, 2) for x in quote_vals]}"
            )

    return numeric_mismatch, fy_mismatch, reasons
