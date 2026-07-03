"""Small, deterministic normalization helpers for customer and catalog input."""

from __future__ import annotations

import re
import unicodedata


def normalize_search(value: str) -> str:
    """Normalize human text while preserving token boundaries."""

    decomposed = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text).split())


def normalize_compact(value: str) -> str:
    """Normalize names for comparisons that should ignore spaces and punctuation."""

    return normalize_search(value).replace(" ", "")


def normalize_phone(value: str) -> str:
    """Keep only phone digits."""

    return re.sub(r"\D", "", value)


def normalize_email(value: str) -> str:
    """Normalize an e-mail address without changing its meaningful characters."""

    return value.strip().lower()
