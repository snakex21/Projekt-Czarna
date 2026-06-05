"""Pomocnicza logika plików kopii zapasowych launchera.

Moduł zawiera operacje bez UI: listowanie, import/eksport i usuwanie plików
backupów. Okna dialogowe i komunikaty zostają w ``launcher_app.py``.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import psycopg2

from launcher.config.paths import BACKUP_FOLDER, BASE_DIR, PROTOKOLY_FOLDER
from launcher.utils import get_data_files, get_db_config_from_env


def backup_path(filename: str) -> Path:
    """Zwraca pełną ścieżkę pliku backupu w katalogu danych miejscowości."""
    return BACKUP_FOLDER / filename


def list_backup_files() -> list[str]:
    """Zwraca listę plików backupu obsługiwanych przez menedżer kopii."""
    try:
        files = [
            f for f in os.listdir(BACKUP_FOLDER)
            if f.startswith("backup_") and f.endswith(".zip")
        ]
        old_backups = [
            f for f in os.listdir(BACKUP_FOLDER)
            if f.startswith("pelny_backup_projektu_") and f.endswith(".zip")
        ]
        files.extend(old_backups)
        files.sort(reverse=True)
        return files
    except FileNotFoundError:
        return []


def export_backup_file(filename: str, destination_path: str | os.PathLike[str]) -> None:
    """Kopiuje backup z katalogu projektu do wskazanej lokalizacji."""
    shutil.copy2(backup_path(filename), destination_path)


def import_backup_file(source_path: str | os.PathLike[str]) -> str:
    """Kopiuje backup z zewnętrznej lokalizacji do katalogu backupów.

    Zwraca nazwę docelowego pliku.
    """
    filename = os.path.basename(source_path)
    shutil.copy2(source_path, backup_path(filename))
    return filename


def delete_backup_file(filename: str) -> None:
    """Usuwa plik backupu z katalogu backupów."""
    os.remove(backup_path(filename))


def build_backup_package(location_choice: str, backup_flags: dict[str, bool], get_active_location, get_all_locations):
    """Buduje listę plików do zapakowania w backup.

    Zwraca: (backup_filename, locations_to_backup, files_to_zip, temp_json_paths)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    locations_to_backup = []
    if location_choice == "Aktywna miejscowość":
        active_loc = get_active_location()
        if active_loc:
            locations_to_backup = [active_loc[1]]
        backup_filename = f"backup_{timestamp}.zip"
    elif location_choice == "Wszystkie miejscowości":
        all_locs = get_all_locations()
        locations_to_backup = [loc[1] for loc in all_locs]
        backup_filename = f"backup_wszystkie_{timestamp}.zip"
    else:
        locations_to_backup = [location_choice]
        backup_filename = f"backup_{location_choice}_{timestamp}.zip"

    if not locations_to_backup:
        raise Exception("Brak miejscowości do skopiowania")

    files_to_zip: list[tuple[str, str]] = []
    temp_json_paths: list[str] = []
    global_scans_added = False

    for location_name in locations_to_backup:
        location_folder = BACKUP_FOLDER / location_name
        if not location_folder.exists():
            continue

        env_path = location_folder / ".env"
        if env_path.exists():
            files_to_zip.append((str(env_path), os.path.join(location_name, ".env")))

        data_files_for_location = get_data_files(location_name)

        if backup_flags.get("config"):
            map_config_path = location_folder / "map_config.json"
            if map_config_path.exists():
                files_to_zip.append((str(map_config_path), os.path.join(location_name, "map_config.json")))

        if backup_flags.get("map_image"):
            for filename in os.listdir(location_folder):
                file_path = location_folder / filename
                if filename.lower().startswith("mapa.") and file_path.is_file():
                    files_to_zip.append((str(file_path), os.path.join(location_name, filename)))

        for key in ["owners", "parcels", "genealogy"]:
            if backup_flags.get(key):
                file_path = data_files_for_location[key]["path"]
                if os.path.exists(file_path):
                    files_to_zip.append((file_path, os.path.join(location_name, os.path.basename(file_path))))
                for related_path in data_files_for_location[key].get("related", []):
                    if os.path.exists(related_path):
                        files_to_zip.append((related_path, os.path.join(location_name, os.path.basename(related_path))))

        if backup_flags.get("history_photos"):
            history_dir = location_folder / "history_photos"
            if history_dir.exists():
                for root, _, files in os.walk(history_dir):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(file_path, location_folder)
                        files_to_zip.append((file_path, os.path.join(location_name, rel_path)))

        if backup_flags.get("scans"):
            local_protokoly = location_folder / "protokoly"
            if local_protokoly.exists():
                for root, _, files in os.walk(local_protokoly):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(file_path, location_folder)
                        files_to_zip.append((file_path, os.path.join(location_name, rel_path)))
            elif not global_scans_added and PROTOKOLY_FOLDER.exists():
                legacy_protokoly = PROTOKOLY_FOLDER
                for root, _, files in os.walk(legacy_protokoly):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        arcname = os.path.relpath(file_path, BASE_DIR)
                        files_to_zip.append((file_path, arcname))
                global_scans_added = True

        if backup_flags.get("custom_icons"):
            for ext in [".png", ".ico", ".jpg", ".jpeg", ".svg"]:
                icon_path = location_folder / f"custom_icon{ext}"
                if icon_path.exists():
                    files_to_zip.append((str(icon_path), os.path.join(location_name, f"custom_icon{ext}")))

        if backup_flags.get("favicon"):
            for ext in [".ico", ".png", ".jpg", ".jpeg", ".svg"]:
                favicon_path = location_folder / f"favicon{ext}"
                if favicon_path.exists():
                    files_to_zip.append((str(favicon_path), os.path.join(location_name, f"favicon{ext}")))

    if backup_flags.get("scans") and not global_scans_added:
        legacy_protokoly = PROTOKOLY_FOLDER
        if legacy_protokoly.exists():
            for root, _, files in os.walk(legacy_protokoly):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, BASE_DIR)
                    files_to_zip.append((file_path, arcname))

    if backup_flags.get("launcher_db"):
        try:
            db_cfg = get_db_config_from_env()
            launcher_db_cfg = db_cfg.copy()
            launcher_db_cfg['dbname'] = 'mapa_launcher_db'
            launcher_db_cfg['client_encoding'] = 'UTF8'

            with psycopg2.connect(**launcher_db_cfg) as conn, conn.cursor() as cur:
                for location_name in locations_to_backup:
                    cur.execute("""
                        SELECT id, name, full_name, powiat, region, active,
                               homepage_template, year, century, homepage_description,
                               history_paragraph1, history_paragraph2, history_paragraph3,
                               postgres_db_name, created_at, updated_at
                        FROM locations
                        WHERE name = %s
                    """, (location_name,))

                    location_row = cur.fetchone()
                    if not location_row:
                        continue

                    location_data = {
                        "id": location_row[0],
                        "name": location_row[1],
                        "full_name": location_row[2],
                        "powiat": location_row[3],
                        "region": location_row[4],
                        "active": location_row[5],
                        "homepage_template": location_row[6],
                        "year": location_row[7],
                        "century": location_row[8],
                        "homepage_description": location_row[9],
                        "history_paragraph1": location_row[10],
                        "history_paragraph2": location_row[11],
                        "history_paragraph3": location_row[12],
                        "postgres_db_name": location_row[13],
                        "created_at": str(location_row[14]) if location_row[14] else None,
                        "updated_at": str(location_row[15]) if location_row[15] else None,
                    }

                    cur.execute("""
                        SELECT id, filename, caption, order_index, created_at
                        FROM history_photos
                        WHERE location_id = %s
                        ORDER BY order_index
                    """, (location_row[0],))

                    photos = []
                    for photo_row in cur.fetchall():
                        photos.append({
                            "id": photo_row[0],
                            "filename": photo_row[1],
                            "caption": photo_row[2],
                            "order_index": photo_row[3],
                            "created_at": str(photo_row[4]) if photo_row[4] else None,
                        })
                    location_data["history_photos"] = photos

                    temp_json_path = BACKUP_FOLDER / f"_temp_launcher_db_{location_name}.json"
                    with open(temp_json_path, "w", encoding="utf-8") as f:
                        json.dump(location_data, f, ensure_ascii=False, indent=2)

                    temp_json_paths.append(str(temp_json_path))
                    files_to_zip.append((str(temp_json_path), os.path.join(location_name, "launcher_db_config.json")))
        except Exception as e:
            print(f"⚠️ Nie udało się wyeksportować danych z bazy launcher: {e}")

    return backup_filename, locations_to_backup, files_to_zip, temp_json_paths


def cleanup_temp_backup_files(temp_json_paths: list[str]) -> None:
    """Usuwa tymczasowe JSON-y utworzone na potrzeby backupu."""
    for temp_json_path in temp_json_paths:
        if os.path.exists(temp_json_path):
            try:
                os.remove(temp_json_path)
            except Exception:
                pass


def write_backup_archive(backup_path_value: str | os.PathLike[str], files_to_zip: list[tuple[str, str]], progress_callback) -> None:
    """Pakuje przygotowane pliki do archiwum ZIP."""
    with zipfile.ZipFile(backup_path_value, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (file_path, arcname) in enumerate(files_to_zip):
            progress_callback(i + 1, len(files_to_zip), f"Pakowanie: {os.path.basename(arcname)}")
            zf.write(file_path, arcname)


def restore_backup_archive(filename: str, get_active_location_name, data_files: dict) -> list[str]:
    """Przywraca pliki z backupu i zwraca listę przywróconych miejscowości."""
    restored_locations: list[str] = []

    with zipfile.ZipFile(backup_path(filename), "r") as zf:
        archive_contents = zf.namelist()
        has_location_folders = any('/' in f and not f.startswith('assets/') for f in archive_contents)

        scan_files = [f for f in archive_contents if f.startswith("assets/protokoly/")]
        if scan_files:
            if PROTOKOLY_FOLDER.exists():
                shutil.rmtree(PROTOKOLY_FOLDER)
            for file_info in zf.infolist():
                if file_info.filename.startswith("assets/protokoly/"):
                    zf.extract(file_info, path=BASE_DIR)

        if has_location_folders:
            for file_info in zf.infolist():
                if not file_info.filename.startswith('assets/'):
                    zf.extract(file_info, path=BACKUP_FOLDER)

            launcher_db_files = [f for f in archive_contents if f.endswith('launcher_db_config.json')]
            if launcher_db_files:
                try:
                    db_cfg = get_db_config_from_env()
                    launcher_db_cfg = db_cfg.copy()
                    launcher_db_cfg['dbname'] = 'mapa_launcher_db'
                    launcher_db_cfg['client_encoding'] = 'UTF8'

                    with psycopg2.connect(**launcher_db_cfg) as conn, conn.cursor() as cur:
                        for launcher_file in launcher_db_files:
                            with zf.open(launcher_file) as json_file:
                                location_data = json.load(json_file)

                            cur.execute("SELECT id FROM locations WHERE name = %s", (location_data['name'],))
                            existing = cur.fetchone()

                            if existing:
                                location_id = existing[0]
                                cur.execute("""
                                    UPDATE locations SET
                                        full_name = %s,
                                        powiat = %s,
                                        region = %s,
                                        homepage_template = %s,
                                        year = %s,
                                        century = %s,
                                        homepage_description = %s,
                                        history_paragraph1 = %s,
                                        history_paragraph2 = %s,
                                        history_paragraph3 = %s,
                                        postgres_db_name = %s
                                    WHERE id = %s
                                """, (
                                    location_data.get('full_name'),
                                    location_data.get('powiat'),
                                    location_data.get('region'),
                                    location_data.get('homepage_template'),
                                    location_data.get('year'),
                                    location_data.get('century'),
                                    location_data.get('homepage_description'),
                                    location_data.get('history_paragraph1'),
                                    location_data.get('history_paragraph2'),
                                    location_data.get('history_paragraph3'),
                                    location_data.get('postgres_db_name'),
                                    location_id,
                                ))
                            else:
                                cur.execute("""
                                    INSERT INTO locations (
                                        name, full_name, powiat, region,
                                        homepage_template, year, century, homepage_description,
                                        history_paragraph1, history_paragraph2, history_paragraph3,
                                        postgres_db_name
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    RETURNING id
                                """, (
                                    location_data['name'],
                                    location_data.get('full_name'),
                                    location_data.get('powiat'),
                                    location_data.get('region'),
                                    location_data.get('homepage_template'),
                                    location_data.get('year'),
                                    location_data.get('century'),
                                    location_data.get('homepage_description'),
                                    location_data.get('history_paragraph1'),
                                    location_data.get('history_paragraph2'),
                                    location_data.get('history_paragraph3'),
                                    location_data.get('postgres_db_name'),
                                ))
                                location_id = cur.fetchone()[0]

                            cur.execute("DELETE FROM history_photos WHERE location_id = %s", (location_id,))
                            for photo in location_data.get('history_photos', []):
                                cur.execute("""
                                    INSERT INTO history_photos (location_id, filename, caption, order_index)
                                    VALUES (%s, %s, %s, %s)
                                """, (
                                    location_id,
                                    photo['filename'],
                                    photo.get('caption'),
                                    photo.get('order_index', 0),
                                ))

                        conn.commit()
                        print(f"✅ Przywrócono dane launcher dla {len(launcher_db_files)} miejscowości")

                        for launcher_file in launcher_db_files:
                            with zf.open(launcher_file) as json_file:
                                location_data = json.load(json_file)
                            restored_locations.append(location_data['name'])

                except Exception as e:
                    print(f"⚠️ Nie udało się przywrócić danych z bazy launcher: {e}")

            if not launcher_db_files and has_location_folders:
                location_folders = set()
                for archive_name in archive_contents:
                    if '/' in archive_name and not archive_name.startswith('assets/'):
                        location_name = archive_name.split('/')[0]
                        if location_name:
                            location_folders.add(location_name)
                restored_locations.extend(list(location_folders))
        else:
            active_location_name = get_active_location_name()
            if active_location_name:
                target_folder = BACKUP_FOLDER / active_location_name
                restored_locations.append(active_location_name)
            else:
                target_folder = BACKUP_FOLDER

            if "map_config.json" in archive_contents:
                zf.extract("map_config.json", path=target_folder)

            for key in ["owners", "parcels", "genealogy"]:
                json_filename = os.path.basename(data_files[key]["path"])
                if json_filename in archive_contents:
                    zf.extract(json_filename, path=target_folder)

                for related_path in data_files[key].get("related", []):
                    related_filename = os.path.basename(related_path)
                    if related_filename in archive_contents:
                        zf.extract(related_filename, path=target_folder)

    return restored_locations
