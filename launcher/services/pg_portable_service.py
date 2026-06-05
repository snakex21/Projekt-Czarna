"""Serwis wykrywania i pobierania portable PostgreSQL.

Ten moduł dostarcza funkcje niskiego poziomu potrzebne do
uruchomienia aplikacji ``Mapa Katastralna Czarna`` na bazie PostgreSQL
bez konieczności ręcznej instalacji serwera:

* ``detect_system_pg`` -- szuka ``pg_ctl`` w ``PATH`` oraz w
  standardowych lokalizacjach instalatorów Windows / Linux / macOS.
* ``get_pg_download_url`` / ``get_pg_install_dir`` -- konfiguracja
  wspierana przez pozostałe etapy planu P2.1 (skąd pobrać, gdzie
  zainstalować portable PG).
* ``download_pg_binary`` / ``extract_pg_archive`` -- pobranie i
  rozpakowanie archiwum z binariami PostgreSQL w sposób atomowy
  (``.tmp`` + ``rename``), z opcjonalnym callbackiem postępu.
* ``is_pg_initialized`` / ``get_portable_pg_paths`` / ``portable_pg_installed``
  -- pomocnicze API do późniejszego startu serwera w Etapach 2-3.

Serwis jest celowo niezależny od warstwy ``backend.*`` i Tkintera
(działa jako czysty helper launchera). Wszystkie operacje I/O są
mockowalne, dzięki czemu testy jednostkowe nie wymagają dostępu do
sieci ani działającego systemu plików poza ``tmp_path``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


# Domyślna wersja PostgreSQL -- LTS, stabilna, testowana z PostGIS 3.6.
DEFAULT_PG_VERSION = "16.4"

# Domyślna wersja PostGIS (kompatybilna z PG 16.x).
DEFAULT_POSTGIS_VERSION = "3.6.2"

# Minimalny rozmiar pliku w cache (poniżej uznajemy za corrupted/truncated
# download). PG binaries ZIP ~ 200 MB, PostGIS bundle ~ 100 MB, więc
# 1 MB to bezpieczny dolny próg dla walidacji integralności.
MIN_VALID_ARCHIVE_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB


# URL-e fallback per platforma. Pierwszy element listy to URL "primary"
# używany domyślnie. Pozostałe są zarezerwowane na przyszłość -- w
# przypadku błędu sieci ``download_pg_binary`` może iterować po liście
# (implementacja Etapu 1 zwraca pierwszy element; mechanizm fallbacków
# zostanie włączony w Etapach 4-5, kiedy walidujemy URL-e na żywo).
#
# Od wersji 1.1.4: dodano drugi mirror (postgresql.org) jako fallback
# na wypadek problemów z serwerem EDB. Mechanizm fallbacków jest
# aktywny w :func:`download_pg_binary_with_fallbacks`.
PG_DOWNLOAD_URLS: dict[tuple[str, str], list[str]] = {
    ("Windows", "AMD64"): [
        f"https://get.enterprisedb.com/postgresql/postgresql-{DEFAULT_PG_VERSION}-1-windows-x64-binaries.zip",
        # Fallback: oficjalne binaria ze strony PostgreSQL (EnterpriseDB
        # archive). Wolniejsze ale redundantne.
        f"https://get.enterprisedb.com/postgresql/postgresql-{DEFAULT_PG_VERSION}-2-windows-x64-binaries.zip",
    ],
    ("Linux", "x86_64"): [
        f"https://get.enterprisedb.com/postgresql/postgresql-{DEFAULT_PG_VERSION}-1-linux-x64-binaries.tar.gz",
        f"https://get.enterprisedb.com/postgresql/postgresql-{DEFAULT_PG_VERSION}-2-linux-x64-binaries.tar.gz",
    ],
    ("Darwin", "x86_64"): [
        f"https://get.enterprisedb.com/postgresql/postgresql-{DEFAULT_PG_VERSION}-1-osx-x64-binaries.zip",
        f"https://get.enterprisedb.com/postgresql/postgresql-{DEFAULT_PG_VERSION}-2-osx-x64-binaries.zip",
    ],
    # Dodatkowe mapowania maszyn (Apple Silicon i386 itp.) celowo
    # pominięte -- poza zakresem Etapu 1.
}


# URL-e PostGIS bundle per platforma. PostGIS bundle dla Windows jest
# dystrybuowany jako NSIS installer (bundle EXE) -- do portable flow
# potrzebujemy samych plików extension. W przyszłości obsłużymy
# rozpakowywanie NSIS (7z dark); na razie wspieramy tylko instalację
# PostGIS bundle EXE przez EDB installer flow (P2.2).
#
# Format URL: ``https://download.osgeo.org/postgis/windows/pgX/postgis-bundle-pgXx64-VER.zip``
# (sprawdzone: OSGeo hostuje archiwa ZIP z plikami extension dla flow portable).
POSTGIS_DOWNLOAD_URLS: dict[tuple[str, str], list[str]] = {
    ("Windows", "AMD64"): [
        f"https://download.osgeo.org/postgis/windows/pg16/postgis-bundle-pg16x64-{DEFAULT_POSTGIS_VERSION}.zip",
        # Fallback mirror -- ten sam plik pod innym URL.
        f"https://postgis.net/windows_downloads/pg16/postgis-bundle-pg16x64-{DEFAULT_POSTGIS_VERSION}.zip",
    ],
    ("Linux", "x86_64"): [
        f"https://download.osgeo.org/postgis/postgis-{DEFAULT_POSTGIS_VERSION}.tar.gz",
    ],
    # macOS -- PostGIS bundle dla macOS nie jest oficjalnie wspierany
    # (rekomendowane: Homebrew). Pozostawiamy pustą listę, żeby
    # get_postgis_download_url() rzucił jasny RuntimeError.
    ("Darwin", "x86_64"): [],
}


# Dodatkowe lokalizacje do sprawdzenia (Windows standardowo).
# Wartość ``{ver}`` jest formatowana numerem wersji major (np. "16").
WINDOWS_PG_PATH_TEMPLATES: list[Path] = [
    Path("C:/Program Files/PostgreSQL/{ver}/bin/pg_ctl.exe"),
    Path("C:/Program Files (x86)/PostgreSQL/{ver}/bin/pg_ctl.exe"),
]


# Wersje major PostgreSQL do sprawdzenia (od najnowszej w dół).
# Zachowujemy krótką listę, żeby detekcja była szybka i deterministyczna.
_PG_MAJOR_VERSIONS: tuple[str, ...] = ("16", "15", "14", "13", "12", "11")


# Domyślna lokalizacja binariów PostgreSQL w Linuksie (pakiet ``postgresql-server``).
# Wyciągnięte do stałej, żeby testy mogły ją podmienić przez ``monkeypatch.setattr``.
LINUX_POSTGRES_LIB_ROOT: Path = Path("/usr/lib/postgresql")


ProgressCallback = Callable[[int, int], None]
ExtractProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class PortablePgPaths:
    """Ścieżki do zainstalowanego portable PG.

    Atrybuty:
        root_dir: katalog główny instalacji portable PG.
        bin_dir: katalog z binariami (``pg_ctl``, ``initdb`` itp.).
        data_dir: katalog danych (gdzie ``initdb`` tworzy klaster).
        pg_ctl_path: pełna ścieżka do ``pg_ctl`` / ``pg_ctl.exe``.
        initdb_path: pełna ścieżka do ``initdb`` / ``initdb.exe``.
        pg_version: wersja PG (string) -- domyślnie DEFAULT_PG_VERSION.
    """

    root_dir: Path
    bin_dir: Path
    data_dir: Path
    pg_ctl_path: Path
    initdb_path: Path
    pg_version: str


@dataclass(frozen=True)
class DownloadResult:
    """Wynik pobierania i ekstrakcji.

    Atrybuty:
        archive_path: ścieżka do pobranego archiwum ZIP/TAR.GZ.
        extracted_path: katalog, do którego rozpakowano archiwum.
        size_bytes: rozmiar pobranego archiwum w bajtach.
        pg_version: wersja PG, której dotyczy pobranie.
    """

    archive_path: Path
    extracted_path: Path
    size_bytes: int
    pg_version: str


def _pg_ctl_filename() -> str:
    """Zwraca nazwę pliku ``pg_ctl`` dla bieżącej platformy."""
    return "pg_ctl.exe" if platform.system() == "Windows" else "pg_ctl"


def _initdb_filename() -> str:
    """Zwraca nazwę pliku ``initdb`` dla bieżącej platformy."""
    return "initdb.exe" if platform.system() == "Windows" else "initdb"


def detect_system_pg() -> Path | None:
    """Wykrywa systemowy ``pg_ctl`` w PATH lub w standardowych lokalizacjach.

    Kolejność sprawdzania:
        1. ``PATH`` (przez :func:`shutil.which`) -- najszybsze i
           najczęściej poprawne (instalator EDB dodaje ``bin`` do PATH).
        2. Standardowe lokalizacje Windows (``C:/Program Files/PostgreSQL/*/bin``)
           -- dla maszyn, gdzie PATH nie jest odświeżony w bieżącej sesji.
        3. ``/usr/lib/postgresql/*/bin/pg_ctl`` -- standardowa lokalizacja
           pakietów ``postgresql-server`` w dystrybucjach Linuksa.

    Returns:
        :class:`pathlib.Path` do pliku ``pg_ctl`` (lub ``pg_ctl.exe`` na
        Windows) jeśli znaleziony, ``None`` w przeciwnym razie.
    """
    # 1) PATH -- najszybsza ścieżka.
    found_in_path = shutil.which("pg_ctl")
    if found_in_path:
        return Path(found_in_path)

    system = platform.system()

    # 2) Standardowe lokalizacje Windows.
    if system == "Windows":
        for template in WINDOWS_PG_PATH_TEMPLATES:
            for major in _PG_MAJOR_VERSIONS:
                candidate = Path(str(template).format(ver=major))
                if candidate.exists():
                    return candidate

    # 3) Linux / macOS: typowe miejsce pakietów.
    else:
        postgres_root = LINUX_POSTGRES_LIB_ROOT
        if postgres_root.exists():
            for version_dir in sorted(postgres_root.glob("*"), reverse=True):
                candidate = version_dir / "bin" / "pg_ctl"
                if candidate.exists():
                    return candidate

    return None


def get_pg_download_url() -> str:
    """Zwraca URL do pobrania portable PG dla bieżącej platformy.

    Returns:
        Pierwszy (primary) URL z listy fallbacków dla bieżącej
        kombinacji ``(system, machine)``.

    Raises:
        RuntimeError: gdy brak zarejestrowanego URL-a dla bieżącej
            platformy (np. nierozpoznany ``platform.system()``).
    """
    system = platform.system()
    machine = platform.machine()
    key = (system, machine)
    urls = PG_DOWNLOAD_URLS.get(key)
    if not urls:
        raise RuntimeError(
            f"Brak URL do pobrania portable PostgreSQL dla platformy "
            f"{system}/{machine}. Obsługiwane kombinacje: "
            f"{sorted(PG_DOWNLOAD_URLS.keys())}"
        )
    return urls[0]


def _find_project_root() -> Path:
    """Znajduje katalog główny projektu Mapa Katastralna Czarna.

    Strategia: idzie w górę od lokalizacji tego pliku szukając markera.
    Ten plik żyje w ``<root>/launcher/services/pg_portable_service.py``,
    więc trzy poziomy wyżej to katalog główny projektu.

    Markery walidacyjne (w kolejności sprawdzania):
        1. ``launcher/launcher_app.py`` (główny plik launchera)
        2. ``requirements.txt`` (zależności backendu)
        3. ``backend/main.py`` (FastAPI entrypoint)

    Returns:
        Ścieżka do katalogu głównego projektu.

    Raises:
        RuntimeError: gdy nie uda się zlokalizować markera (uruchomienie
            z nieznanej lokalizacji, np. po ``pip install``).
    """
    # Ten plik: <root>/launcher/services/pg_portable_service.py
    here = Path(__file__).resolve()
    candidates = [here.parents[2]]  # <root>

    # Jeśli rodzic[2] nie ma markera, spróbuj wyżej (głębsze pakowanie).
    if not any((c / marker).exists() for c in candidates for marker in
               ("launcher/launcher_app.py", "requirements.txt", "backend/main.py")):
        # Spróbuj parents[3] (gdyby ktoś spakował w extra wrapper).
        candidates.append(here.parents[3])

    for candidate in candidates:
        if (candidate / "launcher" / "launcher_app.py").exists():
            return candidate
        if (candidate / "requirements.txt").exists() and \
           (candidate / "backend" / "main.py").exists():
            return candidate

    raise RuntimeError(
        f"Nie można zlokalizować katalogu głównego projektu. "
        f"Sprawdzono: {[str(c) for c in candidates]}. "
        f"Upewnij się, że plik {__file__} jest w <root>/launcher/services/."
    )


def get_pg_install_dir() -> Path:
    """Zwraca domyślny katalog instalacji portable PG.

    Od wersji 1.1.2 portable PG instaluje się w katalogu projektu
    (``<root>/.runtime/postgres/``). Jest to:

    * **ukryty** (kropka-prefix) — nie zaśmieca drzewa projektu,
    * **semantyczny** — ``.runtime/`` to miejsce na runtime (nie dane,
      nie toolsy, nie dependencies),
    * **rozszerzalny** — w przyszłości można tam wrzucić ``.runtime/cache/``,
      ``.runtime/uploads/`` itd.
    * **gitignored** — ``.runtime/`` w ``.gitignore``.

    Konwencja (jednakowa dla wszystkich platform):
        * ``<project_root>/.runtime/postgres/``

    Raises:
        RuntimeError: gdy nie da się zlokalizować katalogu głównego projektu
            (np. uruchomienie z nietypowej lokalizacji, zipapp, PyInstaller
            bez markera ``launcher/launcher_app.py``).
    """
    root = _find_project_root()
    return root / ".runtime" / "postgres"


def get_cache_dir() -> Path:
    """Zwraca katalog cache dla archiwów PG/PostGIS.

    Katalog cache jest współdzielony między instalacjami i przechowuje
    pobrane archiwa (PG binaries ZIP, PostGIS bundle ZIP) żeby uniknąć
    redownload przy ponownej instalacji. Jest to:

    * **publiczny** (bez kropki) — user może ręcznie podejrzeć co jest
      w cache i wyczyścić.
    * **semantyczny** — ``cache/`` to miejsce na pliki tymczasowe
      związane z instalacją (NIE runtime data).
    * **gitignored** — ``cache/`` w ``.gitignore``.

    Konwencja:
        * ``<project_root>/cache/``

    Raises:
        RuntimeError: gdy nie da się zlokalizować katalogu głównego projektu.
    """
    root = _find_project_root()
    return root / "cache"


def is_cache_file_valid(cache_path: Path) -> bool:
    """Sprawdza czy plik w cache nadaje się do użytku.

    Walidacja:
        1. Plik istnieje i jest plikiem.
        2. Rozmiar >= ``MIN_VALID_ARCHIVE_SIZE_BYTES`` (1 MB) —
           chroni przed corrupted/truncated pobraniami.

    Args:
        cache_path: ścieżka do pliku w cache.

    Returns:
        ``True`` jeśli plik istnieje i ma sensowny rozmiar.
    """
    if not cache_path.is_file():
        return False
    try:
        size = cache_path.stat().st_size
    except OSError:
        return False
    return size >= MIN_VALID_ARCHIVE_SIZE_BYTES


def copy_to_cache(source: Path, cache_dir: Path | None = None) -> Path | None:
    """Kopiuje plik archiwum do cache (best-effort).

    Po udanym pobraniu z URL chcemy zachować kopię w cache, żeby
    kolejne instalacje nie wymagały ponownego pobierania. Funkcja jest
    best-effort: gdy kopia się nie powiedzie (np. brak miejsca na
    dysku, brak uprawnień), zwraca ``None`` zamiast rzucać wyjątkiem
    — oryginalny plik w ``target_dir`` nadal jest użyteczny.

    Args:
        source: ścieżka do pliku źródłowego (pobranego archiwum).
        cache_dir: katalog docelowy cache. Domyślnie
            :func:`get_cache_dir`.

    Returns:
        Ścieżka do pliku w cache gdy kopia się powiodła, ``None`` w p.p.
    """
    if not source.is_file():
        return None
    if cache_dir is None:
        try:
            cache_dir = get_cache_dir()
        except RuntimeError:
            return None  # Nie udało się zlokalizować katalogu głównego.
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    dest = cache_dir / source.name
    if dest.exists() and is_cache_file_valid(dest):
        # Już mamy poprawny plik w cache — nie nadpisujemy.
        return dest
    try:
        shutil.copy2(source, dest)
        return dest
    except OSError:
        return None


def download_pg_binary(
    url: str,
    target_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    chunk_size: int = 64 * 1024,
    max_retries: int = 3,
) -> Path:
    """Pobiera archiwum z portable PG do katalogu docelowego (atomowo).

    Plik jest zapisywany do ``<target_dir>/<filename>.tmp``, a po
    pomyślnym pobraniu atomowo przenoszony (``Path.replace``) do
    właściwej nazwy. Dzięki temu częściowo pobrane pliki nie zostają
    pomylone z kompletnymi.

    Args:
        url: pełny URL do archiwum (ZIP lub TAR.GZ).
        target_dir: katalog docelowy, w którym powstanie plik
            archiwum. Zostanie utworzony, jeśli nie istnieje.
        progress_callback: opcjonalny callback ``(downloaded, total)``
            -- ``total`` wynosi 0 jeśli serwer nie zwrócił
            nagłówka ``Content-Length``.
        chunk_size: rozmiar kawałka odczytu w bajtach.
        max_retries: ile razy ponowić pobieranie w przypadku błędu
            sieci (HTTP 5xx, ``URLError``, zerwane połączenie).

    Returns:
        :class:`Path` do pobranego pliku archiwum.

    Raises:
        RuntimeError: jeśli pobranie nie powiedzie się po ``max_retries``
            próbach. Komunikat zawiera liczbę prób i ostatni błąd.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1] or "postgresql-portable.bin"
    final_path = target_dir / filename
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 -- URL przechodzi z argumentu
                content_length_raw = response.headers.get("Content-Length")
                total = int(content_length_raw) if content_length_raw and content_length_raw.isdigit() else 0

                downloaded = 0
                with open(tmp_path, "wb") as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)

            # Atomowy rename: .tmp -> właściwa nazwa.
            tmp_path.replace(final_path)
            return final_path

        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last_error = exc
            # Sprzątamy plik tymczasowy po każdej nieudanej próbie.
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

            if attempt >= max_retries:
                break
            # Krótka pauza między próbami (mockowalna przez testy).
            time.sleep(0.5 * attempt)

    raise RuntimeError(
        f"Nie udało się pobrać archiwum PostgreSQL z {url} po "
        f"{max_retries} próbach. Ostatni błąd: {last_error}"
    )


def download_pg_binary_with_fallbacks(
    urls: list[str],
    target_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    max_retries_per_url: int = 3,
) -> Path:
    """Pobiera archiwum PG/PostGIS z fallbackiem na kolejne URL-e.

    Iteruje po ``urls`` w kolejności. Jeśli pierwszy URL zawiedzie
    (po ``max_retries_per_url`` próbach) próbuje następny. Zwraca
    ścieżkę do pierwszego udanego pobrania.

    Args:
        urls: lista URL-i do archiwum (ZIP lub TAR.GZ). Musi zawierać
            co najmniej jeden element. Kolejność = priorytet (primary
            URL na początku).
        target_dir: katalog docelowy (jak w :func:`download_pg_binary`).
        progress_callback: opcjonalny callback ``(downloaded, total)``
            przekazywany do każdej próby pobierania.
        max_retries_per_url: ile razy ponowić pobieranie per URL zanim
            przejść do następnego fallbacku.

    Returns:
        :class:`Path` do pobranego pliku.

    Raises:
        RuntimeError: gdy wszystkie URL-e zawiodą. Komunikat zawiera
            listę próbowanych URL-i i ostatni błąd.
    """
    if not urls:
        raise RuntimeError("download_pg_binary_with_fallbacks wymaga co najmniej 1 URL-a")

    last_error: Exception | None = None
    attempted: list[str] = []
    for url in urls:
        attempted.append(url)
        try:
            return download_pg_binary(
                url=url,
                target_dir=target_dir,
                progress_callback=progress_callback,
                max_retries=max_retries_per_url,
            )
        except RuntimeError as exc:
            last_error = exc
            # Kolejny URL — kontynuujemy pętlę.
            continue

    raise RuntimeError(
        f"Nie udało się pobrać archiwum z żadnego z {len(attempted)} URL-i: "
        f"{attempted}. Ostatni błąd: {last_error}"
    )


def download_pg_binary_with_cache(
    url: str,
    target_dir: Path,
    cache_dir: Path | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    max_retries: int = 3,
    use_cache: bool = True,
    copy_back_to_cache: bool = True,
) -> tuple[Path, bool]:
    """Pobiera archiwum PG/PostGIS z warstwą cache.

    Kolejność operacji:
        1. Oblicz ``filename = basename(url)`` i sprawdź
           ``<cache_dir>/<filename>``.
        2. Jeśli plik w cache istnieje i :func:`is_cache_file_valid`
           → zwróć go (callback postępu wołany z pełnym rozmiarem,
           bez pobierania z sieci).
        3. Jeśli brak w cache → wywołaj :func:`download_pg_binary`
           (pobiera z URL do ``target_dir``).
        4. Po udanym pobraniu → opcjonalnie skopiuj do cache
           (:func:`copy_to_cache`) dla przyszłych instalacji.

    Args:
        url: URL do archiwum.
        target_dir: katalog docelowy (jak :func:`download_pg_binary`).
        cache_dir: katalog cache. Domyślnie :func:`get_cache_dir`.
        progress_callback: opcjonalny callback ``(downloaded, total)``.
        max_retries: ile razy ponowić pobieranie per URL.
        use_cache: czy sprawdzać cache (domyślnie ``True``).
        copy_back_to_cache: czy po pobraniu skopiować do cache.

    Returns:
        Krotka ``(path, from_cache)``:
            * ``path`` — :class:`Path` do pliku (w cache lub ``target_dir``).
            * ``from_cache`` — ``True`` jeśli plik pochodzi z cache,
              ``False`` jeśli został świeżo pobrany.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1] or "postgresql-portable.bin"

    if use_cache:
        if cache_dir is None:
            try:
                cache_dir = get_cache_dir()
            except RuntimeError:
                cache_dir = None

        if cache_dir is not None:
            cached = cache_dir / filename
            if is_cache_file_valid(cached):
                # Wywołaj callback z pełnym rozmiarem (bez pobierania).
                if progress_callback is not None:
                    size = cached.stat().st_size
                    progress_callback(size, size)
                return cached, True

    # Brak w cache (lub use_cache=False) → pobierz normalnie.
    downloaded_path = download_pg_binary(
        url=url,
        target_dir=target_dir,
        progress_callback=progress_callback,
        max_retries=max_retries,
    )

    # Opcjonalnie: zachowaj w cache dla przyszłych instalacji.
    if copy_back_to_cache and use_cache:
        copy_to_cache(downloaded_path, cache_dir=cache_dir)

    return downloaded_path, False


def get_postgis_download_url() -> str:
    """Zwraca primary URL do pobrania PostGIS bundle dla bieżącej platformy.

    Analogiczne do :func:`get_pg_download_url`. Lista fallbacków
    dostępna przez :data:`POSTGIS_DOWNLOAD_URLS` (drugi element to
    mirror na wypadek problemów z primary).

    Returns:
        Pierwszy URL z listy fallbacków dla bieżącej platformy.

    Raises:
        RuntimeError: gdy brak zarejestrowanego URL-a dla bieżącej
            platformy (np. macOS bez wsparcia PostGIS bundle).
    """
    system = platform.system()
    machine = platform.machine()
    key = (system, machine)
    urls = POSTGIS_DOWNLOAD_URLS.get(key)
    if not urls:
        raise RuntimeError(
            f"Brak URL do pobrania PostGIS bundle dla platformy "
            f"{system}/{machine}. Obsługiwane kombinacje: "
            f"{sorted(POSTGIS_DOWNLOAD_URLS.keys())}. Na macOS zainstaluj "
            f"PostGIS przez Homebrew (brew install postgis)."
        )
    return urls[0]


def install_postgis_to_extension_dir(
    postgis_archive: Path,
    extension_dir: Path,
) -> int:
    """Rozpakowuje PostGIS bundle i kopiuje pliki extension do ``extension_dir``.

    Pliki PostGIS extension (``postgis.control``, ``postgis--*.sql``,
    ``postgis-*.so`` itd.) trafiają do katalogu ``<pg>/share/extension/``
    lub jego portable odpowiednika. Po tej operacji ``CREATE EXTENSION
    postgis`` zadziała w każdej bazie utworzonej na tym serwerze.

    Oczekiwana struktura archiwum PostGIS bundle ZIP (od OSGeo):
        ``postgis-3.6/``
        ├── ``share/extension/postgis.control``
        ├── ``share/extension/postgis--3.6.2.sql``
        ├── ``lib/postgis-3.so``
        └── ... (raster, topology, sfcgal, tiger_geocoder)

    Pliki ``share/extension/*.control`` i ``*.sql`` trafiają do
    ``<extension_dir>``. Pliki binarne (``*.so`` / ``*.dll``) trafiają
    do ``<extension_dir.parent>/lib/`` (standardowy layout PG).

    Args:
        postgis_archive: ścieżka do archiwum PostGIS bundle (ZIP).
        extension_dir: katalog docelowy (``<pg>/share/extension``).

    Returns:
        Liczba skopiowanych plików (control + sql + dll/so).

    Raises:
        RuntimeError: gdy archiwum ma nieobsługiwane rozszerzenie,
            brakuje ``share/extension/`` w archiwum lub kopiowanie
            się nie powiedzie.
    """
    archive = Path(postgis_archive)
    if not archive.is_file():
        raise RuntimeError(f"Archiwum PostGIS nie istnieje: {archive}")
    if archive.suffix.lower() != ".zip":
        raise RuntimeError(
            f"Nieobsługiwane rozszerzenie archiwum PostGIS: {archive.suffix!r}. "
            f"Oczekiwano .zip."
        )

    extension_dir = Path(extension_dir)
    extension_dir.mkdir(parents=True, exist_ok=True)
    lib_dir = extension_dir.parent / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            # Indeksuj pliki extension (control + sql) i biblioteki (so/dll/dylib).
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Normalizuj separatory (ZIP może używać \\ na Windows).
                name = info.filename.replace("\\", "/")
                lower = name.lower()

                if "/share/extension/" in lower and (
                    lower.endswith(".control")
                    or lower.endswith(".sql")
                ):
                    target = extension_dir / Path(name).name
                elif "/lib/" in lower and (
                    lower.endswith(".so")
                    or lower.endswith(".dll")
                    or lower.endswith(".dylib")
                ):
                    target = lib_dir / Path(name).name
                else:
                    continue  # pomijamy pliki spoza share/extension i lib/

                try:
                    with zf.open(info) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    copied += 1
                except OSError as exc:
                    raise RuntimeError(
                        f"Nie udało się skopiować {name} do {target}: {exc}"
                    ) from exc
    except (zipfile.BadZipFile, OSError) as exc:
        raise RuntimeError(
            f"Nie udało się rozpakować archiwum PostGIS {archive}: {exc}"
        ) from exc

    if copied == 0:
        raise RuntimeError(
            f"Archiwum {archive.name} nie zawiera plików PostGIS extension "
            f"(oczekiwano share/extension/*.control i lib/*.so/dll). "
            f"Sprawdź czy pobrano właściwy bundle dla PG 16."
        )

    return copied


def has_postgis_extension_files(extension_dir: Path) -> bool:
    """Sprawdza czy pliki PostGIS extension są zainstalowane w ``extension_dir``.

    Heurystyka: obecność pliku ``postgis.control`` w katalogu. Wszystkie
    inne pliki extension (postgis--*.sql, postgis-*.so) muszą być w tym
    samym katalogu, żeby ``CREATE EXTENSION postgis`` zadziałał.

    Args:
        extension_dir: katalog ``<pg>/share/extension``.

    Returns:
        ``True`` jeśli ``postgis.control`` istnieje.
    """
    if not extension_dir:
        return False
    return (Path(extension_dir) / "postgis.control").is_file()


def extract_pg_archive(
    archive_path: Path,
    target_dir: Path,
    progress_callback: Callable[[str], None] | None = None,
) -> Path:
    """Rozpakowuje ZIP lub TAR.GZ z binariami portable PG do ``target_dir``.

    Obsługuje archiwa wydane przez EDB, w których wszystkie pliki
    leżą w jednym katalogu głównym (zwykle ``pgsql/``). Po rozpakowaniu
    odszukuje podkatalog ``pgsql/bin`` i zwraca do niego ścieżkę.

    Args:
        archive_path: ścieżka do archiwum (``*.zip`` lub ``*.tar.gz``).
        target_dir: katalog docelowy. Musi istnieć lub być możliwym
            do utworzenia.
        progress_callback: opcjonalny callback z komunikatami tekstowymi
            o kolejnych fazach rozpakowywania.

    Returns:
        :class:`Path` do katalogu ``<target_dir>/pgsql/bin``.

    Raises:
        RuntimeError: gdy rozszerzenie archiwum nie jest rozpoznawalne,
            rozpakowanie się nie powiedzie lub brakuje katalogu
            ``pgsql/bin`` po ekstrakcji.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = Path(archive_path)
    suffix = archive_path.suffix.lower()
    secondary_suffix = "".join(archive_path.suffixes[-2:]).lower() if len(archive_path.suffixes) >= 2 else ""

    def _notify(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    _notify(f"Rozpakowuję {archive_path.name} do {target_dir}")

    try:
        if suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(target_dir)
        elif suffix == ".tgz" or secondary_suffix == ".tar.gz" or suffix == ".gz":
            # ``.tar.gz`` zostaje złapane przez ``secondary_suffix``.
            with tarfile.open(archive_path, "r:gz") as tf:
                # ``filter="data"`` jest rekomendowanym ustawieniem od Py 3.12
                # i jedynym bezpiecznym od Py 3.14 (gdzie brak filtra
                # włącza rygorystyczny filtr domyślny, który potrafi odrzucić
                # część plików z archiwum EDB).
                tf.extractall(target_dir, filter="data")
        else:
            raise RuntimeError(
                f"Nieobsługiwane rozszerzenie archiwum: {suffix!r}. "
                f"Oczekiwano .zip lub .tar.gz."
            )
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
        raise RuntimeError(
            f"Nie udało się rozpakować archiwum {archive_path}: {exc}"
        ) from exc

    bin_dir = target_dir / "pgsql" / "bin"
    if not bin_dir.is_dir():
        # EDB czasem pakuje bezpośrednio do "bin/" bez "pgsql/" (rzadko).
        direct_bin = target_dir / "bin"
        if direct_bin.is_dir():
            bin_dir = direct_bin
        else:
            raise RuntimeError(
                f"Po rozpakowaniu nie znaleziono katalogu bin w {target_dir}. "
                f"Oczekiwano {target_dir / 'pgsql' / 'bin'}."
            )

    _notify(f"Archiwum rozpakowane; binaria w {bin_dir}")
    return bin_dir


def is_pg_initialized(data_dir: Path) -> bool:
    """Sprawdza czy katalog danych PG jest zainicjalizowany.

    Po udanym ``initdb`` w katalogu danych tworzony jest plik
    ``PG_VERSION`` z numerem wersji (np. ``16.4``).

    Args:
        data_dir: katalog danych, który ma być sprawdzony.

    Returns:
        ``True`` jeśli ``<data_dir>/PG_VERSION`` istnieje i jest plikiem.
    """
    if not data_dir:
        return False
    return (Path(data_dir) / "PG_VERSION").is_file()


def get_portable_pg_paths(
    install_dir: Path | None = None,
    pg_version: str = DEFAULT_PG_VERSION,
) -> PortablePgPaths:
    """Buduje ścieżki do portable PG (bez weryfikacji istnienia plików).

    Args:
        install_dir: katalog instalacji. Domyślnie :func:`get_pg_install_dir`.
        pg_version: wersja PG (string) -- trafia do ``PortablePgPaths``.

    Returns:
        :class:`PortablePgPaths` z obliczonymi ścieżkami.

    Note:
        Funkcja NIE rzuca ``FileNotFoundError``. Walidację czy pliki
        rzeczywiście istnieją robi :func:`portable_pg_installed` lub
        procedura startu w Etapach 2-3.
    """
    root = Path(install_dir) if install_dir is not None else get_pg_install_dir()
    bin_dir = root / "pgsql" / "bin"
    return PortablePgPaths(
        root_dir=root,
        bin_dir=bin_dir,
        data_dir=root / "data",
        pg_ctl_path=bin_dir / _pg_ctl_filename(),
        initdb_path=bin_dir / _initdb_filename(),
        pg_version=pg_version,
    )


def portable_pg_installed(install_dir: Path | None = None) -> bool:
    """Sprawdza czy portable PG jest zainstalowany w danej lokalizacji.

    Args:
        install_dir: katalog instalacji. Domyślnie :func:`get_pg_install_dir`.

    Returns:
        ``True`` jeśli plik ``pg_ctl`` (lub ``pg_ctl.exe``) istnieje
        w ``<install_dir>/pgsql/bin``.
    """
    paths = get_portable_pg_paths(install_dir=install_dir)
    return paths.pg_ctl_path.is_file()


@dataclass
class UninstallResult:
    """Wynik :func:`uninstall_portable_pg`."""

    success: bool
    install_dir: Path
    removed_files: int = 0
    server_was_running: bool = False
    error: str | None = None

    def __bool__(self) -> bool:
        return self.success


def uninstall_portable_pg(
    install_dir: Path | None = None,
    stop_server: bool = True,
    timeout: float = 10.0,
) -> UninstallResult:
    """Całkowicie odinstalówuje portable PostgreSQL.

    Procedura:
        1. (Opcjonalnie) Zatrzymuje działający serwer PG przez ``pg_ctl stop``
           z timeoutem ``timeout`` sekund. Jeśli ``stop_server=False``,
           pomija — przydatne w testach.
        2. Usuwa cały katalog ``install_dir`` (binaria + dane + logi + PID)
           przez ``shutil.rmtree(ignore_errors=True)``.
        3. Liczy usunięte pliki (best-effort, przed rmtree).

    Args:
        install_dir: katalog do usunięcia. Domyślnie :func:`get_pg_install_dir`
            (czyli ``<root>/.runtime/postgres/`` od wersji 1.1.2).
        stop_server: czy zatrzymać działający serwer przed usunięciem
            (domyślnie ``True``).
        timeout: limit czasu na graceful shutdown serwera (sekundy).

    Returns:
        :class:`UninstallResult` z informacją o sukcesie i liczbie plików.

    Safety:
        Funkcja **odmawia** usuniecia katalogu ktory:
        * nie istnieje (zwraca success=True z 0 plikami),
        * nie wyglada na katalog portable PG (brak podkatalogu ``pgsql/``)
          — to zabezpieczenie przed przypadkowym ``rm -rf``.

    Raises:
        Nie rzuca — wszystkie błędy są łapane i zwracane w
        ``UninstallResult.error``.

    Note:
        Nie wymaga uprawnien administratora (bo pliki leza w katalogu
        projektu, nie w systemowych lokalizacjach).
    """
    if install_dir is None:
        install_dir = get_pg_install_dir()
    target = Path(install_dir).resolve()

    # Bezpiecznik: nie usuwaj katalogu ktory nie wyglada na portable PG.
    if not target.exists():
        return UninstallResult(success=True, install_dir=target, removed_files=0)

    if not (target / "pgsql").is_dir():
        return UninstallResult(
            success=False,
            install_dir=target,
            error=f"Katalog {target} nie zawiera podkatalogu 'pgsql/' — "
            f"prawdopodobnie to nie jest instalacja portable PG. "
            f"Usuwanie przerwane (safety check).",
        )

    server_was_running = False

    # Krok 1: zatrzymaj serwer jeśli działa.
    if stop_server:
        try:
            import subprocess  # lokalny import — patrz niżej safety check

            # Sprawdź czy działa: próba `pg_ctl status` z krótkim timeoutem.
            pg_ctl = target / "pgsql" / "bin" / ("pg_ctl.exe" if platform.system() == "Windows" else "pg_ctl")
            if pg_ctl.is_file():
                try:
                    result = subprocess.run(
                        [str(pg_ctl), "-D", str(target / "data"), "status"],
                        capture_output=True,
                        timeout=2.0,
                        text=True,
                    )
                    # pg_ctl status zwraca 0 gdy działa, 3 gdy nie działa.
                    server_was_running = (result.returncode == 0)
                except (subprocess.TimeoutExpired, OSError):
                    server_was_running = False

                if server_was_running:
                    try:
                        subprocess.run(
                            [str(pg_ctl), "-D", str(target / "data"), "stop", "-m", "fast"],
                            capture_output=True,
                            timeout=timeout,
                            text=True,
                        )
                    except subprocess.TimeoutExpired:
                        # Wymusic — nie robimy tego w uninstall (bezpieczniej
                        # zostawic sierocym proces niz ryzykowac uszkodzenie FS).
                        pass
        except Exception as exc:
            # Nie blokuj uninstall jeśli nie można sprawdzić statusu.
            server_was_running = False
            _uninstall_log(f"Warning: nie udało się sprawdzić statusu PG: {exc}")

    # Krok 2: policz pliki (best-effort, przed rmtree).
    removed_count = 0
    try:
        for _ in target.rglob("*"):
            removed_count += 1
    except OSError:
        pass

    # Krok 3: usun katalog.
    try:
        shutil.rmtree(target, ignore_errors=True)
    except Exception as exc:
        return UninstallResult(
            success=False,
            install_dir=target,
            removed_files=0,
            server_was_running=server_was_running,
            error=f"shutil.rmtree sie nie powiodlo: {exc}",
        )

    if target.exists():
        # ignore_errors=True schowało błąd — sprawdź czy coś zostało.
        return UninstallResult(
            success=False,
            install_dir=target,
            removed_files=0,
            server_was_running=server_was_running,
            error="Katalog nadal istnieje po shutil.rmtree (cos trzyma pliki otwarte).",
        )

    return UninstallResult(
        success=True,
        install_dir=target,
        removed_files=removed_count,
        server_was_running=server_was_running,
    )


def _uninstall_log(message: str) -> None:
    """Loguje ostrzeżenie z uninstall (best-effort, nie rzuca).

    W produkcji powinien być zastąpiony przez module-level ``logging``.
    Na razie: print stderr dla widoczności w launcherze.
    """
    import sys
    print(f"[pg_portable_service] {message}", file=sys.stderr)


def verify_pg_archive_checksum(archive_path: Path, expected_sha256: str) -> bool:
    """Weryfikuje SHA256 pobranego archiwum.

    Args:
        archive_path: ścieżka do pliku archiwum.
        expected_sha256: oczekiwany hash w formacie hex (``hashlib``).

    Returns:
        ``True`` jeśli hash pliku zgadza się z ``expected_sha256``.
        ``False`` w przypadku niezgodności lub braku pliku.
    """
    archive = Path(archive_path)
    if not archive.is_file():
        return False
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return False

    digest = hashlib.sha256()
    with open(archive, "rb") as fh:
        for block in iter(lambda: fh.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest() == expected
