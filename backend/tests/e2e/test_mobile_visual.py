import pytest
from playwright.sync_api import sync_playwright
import os
import time

BASE_URL = "http://127.0.0.1:5000"

def test_mobile_layout_iphone_pro(server, browser):
    """Sprawdza czy strona główna ładuje się poprawnie na iPhone 14 Pro."""
    iphone_14 = {
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "viewport": {"width": 393, "height": 852},
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    }
    
    context = browser.new_context(**iphone_14)
    page = context.new_page()
    
    page.goto(f"{BASE_URL}/strona_glowna/index.html")
    
    assert page.is_visible("body")
    print("OK: Strona glowna zaladowana na symulacji iPhone 14 Pro.")
    
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    viewport_width = page.viewport_size["width"]
    assert scroll_width <= viewport_width, "UWAGA: Wykryto horyzontalny scroll na mobile!"
    
    context.close()

def test_visual_regression_admin_login(server, page):
    """Robi zrzut ekranu logowania admina do przyszłego porównania."""
    page.goto(f"{BASE_URL}/admin/admin.html")
    
    # Tworzymy katalog na screenshoty jeśli nie istnieje
    os.makedirs("backend/tests/e2e/screenshots", exist_ok=True)
    screenshot_path = "backend/tests/e2e/screenshots/admin_login_baseline.png"
    
    page.screenshot(path=screenshot_path)
    print(f"OK: Zrzut ekranu zapisany: {screenshot_path}")
    
    assert os.path.exists(screenshot_path)

def test_genealogia_mobile_search(server, browser):
    """Sprawdza czy wyszukiwarka w genealogii działa na telefonie."""
    iphone_14 = {
        "viewport": {"width": 393, "height": 852},
        "is_mobile": True,
    }
    
    context = browser.new_context(**iphone_14)
    mobile_page = context.new_page()
    
    mobile_page.goto(f"{BASE_URL}/genealogia/genealogia.html")
    
    mobile_page.wait_for_selector("#searchInput")
    # Czekaj na załadowanie danych (ukrycie wskaźnika)
    mobile_page.wait_for_selector("#loadingIndicator", state="hidden")
    
    # Symulacja wpisywania "z ręki" dla wywołania zdarzeń input
    mobile_page.type("#searchInput", "Kubicki", delay=50)
    
    # Czekaj aż licznik zmieni się z zera na wynik
    mobile_page.wait_for_function('document.getElementById("countDisplay").innerText !== "0"')
    
    count = mobile_page.inner_text("#countDisplay")
    assert int(count) > 0, f"Brak wynikow wyszukiwania na mobile dla 'Kubicki' (wynik: {count})"
    print(f"OK: Wyszukiwarka mobilna dziala (znaleziono osob: {count})")
    
    context.close()
