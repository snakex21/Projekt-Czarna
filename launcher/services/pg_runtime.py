"""Runtime portable PostgreSQL — serwis startu/stopu serwera.

Moduł dostarcza publiczne API niskiego poziomu potrzebne do
uruchomienia portable PostgreSQL zainstalowanego przez
:mod:`launcher.services.pg_portable_service` i zarządzania jego
procesem z poziomu launchera.

Kontrakt dla kreatora ``DatabaseWizard`` (Etap 3 P2.1):

* :func:`init_pg_data_dir` — inicjalizuje klaster ``initdb`` w katalogu
  danych. Zwraca :class:`StepResult` (status + komunikat).
* :func:`start_pg_server` — uruchamia ``pg_ctl start`` na podanym
  klastrze. Zwraca :class:`ServerHandle` (alias :class:`PgServerHandle`)
  z uchwytem do procesu.
* :func:`stop_pg_server` — grzecznie zatrzymuje serwer na podstawie
  :class:`ServerHandle`. Zwraca :class:`StepResult`.

Wszystkie operacje I/O są mockowalne (``subprocess.Popen``,
``subprocess.run``, ``socket.create_connection``), dzięki czemu
testy integracyjne nie wymagają prawdziwego serwera PG.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass, field


def _build_pg_env(base_env: dict | None, bin_dir: "os.PathLike[str] | None" = None) -> dict:
    """Buduje env dla subprocess.run z binariami PG.

    Real-install bug 1.1.3 #6: ``initdb``/``pg_ctl``/``psql`` potrzebują
    DLL (``icudt*.dll``, ``ssleay32.dll``, ``libeay32.dll`` itp.) z
    ``bin_dir`` na PATH. Windows ``CreateProcess`` nie szuka DLL w katalogu
    executabla — tylko w PATH. Bez tego dostajemy kod 0xC0000135
    (3221225781) = "DLL not found".

    Args:
        base_env: bazowy env (np. ``os.environ.copy()``).
        bin_dir: katalog ``pgsql/bin`` portable PG.

    Returns:
        dict gotowy do przekazania jako ``env=`` w ``subprocess.run``.
    """
    env = (base_env or os.environ).copy()
    if bin_dir is not None:
        bin_dir_str = str(bin_dir)
        # Dodaj na początek PATH (przed systemowym), by mieć pierwszeństwo
        env["PATH"] = bin_dir_str + os.pathsep + env.get("PATH", "")
    return env
from pathlib import Path
from typing import Any, Callable

from launcher.services.pg_portable_service import (
    PortablePgPaths,
    is_pg_initialized,
)


logger_name = "launcher.services.pg_runtime"


ProgressCallback = Callable[[str], None]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepResult:
    """Wynik pojedynczego kroku pipeline'u (init/start/stop)."""

    name: str
    ok: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PgServerConfig:
    """Konfiguracja serwera portable PG (klaster + port)."""

    paths: PortablePgPaths
    port: int = 5432
    username: str = "postgres"
    password: str | None = None
    listen_addresses: str = "127.0.0.1"
    extra_initdb_args: tuple[str, ...] = ()


@dataclass
class ServerHandle:
    """Uchwyt do działającego procesu ``pg_ctl`` portable PostgreSQL.

    Atrybuty:
        pid: PID procesu ``pg_ctl`` zwrócony przez ``subprocess.Popen``.
        proc: referencja do ``subprocess.Popen`` (używana przez stop)
            — ustawiana po udanym starcie.
        data_dir: katalog danych klastra (``PGDATA``).
        port: port TCP, na którym nasłuchuje serwer.
        host: interfejs (``localhost``/``127.0.0.1``/``*``).
        bin_dir: katalog z binariami ``pg_ctl`` (przydatne przy stop).
        config: opcjonalna referencja do :class:`PgServerConfig`.
    """

    pid: int | None
    data_dir: Path
    port: int
    host: str = "127.0.0.1"
    bin_dir: Path | None = None
    proc: subprocess.Popen | None = None
    config: PgServerConfig | None = None


# Alias dla wygody użycia w testach / UI: ``PgServerHandle``.
PgServerHandle = ServerHandle


# ---------------------------------------------------------------------------
# initdb
# ---------------------------------------------------------------------------


def init_pg_data_dir(
    config: PgServerConfig,
    progress_callback: ProgressCallback | None = None,
) -> StepResult:
    """Inicjalizuje klaster ``initdb`` dla portable PostgreSQL.

    Operacja jest idempotentna — jeżeli ``<data_dir>/PG_VERSION`` już
    istnieje, funkcja zwraca ``ok=True`` bez uruchamiania ``initdb``.

    Args:
        config: konfiguracja z :class:`PgServerConfig` (paths + port).
        progress_callback: opcjonalny callback z komunikatami tekstowymi
            o postępie (wywoływany z krótkimi statusami).

    Returns:
        :class:`StepResult` z ``ok=True`` po udanym ``initdb`` lub gdy
        klaster jest już zainicjalizowany. ``ok=False`` gdy brak
        binarki ``initdb`` albo ``initdb`` zwrócił kod błędu.
    """
    paths = config.paths
    data_dir = paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    def _notify(msg: str) -> None:
        if progress_callback is not None:
            progress_callback(msg)

    if is_pg_initialized(data_dir):
        _notify(f"Klaster PG już zainicjalizowany w {data_dir}")
        return StepResult(
            name="initdb",
            ok=True,
            message=f"Klaster PG już zainicjalizowany w {data_dir}.",
            details={"data_dir": str(data_dir), "skipped": True},
        )

    if not paths.initdb_path.is_file():
        return StepResult(
            name="initdb",
            ok=False,
            message=(
                f"Brak binarki initdb: {paths.initdb_path}. "
                "Najpierw zainstaluj portable PostgreSQL."
            ),
        )

    args = [
        str(paths.initdb_path),
        "-D", str(data_dir),
        "-U", config.username,
        "--auth=trust",
        "--encoding=UTF8",
        "--locale=C",
    ] + list(config.extra_initdb_args)

    _notify(f"Uruchamiam initdb ({paths.initdb_path.name})...")
    env = _build_pg_env(os.environ, paths.bin_dir)
    if config.password:
        env["PGPASSWORD"] = config.password

    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return StepResult(
            name="initdb",
            ok=False,
            message=f"initdb nie powiódł się (wyjątek): {exc}",
            details={"data_dir": str(data_dir), "returncode": -1},
        )

    if result.returncode != 0:
        return StepResult(
            name="initdb",
            ok=False,
            message=(
                f"initdb zwrócił kod {result.returncode}: "
                f"{(result.stderr or result.stdout or '').strip()[:400]}"
            ),
            details={
                "data_dir": str(data_dir),
                "returncode": result.returncode,
                "stderr_tail": (result.stderr or "")[-400:],
            },
        )

    return StepResult(
        name="initdb",
        ok=True,
        message=f"Klaster PG zainicjalizowany w {data_dir}.",
        details={"data_dir": str(data_dir), "returncode": 0},
    )


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------


def start_pg_server(
    config: PgServerConfig,
    wait_ready: bool = True,
    ready_timeout: float = 30.0,
    progress_callback: ProgressCallback | None = None,
) -> ServerHandle:
    """Uruchamia serwer portable PostgreSQL (``pg_ctl start``).

    Args:
        config: konfiguracja z :class:`PgServerConfig`.
        wait_ready: czy czekać aż port zacznie akceptować połączenia.
        ready_timeout: limit czasu w sekundach na readiness check.
        progress_callback: opcjonalny callback postępu.

    Returns:
        :class:`ServerHandle` z referencją do procesu ``Popen`` i
        uzupełnionymi metadanymi (``pid``, ``port``, ``data_dir``).

    Raises:
        RuntimeError: gdy ``pg_ctl`` nie istnieje lub zwrócił błąd.
    """
    paths = config.paths
    if not paths.pg_ctl_path.is_file():
        raise RuntimeError(
            f"Brak binarki pg_ctl: {paths.pg_ctl_path}. "
            "Najpierw zainstaluj portable PostgreSQL."
        )

    log_file = paths.data_dir / "postmaster.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    pg_options = f"-p {config.port} -h {config.listen_addresses}"
    args = [
        str(paths.pg_ctl_path),
        "-D", str(paths.data_dir),
        "-l", str(log_file),
        "-o", pg_options,
        "start",
    ]

    if progress_callback is not None:
        progress_callback(
            f"Uruchamiam pg_ctl (port={config.port}, "
            f"data_dir={paths.data_dir})..."
        )

    proc = subprocess.Popen(args, env=_build_pg_env(os.environ, paths.bin_dir))

    handle = ServerHandle(
        pid=proc.pid,
        proc=proc,
        data_dir=paths.data_dir,
        port=config.port,
        host=config.listen_addresses,
        bin_dir=paths.bin_dir,
        config=config,
    )

    if wait_ready:
        if not wait_for_pg_ready(config, timeout=ready_timeout):
            # Sprawdź czy pg_ctl nie umarł w trakcie startup (np. błąd w configu)
            poll_result = proc.poll()
            if poll_result is not None:
                raise RuntimeError(
                    f"pg_ctl zakończył się kodem {poll_result} podczas startupu. "
                    f"Sprawdź log: {log_file}"
                )
            # Nie zabijamy serwera — UI może chcieć spróbować ponownie.
            if progress_callback is not None:
                progress_callback(
                    f"Serwer nie odpowiada po {ready_timeout:.0f}s, "
                    "sprawdź log: "
                    f"{log_file}"
                )
        else:
            # wait_ready == True — ale sprawdź czy pg_ctl nie wyrzucił błędu.
            # Real-install bug 1.1.3: pg_ctl start -w po sukcesie wychodzi
            # z kodem 0 (normalne), ale kod != 0 po ready to anomalia.
            poll_result = proc.poll()
            if poll_result is not None and poll_result != 0:
                raise RuntimeError(
                    f"pg_ctl zakończył się kodem {poll_result} mimo gotowości. "
                    f"Sprawdź log: {log_file}"
                )
            if progress_callback is not None:
                progress_callback(
                    f"Serwer PG nasłuchuje na {config.listen_addresses}:{config.port}."
                )

    return handle


def stop_pg_server(
    handle: ServerHandle,
    mode: str = "fast",
    timeout: float = 30.0,
    progress_callback: ProgressCallback | None = None,
) -> StepResult:
    """Zatrzymuje serwer portable PostgreSQL.

    Args:
        handle: uchwyt zwrócony przez :func:`start_pg_server`.
        mode: tryb zatrzymania (``fast``/``smart``/``immediate``).
        timeout: limit czasu w sekundach na graceful shutdown.

    Returns:
        :class:`StepResult` z ``ok=True`` gdy serwer został zatrzymany
        (kod wyjścia 0). ``ok=False`` w przeciwnym razie.

    Fallback chain (real-install bug fix 1.1.3):
        1. ``pg_ctl stop -m fast`` (graceful, zamyka transakcje)
        2. ``pg_ctl stop -m immediate`` (twardy kill bez rollbacku)
        3. ``handle.proc.terminate()`` (SIGTERM do pg_ctl)
        4. ``handle.proc.kill()`` / ``taskkill /F`` (SIGKILL/Windows)
        Każdy krok z własnym timeoutem. Pierwszy sukces wygrywa.

    Note:
        Przed 1.1.3 ta funkcja robiła tylko ``handle.proc.wait(timeout)``
        — co wieszało się gdy baza była w "starting up" i ``pg_ctl``
        subprocess czekał na "ready".
    """
    if handle.proc is None:
        return StepResult(
            name="stop",
            ok=False,
            message="Brak referencji do procesu pg_ctl w uchwycie.",
        )

    if progress_callback is not None:
        progress_callback(f"Zatrzymuję serwer PG (pid={handle.pid})...")

    # Szybki exit: jeśli proces już zakończony, OK
    if handle.proc.poll() is not None:
        return StepResult(
            name="stop",
            ok=True,
            message=f"Proces pg_ctl już zakończony (returncode={handle.proc.returncode}).",
            details={"returncode": handle.proc.returncode, "pid": handle.pid, "was_already_dead": True},
        )

    # Strategia: wołaj pg_ctl stop jako NOWY subprocess (nie proc.wait())
    # bo pg_ctl start z -w wisi aż do "ready" i proc.wait() może wisieć.
    pg_ctl_path = handle.config.paths.pg_ctl_path if handle.config else None
    data_dir = handle.data_dir
    # PATH musi zawierac bin_dir (DLL dla pg_ctl) — real-install bug 1.1.3 #6
    bin_dir = handle.config.paths.bin_dir if handle.config else None
    stop_env = _build_pg_env(os.environ, bin_dir)

    if pg_ctl_path and pg_ctl_path.is_file() and data_dir:
        # Krok 1: pg_ctl stop -m fast
        try:
            if progress_callback:
                progress_callback(f"pg_ctl stop -m fast (timeout={timeout:.0f}s)...")
            r = subprocess.run(
                [str(pg_ctl_path), "-D", str(data_dir), "stop", "-m", mode],
                capture_output=True, text=True, timeout=timeout, env=stop_env,
            )
            if r.returncode == 0 and handle.proc.poll() is not None:
                return StepResult(
                    name="stop", ok=True,
                    message=f"pg_ctl stop -m {mode}: OK (returncode=0).",
                    details={"returncode": 0, "mode": mode, "pid": handle.pid, "method": "pg_ctl_fast"},
                )
        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback(f"pg_ctl stop -m {mode} timeout, probuje immediate...")

        # Krok 2: pg_ctl stop -m immediate (twardy)
        try:
            r = subprocess.run(
                [str(pg_ctl_path), "-D", str(data_dir), "stop", "-m", "immediate"],
                capture_output=True, text=True, timeout=10.0, env=stop_env,
            )
            if r.returncode == 0 and handle.proc.poll() is not None:
                return StepResult(
                    name="stop", ok=True,
                    message="pg_ctl stop -m immediate: OK.",
                    details={"returncode": 0, "mode": "immediate", "pid": handle.pid, "method": "pg_ctl_immediate"},
                )
        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback("pg_ctl stop -m immediate timeout, probuje terminate()...")

    # Krok 3: terminate() (SIGTERM)
    try:
        handle.proc.terminate()
        try:
            handle.proc.wait(timeout=5.0)
            return StepResult(
                name="stop", ok=True,
                message="terminate(): OK.",
                details={"returncode": 0, "pid": handle.pid, "method": "terminate"},
            )
        except subprocess.TimeoutExpired:
            pass
    except OSError:
        pass

    # Krok 4: kill() / taskkill /F (Windows)
    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(handle.pid)],
                capture_output=True, text=True, timeout=5.0,
            )
        except (subprocess.TimeoutExpired, OSError):
            pass
    else:
        try:
            handle.proc.kill()
        except OSError:
            pass

    # Czekaj na smierc
    try:
        handle.proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        return StepResult(
            name="stop", ok=False,
            message=(
                f"Serwer PG (pid={handle.pid}) nie zatrzymał się nawet po kill(). "
                f"Proces może być zombie."
            ),
            details={"pid": handle.pid, "method": "force_kill_failed"},
        )

    return StepResult(
        name="stop", ok=True,
        message="Wymuszono zatrzymanie (force kill).",
        details={"returncode": -1, "pid": handle.pid, "method": "force_kill"},
    )

    if progress_callback is not None:
        progress_callback(f"Zatrzymuję serwer PG (pid={handle.pid})...")

    try:
        returncode = handle.proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return StepResult(
            name="stop",
            ok=False,
            message=(
                f"Serwer PG (pid={handle.pid}) nie zatrzymał się "
                f"w ciągu {timeout:.0f}s."
            ),
            details={"timeout": timeout, "exception": str(exc)},
        )
    except OSError as exc:
        return StepResult(
            name="stop",
            ok=False,
            message=f"Błąd systemowy przy zatrzymywaniu PG: {exc}",
        )

    if returncode != 0:
        return StepResult(
            name="stop",
            ok=False,
            message=(
                f"pg_ctl stop zwrócił kod {returncode} "
                f"(mode={mode!r}, pid={handle.pid})."
            ),
            details={"returncode": returncode, "mode": mode},
        )

    return StepResult(
        name="stop",
        ok=True,
        message=f"Serwer PG zatrzymany (pid={handle.pid}, mode={mode!r}).",
        details={"returncode": 0, "mode": mode, "pid": handle.pid},
    )


# ---------------------------------------------------------------------------
# Predykaty / helpers
# ---------------------------------------------------------------------------


def is_pg_server_running(handle: ServerHandle) -> bool:
    """Sprawdza czy serwer PG nadal nasłuchuje na porcie.

    Real-install bug 1.1.3: ``pg_ctl start -w`` po udanym starcie wychodzi
    z kodem 0, więc ``handle.proc.poll()`` NIE służy do weryfikacji
    działania serwera. Sprawdzamy port (TCP socket).
    """
    if handle.proc is None:
        return False
    port = handle.port
    if not port:
        return False
    try:
        with socket.create_connection(
            ("127.0.0.1", port), timeout=0.5
        ) as _:
            return True
    except OSError:
        return False


def wait_for_pg_ready(
    config: PgServerConfig,
    timeout: float = 30.0,
    interval: float = 0.5,
) -> bool:
    """Czeka aż baza PG faktycznie akceptuje zapytania (nie tylko socket bind).

    Strategia dwuetapowa (szybka + pewna):
        1. Najpierw szybki TCP connect — odpada gdy port jeszcze nie słucha.
        2. Gdy socket OK, próbuje ``psql -c "SELECT 1"`` żeby potwierdzić
            że baza przeszła recovery / startup i akceptuje queries.
            Dlaczego oba? Bo PG w recovery binduje port natychmiast
            ale odpowiada "FATAL: the database system is starting up" —
            sam socket to za mało.

    Args:
        config: konfiguracja z portem i hostem.
        timeout: maksymalny czas oczekiwania w sekundach.
        interval: odstęp między próbami w sekundach.

    Returns:
        ``True`` jeśli ``SELECT 1`` zwróciło ``1`` przed upływem ``timeout``.
        ``False`` jeśli timeout, port nie słucha, lub psql zawiedzie.
    """
    host = config.listen_addresses
    if host in ("*", "0.0.0.0"):
        host = "127.0.0.1"

    deadline = time.time() + timeout
    socket_open = False
    while time.time() < deadline:
        # Etap 1: szybki socket check
        try:
            with socket.create_connection(
                (host, config.port),
                timeout=min(1.0, max(0.1, interval)),
            ):
                socket_open = True
                break
        except OSError:
            time.sleep(interval)

    if not socket_open:
        return False

    # Etap 2: prawdziwy query check (psql -c "SELECT 1")
    # Dopóki nie ma bazy 'postgres' (albo innej domyślnej), to nie zadziała,
    # ale SELECT 1 nie wymaga konkretnej bazy - działa na maintenance DB.
    psql_bin = config.paths.bin_dir / ("psql.exe" if platform.system() == "Windows" else "psql")
    if not psql_bin.is_file():
        # Brak psql w binariach — wracamy do socket-only check
        return True

    while time.time() < deadline:
        try:
            result = subprocess.run(
                [
                    str(psql_bin),
                    "-h", host,
                    "-p", str(config.port),
                    "-U", config.username,
                    "-d", "postgres",
                    "-c", "SELECT 1;",
                ],
                capture_output=True,
                text=True,
                timeout=min(2.0, max(0.5, interval * 2)),
                env=_build_pg_env(
                    {"PGPASSWORD": config.password or ""},
                    config.paths.bin_dir,
                ),
            )
            if result.returncode == 0 and "1" in result.stdout:
                return True
        except (subprocess.TimeoutExpired, OSError):
            pass
        time.sleep(interval)
    return False


def get_postmaster_pid(data_dir: Path) -> int | None:
    """Zwraca PID postmastera z pliku ``postmaster.pid``.

    PG zapisuje ten plik przy starcie; pierwsza linia zawiera PID.

    Args:
        data_dir: katalog danych klastra (``PGDATA``).

    Returns:
        :class:`int` z PID lub ``None`` gdy plik nie istnieje / jest
        nieprawidłowy.
    """
    pid_file = Path(data_dir) / "postmaster.pid"
    if not pid_file.is_file():
        return None
    try:
        first_line = pid_file.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()[0]
        return int(first_line.strip())
    except (ValueError, IndexError, OSError):
        return None


def remove_pg_data_dir(data_dir: Path) -> bool:
    """Usuwa katalog danych PG (z zabezpieczeniem przed przypadkowym rm).

    Args:
        data_dir: katalog danych do usunięcia.

    Returns:
        ``True`` gdy katalog nie istnieje lub został pomyślnie
        usunięty. ``False`` gdy ścieżka nie wygląda na katalog danych
        PG (nazwa musi być ``data``/``pgdata``/``pgsql/data``) albo
        usunięcie się nie powiodło.
    """
    target = Path(data_dir)
    if not target.exists():
        return True

    name = target.name.lower()
    parent = target.parent.name.lower() if target.parent else ""
    if name not in ("data", "pgdata") and not (
        parent in ("pgsql", "postgresql") and name == "data"
    ):
        return False

    try:
        shutil.rmtree(target)
        return True
    except OSError:
        return False
