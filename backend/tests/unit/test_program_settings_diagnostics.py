"""Kontrakt UI launchera - zakładka 'Diagnostyka' - sekcja jakości danych.

Weryfikuje strukturę nowej karty z 9 metrykami:
- Klasa ``ProgramSettingsWindow`` ma ``_build_data_quality_card``,
- Metoda renderuje kartę + przycisk + pole tekstowe,
- Metoda ``_refresh_data_quality`` robi HTTP GET do backendu,
- Metoda ``_format_diagnostics_payload`` formatuje payload w czytelny tekst,
- Stałe dla 9 metryk są zdefiniowane (kolejność kart w panelu webowym).
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_SETTINGS_PY = PROJECT_ROOT / "launcher" / "ui" / "program_settings.py"


# Regex helper: łapie ``def name(args) [-> type]:`` łącznie z opcjonalnym
# type hintem zwracanym (np. ``-> str``).
_DEF_RE = re.compile(
    r"def\s+(\w+)\s*\([^)]*\)(?:\s*->\s*[^:]+)?\s*:(.*?)(?=\n    def |\nclass |\Z)",
    re.S,
)


def _extract_method(name: str) -> str:
    """Zwraca ciało metody ``name`` z pliku program_settings.py."""
    source = PROGRAM_SETTINGS_PY.read_text(encoding="utf-8")
    match = _DEF_RE.search(source)
    # szukamy konkretnej nazwy
    for m in _DEF_RE.finditer(source):
        if m.group(1) == name:
            return m.group(2)
    raise AssertionError(f"Nie znaleziono metody {name}")


def test_diagnostics_tab_has_data_quality_card_builder():
    """``_build_data_quality_card`` istnieje w ProgramSettingsWindow."""
    body = _extract_method("_build_data_quality_card")
    assert body, "Brak metody _build_data_quality_card"


def test_data_quality_card_has_refresh_button():
    """Metoda tworzy przycisk do odświeżania metryk."""
    body = _extract_method("_build_data_quality_card")
    assert "refresh_quality_btn" in body, "Brak self.refresh_quality_btn"
    assert "ttk.Button" in body, "Powinien używać ttk.Button"


def test_data_quality_card_has_text_widget():
    """Metoda tworzy ScrolledText do wyświetlania metryk."""
    body = _extract_method("_build_data_quality_card")
    assert "self.data_quality_text" in body, (
        "Brak self.data_quality_text - widget na wyniki"
    )
    assert "ScrolledText" in body, "Powinien używać ScrolledText"


def test_diagnostics_tab_calls_data_quality_card_builder():
    """``_build_diagnostics_tab`` wywołuje ``_build_data_quality_card``."""
    body = _extract_method("_build_diagnostics_tab")
    assert "_build_data_quality_card" in body, (
        "_build_diagnostics_tab musi wywołać _build_data_quality_card"
    )


def test_refresh_data_quality_does_http_get():
    """``_refresh_data_quality`` robi HTTP GET (przez urllib)."""
    body = _extract_method("_refresh_data_quality")
    assert "urllib.request.Request" in body or "threading.Thread" in body, (
        "Powinien używać urllib.request.Request + threading.Thread"
    )
    # Albo _fetch_data_quality_sync (delegat)
    sync_body = _extract_method("_fetch_data_quality_sync")
    assert "urllib.request.Request" in sync_body


def test_fetch_data_quality_sync_uses_admin_diagnostics_endpoint():
    """Pobiera metryki z ``/api/admin/diagnostics`` (kontrakt z backendem)."""
    body = _extract_method("_fetch_data_quality_sync")
    assert "/api/admin/diagnostics" in body, (
        "Endpoint musi być /api/admin/diagnostics (kontrakt z routerem)"
    )


def test_format_diagnostics_payload_lists_all_9_metrics():
    """``_format_diagnostics_payload`` zawiera wszystkie 9 metryk."""
    body = _extract_method("_format_diagnostics_payload")
    expected = [
        "parcels_without_owners",
        "owners_without_parcels",
        "protocols_without_genealogy",
        "people_without_parents",
        "people_without_birth_date",
        "people_without_death_date",
        "parcels_without_category",
        "owners_without_house_number",
        "parcel_owner_links",
        "incomplete_records",
    ]
    for key in expected:
        assert key in body, f"Brak metryki {key} w _format_diagnostics_payload"


def test_format_diagnostics_payload_uses_polish_labels():
    """Formatowanie używa polskich etykiet."""
    body = _extract_method("_format_diagnostics_payload")
    for label in [
        "Działki bez właściciela",
        "Osoby bez rodziców",
        "Powiązania",
    ]:
        assert label in body, f"Brak polskiej etykiety '{label}'"


def test_get_backend_url_uses_urls_config():
    """``_get_backend_url`` czyta z URLS (nie hardkoduje localhost:5000)."""
    body = _extract_method("_get_backend_url")
    assert "URLS" in body, "Powinien czytać URL z URLS (launcher/config/settings.py)"


def test_data_quality_card_handles_backend_unavailable():
    """Launcher gracefully obsługuje brak backendu (URLError/ConnectionError)."""
    body = _extract_method("_fetch_data_quality_sync")
    assert "URLError" in body or "ConnectionError" in body, (
        "Powinien łapać URLError/ConnectionError"
    )
    assert "Backend niedostępny" in body or "Błąd HTTP" in body, (
        "Powinien wyświetlać czytelny komunikat błędu"
    )


def test_set_data_quality_text_is_helper():
    """``_set_data_quality_text`` istnieje (helper do update widgetu)."""
    body = _extract_method("_set_data_quality_text")
    for token in ['state="normal"', "delete", "insert", 'state="disabled"']:
        assert token in body, f"Brak '{token}' w helperze _set_data_quality_text"


# ============================================================================
# Priorytet 6.5: Karta "Bezpieczeństwo admina" w launcherze
# ============================================================================
# Pokazuje status: auth_enabled, using_default_password, using_default_secret_key,
# is_production + lista ostrzeżeń. Fetch z GET /api/admin/auth-status.


def test_diagnostics_tab_has_security_card_builder():
    """``_build_security_card`` istnieje w ProgramSettingsWindow."""
    body = _extract_method("_build_security_card")
    assert body, "Brak metody _build_security_card"


def test_security_card_has_refresh_button():
    """Karta bezpieczeństwa ma przycisk 'Odśwież' (fetch /api/admin/auth-status)."""
    body = _extract_method("_build_security_card")
    assert "security_refresh_btn" in body, "Brak self.security_refresh_btn"
    assert "ttk.Button" in body


def test_security_card_has_text_widget():
    """Karta bezpieczeństwa ma widget tekstowy na wyniki."""
    body = _extract_method("_build_security_card")
    assert "self.security_text" in body, "Brak self.security_text"
    assert "ScrolledText" in body


def test_security_card_calls_in_diagnostics_tab():
    """``_build_diagnostics_tab`` wywołuje ``_build_security_card``."""
    body = _extract_method("_build_diagnostics_tab")
    assert "_build_security_card" in body, (
        "_build_diagnostics_tab musi wywołać _build_security_card"
    )


def test_format_security_status_polish_labels():
    """``_format_security_status`` zawiera polskie etykiety + emoji statusu."""
    body = _extract_method("_format_security_status")
    # Polskie etykiety
    assert "Autoryzacja" in body or "autoryzacja" in body
    assert "Hasło" in body or "hasło" in body
    assert "SECRET_KEY" in body
    assert "Produkcja" in body or "produkcja" in body
    # Emoji statusu (✅ / ⚠️ / ❌)
    assert "✅" in body or "⚠" in body or "❌" in body


def test_refresh_security_fetches_from_auth_status_endpoint():
    """``_refresh_security`` (entry point) + ``_fetch_security_sync`` (worker) używają urllib."""
    refresh_body = _extract_method("_refresh_security")
    fetch_body = _extract_method("_fetch_security_sync")
    # URL endpointu - musi być w entry point LUB worker
    assert "/api/admin/auth-status" in (refresh_body + fetch_body), (
        "Brak fetch-owania /api/admin/auth-status"
    )
    # urllib musi być w workerze (tam są requesty HTTP)
    assert "urllib.request.Request" in fetch_body or "urlopen" in fetch_body, (
        "_fetch_security_sync musi używać urllib do HTTP"
    )
