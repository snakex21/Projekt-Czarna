import pytest
import os
import subprocess
import time
import requests
import sys

BASE_URL = "http://127.0.0.1:5000"

@pytest.fixture(scope="session")
def server():
    """Uruchamia serwer backendowy na potrzeby testów."""
    print("\n[INFO] Uruchamianie serwera testowego...")
    
    # Ustawiamy TEST_LOCATION, żeby backend wiedział skąd brać dane
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1" # Wymuszamy niebuforowane wyjście dla logów
    if "TEST_LOCATION" not in env:
        env["TEST_LOCATION"] = "Czarna"
    
    # backend/tests/e2e/conftest.py -> ../../../.. -> root
    # os.path.dirname(__file__) = .../backend/tests/e2e
    # .. = .../backend/tests
    # .. = .../backend
    # .. = .../root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    backend_path = os.path.join(project_root, "backend", "app.py")
    
    print(f"[DEBUG] project_root: {project_root}")
    print(f"[DEBUG] backend_path: {backend_path}")

    # Używamy sys.executable
    process = subprocess.Popen(
        [sys.executable, backend_path],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Łączymy stderr z stdout
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    
    # Czekamy aż serwer wystartuje
    max_retries = 20
    server_started = False
    for i in range(max_retries):
        try:
            # Próbujemy odczytać trochę wyjścia, żeby nie wisiało
            # Ale uwaga: .readline() blokuje jeśli nic nie ma
            # Zamiast tego używamy requests i krótkiego timeoutu
            response = requests.get(BASE_URL, timeout=1)
            if response.status_code == 200:
                print(f"[SUCCESS] Serwer dostępny pod {BASE_URL}")
                server_started = True
                break
        except requests.exceptions.ConnectionError:
            print(f"[WAIT] Czekam na serwer... ({i+1}/{max_retries})")
            time.sleep(2)
    
    if not server_started:
        print(f"\n[ERROR] Serwer nie wystartował w wyznaczonym czasie.")
        process.terminate()
        # Pobierz logi z procesu
        logs = ""
        try:
            logs, _ = process.communicate(timeout=2)
        except:
            pass
        with open("server_e2e_error.log", "w", encoding="utf-8") as f:
            f.write(logs)
        pytest.fail(f"Serwer nie wystartował. Logi w server_e2e_error.log")
    
    yield process
    
    # Zamykamy serwer po testach
    process.terminate()
    try:
        process.wait(timeout=5)
    except:
        process.kill()
    print("[INFO] Serwer testowy zatrzymany.")
