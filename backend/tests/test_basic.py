# Proste sanity-checki aplikacji publicznej.

def test_root_redirects_to_main(client):
    # "/" powinno przekierować do /strona_glowna/index.html
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 303)
    loc = resp.headers.get("Location", "")
    assert "/strona_glowna/index.html" in loc


def test_check_auth_when_disabled(client, monkeypatch):
    # Wymuszamy wyłączenie autoryzacji admina niezależnie od .env
    import app as backend_app
    monkeypatch.setattr(backend_app, "ADMIN_AUTH_ENABLED", False)

    resp = client.get("/api/admin/check-auth")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"authenticated": True, "auth_required": False}

