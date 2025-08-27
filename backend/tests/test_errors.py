# Zachowanie aplikacji dla błędnych adresów

def test_404_for_unknown_path(client):
    resp = client.get("/to/na/pewno/nie/istnieje")
    assert resp.status_code == 404
