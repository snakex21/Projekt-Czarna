import os
import json
import shutil
import threading
import webbrowser
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for

# --- KONFIGURACJA ŚCIEŻEK ---

# Ścieżka bazowa aplikacji (folder zawierający ten skrypt)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ścieżka katalogu projektu (2 poziomy wyżej: .../Projekt Mapa Czarna)
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, os.pardir))

# Ścieżka do folderu z kopiami zapasowymi (współdzielony dla całego projektu)
BACKUP_DIR = os.path.join(PROJECT_DIR, "backup")

# Ścieżka do głównego pliku danych działek
DATA_FILE_PATH = os.path.join(BACKUP_DIR, "parcels_data.json")

# --- KONFIGURACJA APLIKACJI FLASK ---

# Inicjalizacja głównego obiektu aplikacji Flask
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates"),
)

# Wyłączenie kodowania znaków Unicode do sekwencji \uXXXX
# Pozwala na poprawne zapisywanie polskich znaków w JSON
app.config["JSON_AS_ASCII"] = False

# Wyłączenie automatycznego sortowania kluczy w JSON
# Ważne dla zachowania kolejności działek w pliku
app.config["JSON_SORT_KEYS"] = False

# Globalna zmienna przechowująca dane działek w pamięci
parcels_data = {}

# --- FUNKCJE POMOCNICZE DO ZARZĄDZANIA DANYMI ---

def load_data_from_file():
    """Wczytuje dane działek z pliku JSON do pamięci.
    
    Funkcja próbuje odczytać plik parcels_data.json i załadować
    jego zawartość do globalnej zmiennej parcels_data.
    W przypadku błędu inicjalizuje pusty słownik.
    """
    global parcels_data
    
    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            parcels_data = json.load(f)
    except FileNotFoundError:
        # Plik nie istnieje - tworzenie pustej struktury
        parcels_data = {}
        print(
            f"Ostrzeżenie: Plik {DATA_FILE_PATH} nie znaleziony. Utworzono pusty słownik."
        )
    except json.JSONDecodeError:
        # Plik jest uszkodzony - tworzenie pustej struktury
        parcels_data = {}
        print(f"Błąd: Nie można zdekodować pliku JSON. Użyto pustego słownika.")


def save_data_to_file():
    """Zapisuje dane działek z pamięci do pliku JSON.
    
    Funkcja zapisuje aktualny stan zmiennej parcels_data
    do pliku z odpowiednim formatowaniem i kodowaniem UTF-8.
    """
    try:
        with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(parcels_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Krytyczny błąd podczas zapisu do pliku: {e}")

# --- API DO ZARZĄDZANIA DANYMI DZIAŁEK ---

@app.route("/api/parcels")
def get_parcels():
    """Zwraca wszystkie działki w formacie JSON.
    
    Endpoint używany przez frontend do początkowego załadowania
    wszystkich działek na mapę.
    """
    return jsonify(parcels_data)


@app.route("/api/parcel", methods=["POST"])
def add_parcel():
    """Dodaje nową działkę do systemu.
    
    Oczekuje JSON z polami:
    - id: unikalne ID działki
    - parcel: obiekt z danymi działki (kategoria, geometria)
    
    Zwraca status operacji i komunikat.
    """
    data = request.get_json()
    parcel_id = data.get("id")
    parcel_info = data.get("parcel")

    # Walidacja danych wejściowych
    if not parcel_id or not parcel_info:
        return (
            jsonify({"status": "error", "message": "Brak ID lub danych działki"}),
            400,
        )

    # Sprawdzenie unikalności ID
    if parcel_id in parcels_data:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Działka o ID '{parcel_id}' już istnieje.",
                }
            ),
            409,  # HTTP 409 Conflict
        )

    # Dodanie nowej działki i zapis do pliku
    parcels_data[parcel_id] = parcel_info
    save_data_to_file()
    
    return jsonify(
        {"status": "success", "message": f"Działka '{parcel_id}' została dodana."}
    )


@app.route("/api/parcel/<string:parcel_id>", methods=["PUT"])
def update_parcel_geometry(parcel_id):
    """Aktualizuje geometrię istniejącej działki.
    
    Pozwala na zmianę kształtu/położenia działki bez zmiany
    innych jej właściwości.
    
    Args:
        parcel_id: ID działki do aktualizacji (z URL)
    """
    # Sprawdzenie czy działka istnieje
    if parcel_id not in parcels_data:
        return jsonify({"status": "error", "message": "Działka nie znaleziona."}), 404

    data = request.get_json()
    new_geometry = data.get("geometria")

    # Walidacja nowej geometrii
    if not new_geometry:
        return jsonify({"status": "error", "message": "Brak nowej geometrii."}), 400

    # Aktualizacja geometrii i zapis
    parcels_data[parcel_id]["geometria"] = new_geometry
    save_data_to_file()
    
    return jsonify(
        {
            "status": "success",
            "message": f"Geometria działki '{parcel_id}' została zaktualizowana.",
        }
    )


@app.route("/api/parcel/rename/<string:old_id>", methods=["PATCH"])
def rename_parcel(old_id):
    """Zmienia ID (nazwę) istniejącej działki.
    
    Zachowuje pozycję działki w kolejności słownika,
    co jest ważne dla zachowania porządku w liście.
    
    Args:
        old_id: Obecne ID działki do zmiany (z URL)
    """
    global parcels_data
    
    # Sprawdzenie czy działka istnieje
    if old_id not in parcels_data:
        return (
            jsonify(
                {"status": "error", "message": f"Działka '{old_id}' nie znaleziona."}
            ),
            404,
        )

    data = request.get_json()
    new_id = data.get("new_id")

    # Walidacja nowego ID
    if not new_id:
        return jsonify({"status": "error", "message": "Nie podano nowego ID."}), 400

    # Sprawdzenie unikalności nowego ID
    if new_id in parcels_data and new_id != old_id:
        return (
            jsonify({"status": "error", "message": f"ID '{new_id}' jest już zajęte."}),
            409,
        )

    # Zmiana ID z zachowaniem kolejności w słowniku
    if old_id != new_id:
        # Tworzenie nowego słownika z zachowaniem kolejności
        items = list(parcels_data.items())
        try:
            # Znajdź indeks elementu do zmiany nazwy
            index = [i for i, (key, val) in enumerate(items) if key == old_id][0]
            # Usuń stary element
            parcel_content = parcels_data.pop(old_id)
            # Stwórz nową listę tupli
            new_items = [(key, val) for key, val in items if key != old_id]
            # Wstaw nowy element na prawidłowej pozycji
            new_items.insert(index, (new_id, parcel_content))
            # Zaktualizuj główną zmienną
            parcels_data = dict(new_items)
        except IndexError:  
            # Fallback - prosty sposób bez zachowania kolejności
            parcel_content = parcels_data.pop(old_id)
            parcels_data[new_id] = parcel_content

    save_data_to_file()
    
    return jsonify(
        {
            "status": "success",
            "message": f"Zmieniono nazwę działki z '{old_id}' na '{new_id}'.",
        }
    )


@app.route("/api/parcel/<string:parcel_id>", methods=["DELETE"])
def delete_parcel(parcel_id):
    """Usuwa działkę z systemu.
    
    Trwale usuwa działkę z pliku danych.
    
    Args:
        parcel_id: ID działki do usunięcia (z URL)
    """
    if parcel_id in parcels_data:
        # Usunięcie działki z pamięci i zapis zmian
        del parcels_data[parcel_id]
        save_data_to_file()
        
        return jsonify(
            {"status": "success", "message": f"Usunięto działkę '{parcel_id}'."}
        )
    
    return jsonify({"status": "error", "message": "Działka nie znaleziona."}), 404

# --- ENDPOINTY APLIKACJI (STRONY I NAWIGACJA) ---

@app.route("/")
def root():
    """Przekierowuje z głównego URL na stronę startową aplikacji."""
    return redirect(url_for("index"))


@app.route("/template.html")
def index():
    """Serwuje główny plik HTML aplikacji edytora działek."""
    return render_template("template.html")


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """Zamyka serwer Flask.
    
    Uruchamia zamknięcie w osobnym wątku, aby zdążyć
    zwrócić odpowiedź HTTP przed faktycznym wyłączeniem.
    """
    threading.Thread(target=lambda: os._exit(0)).start()
    return jsonify({"status": "success"})

# --- API DO ZARZĄDZANIA KOPIAMI ZAPASOWYMI ---

@app.route("/api/backups")
def get_backups():
    """Zwraca listę dostępnych plików kopii zapasowych.
    
    Skanuje folder backup w poszukiwaniu plików JSON
    zawierających kopie zapasowe danych działek.
    """
    # Sprawdzenie czy folder istnieje
    if not os.path.exists(BACKUP_DIR):
        return jsonify([])
    
    # Filtrowanie i sortowanie plików kopii zapasowych
    files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".json") and "backup" in f],
        reverse=True,  # Najnowsze pierwsze
    )
    
    return jsonify(files)


@app.route("/backup", methods=["POST"])
def backup_data():
    """Tworzy nową kopię zapasową bieżących danych.
    
    Zapisuje aktualny stan danych do pliku z timestampem
    w nazwie dla łatwej identyfikacji.
    """
    # Generowanie unikalnej nazwy pliku z datą i czasem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"parcels_data_backup_{timestamp}.json")
    
    # Zapisanie aktualnych danych i utworzenie kopii
    save_data_to_file()
    shutil.copy2(DATA_FILE_PATH, backup_path)
    
    return jsonify(
        {
            "status": "success",
            "message": f"Kopia utworzona: {os.path.basename(backup_path)}",
        }
    )


@app.route("/restore", methods=["POST"])
def restore_data():
    """Przywraca dane z wybranej kopii zapasowej.
    
    Zastępuje obecny plik danych wybraną kopią zapasową
    i przeładowuje dane do pamięci.
    """
    filename = request.json.get("filename")
    
    # Walidacja nazwy pliku
    if not filename:
        return jsonify({"status": "error", "message": "Brak nazwy pliku."}), 400
    
    source_path = os.path.join(BACKUP_DIR, filename)
    
    # Sprawdzenie bezpieczeństwa ścieżki (zapobieganie path traversal)
    if not (os.path.isfile(source_path) and source_path.startswith(BACKUP_DIR)):
        return jsonify({"status": "error", "message": "Plik nie istnieje."}), 404
    
    # Przywrócenie kopii i przeładowanie danych
    shutil.copy2(source_path, DATA_FILE_PATH)
    load_data_from_file()
    
    return jsonify({"status": "success", "message": f"Wczytano plik '{filename}'."})


@app.route("/delete_backup", methods=["POST"])
def delete_backup():
    """Usuwa wybraną kopię zapasową.
    
    Trwale usuwa plik kopii zapasowej z dysku.
    Zawiera zabezpieczenia przed usunięciem plików spoza
    dozwolonego katalogu.
    """
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")

    # Walidacja nazwy pliku
    if not filename:
        return jsonify({"status": "error", "message": "Brak nazwy pliku."}), 400

    # Prosta walidacja bezpieczeństwa: tylko pliki .json z "backup" w nazwie
    if not filename.endswith(".json") or "backup" not in filename:
        return jsonify({"status": "error", "message": "Nieprawidłowa nazwa pliku."}), 400

    file_path = os.path.join(BACKUP_DIR, filename)

    # Upewnienie się, że ścieżka nie wychodzi poza BACKUP_DIR (ochrona przed path traversal)
    if not (os.path.isfile(file_path) and os.path.abspath(file_path).startswith(os.path.abspath(BACKUP_DIR))):
        return jsonify({"status": "error", "message": "Plik nie istnieje."}), 404

    try:
        # Usunięcie pliku
        os.remove(file_path)
        return jsonify({"status": "success", "message": f"Usunięto '{filename}'."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Nie udało się usunąć: {e}"}), 500

# --- URUCHOMIENIE SERWERA ---

if __name__ == "__main__":
    # Wczytanie danych przy starcie serwera
    load_data_from_file()
    
    # Konfiguracja portu i adresu URL
    port = 5003
    url = f"http://127.0.0.1:{port}/template.html"
    
    # Automatyczne otwarcie przeglądarki po uruchomieniu
    threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    
    # Wyświetlenie informacji startowych
    print("---------------------------------------------")
    print(f"Uruchamianie serwera edytora mapy pod adresem: {url}")
    print("---------------------------------------------")
    
    # Uruchomienie serwera Flask
    # debug=False - wyłączony tryb debugowania dla stabilności
    # use_reloader=False - zapobiega podwójnemu uruchomieniu
    app.run(port=port, debug=False, use_reloader=False)