"""Deterministic similarity scoring (entity resolution).

Pure string/metric functions with no state: the same inputs always produce
the same score, on any machine. Used by the duplicate detectors for blocking
and pair scoring.
"""

from __future__ import annotations

import re
import unicodedata

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_text(value: str) -> str:
    """Lowercase, strip accents, collapse whitespace and punctuation."""
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return _WS.sub(" ", _NON_ALNUM.sub(" ", value.lower())).strip()


def normalize_phone(value: str) -> str:
    """Digits only — the block key for phone matching."""
    return re.sub(r"\D", "", str(value))


def normalize_email(value: str) -> str:
    """Lowercased, stripped — the block key for email matching."""
    return str(value).strip().lower()


def jaro(a: str, b: str) -> float:
    """Jaro similarity (0-1) between two strings."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    a, b = a.lower(), b.lower()
    match_distance = max(len(a), len(b)) // 2 - 1
    match_distance = max(match_distance, 0)
    a_matches = [False] * len(a)
    b_matches = [False] * len(b)
    matches = 0
    for i, ca in enumerate(a):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len(b))
        for j in range(start, end):
            if b_matches[j] or ca != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    transpositions = 0
    j = 0
    for i in range(len(a)):
        if not a_matches[i]:
            continue
        while not b_matches[j]:
            j += 1
        if a[i] != b[j]:
            transpositions += 1
        j += 1
    transpositions //= 2
    m = float(matches)
    return (m / len(a) + m / len(b) + (m - transpositions) / m) / 3.0


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1) -> float:
    """Jaro-Winkler similarity — boosts common prefixes (typo variants)."""
    score = jaro(a, b)
    prefix = 0
    for ca, cb in zip(a.lower(), b.lower()):
        if ca != cb:
            break
        prefix += 1
        if prefix == 4:
            break
    return score + prefix * prefix_weight * (1.0 - score)


def token_jaccard(a: str, b: str) -> float:
    """Jaccard over normalized tokens — robust to word-order changes."""
    ta = set(normalize_text(a).split())
    tb = set(normalize_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def name_similarity(a: str, b: str) -> float:
    """Best of Jaro-Winkler and token Jaccard for name-like fields."""
    return max(jaro_winkler(a, b), token_jaccard(a, b))


def record_similarity(a: dict, b: dict) -> float:
    """Weighted similarity across comparable record fields (0-1).

    Weights favour identity-bearing fields; the exact-match fields
    (date of birth) contribute their full weight only on agreement.
    """
    scores: list[float] = []
    weights: list[float] = []
    for field, weight in (
        ("name", 0.4),
        ("guardian_name", 0.2),
        ("dob", 0.2),
        ("address", 0.2),
    ):
        va, vb = a.get(field), b.get(field)
        if not va or not vb:
            continue
        if field == "dob":
            score = 1.0 if normalize_text(str(va)) == normalize_text(str(vb)) else 0.0
        else:
            score = name_similarity(str(va), str(vb))
        scores.append(score)
        weights.append(weight)
    if not scores:
        return 0.0
    return sum(s * w for s, w in zip(scores, weights)) / sum(weights)
