import pytest
import os
import signal
import subprocess
import time
import requests
from playwright.sync_api import sync_playwright

# Konfiguracja adresów URL (domyślne dla projektu)
BASE_URL = "http://127.0.0.1:5000"
EDITOR_URL = "http://127.0.0.1:5001"

# Fixture 'server' została przeniesiona do conftest.py


def test_homepage_loads(server, page):
    """Sprawdza czy strona główna ładuje się poprawnie."""
    page.goto(BASE_URL)
    # Sprawdzamy czy tytuł zawiera nazwę projektu (lub czy w ogóle coś się wczytało)
    expect_title = "Mapa" # lub inny kluczowy element
    assert page.title() != ""
    print(f"OK: Strona glowna zaladowana: {page.title()}")

def test_admin_panel_navigation(server, page):
    """Sprawdza czy można wejść do panelu administratora."""
    page.goto(f"{BASE_URL}/admin/admin.html")
    # Szukamy nagłówka "Panel Administracyjny"
    assert "Panel Administracyjny" in page.content()
    print("OK: Panel administracyjny dostepny (ekran logowania).")

def test_editor_smoke(server, page):
    """Sprawdza czy edytor genealogiczny ładuje się (jeśli serwer edytora działa)."""
    # Tu zakładamy, że edytor jest serwowany przez główny serwer lub pod innym portem
    # Jeśli edytor wymaga osobnego procesu, trzeba by go też uruchomić w fixture
    page.goto(f"{BASE_URL}/genealogia/genealogia.html")
    assert "Genealogia" in page.content()
    print("OK: Widok genealogii zaladowany.")
