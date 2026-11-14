"""Pomocnicze funkcje uwierzytelniania w testach.

Hasło admina jest losowane na sesję pytest w ``backend/tests/conftest.py``
(zmienna ``MAPA_TEST_ADMIN_PASSWORD``), a jego hash trafia do
``ADMIN_PASSWORD_HASH``. Testy logują się prawdziwym endpointem.
"""
import os

TEST_ADMIN_USERNAME = "admin"


def admin_password() -> str:
    return os.environ["MAPA_TEST_ADMIN_PASSWORD"]


def login_admin(client):
    """Loguje ``client`` (TestClient) jako admin; ciasteczko zostaje w kliencie."""
    resp = client.post(
        "/api/admin/login",
        json={"username": TEST_ADMIN_USERNAME, "password": admin_password()},
    )
    assert resp.status_code == 200, f"Logowanie nie powiodło się: {resp.status_code} {resp.text}"
    assert resp.json()["status"] == "ok"
    return client
