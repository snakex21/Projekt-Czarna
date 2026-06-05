"""Kompatybilnościowy wrapper dla runtime Test Center.

Implementacja GUI znajduje się w ``launcher.ui.test_center_runtime``,
a czysta logika w ``launcher.services.test_service``. Ten moduł
pozostaje cienką warstwą re-exportów dla starszych importów.
"""

from launcher.ui.test_center_runtime import (
    CONSOLE_TAGS,
    copy_test_logs_to_clipboard,
    log_to_test_console,
    open_test_center_window,
    run_playwright_tests,
    run_pytest,
    run_selected_tests,
    save_test_logs_to_file,
    setup_console_tags,
)
from launcher.services.test_service import (
    DEFAULT_TEST_VARS,
    TEST_PATH_MAP,
    accumulate_section_stats,
    build_test_command,
    extract_percentage,
    extract_test_name,
    format_section_summary,
    format_summary_line,
    parse_pytest_line,
)


__all__ = [
    "CONSOLE_TAGS",
    "DEFAULT_TEST_VARS",
    "TEST_PATH_MAP",
    "accumulate_section_stats",
    "build_test_command",
    "copy_test_logs_to_clipboard",
    "extract_percentage",
    "extract_test_name",
    "format_section_summary",
    "format_summary_line",
    "log_to_test_console",
    "open_test_center_window",
    "parse_pytest_line",
    "run_playwright_tests",
    "run_pytest",
    "run_selected_tests",
    "save_test_logs_to_file",
    "setup_console_tags",
]
