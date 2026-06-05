"""Testy jednostkowe serwisu ``launcher.services.pg_portable_service``.

Wszystkie testy są w pełni mockowane -- nie wymagają dostępu do sieci,
działającego PostgreSQL ani żadnych zapisów poza ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import io
import platform as platform_module
import tarfile
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from launcher.services import pg_portable_service as service
from launcher.services.pg_portable_service import (
    DEFAULT_PG_VERSION,
    DEFAULT_POSTGIS_VERSION,
    PG_DOWNLOAD_URLS,
    POSTGIS_DOWNLOAD_URLS,
    PortablePgPaths,
    copy_to_cache,
    detect_system_pg,
    download_pg_binary,
    download_pg_binary_with_cache,
    download_pg_binary_with_fallbacks,
    extract_pg_archive,
    get_cache_dir,
    get_pg_download_url,
    get_pg_install_dir,
    get_portable_pg_paths,
    get_postgis_download_url,
    has_postgis_extension_files,
    install_postgis_to_extension_dir,
    is_cache_file_valid,
    is_pg_initialized,
    portable_pg_installed,
    verify_pg_archive_checksum,
)


# ---------------------------------------------------------------------------
# detect_system_pg
# ---------------------------------------------------------------------------


def test_detect_system_pg_finds_in_path(monkeypatch):
    """``detect_system_pg`` zwraca ścieżkę z PATH gdy ``shutil.which`` ją znajdzie."""
    monkeypatch.setattr(service.shutil, "which", lambda name: "/usr/bin/pg_ctl" if name == "pg_ctl" else None)
    result = detect_system_pg()
    assert result == Path("/usr/bin/pg_ctl")


def test_detect_system_pg_finds_in_windows_standard_path(monkeypatch):
    """Na Windows szuka w C:/Program Files/PostgreSQL/ gdy brak w PATH."""
    monkeypatch.setattr(service.shutil, "which", lambda name: None)
    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service.Path, "exists", lambda self: True)

    result = detect_system_pg()

    assert result is not None
    assert "PostgreSQL" in str(result)
    assert str(result).lower().endswith("pg_ctl.exe")


def test_detect_system_pg_finds_in_linux_postgres_lib(monkeypatch, tmp_path):
    """Na Linux szuka w ``LINUX_POSTGRES_LIB_ROOT/*/bin/pg_ctl``."""
    monkeypatch.setattr(service.shutil, "which", lambda name: None)
    monkeypatch.setattr(service.platform, "system", lambda: "Linux")

    pg_root = tmp_path / "postgresql"
    version_dir = pg_root / "16"
    bin_dir = version_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pg_ctl").write_bytes(b"")

    monkeypatch.setattr(service, "LINUX_POSTGRES_LIB_ROOT", pg_root)

    result = detect_system_pg()
    assert result == version_dir / "bin" / "pg_ctl"


def test_detect_system_pg_returns_none_when_not_found(monkeypatch):
    """``None`` gdy brak ``pg_ctl`` w żadnej lokalizacji."""
    monkeypatch.setattr(service.shutil, "which", lambda name: None)
    monkeypatch.setattr(service.Path, "exists", lambda self: False)

    result = detect_system_pg()
    assert result is None


# ---------------------------------------------------------------------------
# get_pg_download_url
# ---------------------------------------------------------------------------


def test_get_pg_download_url_returns_url_for_windows(monkeypatch):
    """Zwraca URL Windows gdy platform=Windows."""
    monkeypatch.setattr(platform_module, "system", lambda: "Windows")
    monkeypatch.setattr(platform_module, "machine", lambda: "AMD64")
    url = get_pg_download_url()
    assert url.startswith("https://")
    assert "windows" in url.lower() or "win" in url.lower()


def test_get_pg_download_url_returns_url_for_linux(monkeypatch):
    """Zwraca URL Linux gdy platform=Linux."""
    monkeypatch.setattr(platform_module, "system", lambda: "Linux")
    monkeypatch.setattr(platform_module, "machine", lambda: "x86_64")
    url = get_pg_download_url()
    assert url.startswith("https://")
    assert "linux" in url.lower()


def test_get_pg_download_url_returns_url_for_macos(monkeypatch):
    """Zwraca URL macOS gdy platform=Darwin."""
    monkeypatch.setattr(platform_module, "system", lambda: "Darwin")
    monkeypatch.setattr(platform_module, "machine", lambda: "x86_64")
    url = get_pg_download_url()
    assert url.startswith("https://")


def test_get_pg_download_url_raises_for_unsupported_platform(monkeypatch):
    """``RuntimeError`` gdy brak URL dla platformy."""
    monkeypatch.setattr(platform_module, "system", lambda: "Plan9")
    monkeypatch.setattr(platform_module, "machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Plan9"):
        get_pg_download_url()


# ---------------------------------------------------------------------------
# get_pg_install_dir (od 1.1.2: <root>/.runtime/postgres/)
# ---------------------------------------------------------------------------


def test_get_pg_install_dir_returns_project_root_postgres(monkeypatch):
    """Od 1.1.2 portable PG instaluje się w ``<project_root>/.runtime/postgres/``.

    Weryfikacja: katalog musi być względny wobec ``_find_project_root()``
    i znajdować się pod ukrytym katalogiem ``.runtime/postgres`` (bez
    ``MapaCzarna`` w ścieżce, bo to NIE jest w AppData).
    """
    result = get_pg_install_dir()
    root = service._find_project_root()
    assert result == root / ".runtime" / "postgres"
    assert "postgres" in str(result)
    assert ".runtime" in str(result)
    assert "MapaCzarna" not in str(result)  # nie w AppData
    assert "AppData" not in str(result)  # nie w AppData
    assert "Library" not in str(result)  # nie w macOS app support


def test_get_pg_install_dir_is_consistent_across_platforms(monkeypatch):
    """Ścieżka jest jednakowa niezależnie od platformy (od 1.1.2)."""
    for plat in ("Windows", "Linux", "Darwin", "Plan9"):
        monkeypatch.setattr(platform_module, "system", lambda p=plat: p)
        result = get_pg_install_dir()
        root = service._find_project_root()
        assert result == root / ".runtime" / "postgres", f"FAIL dla platformy {plat}"


def test_find_project_root_finds_marker_files():
    """``_find_project_root()`` znajduje root po markerach."""
    root = service._find_project_root()
    # Sprawdź że któryś z markerów istnieje.
    has_marker = (
        (root / "launcher" / "launcher_app.py").exists()
        or (root / "requirements.txt").exists()
    )
    assert has_marker, f"Root {root} nie zawiera żadnego markera"


def test_find_project_root_raises_when_no_marker(tmp_path, monkeypatch):
    """Gdy brak markerów — RuntimeError z jasnym komunikatem."""
    # Stwórz sztuczny plik pg_portable_service.py w katalogu bez markerów
    # i sprawdź że _find_project_root rzuca.
    fake_file = tmp_path / "weird" / "path" / "pg_portable_service.py"
    fake_file.parent.mkdir(parents=True)
    fake_file.write_text("# placeholder")
    monkeypatch.setattr(service, "__file__", str(fake_file))
    with pytest.raises(RuntimeError, match="Nie można zlokalizować"):
        service._find_project_root()


# ---------------------------------------------------------------------------
# download_pg_binary
# ---------------------------------------------------------------------------


def _fake_response(chunks: list[bytes], content_length: str | None = "0"):
    """Buduje mock context-managera zachowującego się jak HTTPResponse."""
    response = MagicMock()
    response.read.side_effect = list(chunks) + [b""]
    response.headers.get.return_value = content_length
    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *args: None
    return response


def test_download_pg_binary_succeeds(monkeypatch, tmp_path):
    """Pobiera plik i zwraca ścieżkę (mock HTTP)."""
    fake = _fake_response([b"a" * 100, b"b" * 100], content_length="200")
    monkeypatch.setattr(service.urllib.request, "urlopen", lambda url, timeout=60: fake)

    result = download_pg_binary("https://example.com/pg.zip", tmp_path)
    assert result.exists()
    assert result.read_bytes() == b"a" * 100 + b"b" * 100
    assert result.name == "pg.zip"


def test_download_pg_binary_atomic_rename_cleans_tmp(monkeypatch, tmp_path):
    """Po pobraniu nie zostaje plik ``.tmp`` w katalogu."""
    fake = _fake_response([b"data" * 10], content_length="40")
    monkeypatch.setattr(service.urllib.request, "urlopen", lambda url, timeout=60: fake)

    result = download_pg_binary("https://example.com/postgres.zip", tmp_path)
    assert result.exists()
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_download_pg_binary_invokes_progress_callback(monkeypatch, tmp_path):
    """Progress callback jest wołany z (downloaded, total)."""
    fake = _fake_response([b"x" * 50, b"x" * 50], content_length="100")
    monkeypatch.setattr(service.urllib.request, "urlopen", lambda url, timeout=60: fake)

    calls: list[tuple[int, int]] = []
    download_pg_binary(
        "https://example.com/pg.zip",
        tmp_path,
        progress_callback=lambda downloaded, total: calls.append((downloaded, total)),
    )
    assert len(calls) >= 2
    # Końcowe wywołanie powinno odpowiadać pobranemu rozmiarowi.
    final_downloaded, final_total = calls[-1]
    assert final_downloaded == 100
    assert final_total == 100


def test_download_pg_binary_retries_on_failure(monkeypatch, tmp_path):
    """Retry przy błędach sieciowych -- sukces po 2 nieudanych próbach."""
    success_response = _fake_response([b"data"], content_length="4")

    call_count = {"n": 0}

    def fake_urlopen(url, timeout=60):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise urllib.error.URLError("network error")
        return success_response

    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)

    result = download_pg_binary("https://example.com/pg.zip", tmp_path, max_retries=3)
    assert call_count["n"] == 3
    assert result.exists()
    assert result.read_bytes() == b"data"


def test_download_pg_binary_raises_after_max_retries(monkeypatch, tmp_path):
    """``RuntimeError`` gdy wszystkie próby zawiodą."""
    def always_fail(url, timeout=60):
        raise urllib.error.URLError("permanent network error")

    monkeypatch.setattr(service.urllib.request, "urlopen", always_fail)
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="Nie udało się pobrać"):
        download_pg_binary("https://example.com/pg.zip", tmp_path, max_retries=2)
    # Po niepowodzeniu nie powinno zostać ani pełnego pliku, ani .tmp.
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# extract_pg_archive
# ---------------------------------------------------------------------------


def test_extract_pg_archive_zip(tmp_path):
    """``extract_pg_archive`` rozpakowuje .zip i zwraca katalog bin."""
    archive = tmp_path / "test.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pgsql/bin/pg_ctl.exe", "fake binary")
        zf.writestr("pgsql/bin/initdb.exe", "fake initdb")
        zf.writestr("pgsql/share/postgresql.conf", "fake conf")

    target = tmp_path / "extracted"
    result = extract_pg_archive(archive, target)

    assert result == target / "pgsql" / "bin"
    assert (target / "pgsql" / "bin" / "pg_ctl.exe").exists()
    assert (target / "pgsql" / "bin" / "initdb.exe").exists()
    assert (target / "pgsql" / "share" / "postgresql.conf").exists()


def test_extract_pg_archive_tar_gz(tmp_path):
    """``extract_pg_archive`` rozpakowuje .tar.gz i zwraca katalog bin."""
    archive = tmp_path / "test.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name="pgsql/bin/pg_ctl")
        data = b"fake"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
        info2 = tarfile.TarInfo(name="pgsql/bin/initdb")
        info2.size = len(data)
        tf.addfile(info2, io.BytesIO(data))

    target = tmp_path / "extracted"
    result = extract_pg_archive(archive, target)

    assert result == target / "pgsql" / "bin"
    assert (target / "pgsql" / "bin" / "pg_ctl").exists()
    assert (target / "pgsql" / "bin" / "initdb").exists()


def test_extract_pg_archive_invokes_progress_callback(tmp_path):
    """Callback jest wywoływany z komunikatami o postępie."""
    archive = tmp_path / "test.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("pgsql/bin/pg_ctl.exe", "x")

    calls: list[str] = []
    extract_pg_archive(archive, tmp_path / "out", progress_callback=lambda msg: calls.append(msg))
    assert any("Rozpakowuję" in msg for msg in calls)
    assert any("rozpakowane" in msg for msg in calls)


def test_extract_pg_archive_raises_for_unknown_format(tmp_path):
    """``RuntimeError`` dla nieznanego rozszerzenia archiwum."""
    archive = tmp_path / "test.rar"
    archive.write_bytes(b"fake")
    with pytest.raises(RuntimeError, match=r"rar|rozszerzenie|Nieobsługiwane"):
        extract_pg_archive(archive, tmp_path / "out")


def test_extract_pg_archive_raises_when_bin_dir_missing(tmp_path):
    """``RuntimeError`` gdy po rozpakowaniu brak katalogu ``pgsql/bin``."""
    archive = tmp_path / "test.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("README.txt", "no bin here")

    with pytest.raises(RuntimeError, match="bin"):
        extract_pg_archive(archive, tmp_path / "out")


# ---------------------------------------------------------------------------
# is_pg_initialized
# ---------------------------------------------------------------------------


def test_is_pg_initialized_true_when_version_file_exists(tmp_path):
    """``True`` gdy ``PG_VERSION`` istnieje."""
    (tmp_path / "PG_VERSION").write_text("16.4\n", encoding="utf-8")
    assert is_pg_initialized(tmp_path) is True


def test_is_pg_initialized_false_when_version_file_missing(tmp_path):
    """``False`` gdy brak ``PG_VERSION``."""
    assert is_pg_initialized(tmp_path) is False


def test_is_pg_initialized_false_for_empty_path():
    """``False`` dla pustej ścieżki (zabezpieczenie)."""
    assert is_pg_initialized(Path("")) is False


# ---------------------------------------------------------------------------
# get_portable_pg_paths / portable_pg_installed
# ---------------------------------------------------------------------------


def test_get_portable_pg_paths_constructs_paths():
    """Buduje ścieżki na podstawie install_dir (Windows-style w teście)."""
    install = Path("C:/Users/Test/AppData/Local/MapaCzarna/postgres")
    paths = get_portable_pg_paths(install)
    assert paths.root_dir == install
    assert paths.bin_dir == install / "pgsql" / "bin"
    assert paths.data_dir == install / "data"
    assert paths.pg_ctl_path.parent == install / "pgsql" / "bin"
    assert paths.initdb_path.parent == install / "pgsql" / "bin"
    assert paths.pg_ctl_path.name in ("pg_ctl.exe", "pg_ctl")
    assert paths.pg_version == DEFAULT_PG_VERSION


def test_get_portable_pg_paths_uses_default_install_dir(monkeypatch, tmp_path):
    """Gdy ``install_dir`` jest ``None`` używa ``get_pg_install_dir``."""
    monkeypatch.setattr(service, "get_pg_install_dir", lambda: tmp_path / "postgres")
    paths = get_portable_pg_paths()
    assert paths.root_dir == tmp_path / "postgres"
    assert paths.bin_dir == tmp_path / "postgres" / "pgsql" / "bin"


def test_portable_pg_installed_returns_true_when_pg_ctl_exists(monkeypatch, tmp_path):
    """``True`` gdy ``pg_ctl`` istnieje w domyślnej lokalizacji."""
    install_dir = tmp_path / "postgres"
    bin_dir = install_dir / "pgsql" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pg_ctl.exe").write_bytes(b"")
    monkeypatch.setattr(service, "get_pg_install_dir", lambda: install_dir)
    assert portable_pg_installed() is True


def test_portable_pg_installed_returns_false_when_missing(monkeypatch, tmp_path):
    """``False`` gdy brak ``pg_ctl`` w domyślnej lokalizacji."""
    install_dir = tmp_path / "postgres"
    install_dir.mkdir()
    monkeypatch.setattr(service, "get_pg_install_dir", lambda: install_dir)
    assert portable_pg_installed() is False


def test_portable_pg_installed_with_explicit_install_dir(tmp_path):
    """``portable_pg_installed(install_dir=...)`` działa bez monkeypatch."""
    install_dir = tmp_path / "postgres"
    bin_dir = install_dir / "pgsql" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pg_ctl.exe").write_bytes(b"")
    assert portable_pg_installed(install_dir) is True


# ---------------------------------------------------------------------------
# verify_pg_archive_checksum
# ---------------------------------------------------------------------------


def test_verify_pg_archive_checksum_match(tmp_path):
    """``True`` gdy SHA256 się zgadza."""
    archive = tmp_path / "test.zip"
    data = b"test data content"
    archive.write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    assert verify_pg_archive_checksum(archive, expected) is True


def test_verify_pg_archive_checksum_mismatch(tmp_path):
    """``False`` gdy SHA256 się nie zgadza."""
    archive = tmp_path / "test.zip"
    archive.write_bytes(b"test data content")
    assert verify_pg_archive_checksum(archive, "0" * 64) is False


def test_verify_pg_archive_checksum_missing_file(tmp_path):
    """``False`` gdy plik nie istnieje."""
    assert verify_pg_archive_checksum(tmp_path / "nope.zip", "abc") is False


def test_verify_pg_archive_checksum_empty_expected_returns_false(tmp_path):
    """``False`` gdy oczekiwany hash jest pusty."""
    archive = tmp_path / "test.zip"
    archive.write_bytes(b"x")
    assert verify_pg_archive_checksum(archive, "") is False
    assert verify_pg_archive_checksum(archive, "   ") is False


# ---------------------------------------------------------------------------
# Stałe modułu
# ---------------------------------------------------------------------------


def test_default_pg_version_is_set():
    """``DEFAULT_PG_VERSION`` jest zdefiniowany i ma format X.Y."""
    assert DEFAULT_PG_VERSION
    parts = DEFAULT_PG_VERSION.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts)


def test_pg_download_urls_contains_all_supported_platforms():
    """``PG_DOWNLOAD_URLS`` ma wpisy dla Windows, Linux, macOS."""
    keys = set(PG_DOWNLOAD_URLS.keys())
    assert ("Windows", "AMD64") in keys
    assert ("Linux", "x86_64") in keys
    assert ("Darwin", "x86_64") in keys
    for urls in PG_DOWNLOAD_URLS.values():
        assert urls, "każda platforma musi mieć co najmniej jeden URL"
        assert all(u.startswith("https://") for u in urls)


# ---------------------------------------------------------------------------
# uninstall_portable_pg (1.1.1)
# ---------------------------------------------------------------------------


def test_uninstall_portable_pg_removes_directory(tmp_path):
    """Usuwa katalog portable PG (binaria + dane)."""
    install_dir = tmp_path / "postgres"
    pgsql = install_dir / "pgsql" / "bin"
    pgsql.mkdir(parents=True)
    (pgsql / "pg_ctl").write_bytes(b"")
    (install_dir / "data" / "postgresql.conf").parent.mkdir(parents=True)
    (install_dir / "data" / "postgresql.conf").write_text("# pg config")

    result = service.uninstall_portable_pg(install_dir=install_dir, stop_server=False)

    assert result.success is True
    assert result.install_dir == install_dir.resolve()
    assert result.removed_files > 0
    assert result.error is None
    assert not install_dir.exists()


def test_uninstall_portable_pg_returns_success_when_already_removed(tmp_path):
    """Gdy katalog nie istnieje — zwraca success=True z 0 plikami."""
    install_dir = tmp_path / "postgres_does_not_exist"

    result = service.uninstall_portable_pg(install_dir=install_dir, stop_server=False)

    assert result.success is True
    assert result.removed_files == 0
    assert result.error is None


def test_uninstall_portable_pg_refuses_non_pg_directory(tmp_path):
    """Safety check: odmawia usunięcia katalogu bez podkatalogu ``pgsql/``."""
    not_pg = tmp_path / "important_data"
    not_pg.mkdir()
    (not_pg / "userfile.txt").write_text("DO NOT DELETE")

    result = service.uninstall_portable_pg(install_dir=not_pg, stop_server=False)

    assert result.success is False
    assert "safety check" in (result.error or "").lower() or "pgsql" in (result.error or "")
    # Plik nie został usunięty.
    assert (not_pg / "userfile.txt").exists()


def test_uninstall_portable_pg_stops_running_server(tmp_path, monkeypatch):
    """Gdy serwer działa, próbuje go zatrzymać przed usunięciem."""
    install_dir = tmp_path / "postgres"
    pgsql_bin = install_dir / "pgsql" / "bin"
    pgsql_bin.mkdir(parents=True)

    pg_ctl_name = "pg_ctl.exe" if platform_module.system() == "Windows" else "pg_ctl"
    pg_ctl = pgsql_bin / pg_ctl_name
    pg_ctl.write_bytes(b"")
    (install_dir / "data").mkdir(parents=True)

    # Mockuj subprocess: status zwraca 0 (działa), stop zwraca 0.
    class MockRun:
        returncode = 0
        stdout = "pg_ctl: server is running"
        stderr = ""

    calls = []

    def mock_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if "status" in cmd:
            return MockRun()
        if "stop" in cmd:
            return MockRun()
        return MockRun()

    # Patchuj subprocess w module service.
    import subprocess as sp
    monkeypatch.setattr(sp, "run", mock_run)

    result = service.uninstall_portable_pg(install_dir=install_dir, stop_server=True, timeout=5.0)

    assert result.success is True
    assert result.server_was_running is True
    # Sprawdź że były wywołania status + stop.
    assert any("status" in str(c) for c in calls)
    assert any("stop" in str(c) for c in calls)
    assert not install_dir.exists()


def test_uninstall_portable_pg_skips_stop_when_disabled(tmp_path):
    """Gdy ``stop_server=False`` — pomija sprawdzanie i stop."""
    install_dir = tmp_path / "postgres"
    pgsql_bin = install_dir / "pgsql" / "bin"
    pgsql_bin.mkdir(parents=True)
    (install_dir / "data").mkdir(parents=True)

    result = service.uninstall_portable_pg(install_dir=install_dir, stop_server=False)

    assert result.success is True
    assert result.server_was_running is False
    assert not install_dir.exists()


def test_uninstall_portable_pg_uses_default_install_dir(monkeypatch, tmp_path):
    """Bez argumentu ``install_dir`` używa ``get_pg_install_dir()``."""
    # Stwórz katalog w domyślnej lokalizacji (project root + postgres).
    install_dir = service._find_project_root() / ".runtime" / "postgres"
    pgsql_bin = install_dir / "pgsql" / "bin"
    pgsql_bin.mkdir(parents=True)
    (install_dir / "data").mkdir(parents=True)

    try:
        result = service.uninstall_portable_pg(stop_server=False)
        assert result.success is True
        assert not install_dir.exists()
    finally:
        # Cleanup na wypadek błędu.
        import shutil
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)


def test_uninstall_result_is_truthy_on_success(tmp_path):
    """``UninstallResult`` ma ``__bool__`` zwracający ``result.success``."""
    install_dir = tmp_path / "postgres"
    (install_dir / "pgsql").mkdir(parents=True)

    result = service.uninstall_portable_pg(install_dir=install_dir, stop_server=False)
    assert bool(result) is True
    assert result.success is True


# ---------------------------------------------------------------------------
# Cache layer (A) -- get_cache_dir, is_cache_file_valid, copy_to_cache
# ---------------------------------------------------------------------------


def test_get_cache_dir_returns_cache_subdir(monkeypatch, tmp_path):
    """``get_cache_dir`` zwraca ``<root>/cache/``."""
    # Marker żeby _find_project_root zwrócił tmp_path
    (tmp_path / "launcher" / "launcher_app.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "launcher" / "launcher_app.py").write_text("# marker")
    (tmp_path / "requirements.txt").write_text("fastapi")
    (tmp_path / "backend" / "main.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "backend" / "main.py").write_text("# marker")

    monkeypatch.setattr(service, "_find_project_root", lambda: tmp_path)
    cache = get_cache_dir()
    assert cache == tmp_path / "cache"


def test_is_cache_file_valid_true_for_large_file(tmp_path):
    """Plik >= 1 MB w cache uznajemy za poprawny."""
    valid = tmp_path / "pg.zip"
    valid.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MB
    assert is_cache_file_valid(valid) is True


def test_is_cache_file_valid_false_for_too_small_file(tmp_path):
    """Plik < 1 MB (corrupted/truncated download) jest odrzucany."""
    small = tmp_path / "pg.zip"
    small.write_bytes(b"x" * 100)  # 100 B
    assert is_cache_file_valid(small) is False


def test_is_cache_file_valid_false_for_missing_file(tmp_path):
    """Brak pliku w cache → False (nie wyjątek)."""
    assert is_cache_file_valid(tmp_path / "nonexistent.zip") is False


def test_copy_to_cache_copies_file(tmp_path, monkeypatch):
    """``copy_to_cache`` kopiuje plik i zwraca ścieżkę w cache."""
    monkeypatch.setattr(service, "get_cache_dir", lambda: tmp_path / "cache")
    source = tmp_path / "pg.zip"
    source.write_bytes(b"x" * (2 * 1024 * 1024))

    result = copy_to_cache(source)
    assert result is not None
    assert result.exists()
    assert result == tmp_path / "cache" / "pg.zip"


def test_copy_to_cache_skips_existing_valid_file(tmp_path, monkeypatch):
    """Gdy plik w cache już istnieje i jest poprawny, nie nadpisujemy."""
    monkeypatch.setattr(service, "get_cache_dir", lambda: tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    existing = tmp_path / "cache" / "pg.zip"
    existing.write_bytes(b"old" * (1024 * 1024))  # 3 MB

    source = tmp_path / "pg.zip"
    source.write_bytes(b"new" * (1024 * 1024))

    result = copy_to_cache(source)
    assert result == existing
    # Zachowana stara zawartość (nie nadpisana).
    assert existing.read_bytes()[:3] == b"old"


# ---------------------------------------------------------------------------
# Cache layer (A) -- download_pg_binary_with_cache
# ---------------------------------------------------------------------------


def test_download_pg_binary_with_cache_uses_cached_file(monkeypatch, tmp_path):
    """Gdy plik jest w cache, download nie jest wywoływany."""
    cache = tmp_path / "cache"
    cache.mkdir()
    cached_file = cache / "pg.zip"
    cached_file.write_bytes(b"x" * (2 * 1024 * 1024))

    monkeypatch.setattr(service, "get_cache_dir", lambda: cache)

    def must_not_call(**kwargs):
        raise AssertionError("download_pg_binary nie powinien być wołany gdy cache hit")

    monkeypatch.setattr(service, "download_pg_binary", must_not_call)

    calls: list[tuple[int, int]] = []
    path, from_cache = download_pg_binary_with_cache(
        "https://example.com/pg.zip",
        tmp_path / "target",
        progress_callback=lambda d, t: calls.append((d, t)),
    )
    assert from_cache is True
    assert path == cached_file
    # Callback powinien być wywołany z pełnym rozmiarem.
    assert calls
    assert calls[-1] == (cached_file.stat().st_size, cached_file.stat().st_size)


def test_download_pg_binary_with_cache_downloads_when_missing(monkeypatch, tmp_path):
    """Gdy cache miss, wywołuje download_pg_binary i zapisuje w cache."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(service, "get_cache_dir", lambda: cache)

    fake = _fake_response([b"data" * 100], content_length="400")
    monkeypatch.setattr(service.urllib.request, "urlopen", lambda url, timeout=60: fake)

    path, from_cache = download_pg_binary_with_cache(
        "https://example.com/pg.zip",
        tmp_path / "target",
    )
    assert from_cache is False
    assert path.exists()
    assert (cache / "pg.zip").exists(), "Powinien zachować kopię w cache"


def test_download_pg_binary_with_cache_skip_when_disabled(monkeypatch, tmp_path):
    """``use_cache=False`` pomija sprawdzanie cache (zawsze pobiera)."""
    cache = tmp_path / "cache"
    cache.mkdir()
    cached_file = cache / "pg.zip"
    cached_file.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr(service, "get_cache_dir", lambda: cache)

    fake_called = {"n": 0}
    def fake_download(*args, **kwargs):
        fake_called["n"] += 1
        out = tmp_path / "target" / "pg.zip"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"downloaded")
        return out

    monkeypatch.setattr(service, "download_pg_binary", fake_download)
    monkeypatch.setattr(service, "time", "sleep", lambda _s: None)

    path, from_cache = download_pg_binary_with_cache(
        "https://example.com/pg.zip",
        tmp_path / "target",
        use_cache=False,
    )
    assert fake_called["n"] == 1
    assert from_cache is False


# ---------------------------------------------------------------------------
# Fallback (C) -- download_pg_binary_with_fallbacks
# ---------------------------------------------------------------------------


def test_download_pg_binary_with_fallbacks_first_url_succeeds(monkeypatch, tmp_path):
    """Gdy pierwszy URL działa, nie próbuje kolejnych."""
    success_response = _fake_response([b"data"], content_length="4")
    monkeypatch.setattr(service.urllib.request, "urlopen", lambda url, timeout=60: success_response)
    monkeypatch.setattr(service.time, "sleep", lambda _s: None)

    result = download_pg_binary_with_fallbacks(
        ["https://primary.example.com/pg.zip", "https://fallback.example.com/pg.zip"],
        tmp_path,
    )
    assert result.exists()


def test_download_pg_binary_with_fallbacks_uses_fallback(monkeypatch, tmp_path):
    """Gdy pierwszy URL zawiedzie (po max_retries), próbuje drugi."""
    success_response = _fake_response([b"data"], content_length="4")

    calls: list[str] = []
    def fake_urlopen(url, timeout=60):
        calls.append(url)
        if "primary" in url:
            raise urllib.error.URLError("primary down")
        return success_response

    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(service.time, "sleep", lambda _s: None)

    result = download_pg_binary_with_fallbacks(
        ["https://primary.example.com/pg.zip", "https://fallback.example.com/pg.zip"],
        tmp_path,
        max_retries_per_url=1,
    )
    assert result.exists()
    # Pierwszy URL zawiódł, drugi zadziałał.
    assert any("primary" in c for c in calls)
    assert any("fallback" in c for c in calls)


def test_download_pg_binary_with_fallbacks_raises_when_all_fail(monkeypatch, tmp_path):
    """Gdy wszystkie URL-e zawiodą, rzuca RuntimeError z listą URL-i."""
    def always_fail(url, timeout=60):
        raise urllib.error.URLError(f"network down for {url}")

    monkeypatch.setattr(service.urllib.request, "urlopen", always_fail)
    monkeypatch.setattr(service.time, "sleep", lambda _s: None)

    with pytest.raises(RuntimeError, match="Nie udało się pobrać"):
        download_pg_binary_with_fallbacks(
            ["https://a.example.com/pg.zip", "https://b.example.com/pg.zip"],
            tmp_path,
            max_retries_per_url=1,
        )


def test_download_pg_binary_with_fallbacks_empty_urls_raises(tmp_path):
    """Pusta lista URL-i → RuntimeError natychmiast."""
    with pytest.raises(RuntimeError, match="co najmniej 1 URL-a"):
        download_pg_binary_with_fallbacks([], tmp_path)


# ---------------------------------------------------------------------------
# PostGIS (B) -- get_postgis_download_url, install_postgis_to_extension_dir
# ---------------------------------------------------------------------------


def test_default_postgis_version_is_set():
    """``DEFAULT_POSTGIS_VERSION`` to wersja kompatybilna z PG 16.x."""
    assert DEFAULT_POSTGIS_VERSION
    # PostGIS 3.6.x jest kompatybilny z PG 14-17.
    assert DEFAULT_POSTGIS_VERSION.startswith("3.")


def test_postgis_download_urls_contains_windows_amd64():
    """``POSTGIS_DOWNLOAD_URLS`` ma primary URL dla Windows x64."""
    urls = POSTGIS_DOWNLOAD_URLS.get(("Windows", "AMD64"))
    assert urls, "Brak URL-i PostGIS dla Windows/AMD64"
    assert len(urls) >= 1
    assert urls[0].endswith(".zip"), f"PostGIS bundle powinien być ZIP: {urls[0]}"


def test_get_postgis_download_url_returns_windows_url(monkeypatch):
    """``get_postgis_download_url`` zwraca primary URL dla bieżącej platformy."""
    monkeypatch.setattr(service.platform, "system", lambda: "Windows")
    monkeypatch.setattr(service.platform, "machine", lambda: "AMD64")
    url = get_postgis_download_url()
    assert url.startswith("https://")
    assert "postgis" in url.lower()


def test_get_postgis_download_url_raises_for_unsupported(monkeypatch):
    """``RuntimeError`` gdy brak URL-i dla platformy (np. Darwin)."""
    monkeypatch.setattr(service.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(service.platform, "machine", lambda: "x86_64")
    with pytest.raises(RuntimeError, match="Brak URL do pobrania PostGIS"):
        get_postgis_download_url()


def test_install_postgis_to_extension_dir_copies_files(tmp_path):
    """Bundle ZIP z prawidłową strukturą → pliki trafiają do extension/lib."""
    archive = tmp_path / "postgis-bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("postgis-3.6/share/extension/postgis.control", "control")
        zf.writestr("postgis-3.6/share/extension/postgis--3.6.2.sql", "sql")
        zf.writestr("postgis-3.6/lib/postgis-3.so", "so")
        # Plik spoza share/extension i lib/ → pomijany.
        zf.writestr("postgis-3.6/README.md", "readme")

    ext_dir = tmp_path / "share" / "extension"
    copied = install_postgis_to_extension_dir(archive, ext_dir)
    assert copied == 3
    assert (ext_dir / "postgis.control").is_file()
    assert (ext_dir / "postgis--3.6.2.sql").is_file()
    assert (ext_dir.parent / "lib" / "postgis-3.so").is_file()
    assert not (ext_dir / "README.md").exists()


def test_install_postgis_to_extension_dir_raises_for_wrong_extension(tmp_path):
    """Archiwum niebędące ZIP-em → RuntimeError z jasnym komunikatem."""
    fake = tmp_path / "postgis.exe"
    fake.write_bytes(b"MZ")  # sygnatura EXE
    with pytest.raises(RuntimeError, match="Oczekiwano .zip"):
        install_postgis_to_extension_dir(fake, tmp_path / "ext")


def test_install_postgis_to_extension_dir_raises_when_no_extension_files(tmp_path):
    """Archiwum ZIP bez plików extension → RuntimeError z instrukcją."""
    archive = tmp_path / "wrong-bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("README.md", "to nie jest PostGIS bundle")
        zf.writestr("random/file.txt", "x")
    with pytest.raises(RuntimeError, match="nie zawiera plików PostGIS extension"):
        install_postgis_to_extension_dir(archive, tmp_path / "ext")


def test_has_postgis_extension_files_true_when_control_exists(tmp_path):
    """``has_postgis_extension_files`` zwraca True gdy ``postgis.control`` jest w katalogu."""
    ext_dir = tmp_path / "share" / "extension"
    ext_dir.mkdir(parents=True)
    (ext_dir / "postgis.control").write_text("# postgis")
    assert has_postgis_extension_files(ext_dir) is True


def test_has_postgis_extension_files_false_when_missing(tmp_path):
    """Brak ``postgis.control`` → False (CREATE EXTENSION postgis zawiedzie)."""
    ext_dir = tmp_path / "share" / "extension"
    ext_dir.mkdir(parents=True)
    (ext_dir / "postgis--3.6.2.sql").write_text("sql only")
    assert has_postgis_extension_files(ext_dir) is False
