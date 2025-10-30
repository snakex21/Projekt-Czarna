"""
============================================================================
Aplikacja: Edytor Mapy Katastralnej
Opis: Serwer Flask obsługujący edycję działek na mapie interaktywnej.
      Umożliwia dodawanie, edycję, usuwanie działek oraz zarządzanie kopiami.
============================================================================
"""

import os
import json
import shutil
import threading
import webbrowser
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for

# ==========================================================================
# KONFIGURACJA ŚCIEŻEK SYSTEMU
# ==========================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, os.pardir, os.pardir))
BACKUP_DIR = os.path.join(PROJECT_DIR, "backup")
DATA_FILE_PATH = os.path.join(BACKUP_DIR, "parcels_data.json")

# ==========================================================================
# INICJALIZACJA APLIKACJI FLASK
# ==========================================================================
app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates"),
)

# Konfiguracja kodowania JSON - zachowanie polskich znaków
app.config["JSON_AS_ASCII"] = False
app.config["JSON_SORT_KEYS"] = False

# Globalne przechowywanie danych
map_config = {}
parcels_data = {}

# ==========================================================================
# FUNKCJE ZARZĄDZANIA KONFIGURACJĄ
# ==========================================================================
def load_map_config_from_file():
    """Wczytuje konfigurację mapy z pliku JSON."""
    global map_config
    config_path = os.path.join(PROJECT_DIR, "backup", "map_config.json")
    
    try:
        if not os.path.exists(config_path):
            # Domyślna konfiguracja gdy brak pliku
            default_config = {
                "calibration": {
                    "sw": {"lat": 50.0414, "lng": 21.2261}, 
                    "ne": {"lat": 50.0814, "lng": 21.2661}
                },
                "defaults": {
                    "center": {"lat": 50.0614, "lng": 21.2461}, 
                    "zoom": 14
                }
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            map_config = default_config
            print("✅ Utworzono domyślny plik konfiguracyjny mapy")
        else:
            with open(config_path, 'r', encoding='utf-8') as f:
                map_config = json.load(f)
            print("✅ Konfiguracja mapy załadowana pomyślnie")
    except Exception as e:
        print(f"❌ Błąd wczytywania konfiguracji: {e}")
        # Konfiguracja awaryjna
        map_config = {
            "calibration": {
                "sw": {"lat": 50.0414, "lng": 21.2261}, 
                "ne": {"lat": 50.0814, "lng": 21.2661}
            },
            "defaults": {
                "center": {"lat": 50.0614, "lng": 21.2461}, 
                "zoom": 14
            }
        }

# ==========================================================================
# FUNKCJE ZARZĄDZANIA DANYMI
# ==========================================================================
def migrate_data_to_new_format():
    """Migruje dane ze starego formatu (numer) na nowy format (numer_kategoria)."""
    global parcels_data

    migrated = False
    new_parcels_data = {}

    for parcel_id, parcel_info in parcels_data.items():
        # Sprawdź czy to stary format (klucz bez kategorii)
        category = parcel_info.get("kategoria", "")

        # Jeśli klucz nie zawiera już kategorii na końcu, migruj
        if category and not parcel_id.endswith(f"_{category}"):
            new_key = f"{parcel_id}_{category}"
            new_parcels_data[new_key] = parcel_info
            migrated = True
            print(f"🔄 Migracja: '{parcel_id}' -> '{new_key}'")
        else:
            # Dane już w nowym formacie
            new_parcels_data[parcel_id] = parcel_info

    if migrated:
        parcels_data = new_parcels_data
        save_data_to_file()
        print(f"✅ Migracja zakończona - zaktualizowano format danych")

def load_data_from_file():
    """Wczytuje dane działek z pliku JSON."""
    global parcels_data

    try:
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            parcels_data = json.load(f)
        print(f"✅ Załadowano {len(parcels_data)} działek")

        # Automatyczna migracja do nowego formatu jeśli potrzeba
        migrate_data_to_new_format()
    except FileNotFoundError:
        parcels_data = {}
        print(f"⚠️  Brak pliku danych - utworzono nową bazę")
    except json.JSONDecodeError as e:
        parcels_data = {}
        print(f"❌ Błąd dekodowania JSON: {e}")

def save_data_to_file():
    """Zapisuje dane działek do pliku JSON."""
    try:
        with open(DATA_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(parcels_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Błąd zapisu: {e}")

# ==========================================================================
# ENDPOINTY API - OPERACJE CRUD
# ==========================================================================
@app.route("/api/parcels")
def get_parcels():
    """Zwraca wszystkie działki."""
    return jsonify(parcels_data)

@app.route("/api/parcel", methods=["POST"])
def add_parcel():
    """Dodaje nową działkę do systemu."""
    data = request.get_json()
    parcel_id = data.get("id")
    parcel_info = data.get("parcel")

    # Walidacja danych
    if not parcel_id or not parcel_info:
        return jsonify({"status": "error", "message": "Brak wymaganych danych"}), 400

    # Pobranie kategorii z danych działki
    category = parcel_info.get("kategoria", "")

    # Utworzenie pełnego klucza: numer_kategoria
    full_key = f"{parcel_id}_{category}"

    # Sprawdzenie duplikatu - sprawdzamy tylko dla tej samej kategorii
    if full_key in parcels_data:
        return jsonify({
            "status": "error",
            "message": f"Działka '{parcel_id}' typu '{category}' już istnieje"
        }), 409

    # Zapis nowej działki z pełnym kluczem
    parcels_data[full_key] = parcel_info
    save_data_to_file()

    return jsonify({
        "status": "success",
        "message": f"Dodano działkę '{parcel_id}' typu '{category}'",
        "full_key": full_key  # Zwracamy pełny klucz do front-endu
    })

@app.route("/api/parcel/<path:parcel_id>", methods=["PUT"])
def update_parcel_geometry(parcel_id):
    """Aktualizuje geometrię działki."""
    if parcel_id not in parcels_data:
        return jsonify({"status": "error", "message": "Działka nie istnieje"}), 404

    data = request.get_json()
    new_geometry = data.get("geometria")

    if not new_geometry:
        return jsonify({"status": "error", "message": "Brak geometrii"}), 400

    parcels_data[parcel_id]["geometria"] = new_geometry
    save_data_to_file()
    
    return jsonify({
        "status": "success",
        "message": f"Zaktualizowano geometrię '{parcel_id}'"
    })

@app.route("/api/parcel/<path:parcel_id>/category", methods=["PATCH"])
def update_parcel_category(parcel_id):
    """Zmienia kategorię działki."""
    global parcels_data

    if parcel_id not in parcels_data:
        return jsonify({"status": "error", "message": "Działka nie istnieje"}), 404

    data = request.get_json()
    new_category = data.get("kategoria")

    if not new_category:
        return jsonify({"status": "error", "message": "Brak kategorii"}), 400

    # Pobierz dane działki
    parcel_content = parcels_data[parcel_id]
    old_category = parcel_content.get("kategoria", "")

    # Jeśli kategoria się zmienia, trzeba zmienić klucz
    if old_category != new_category:
        # Wyciągnij numer z pełnego klucza
        last_underscore = parcel_id.rfind(f"_{old_category}")
        if last_underscore > 0:
            base_number = parcel_id[:last_underscore]
        else:
            base_number = parcel_id

        # Utwórz nowy klucz
        new_full_key = f"{base_number}_{new_category}"

        # Sprawdź czy nowy klucz już istnieje
        if new_full_key in parcels_data:
            return jsonify({
                "status": "error",
                "message": f"Działka '{base_number}' typu '{new_category}' już istnieje"
            }), 409

        # Zaktualizuj kategorię w danych
        parcel_content["kategoria"] = new_category

        # Przenieś działkę do nowego klucza zachowując kolejność
        items = list(parcels_data.items())
        try:
            index = next(i for i, (key, val) in enumerate(items) if key == parcel_id)
            parcels_data.pop(parcel_id)
            new_items = [(key, val) for key, val in items if key != parcel_id]
            new_items.insert(index, (new_full_key, parcel_content))
            parcels_data = dict(new_items)
        except StopIteration:
            parcels_data.pop(parcel_id)
            parcels_data[new_full_key] = parcel_content

        save_data_to_file()

        return jsonify({
            "status": "success",
            "message": f"Zmieniono kategorię na '{new_category}'",
            "full_key": new_full_key
        })
    else:
        # Kategoria się nie zmienia, nic nie rób
        return jsonify({
            "status": "success",
            "message": f"Kategoria pozostaje '{new_category}'"
        })

@app.route("/api/parcel/rename/<path:old_id>", methods=["PATCH"])
def rename_parcel(old_id):
    """Zmienia identyfikator działki zachowując pozycję."""
    global parcels_data

    if old_id not in parcels_data:
        return jsonify({
            "status": "error",
            "message": f"Działka '{old_id}' nie istnieje"
        }), 404

    data = request.get_json()
    new_id = data.get("new_id")

    if not new_id:
        return jsonify({"status": "error", "message": "Brak nowego ID"}), 400

    # Pobierz kategorię z istniejącej działki
    parcel_content = parcels_data[old_id]
    category = parcel_content.get("kategoria", "")

    # Utwórz pełny klucz dla nowego ID
    new_full_key = f"{new_id}_{category}"

    # Sprawdź czy nowy klucz już istnieje
    if new_full_key in parcels_data and new_full_key != old_id:
        return jsonify({
            "status": "error",
            "message": f"ID '{new_id}' typu '{category}' jest zajęte"
        }), 409

    # Zmiana ID z zachowaniem kolejności
    if old_id != new_full_key:
        items = list(parcels_data.items())
        try:
            index = next(i for i, (key, val) in enumerate(items) if key == old_id)
            parcels_data.pop(old_id)
            new_items = [(key, val) for key, val in items if key != old_id]
            new_items.insert(index, (new_full_key, parcel_content))
            parcels_data = dict(new_items)
        except StopIteration:
            parcels_data.pop(old_id)
            parcels_data[new_full_key] = parcel_content

    save_data_to_file()

    return jsonify({
        "status": "success",
        "message": f"Zmieniono ID z '{old_id}' na '{new_id}'",
        "full_key": new_full_key  # Zwracamy pełny klucz do front-endu
    })

@app.route("/api/parcels/delete_all", methods=["DELETE"])
def delete_all_parcels():
    """Usuwa wszystkie działki."""
    global parcels_data
    parcels_data.clear()
    save_data_to_file()
    
    return jsonify({
        "status": "success",
        "message": "Usunięto wszystkie obiekty"
    })

@app.route("/api/parcel/<path:parcel_id>", methods=["DELETE"])
def delete_parcel(parcel_id):
    """Usuwa pojedynczą działkę."""
    if parcel_id in parcels_data:
        del parcels_data[parcel_id]
        save_data_to_file()
        
        return jsonify({
            "status": "success", 
            "message": f"Usunięto działkę '{parcel_id}'"
        })
    
    return jsonify({"status": "error", "message": "Działka nie istnieje"}), 404

# ==========================================================================
# ROUTING INTERFEJSU
# ==========================================================================
@app.route("/")
def root():
    """Przekierowanie na główną stronę."""
    return redirect(url_for("index"))

@app.route("/template.html")
def index():
    """Renderuje interfejs edytora z konfiguracją mapy."""
    return render_template("template.html", map_config_data=map_config)

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    """Bezpieczne zamknięcie serwera."""
    threading.Thread(target=lambda: os._exit(0)).start()
    return jsonify({"status": "success"})

# ==========================================================================
# SYSTEM KOPII ZAPASOWYCH
# ==========================================================================
@app.route("/api/backups")
def get_backups():
    """Lista dostępnych kopii zapasowych."""
    if not os.path.exists(BACKUP_DIR):
        return jsonify([])
    
    files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.endswith(".json") and "backup" in f],
        reverse=True
    )
    
    return jsonify(files)

@app.route("/backup", methods=["POST"])
def backup_data():
    """Tworzy kopię zapasową z timestampem."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"parcels_data_backup_{timestamp}.json")
    
    save_data_to_file()
    shutil.copy2(DATA_FILE_PATH, backup_path)
    
    return jsonify({
        "status": "success",
        "message": f"Utworzono kopię: {os.path.basename(backup_path)}"
    })

@app.route("/restore", methods=["POST"])
def restore_data():
    """Przywraca dane z kopii."""
    filename = request.json.get("filename")
    
    if not filename:
        return jsonify({"status": "error", "message": "Brak nazwy pliku"}), 400
    
    source_path = os.path.join(BACKUP_DIR, filename)
    
    # Weryfikacja bezpieczeństwa
    if not (os.path.isfile(source_path) and source_path.startswith(BACKUP_DIR)):
        return jsonify({"status": "error", "message": "Plik nie istnieje"}), 404
    
    shutil.copy2(source_path, DATA_FILE_PATH)
    load_data_from_file()
    
    return jsonify({
        "status": "success", 
        "message": f"Przywrócono z '{filename}'"
    })

@app.route("/delete_backup", methods=["POST"])
def delete_backup():
    """Usuwa kopię zapasową."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename")

    if not filename:
        return jsonify({"status": "error", "message": "Brak nazwy pliku"}), 400

    # Walidacja nazwy
    if not filename.endswith(".json") or "backup" not in filename:
        return jsonify({"status": "error", "message": "Nieprawidłowa nazwa"}), 400

    file_path = os.path.join(BACKUP_DIR, filename)

    # Ochrona przed path traversal
    if not (os.path.isfile(file_path) and 
            os.path.abspath(file_path).startswith(os.path.abspath(BACKUP_DIR))):
        return jsonify({"status": "error", "message": "Plik nie istnieje"}), 404

    try:
        os.remove(file_path)
        return jsonify({
            "status": "success", 
            "message": f"Usunięto '{filename}'"
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Błąd usuwania: {e}"
        }), 500

# ==========================================================================
# PUNKT STARTOWY APLIKACJI
# ==========================================================================
if __name__ == "__main__":
    # Inicjalizacja przy starcie
    load_data_from_file()
    load_map_config_from_file()
    
    # Konfiguracja serwera
    port = 5003
    url = f"http://127.0.0.1:{port}/template.html"
    
    # Auto-otwarcie przeglądarki po 1.25s
    threading.Timer(1.25, lambda: webbrowser.open(url)).start()
    
    print("=" * 50)
    print(f"🚀 Edytor Mapy Katastralnej")
    print(f"📍 Adres: {url}")
    print("=" * 50)
    
    # Uruchomienie serwera
    app.run(port=port, debug=False, use_reloader=False)