"""Re-exporty wspólnych helperów dla wygodnych importów.

Użycie:
    from backend.utils import extract_year, is_real_ownership, parse_polish_date
"""

from .shared import (
    extract_year,
    parse_polish_date,
    is_real_ownership,
    fix_windows_console_encoding,
)

__all__ = [
    "extract_year",
    "parse_polish_date",
    "is_real_ownership",
    "fix_windows_console_encoding",
]
