"""Czysta logika Test Center - parsowanie outputu pytest, formatowanie, mapa ścieżek.

Moduł jest wolny od Tkintera / messagebox / webbrowser. Implementacja GUI
znajduje się w ``launcher.ui.test_center_runtime``, a ten moduł jest
konsumowany przez nią.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional, Tuple

from launcher.config.paths import BACKEND_DIR, BASE_DIR


# ─── Mapa klucz testu → ścieżka relatywna ────────────────────────────────────
TEST_PATH_MAP: dict[str, str] = {
    "unit": "backend/tests/unit",
    "integration": "backend/tests/integration",
    "e2e": "backend/tests/e2e",
    "logic": "backend/tests/logic",
    "duplicates": "backend/tests/logic/test_duplicates.py",
    "spatial": "backend/tests/unit/test_spatial.py",
    "resources": "backend/tests/health/test_resources.py",
    "gaps": "backend/tests/logic/test_data_gaps.py",
    "backups": "backend/tests/health/test_backups.py",
    "encoding": "backend/tests/health/test_encoding.py",
    "wcag": "backend/tests/health/test_accessibility.py",
    "perf": "backend/tests/performance",
    "security": "backend/tests/security",
}


# ─── Domyślne wartości BooleanVar dla app.test_vars ──────────────────────────
DEFAULT_TEST_VARS: dict[str, bool] = {
    "unit": True,
    "integration": True,
    "e2e": False,
    "logic": True,
    "sql": True,
    "duplicates": True,
    "spatial": False,
    "resources": False,
    "gaps": False,
    "backups": True,
    "encoding": True,
    "wcag": False,
    "perf": False,
    "security": False,
}


def parse_pytest_line(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parsuje linie wyjscia pytest i zwraca (emoji, tag, sformatowana_linia).

    Obsługiwane wzorce (format verbose -v):
      - "tests/...::test_name PASSED                                 [  2%]" -> ✅
      - "tests/...::test_name FAILED                                 [  5%]" -> ❌
      - "tests/...::test_name SKIPPED                                [ 10%]" -> ⏭
      - "tests/...::test_name ERROR                                  [ 15%]" -> 🔴
      - "...........                                                 [100%]" -> pomijamy
      - "36 passed in 2.47s"                                         -> 📊 podsumowanie
      - "FAILED tests/...::test_name"                               -> ❌ (summary section)
    """
    stripped = line.strip()

    # Pomijamy puste linie
    if not stripped:
        return None, None, line

    # Pomijamy szum naglowka pytest (już częściowo stłumiony przez --no-header)
    if "test session starts" in stripped:
        return None, None, None
    if re.match(r'^platform\s+\w+\s+--\s+Python', stripped):
        return None, None, None
    if stripped.startswith("rootdir:"):
        return None, None, None
    if stripped.startswith("configfile:"):
        return None, None, None
    if stripped.startswith("plugins:"):
        return None, None, None
    if re.match(r'^collecting\s+\.\.\.\s+collected\s+\d+\s+items?', stripped):
        return None, None, None

    # Pomijamy linie postepu (samo "........... [XX%]")
    if re.match(r'^[\.\s\*]+.*\[\s*\d+%\]\s*$', stripped):
        return None, None, None

    # Wynik testu w formacie verbose
    verbose_match = re.match(
        r'^(\S+\.py::\S+)\s+(PASSED|FAILED|SKIPPED|ERROR)\s*(?:\[\s*\d+%\])?\s*$',
        stripped,
    )
    if verbose_match:
        test_name = verbose_match.group(1)
        result = verbose_match.group(2)
        pct = extract_percentage(stripped)

        parts = test_name.split("::")
        if len(parts) >= 2:
            short_name = f"{parts[0]}::{parts[-1]}"
        else:
            short_name = test_name

        pct_str = f"  {pct}" if pct else ""

        if result == "PASSED":
            return "✅", "test_passed_line", f"  ✅  {short_name}{pct_str}\n"
        elif result == "FAILED":
            return "❌", "test_failed_line", f"  ❌  {short_name}{pct_str}\n"
        elif result == "SKIPPED":
            return "⏭️", "test_skipped_line", f"  ⏭️  {short_name} (pominięty)\n"
        elif result == "ERROR":
            return "🔴", "test_failed_line", f"  🔴  {short_name} (BŁĄD)\n"

    # Podsumowanie: "X passed in Ys" lub "X passed, Y failed"
    if re.search(r'\d+\s+passed', stripped):
        return "📊", "bold_summary", format_summary_line(stripped)

    # Linia FAILED w sekcji podsumowania
    if stripped.startswith("FAILED "):
        parts = stripped.split(None, 1)
        test_name = parts[1] if len(parts) > 1 else stripped
        test_name = test_name.split(" - ")[0]
        # Summary pytest powtarza testy, które już policzyliśmy w liniach verbose.
        # Pokazujemy je w konsoli, ale NIE zwracamy emoji zliczającego, żeby
        # globalne statystyki nie dublowały failure count.
        return None, "test_failed_line", f"  ❌  {test_name}\n"

    # Linia ERROR w sekcji podsumowania
    if stripped.startswith("ERROR "):
        parts = stripped.split(None, 1)
        test_name = parts[1] if len(parts) > 1 else stripped
        # Jak wyzej: summary-only display, bez podwojnego liczenia.
        return None, "test_failed_line", f"  🔴  {test_name}\n"

    # Separator z wynikami
    if (stripped.startswith("===") or stripped.startswith("---")) and any(
        kw in stripped for kw in ["passed", "failed", "error", "skipped"]
    ):
        return "📊", "bold_summary", f"  📊  {stripped.strip('= ')}\n"

    # "short test summary info" naglowek
    if "short test summary" in stripped.lower():
        return None, "bold_header", f"\n  📋 PODSUMOWANIE BŁĘDÓW:\n"

    # "warnings summary" — pomijamy
    if "warnings summary" in stripped.lower():
        return None, "bold_header", f"\n  ⚠️  OSTRZEŻENIA:\n"

    # Linia z "::" w innym formacie (fallback)
    if "::" in stripped and any(kw in stripped for kw in ["PASS", "FAIL", "SKIP", "ERR"]):
        if "PASS" in stripped:
            return "✅", "test_passed_line", f"  ✅  {stripped}\n"
        elif "FAIL" in stripped:
            return "❌", "test_failed_line", f"  ❌  {stripped}\n"

    # Zwykla linia (np. z wlasnego skryptu SQL) — bez zmian
    return None, None, line


def extract_test_name(line: str) -> str:
    """Wyciaga nazwe testu z linii pytest."""
    match = re.search(r'(\S+\.py::\S+)', line)
    if match:
        name = match.group(1)
        parts = name.split("::")
        if len(parts) >= 2:
            return f"{parts[0]}::{parts[-1]}"
        return name
    match = re.search(r'(\S+::\S+)\s', line)
    if match:
        return match.group(1)
    return line


def extract_percentage(line: str) -> Optional[str]:
    """Wyciaga procent postepu z linii pytest."""
    match = re.search(r'\[\s*(\d+)\s*%\]', line)
    if match:
        return f"[{match.group(1)}%]"
    return None


def format_summary_line(line: str) -> str:
    """Formatuje linie podsumowania pytest z emoji."""
    parts = []
    for count, label in re.findall(r'(\d+)\s+(passed|failed|error|skipped|warning)', line):
        count = int(count)
        if label == "passed":
            parts.append(f"✅ {count} passed")
        elif label == "failed":
            parts.append(f"❌ {count} failed")
        elif label == "error":
            parts.append(f"🔴 {count} error")
        elif label == "skipped":
            parts.append(f"⏭️ {count} skipped")
        elif label == "warning":
            parts.append(f"⚠️ {count} warning")
    time_match = re.search(r'in\s+([\d.]+)s', line)
    if time_match:
        parts.append(f"⏱️ {time_match.group(1)}s")

    if parts:
        return f"  📊  {' | '.join(parts)}\n"
    return f"  📊  {line}\n"


def build_test_command(test_key: str, base_dir: str) -> list[str]:
    """Buduje komendę do uruchomienia wybranego zestawu testów.

    Dla ``test_key == "sql"`` uruchamia skrypt ``test_data_integrity.py``.
    Dla pozostałych kluczy używa ``TEST_PATH_MAP`` i ``pytest -v``.

    Zwraca pustą listę, jeśli katalog testu nie istnieje (pomijane przez
    orkiestratora UI).
    """
    if test_key == "sql":
        script_path = os.path.join(BACKEND_DIR, "tests", "unit", "test_data_integrity.py")
        return [sys.executable, script_path]

    if test_key not in TEST_PATH_MAP:
        return []

    test_rel_path = TEST_PATH_MAP[test_key]
    test_path = os.path.join(base_dir, test_rel_path)
    if not os.path.exists(test_path):
        return []

    return [
        sys.executable,
        "-m",
        "pytest",
        test_rel_path,
        "-v",
        "--tb=no",
        "--no-header",
        "-p",
        "no:cacheprovider",
    ]


def accumulate_section_stats(stats: dict, emoji: Optional[str]) -> None:
    """Inkrementuje liczniki w ``stats`` na podstawie emoji z parse_pytest_line."""
    if emoji == "✅":
        stats["passed"] += 1
    elif emoji == "❌":
        stats["failed"] += 1
    elif emoji == "⏭️":
        stats["skipped"] += 1
    elif emoji == "🔴":
        stats["errors"] += 1


def format_section_summary(section_stats: dict) -> str:
    """Formatuje podsumowanie pojedynczej sekcji testu."""
    section_parts = []
    if section_stats.get("passed", 0) > 0:
        section_parts.append(f"✅ {section_stats['passed']} passed")
    if section_stats.get("failed", 0) > 0:
        section_parts.append(f"❌ {section_stats['failed']} failed")
    if section_stats.get("skipped", 0) > 0:
        section_parts.append(f"⏭️ {section_stats['skipped']} skipped")
    if section_stats.get("errors", 0) > 0:
        section_parts.append(f"🔴 {section_stats['errors']} errors")
    return f"  {' | '.join(section_parts)}" if section_parts else ""


__all__ = [
    "BACKEND_DIR",
    "BASE_DIR",
    "DEFAULT_TEST_VARS",
    "TEST_PATH_MAP",
    "accumulate_section_stats",
    "build_test_command",
    "extract_percentage",
    "extract_test_name",
    "format_section_summary",
    "format_summary_line",
    "parse_pytest_line",
]
