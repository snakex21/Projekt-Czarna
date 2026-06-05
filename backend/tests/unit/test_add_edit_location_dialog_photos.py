"""Kontrakt UI dialogu edycji miejscowości - sekcja 'Punkty historyczne'.

Weryfikuje strukturę edytora zdjęć:
- Dwupanelowy layout (pliki na dysku + lista zdjęć punktu),
- Pole 'Podpis' do edycji caption,
- Helpery ``_hp_add_to_point``/``_hp_remove_from_point``/``_hp_move_photo`` istnieją,
- ``_on_hp_save`` zapisuje ``self.hp_point_photos`` (zachowuje podpisy i kolejność),
- Priorytet 3.1: lewy listbox plików pokazuje TYLKO zdjęcia jeszcze nie przypisane
  do bieżącego punktu (ukrywa te z ``self.hp_point_photos``).

NIE uruchamia prawdziwego Tkinter - testuje strukturę kodu źródłowego.
"""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DIALOG_PY = PROJECT_ROOT / "launcher" / "ui" / "add_edit_location_dialog.py"


# ============================================================================
# Atrybuty instancji (deklaracje widgetów)
# ============================================================================


def test_dialog_has_files_listbox_attribute():
    """Lewy panel - pliki z ``history_photos/`` (nowa nazwa)."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert "self.hp_files_listbox" in source, (
        "Brak self.hp_files_listbox - lewy panel plików"
    )


def test_dialog_has_point_photos_tree_attribute():
    """Prawy panel - drzewo zdjęć bieżącego punktu."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert "self.hp_point_photos_tree" in source, (
        "Brak self.hp_point_photos_tree - prawy panel zdjęć"
    )


def test_dialog_has_caption_entry_attribute():
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert "self.hp_caption_entry" in source, (
        "Brak self.hp_caption_entry - pole podpisu zdjęcia"
    )
    assert "self.hp_caption_var" in source, (
        "Brak self.hp_caption_var (StringVar dla podpisu)"
    )


def test_dialog_has_point_photos_state_attribute():
    """Stan ``hp_point_photos`` trzyma listę zdjęć z podpisami."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert "self.hp_point_photos" in source, (
        "Brak self.hp_point_photos - wewnętrzny stan listy zdjęć punktu"
    )


# ============================================================================
# Helpery (akcje użytkownika)
# ============================================================================


def test_dialog_has_hp_add_to_point_method():
    """Dodawanie plików z lewego panelu do bieżącego punktu."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert re.search(r"def\s+_hp_add_to_point\s*\(", source), (
        "Brak metody _hp_add_to_point (dodawanie plików do punktu)"
    )


def test_dialog_has_hp_remove_from_point_method():
    """Usuwanie zdjęcia z bieżącego punktu (nie z dysku)."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert re.search(r"def\s+_hp_remove_from_point\s*\(", source), (
        "Brak metody _hp_remove_from_point (usuwanie z listy punktu)"
    )


def test_dialog_has_hp_move_photo_method():
    """Przesuwanie zdjęcia w górę / w dół."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert re.search(r"def\s+_hp_move_photo\s*\(", source), (
        "Brak metody _hp_move_photo (reorder ↑/↓)"
    )


def test_dialog_add_to_point_skips_duplicates():
    """Dodawanie tego samego pliku dwa razy jest pomijane."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+_hp_add_to_point\s*\([^)]*\)\s*:(.*?)(?=\n    def |\nclass )",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała _hp_add_to_point"
    body = match.group(1)
    assert "existing" in body, (
        "_hp_add_to_point musi sprawdzać duplikaty (słownik existing lub set)"
    )


def test_dialog_move_photo_uses_delta_parameter():
    """``_hp_move_photo(delta)`` przesuwa o ``delta`` pozycji."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+_hp_move_photo\s*\([^)]*\)\s*:(.*?)(?=\n    def |\nclass )",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała _hp_move_photo"
    body = match.group(1)
    # Argument powinien być używany (np. ``new_idx = idx + delta``)
    assert re.search(r"idx\s*\+\s*delta|delta\s*\(\s*self", body), (
        "_hp_move_photo musi używać argumentu 'delta' do przesuwania"
    )


# ============================================================================
# Synchronizacja caption (caption <-> drzewo)
# ============================================================================


def test_dialog_syncs_caption_to_data_on_change():
    """Wpisując tekst w Entry, aktualizuje ``self.hp_point_photos[idx]['caption']``."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert "_hp_sync_caption_to_data" in source, (
        "Brak _hp_sync_caption_to_data - callback synchronizujący podpis"
    )


def test_dialog_suppresses_caption_sync_on_programmatic_set():
    """Programowe ustawianie Entry nie nadpisuje danych użytkownika."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    assert "_hp_caption_sync_active" in source, (
        "Brak flagi _hp_caption_sync_active - programowe ustawienia Entry "
        "nie powinny triggerować zapisu do danych"
    )


# ============================================================================
# Zapis i odczyt punktu - korzysta z hp_point_photos
# ============================================================================


def test_dialog_on_hp_save_uses_point_photos_state():
    """``_on_hp_save`` czyta ``self.hp_point_photos`` (zachowuje podpisy + kolejność)."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+_on_hp_save\s*\([^)]*\)\s*:(.*?)(?=\n    def |\nclass )",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała _on_hp_save"
    body = match.group(1)
    assert "self.hp_point_photos" in body, (
        "_on_hp_save musi używać self.hp_point_photos "
        "(nie starego hp_photos_listbox - to nie zachowa podpisów)"
    )
    # Anty-regresja: nie powinno już korzystać z usuniętego listboxa
    assert "self.hp_photos_listbox" not in body, (
        "_on_hp_save NIE powinien korzystać z usuniętego self.hp_photos_listbox"
    )


def test_dialog_on_hp_select_loads_point_photos_state():
    """``_on_hp_select`` ładuje ``point.photos`` do ``self.hp_point_photos``."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+_on_hp_select\s*\([^)]*\)\s*:(.*?)(?=\n    def |\nclass )",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała _on_hp_select"
    body = match.group(1)
    assert "self.hp_point_photos" in body, (
        "_on_hp_select musi ładować zdjęcia z punktu do self.hp_point_photos"
    )


def test_dialog_on_hp_new_clears_point_photos_state():
    """``_on_hp_new`` czyści ``self.hp_point_photos``."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+_on_hp_new\s*\([^)]*\)\s*:(.*?)(?=\n    def |\nclass )",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała _on_hp_new"
    body = match.group(1)
    assert "self.hp_point_photos" in body, (
        "_on_hp_new musi czyścić self.hp_point_photos"
    )


# ============================================================================
# Auto-commit w save() — zabezpieczenie przed utratą zdjęć
# ============================================================================


def test_dialog_on_hp_save_returns_bool():
    """``_on_hp_save`` zwraca bool — ``True`` po zapisie, ``False`` przy błędzie walidacji.

    Potrzebne żeby ``save()`` mógł zdecydować: kontynuować zapis lokalizacji czy
    zostawić dialog otwarty po błędzie walidacji punktu.
    """
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+_on_hp_save\s*\([^)]*\)\s*:(.*?)(?=\n    def |\nclass )",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała _on_hp_save"
    body = match.group(1)
    # Funkcja musi zwracać ``True`` w ścieżce sukcesu i ``False`` przy błędzie walidacji
    assert re.search(r"\breturn\s+True\b", body), (
        "_on_hp_save powinno zwracać True przy powodzeniu"
    )
    assert re.search(r"\breturn\s+False\b", body), (
        "_on_hp_save powinno zwracać False przy błędzie walidacji"
    )


def test_dialog_save_auto_commits_current_point():
    """``save()`` automatycznie commituje edytowany punkt przed zapisem lokalizacji.

    Bez tego użytkownik, który doda zdjęcia/podpisy ale nie kliknie "Zapisz"
    na punkcie, traci te zmiany przy zapisie lokalizacji. Auto-commit w save()
    ratuje ten flow.
    """
    source = DIALOG_PY.read_text(encoding="utf-8")
    # save() jest ostatnią metodą w klasie - wyciągamy od ``def save(self):`` do EOF.
    match = re.search(
        r"def\s+save\s*\([^)]*\)\s*:(.*)",
        source,
        re.S,
    )
    assert match, "Nie znaleziono ciała save()"
    body = match.group(1)
    assert "_on_hp_save" in body, (
        "save() musi wywołać _on_hp_save (auto-commit bieżącego punktu)"
    )
    assert "hp_current_id" in body, (
        "save() musi sprawdzać hp_current_id (nie commitować gdy brak edytowanego punktu)"
    )
    # Musi też obsłużyć tryb "Nowy punkt" - formularz z danymi ale hp_current_id=None
    assert "form_has_data" in body, (
        "save() powinno sprawdzać form_has_data (obsługa trybu 'Nowy punkt')"
    )
    assert "hp_point_photos" in body, (
        "save() powinno sprawdzać hp_point_photos przy decyzji o auto-commicie"
    )


# ============================================================================
# End-to-end: auto-commit w save() z mockowanym dialogiem
# ============================================================================


class _FakeVar:
    """Minimalistyczny StringVar-stand-in dla testów (bez Tk).

    ``.get()`` akceptuje opcjonalne argumenty pozycyjne (``*args``),
    dzięki czemu ten sam mock pasuje zarówno do widgetów Entry
    (``get()``), jak i Text/ScrolledText (``get("1.0", tk.END)``).
    Dzięki temu mock może być użyty do każdego pola, które w produkcji
    zostało zmienione z Entry na ScrolledText.
    """
    def __init__(self, value=""):
        self._v = value

    def get(self, *args, **kwargs):
        return self._v

    def set(self, v):
        self._v = v


class _FakeText:
    """Stand-in dla ScrolledText (używa .get("1.0", END))."""
    def __init__(self, value=""):
        self._v = value

    def get(self, *args, **kwargs):
        return self._v

    def delete(self, *args, **kwargs):
        self._v = ""

    def insert(self, *args, **kwargs):
        self._v += args[1] if len(args) > 1 else ""


def _populate_location_widgets(dialog):
    """Ustawia wszystkie widgety location-level, których ``save()`` potrzebuje."""
    dialog.name_entry = _FakeVar("Czarna")
    dialog.full_name_entry = _FakeVar("Czarna")
    dialog.powiat_entry = _FakeVar("powiat")
    dialog.region_entry = _FakeVar("region")
    dialog.year_entry = _FakeVar("1920")
    dialog.century_entry = _FakeVar("XX")
    dialog.db_combo = _FakeVar("(SQLite lokalnie)")
    dialog.homepage_desc_text = _FakeText("")
    dialog.history_p1_text = _FakeText("")
    dialog.history_p2_text = _FakeText("")
    dialog.history_p3_text = _FakeText("")
    dialog.history_photos = []
    dialog.homepage_template_var = _FakeVar("default")
    dialog.gmina_katastralna_entry = _FakeVar("Czarna")
    dialog.jewish_protocols_entry = _FakeVar("")


def test_dialog_save_auto_commits_2_photos_end_to_end(monkeypatch):
    """End-to-end: dialog.save() commituje 2 zdjęcia dodane przez usera.

    Scenariusz: user dodaje drugie zdjęcie do istniejącego punktu (hp_current_id=0),
    klika "OK" na dialogu (czyli ``dialog.save()``) BEZ klikania "Zapisz" na punkcie.
    Oczekiwanie: ``result[-1]`` (``historical_points_data``) zawiera 2 zdjęcia.

    Mockujemy cały Tkinter - testujemy tylko logikę auto-commit.
    """
    from launcher.ui import add_edit_location_dialog as dlg_module

    # Tworzymy instancję dialogu BEZ wywoływania __init__ (omija tworzenie widgetów Tk).
    dialog = dlg_module.AddEditLocationDialog.__new__(dlg_module.AddEditLocationDialog)
    dialog.destroy = lambda: None  # save() wywołuje destroy() na końcu
    dialog.hp_current_id = 0
    dialog.hp_point_photos = [
        {"filename": "existing.png", "caption": "Stare zdjęcie"},
    ]
    # Mocki atrybutów, które ``_on_hp_save`` czyta
    dialog.hp_object_combo = _FakeVar("dworzec_czarna")
    dialog._hp_candidate_map = {"dworzec_czarna": "dworzec_czarna"}  # label → object_name
    dialog.hp_display_entry = _FakeVar("Dworzec kolejowy")
    dialog.hp_desc_text = _FakeText("Opis dworca")
    dialog.hp_source_entry = _FakeVar("Archiwum")
    # _on_hp_save potrzebuje jeszcze _refresh_hp_list i hp_tree (do odświeżenia GUI)
    dialog.hp_tree = type("T", (), {
        "selection_set": lambda *a, **k: None,
        "see": lambda *a, **k: None,
    })()
    dialog._refresh_hp_list = lambda: None

    # Symulacja user flow: user dodaje 2. zdjęcie (BEZ klikania "Zapisz" na punkcie)
    dialog.hp_point_photos.append({
        "filename": "new_photo.jpg",
        "caption": "Nowe zdjęcie dodane w launcherze",
    })

    # Mocki dla reszty save() - location-level fields
    _populate_location_widgets(dialog)

    # Mock walidacji + trybu SQLite (żeby nie blokował na pustej nazwie bazy)
    monkeypatch.setattr(
        dlg_module.HistoricalPoint, "validate", lambda self: None
    )
    monkeypatch.setattr(dlg_module, "is_sqlite_mode", lambda: True)
    # Tłumienie messagebox żeby testy nie wieszały się na dialogach
    monkeypatch.setattr(dlg_module.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(dlg_module.messagebox, "showinfo", lambda *a, **k: None)

    # Dane startowe
    dialog.historical_points_data = [
        {
            "object_name": "dworzec_czarna",
            "display_name": "Dworzec kolejowy",
            "description": "Opis dworca",
            "source_note": "Archiwum",
            "photos": [{"filename": "existing.png", "caption": "Stare zdjęcie"}],
        }
    ]

    # KLUCZOWE: wywołanie save() - symuluje kliknięcie OK
    dialog.save()

    # Weryfikacja: result[-1] to historical_points_data
    assert dialog.result is not None, "save() powinno ustawić dialog.result"
    historical_points_data = dialog.result[-1]
    assert len(historical_points_data) == 1
    photos = historical_points_data[0]["photos"]
    assert len(photos) == 2, (
        f"Auto-commit powinien zachować oba zdjęcia - jest {len(photos)}"
    )
    assert photos[0]["filename"] == "existing.png"
    assert photos[1]["filename"] == "new_photo.jpg"
    assert photos[1]["caption"] == "Nowe zdjęcie dodane w launcherze"


def test_dialog_save_auto_commits_new_point_with_photos(monkeypatch):
    """End-to-end: dialog.save() commituje nowy punkt dodany w trybie "Nowy".

    Scenariusz: user klika "Nowy" (hp_current_id=None), wpisuje dane, dodaje zdjęcie,
    klika "OK" BEZ klikania "Zapisz" na punkcie. Oczekiwanie: nowy punkt ląduje
    w ``historical_points_data`` z 1 zdjęciem.
    """
    from launcher.ui import add_edit_location_dialog as dlg_module

    dialog = dlg_module.AddEditLocationDialog.__new__(dlg_module.AddEditLocationDialog)
    dialog.destroy = lambda: None
    dialog.hp_current_id = None
    dialog.hp_point_photos = [
        {"filename": "nowe.jpg", "caption": "Pierwsze zdjęcie"},
    ]
    dialog.hp_object_combo = _FakeVar("nowy_punkt")
    dialog._hp_candidate_map = {"nowy_punkt": "nowy_punkt"}
    dialog.hp_display_entry = _FakeVar("Nowy punkt")
    dialog.hp_desc_text = _FakeText("Opis")
    dialog.hp_source_entry = _FakeVar("Źródło")
    dialog.hp_tree = type("T", (), {
        "selection_set": lambda *a, **k: None,
        "see": lambda *a, **k: None,
    })()
    dialog._refresh_hp_list = lambda: None

    _populate_location_widgets(dialog)

    monkeypatch.setattr(
        dlg_module.HistoricalPoint, "validate", lambda self: None
    )
    monkeypatch.setattr(dlg_module, "is_sqlite_mode", lambda: True)
    monkeypatch.setattr(dlg_module.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(dlg_module.messagebox, "showinfo", lambda *a, **k: None)

    # Brak istniejących punktów
    dialog.historical_points_data = []

    dialog.save()

    historical_points_data = dialog.result[-1]
    assert len(historical_points_data) == 1, (
        f"Nowy punkt powinien zostać dodany - jest {len(historical_points_data)}"
    )
    assert historical_points_data[0]["object_name"] == "nowy_punkt"
    assert len(historical_points_data[0]["photos"]) == 1
    assert historical_points_data[0]["photos"][0]["filename"] == "nowe.jpg"


def test_dialog_save_skips_auto_commit_when_form_is_empty(monkeypatch):
    """End-to-end: dialog.save() z pustym formularzem trybu "Nowy" - nic nie robi.

    Scenariusz: user otwiera dialog, klika "Nowy" (przez przypadek), klika "OK"
    bez wpisywania niczego. Oczekiwanie: ``historical_points_data`` pozostaje
    puste (bez pustych punktów), dialog.result zostaje ustawiony normalnie.
    """
    from launcher.ui import add_edit_location_dialog as dlg_module

    dialog = dlg_module.AddEditLocationDialog.__new__(dlg_module.AddEditLocationDialog)
    dialog.destroy = lambda: None

    dialog.hp_current_id = None
    dialog.hp_point_photos = []
    dialog.hp_object_combo = _FakeVar("")
    dialog._hp_candidate_map = {}
    dialog.hp_display_entry = _FakeVar("")
    dialog.hp_desc_text = _FakeText("")
    dialog.hp_source_entry = _FakeVar("")

    _populate_location_widgets(dialog)

    monkeypatch.setattr(
        dlg_module.HistoricalPoint, "validate", lambda self: None
    )
    monkeypatch.setattr(dlg_module, "is_sqlite_mode", lambda: True)
    monkeypatch.setattr(dlg_module.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(dlg_module.messagebox, "showinfo", lambda *a, **k: None)

    dialog.historical_points_data = []

    dialog.save()

    assert dialog.result is not None
    assert dialog.result[-1] == [], (
        "Pusty formularz w trybie 'Nowy' nie powinien dodawać pustego punktu"
    )


# ============================================================================
# Schemat danych - photographs przetrwają roundtrip
# ============================================================================


def test_historical_point_photos_with_caption_roundtrip_via_save_load():
    """End-to-end: HistoricalPoint z caption → save → load → caption zachowany.

    Test integruje service + zapis na dysk w tmpdir.
    """
    import json
    from launcher.services.historical_points_service import (
        HistoricalPoint,
        save_historical_points,
        load_historical_points,
    )

    points = [
        HistoricalPoint(
            object_name="dworzec kolejowy",
            display_name="Dworzec",
            description="Opis",
            source_note="Źródło",
            photos=[
                {"filename": "dworzec_czarna.png", "caption": "Dworzec kolejowy w Czarnej, ok. 1935 r."},
                {"filename": "drugi.jpg", "caption": "Drugie zdjęcie"},
            ],
        ),
    ]

    # Zapis do tymczasowego pliku
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        from launcher.services import historical_points_service as svc
        # Monkeypatch ścieżek
        import pathlib
        orig_dir = svc.location_data_dir
        svc.location_data_dir = lambda name: pathlib.Path(tmpdir)
        try:
            save_historical_points("TestLocation", points)
            loaded = load_historical_points("TestLocation")
            assert len(loaded) == 1
            assert loaded[0].object_name == "dworzec kolejowy"
            assert len(loaded[0].photos) == 2
            assert loaded[0].photos[0]["filename"] == "dworzec_czarna.png"
            assert loaded[0].photos[0]["caption"] == "Dworzec kolejowy w Czarnej, ok. 1935 r."
            assert loaded[0].photos[1]["caption"] == "Drugie zdjęcie"
        finally:
            svc.location_data_dir = orig_dir


# ============================================================================
# Priorytet 3.1: Lewy listbox plików pokazuje TYLKO nieprzypisane zdjęcia
# ============================================================================
# Dzięki temu listbox nie jest zaśmiecony plikami już użytymi w bieżącym
# punkcie historycznym (które są widoczne w prawym panelu "Zdjęcia teg...").
# Selektory są świadome aktualnego punktu (przeładowanie po zmianie punktu).


def _body_of(name: str) -> str:
    """Zwraca ciało metody ``name`` (do testów strukturalnych)."""
    source = DIALOG_PY.read_text(encoding="utf-8")
    match = re.search(
        r"def\s+" + re.escape(name) + r"\s*\([^)]*\)(?:\s*->\s*[^:]+)?\s*:(.*?)(?=\n    def |\nclass |\Z)",
        source,
        re.S,
    )
    assert match, f"Nie znaleziono ciała {name}"
    return match.group(1)


def test_refresh_hp_photo_files_filters_out_assigned_files():
    """``_refresh_hp_photo_files`` pomija pliki już w ``self.hp_point_photos``.

    Lewy listbox powinien pokazywać wyłącznie pliki dostępne do dodania
    (nie te już użyte w bieżącym punkcie).
    """
    body = _body_of("_refresh_hp_photo_files")
    # Sprawdzenie: buduje set z hp_point_photos (lub list comprehension).
    assert re.search(r"hp_point_photos", body), (
        "_refresh_hp_photo_files musi korzystać z self.hp_point_photos "
        "żeby odfiltrować już przypisane pliki"
    )
    # Sprawdzenie: wyciąga 'filename' z hp_point_photos (subscript lub .get())
    assert re.search(
        r"\[.filename.\]\s+for.*hp_point_photos"
        r"|\[.filename.\].*hp_point_photos"
        r"|\.get\(.{1,2}filename.{1,2}\).*hp_point_photos"
        r"|hp_point_photos.*\.get\(.{1,2}filename.{1,2}\)",
        body,
    ), (
        "_refresh_hp_photo_files musi wyciągać 'filename' z hp_point_photos "
        "(np. {p['filename'] for p in self.hp_point_photos} lub p.get('filename'))"
    )
    # Sprawdzenie: filtruje listę files (albo set/dict comprehension)
    assert re.search(
        r"f\s+not\s+in\s+used|used\s*=\s*\{|used_filename|assigned",
        body,
    ), (
        "_refresh_hp_photo_files musi odfiltrować files (np. [f for f in files if f not in used])"
    )


def test_on_hp_select_refreshes_files_listbox():
    """``_on_hp_select`` przeładowuje listbox plików po zmianie punktu.

    Po wybraniu innego punktu w lewej liście prawy panel (hp_point_photos)
    się zmienia → lewy listbox musi pokazać tylko nieprzypisane do NOWEGO punktu.
    """
    body = _body_of("_on_hp_select")
    assert "_refresh_hp_photo_files" in body, (
        "_on_hp_select musi wywołać _refresh_hp_photo_files "
        "żeby lewy listbox pokazywał pliki nieprzypisane do wybranego punktu"
    )


def test_on_hp_new_refreshes_files_listbox():
    """``_on_hp_new`` przeładowuje listbox plików (nowy punkt = puste hp_point_photos).

    Dla nowego punktu hp_point_photos = [] → lewy listbox pokazuje WSZYSTKIE pliki.
    """
    body = _body_of("_on_hp_new")
    assert "_refresh_hp_photo_files" in body, (
        "_on_hp_new musi wywołać _refresh_hp_photo_files "
        "żeby lewy listbox pokazał wszystkie pliki (bo nowy punkt jest pusty)"
    )


def test_hp_remove_from_point_refreshes_files_listbox():
    """``_hp_remove_from_point`` przeładowuje listbox plików.

    Po usunięciu zdjęcia z prawego panelu (hp_point_photos) plik powinien
    z powrotem pojawić się w lewym listboxie.
    """
    body = _body_of("_hp_remove_from_point")
    assert "_refresh_hp_photo_files" in body, (
        "_hp_remove_from_point musi wywołać _refresh_hp_photo_files "
        "żeby usunięty plik z powrotem pojawił się w lewym listboxie"
    )


def test_refresh_hp_photo_files_uses_point_photos_dir():
    """``_refresh_hp_photo_files`` czyta z osobnego folderu ``point_photos/``.

    Zdjęcia markerów (przypisywane do punktów historycznych) są w osobnym
    folderze niż galeria miejscowości (``history_photos/``). Dzięki temu
    użytkownik widzi mniej śmieci w lewym listboxie.
    """
    source = DIALOG_PY.read_text(encoding="utf-8")
    # Dialog importuje list_point_photos (i nadal list_history_photos dla galerii)
    import_block = re.search(
        r"from\s+\S*services\.historical_points_service\s+import\s*\((.*?)\)",
        source,
        re.S,
    )
    assert import_block, "Brak importu z historical_points_service"
    imports = import_block.group(1)
    assert "list_point_photos" in imports, (
        "Dialog musi importować list_point_photos (osobny folder dla markerów)"
    )
    assert "list_history_photos" in imports, (
        "Dialog musi nadal importować list_history_photos (galeria - używana gdzie indziej)"
    )
    # W _refresh_hp_photo_files jest wywołanie list_point_photos
    body = _body_of("_refresh_hp_photo_files")
    assert "list_point_photos" in body, (
        "_refresh_hp_photo_files musi wywołać list_point_photos "
        "(zdjęcia markerów, nie galerii)"
    )
    # Anty-regresja: nie wracamy do list_history_photos w lewym panelu
    assert "list_history_photos" not in body, (
        "_refresh_hp_photo_files NIE powinien czytać z galerii (history_photos/)"
    )
