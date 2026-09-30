"""
Współdzielony conftest dla wszystkich kategorii testów (E2E, PERF, SECURITY).
Uruchamia serwer FastAPI przez uvicorn na potrzeby testów HTTP.
"""
import pytest
import os
import subprocess
import time
import requests
import sys

# Konfiguracja przed importem aplikacji w podkatalogach. Jeden proces pytest
# musi używać jednej bazy, także gdy zbiera unit i integration razem.
import atexit
import shutil
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.tests.sample_data import create_sample_database, create_sample_location, assert_port_available

_test_root = Path(tempfile.mkdtemp(prefix="czarna_synthetic_tests_"))
atexit.register(shutil.rmtree, _test_root, ignore_errors=True)
os.environ["DB_ENGINE"] = "sqlite"
os.environ["DB_PATH"] = str(create_sample_database(_test_root / "tests.db"))
os.environ["BACKUP_DIR"] = str(_test_root / "locations")
os.environ["ACTIVE_LOCATION"] = "Czarna"
os.environ["TEST_LOCATION"] = "Czarna"
create_sample_location(_test_root / "locations")

BASE_URL = "http://127.0.0.1:5000"


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    """Uruchamia serwer backendowy (FastAPI/uvicorn) na potrzeby testów."""
    print("\n[TEST] Uruchamianie serwera testowego...")
    
    # Testy legacy używają stałego portu. Nie wolno podłączyć ich do
    # wcześniej uruchomionej aplikacji użytkownika zamiast własnego procesu.
    try:
        assert_port_available("127.0.0.1", 5000)
    except OSError as error:
        pytest.fail(f"Port testowy 5000 jest zajęty; nie używam istniejącego serwera: {error}")

    env = os.environ.copy()
    server_root = tmp_path_factory.mktemp("e2e_server")
    env["DB_PATH"] = str(create_sample_database(server_root / "e2e.db"))
    env["BACKUP_DIR"] = str(server_root / "locations")
    create_sample_location(server_root / "locations")
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if "TEST_LOCATION" not in env:
        env["TEST_LOCATION"] = "Czarna"
    # Wymuszamy SQLite dla testów security/e2e/perf.
    # Jeśli host ma w shellu DB_ENGINE=postgresql z poprzedniej sesji,
    # to bez FORCE serwer próbuje połączyć się z PG (które często nie działa
    # lokalnie) i wisi na starcie → 40s timeout zamiast pracy z SQLite.
    # PG E2E testy mają własny fixture (pg_session) i nie korzystają z tego servera.
    env["DB_ENGINE"] = "sqlite"
    
    # backend/tests/conftest.py -> ../.. -> project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    print(f"[TEST] project_root: {project_root}")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "5000",
            # Test Center/pytest nie czyta stdout procesu w trakcie testow.
            # Domyslny access log uvicorn potrafi zapelnic pipe po kilku
            # testach Playwright i zablokowac serwer, co dawalo timeouty
            # ostatnich E2E w launcherze mimo poprawnej aplikacji.
            "--no-access-log",
            "--log-level",
            "warning",
        ],
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    
    max_retries = 20
    server_started = False
    for i in range(max_retries):
        if process.poll() is not None:
            break
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=1)
            if response.status_code == 200:
                # Daj uvicorn zgłosić ewentualny wyścig o port po preflight.
                time.sleep(0.2)
                if process.poll() is not None:
                    break
                print(f"[TEST] Serwer dostepny pod {BASE_URL}")
                server_started = True
                break
        except requests.exceptions.ConnectionError:
            print(f"[TEST] Czekam na serwer... ({i+1}/{max_retries})")
            time.sleep(2)
    
    if not server_started:
        print("\n[TEST] Serwer nie wystartowal.")
        process.terminate()
        logs = ""
        try:
            logs, _ = process.communicate(timeout=2)
        except:
            pass
        with open("server_e2e_error.log", "w", encoding="utf-8") as f:
            f.write(logs)
        pytest.fail("Serwer nie wystartowal. Logi w server_e2e_error.log")
    
    yield process
    
    process.terminate()
    try:
        process.wait(timeout=5)
    except:
        process.kill()
    print("[TEST] Serwer testowy zatrzymany.")
