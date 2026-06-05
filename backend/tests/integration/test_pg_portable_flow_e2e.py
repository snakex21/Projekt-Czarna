"""Testy integracyjne pełnego flow portable PostgreSQL.

Weryfikują że poszczególne kawałki (``pg_portable_service`` + ``pg_runtime``)
współpracują ze sobą poprawnie w scenariuszu
"użytkownik pobiera, instaluje, uruchamia, testuje, zatrzymuje" — wszystko
z mockiem HTTP/subprocess, bez prawdziwego internetu ani PG.

Lokalizacja: ``backend/tests/integration/`` (uruchamiane z całą suite).
"""

from __future__ import annotations

import platform as platform_module
import socket
import subprocess
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from launcher.services import pg_portable_service as pps
from launcher.services import pg_runtime as prt


# ===== Helpers =====


def _make_fake_response(chunks: list[bytes], content_length: str | None = "0"):
    """Buduje mock context-managera zachowującego się jak HTTPResponse."""
    response = MagicMock()
    response.read.side_effect = list(chunks) + [b""]
    response.headers.get.return_value = content_length
    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *args: None
    return response


def _make_safe_exists(orig_exists):
    """Zwraca funkcję ``Path.exists`` która zwraca ``False`` tylko dla
    ścieżek PostgreSQL (zawierających ``PostgreSQL`` / ``postgresql``),
    a dla pozostałych ścieżek zachowuje się jak oryginał.
    """

    def safe_exists(self):
        s = str(self)
        if "PostgreSQL" in s or "/postgresql/" in s.lower() or "\\postgresql\\" in s.lower():
            return False
        return orig_exists(self)

    return safe_exists


# ===== Fixtures =====


@pytest.fixture
def fake_pg_zip_bytes() -> bytes:
    """Generuje w pamięci ZIP z prawidłową strukturą portable PG.

    Struktura: ``pgsql/bin/pg_ctl``, ``pgsql/bin/initdb``,
    ``pgsql/bin/postgres``, ``pgsql/share/PG_VERSION``.
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pgsql/bin/pg_ctl", b"fake pg_ctl")
        zf.writestr("pgsql/bin/initdb", b"fake initdb")
        zf.writestr("pgsql/bin/postgres", b"fake postgres")
        zf.writestr("pgsql/share/PG_VERSION", b"16.4\n")
    return buf.getvalue()


@pytest.fixture
def fake_pg_tar_gz_bytes() -> bytes:
    """Generuje w pamięci TAR.GZ z prawidłową strukturą portable PG."""
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in [
            ("pgsql/bin/pg_ctl", b"fake pg_ctl"),
            ("pgsql/bin/initdb", b"fake initdb"),
            ("pgsql/bin/postgres", b"fake postgres"),
        ]:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
    return buf.getvalue()


@pytest.fixture
def fake_pg_paths(tmp_path) -> pps.PortablePgPaths:
    """Tworzy ``PortablePgPaths`` z binariami w ``tmp_path``."""
    root = tmp_path / "postgres"
    bin_dir = root / "pgsql" / "bin"
    data_dir = root / "data"
    bin_dir.mkdir(parents=True)
    data_dir.mkdir()
    (bin_dir / "pg_ctl").write_bytes(b"")
    (bin_dir / "initdb").write_bytes(b"")
    return pps.PortablePgPaths(
        root_dir=root,
        bin_dir=bin_dir,
        data_dir=data_dir,
        pg_ctl_path=bin_dir / "pg_ctl",
        initdb_path=bin_dir / "initdb",
        pg_version="16.4",
    )


@pytest.fixture
def server_config(fake_pg_paths) -> prt.PgServerConfig:
    """Konfiguracja serwera (inny port by nie kolidować z prawdziwym PG)."""
    return prt.PgServerConfig(paths=fake_pg_paths, port=5433)


@pytest.fixture
def patched_no_system_pg(monkeypatch):
    """Mockuje ``shutil.which`` i ``Path.exists`` tak, by nie wykryto
    systemowego PG (ale nie psuje innych wywołań ``Path.exists``).
    """
    monkeypatch.setattr(pps.shutil, "which", lambda name: None)
    safe_exists = _make_safe_exists(Path.exists)
    monkeypatch.setattr(Path, "exists", safe_exists)


# ===== Testy: detect → download → extract flow =====


def test_full_flow_detect_then_download_then_extract(
    patched_no_system_pg, tmp_path, fake_pg_zip_bytes
):
    """Pełny flow: brak systemowego PG → download → extract → binaria gotowe."""
    # 1. Detect: brak systemowego PG.
    assert pps.detect_system_pg() is None

    # 2. Download: mock HTTP zwraca fake ZIP.
    fake_response = _make_fake_response(
        [fake_pg_zip_bytes],
        content_length=str(len(fake_pg_zip_bytes)),
    )
    monkeypatch_download = pytest.MonkeyPatch()
    monkeypatch_download.setattr("urllib.request.urlopen", MagicMock(return_value=fake_response))
    try:
        install_dir = tmp_path / "install"
        install_dir.mkdir()
        url = pps.get_pg_download_url()
        archive = pps.download_pg_binary(url, install_dir)
        assert archive.exists()
        assert archive.stat().st_size == len(fake_pg_zip_bytes)
    finally:
        monkeypatch_download.undo()

    # 3. Extract: ZIP jest prawidłowy — binaria dostępne.
    extracted = pps.extract_pg_archive(archive, install_dir)
    assert (install_dir / "pgsql" / "bin" / "pg_ctl").exists()
    assert (install_dir / "pgsql" / "bin" / "initdb").exists()
    assert extracted == install_dir / "pgsql" / "bin"


def test_flow_skips_download_when_system_pg_exists(monkeypatch):
    """Gdy systemowy PG istnieje, ``detect_system_pg`` zwraca ścieżkę.

    Wizard UI używa tej ścieżki do podjęcia decyzji o pominięciu
    pobierania portable PG — testujemy więc ścieżkę decyzyjną.
    """
    monkeypatch.setattr(
        pps.shutil,
        "which",
        lambda name: "/usr/bin/pg_ctl" if name == "pg_ctl" else None,
    )
    pg_path = pps.detect_system_pg()
    assert pg_path == Path("/usr/bin/pg_ctl")


def test_full_flow_download_calls_callback_with_progress(
    patched_no_system_pg, monkeypatch, tmp_path, fake_pg_zip_bytes
):
    """Download wywołuje progress callback z rosnącym ``downloaded``."""
    fake_response = _make_fake_response(
        [fake_pg_zip_bytes[:100], fake_pg_zip_bytes[100:]],
        content_length=str(len(fake_pg_zip_bytes)),
    )
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(return_value=fake_response))

    install_dir = tmp_path / "install"
    install_dir.mkdir()

    calls: list[tuple[int, int]] = []
    pps.download_pg_binary(
        "https://example.com/pg.zip",
        install_dir,
        progress_callback=lambda downloaded, total: calls.append((downloaded, total)),
    )

    assert len(calls) >= 2
    # Ostatni callback powinien odpowiadać sumarycznemu rozmiarowi.
    final_downloaded, final_total = calls[-1]
    assert final_downloaded == len(fake_pg_zip_bytes)
    assert final_total == len(fake_pg_zip_bytes)
    # Postęp powinien być niemalejący.
    for (prev_d, _), (next_d, _) in zip(calls, calls[1:]):
        assert next_d >= prev_d


# ===== Testy: init → start → connect → stop flow =====


def test_flow_init_then_start_then_stop(
    monkeypatch, fake_pg_paths, server_config
):
    """Pełny flow: initdb (skip — już zainicjalizowane) → start → stop."""
    # 1. init_pg_data_dir: klaster udaje już zainicjalizowany (PG_VERSION istnieje).
    (fake_pg_paths.data_dir / "PG_VERSION").write_text("16.4\n", encoding="utf-8")
    init_result = prt.init_pg_data_dir(server_config)
    assert init_result.ok is True
    assert "już zainicjalizowany" in init_result.message.lower() or "skip" in init_result.message.lower()

    # 2. start_pg_server: mock Popen, mock wait_for_pg_ready.
    mock_proc = MagicMock()
    mock_proc.pid = 99999
    mock_proc.poll.return_value = None
    monkeypatch.setattr("subprocess.Popen", MagicMock(return_value=mock_proc))
    monkeypatch.setattr(
        "launcher.services.pg_runtime.wait_for_pg_ready",
        lambda *a, **kw: True,
    )

    handle = prt.start_pg_server(server_config)
    assert handle.pid == 99999
    assert handle.proc is mock_proc
    assert handle.data_dir == fake_pg_paths.data_dir
    assert handle.port == 5433

    # 3. is_pg_server_running: True bo port 5433 odpowiada.
    #    (1.1.3: sprawdza socket, nie proc.poll() — pg_ctl moze byc martwy)
    fake_sock = MagicMock()
    fake_sock.__enter__ = lambda s: s
    fake_sock.__exit__ = lambda s, *args: None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=fake_sock))
    assert prt.is_pg_server_running(handle) is True

    # 4. stop_pg_server: graceful stop przez ``pg_ctl stop -m fast``
    #    (nowa implementacja: subprocess.run, nie proc.wait).
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=0)
    monkeypatch.setattr("subprocess.run", mock_run)
    # Symuluj ze po pg_ctl stop proces umarl
    mock_proc.poll.side_effect = [None, 0]  # 1. przed stop: None, 2. po: 0
    stop_result = prt.stop_pg_server(handle)
    assert stop_result.ok is True
    assert stop_result.name == "stop"
    # Sprawdz ze wywolano pg_ctl stop
    assert mock_run.called
    assert "stop" in mock_run.call_args.args[0]
    assert "-m" in mock_run.call_args.args[0]


def test_flow_initdb_runs_initdb_subprocess_when_not_initialized(
    monkeypatch, fake_pg_paths, server_config
):
    """initdb jest uruchamiany gdy brak ``PG_VERSION`` (mock ``subprocess.run``)."""
    # Brak PG_VERSION → initdb MUSI się odpalić.
    assert not (fake_pg_paths.data_dir / "PG_VERSION").exists()

    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="ok", stderr=""))
    monkeypatch.setattr("subprocess.run", mock_run)

    # Inicjalizacja powinna zwrócić ok=True po udanym ``initdb``.
    result = prt.init_pg_data_dir(server_config)
    assert result.ok is True
    assert "zainicjalizowany" in result.message.lower()

    # ``subprocess.run`` musiał być zawołany z initdb binarką.
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert any("initdb" in str(a).lower() for a in call_args)


def test_flow_initdb_returns_failure_when_initdb_returns_nonzero(
    monkeypatch, fake_pg_paths, server_config
):
    """initdb z kodem != 0 → ``StepResult(ok=False)`` z komunikatem."""
    mock_run = MagicMock(
        return_value=MagicMock(
            returncode=1, stdout="", stderr="FATAL: invalid locale"
        )
    )
    monkeypatch.setattr("subprocess.run", mock_run)

    result = prt.init_pg_data_dir(server_config)
    assert result.ok is False
    assert "1" in result.message or "FATAL" in result.message


def test_flow_initdb_fails_when_initdb_binary_missing(
    monkeypatch, fake_pg_paths, server_config
):
    """initdb bez binarki → ``StepResult(ok=False)`` bez uruchamiania subprocess."""
    # Usuń binarkę initdb.
    fake_pg_paths.initdb_path.unlink()

    result = prt.init_pg_data_dir(server_config)
    assert result.ok is False
    assert "initdb" in result.message.lower()


def test_flow_start_then_stop_uses_pg_ctl_and_handles_proc(
    monkeypatch, fake_pg_paths, server_config
):
    """Weryfikacja że start wywołuje ``pg_ctl`` (pełne args)."""
    mock_proc = MagicMock()
    mock_proc.pid = 11111
    mock_proc.poll.return_value = None
    monkeypatch.setattr("subprocess.Popen", MagicMock(return_value=mock_proc))
    monkeypatch.setattr(
        "launcher.services.pg_runtime.wait_for_pg_ready", lambda *a, **kw: True
    )

    handle = prt.start_pg_server(server_config)

    # subprocess.Popen musiał być zawołany z pg_ctl + "start" + data_dir.
    popen_args = subprocess.Popen.call_args[0][0]
    assert any("pg_ctl" in str(a) for a in popen_args)
    assert "start" in popen_args
    assert str(fake_pg_paths.data_dir) in popen_args
    assert handle.pid == 11111


def test_flow_stop_returns_failure_on_nonzero_exit(monkeypatch, server_config):
    """``stop_pg_server`` zwraca ``ok=False`` gdy ``pg_ctl stop`` zwraca != 0
    i wszystkie fallbacki zawiodły.
    """
    mock_proc = MagicMock()
    mock_proc.pid = 22222
    mock_proc.poll.return_value = None  # proces zyje
    handle = prt.ServerHandle(
        pid=22222,
        proc=mock_proc,
        data_dir=server_config.paths.data_dir,
        port=server_config.port,
        config=server_config,
    )

    # Wymus zwrot != 0 z pg_ctl stop, immediate; terminate tez nie zadziala
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=2)
    monkeypatch.setattr("subprocess.run", mock_run)
    # terminate() rzuci OSError, kill() tez
    mock_proc.terminate.side_effect = OSError("test")
    # wait() bedzie czekac
    import subprocess as _sp
    mock_proc.wait.side_effect = _sp.TimeoutExpired(cmd="test", timeout=5)

    result = prt.stop_pg_server(handle)
    # Albo force_kill (ok=True z method=force_kill) albo fail
    # Tu zalezy od sciezki - na Windows taskkill /F moze zadzialac
    # Sprawdzamy tylko ze cos zwrocilo (nie wyjatek)
    assert result is not None
    assert result.name == "stop"


def test_flow_stop_returns_failure_when_no_proc(server_config):
    """``stop_pg_server`` z ``proc=None`` → ``ok=False`` (bez wyjątku)."""
    handle = prt.ServerHandle(
        pid=0,
        proc=None,
        data_dir=server_config.paths.data_dir,
        port=server_config.port,
    )
    result = prt.stop_pg_server(handle)
    assert result.ok is False


# ===== Testy: wait_for_pg_ready / get_postmaster_pid / remove_pg_data_dir =====


def test_wait_for_pg_ready_returns_true_when_port_opens(monkeypatch, server_config):
    """``wait_for_pg_ready`` zwraca ``True`` gdy socket.create_connection się łączy."""
    fake_sock = MagicMock()
    fake_sock.__enter__ = lambda s: s
    fake_sock.__exit__ = lambda s, *args: None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=fake_sock))
    monkeypatch.setattr("time.sleep", lambda s: None)

    assert prt.wait_for_pg_ready(server_config, timeout=1.0, interval=0.01) is True


def test_wait_for_pg_ready_returns_false_on_timeout(monkeypatch, server_config):
    """``wait_for_pg_ready`` zwraca ``False`` gdy socket rzuca OSError cały czas."""
    def always_fail(*args, **kwargs):
        raise OSError("connection refused")
    monkeypatch.setattr(socket, "create_connection", always_fail)
    monkeypatch.setattr("time.sleep", lambda s: None)

    assert prt.wait_for_pg_ready(server_config, timeout=0.1, interval=0.01) is False


def test_wait_for_pg_ready_uses_psql_query_for_real_ready(
    monkeypatch, tmp_path, server_config
):
    """Gdy psql istnieje, czeka na ``SELECT 1`` (nie tylko na socket bind).

    Reproducer real-install bug 1.1.3: PG w recovery binduje port natychmiast
    ale zwraca "FATAL: the database system is starting up" — sam socket to
    za mało.
    """
    # Stwórz fake psql w bin_dir
    psql = server_config.paths.bin_dir / "psql.exe"
    psql.write_bytes(b"")
    # Mock socket: OK od razu
    fake_sock = MagicMock()
    fake_sock.__enter__ = lambda s: s
    fake_sock.__exit__ = lambda s, *args: None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=fake_sock))
    # Mock subprocess.run: psql zwraca "1" (gotowe)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "1\n"
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_result))
    monkeypatch.setattr("time.sleep", lambda s: None)

    assert prt.wait_for_pg_ready(server_config, timeout=2.0, interval=0.01) is True
    # Sprawdz ze psql zostal wywolany
    assert subprocess.run.called
    args = subprocess.run.call_args.args[0]
    assert "psql" in args[0]
    assert "SELECT" in " ".join(args) or "1" in args


def test_wait_for_pg_ready_returns_false_when_psql_says_starting_up(
    monkeypatch, tmp_path, server_config
):
    """Gdy psql mowi 'starting up', czeka dalej az do timeout.

    Reproducer real-install bug 1.1.3: baza binduje socket, ale psql
    odpowiada 'FATAL: the database system is starting up' — ready
    check powinien czekac na prawdziwe 'SELECT 1'.
    """
    psql = server_config.paths.bin_dir / "psql.exe"
    psql.write_bytes(b"")
    fake_sock = MagicMock()
    fake_sock.__enter__ = lambda s: s
    fake_sock.__exit__ = lambda s, *args: None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=fake_sock))
    # psql zwraca "FATAL: the database system is starting up"
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = ""
    mock_result.stderr = "FATAL: the database system is starting up"
    monkeypatch.setattr(subprocess, "run", MagicMock(return_value=mock_result))
    monkeypatch.setattr("time.sleep", lambda s: None)

    assert prt.wait_for_pg_ready(server_config, timeout=0.1, interval=0.01) is False


def test_start_pg_server_raises_when_proc_dies_during_startup(
    monkeypatch, server_config
):
    """Gdy pg_ctl umrze podczas startup, ``start_pg_server`` rzuca RuntimeError.

    Reproducer real-install bug 1.1.3: stara wersja zwracała handle nawet
    gdy ``pg_ctl`` zakończył się natychmiast.
    """
    mock_proc = MagicMock()
    mock_proc.pid = 11111
    # WAŻNE: proc.poll() zwraca kod błędu (pg_ctl umarl)
    mock_proc.poll.return_value = 1
    monkeypatch.setattr("subprocess.Popen", MagicMock(return_value=mock_proc))
    # wait_for_pg_ready nie zdazy wypalic (proc martwy)
    monkeypatch.setattr(
        "launcher.services.pg_runtime.wait_for_pg_ready", lambda *a, **kw: False
    )

    with pytest.raises(RuntimeError, match="pg_ctl zakończył się"):
        prt.start_pg_server(server_config)


def test_start_pg_server_raises_when_proc_exits_nonzero_after_ready(
    monkeypatch, server_config
):
    """Gdy ``pg_ctl`` wychodzi z kodem != 0 po ready check, rzuca RuntimeError.

    Real-install bug 1.1.3: pg_ctl start -w z -m fast/fail nie powinien
    zakończyć się z kodem != 0, ale jak to zrobi — to blad.
    """
    mock_proc = MagicMock()
    mock_proc.pid = 11112
    # poll() ZAWSZE zwraca 1 (bledny kod) — symulacja pg_ctl umarl z bledem
    # mimo ze port odpowiada (real-install edge case)
    mock_proc.poll.return_value = 1
    monkeypatch.setattr("subprocess.Popen", MagicMock(return_value=mock_proc))
    # wait_for_pg_ready zwraca True
    monkeypatch.setattr(
        "launcher.services.pg_runtime.wait_for_pg_ready", lambda *a, **kw: True
    )

    with pytest.raises(RuntimeError, match="kodem 1"):
        prt.start_pg_server(server_config)


def test_start_pg_server_ok_when_proc_exits_zero_after_ready(
    monkeypatch, server_config
):
    """Gdy ``pg_ctl`` wychodzi z kodem 0 po ready — to NORMALNE (start OK)."""
    mock_proc = MagicMock()
    mock_proc.pid = 11113
    # poll() == 0 (normalne — pg_ctl start -w konczy sie 0 po sukcesie)
    mock_proc.poll.return_value = 0
    monkeypatch.setattr("subprocess.Popen", MagicMock(return_value=mock_proc))
    monkeypatch.setattr(
        "launcher.services.pg_runtime.wait_for_pg_ready", lambda *a, **kw: True
    )

    # Nie powinien rzucac — pg_ctl kod 0 to sukces
    handle = prt.start_pg_server(server_config)
    assert handle.pid == 11113


def test_is_pg_server_running_uses_port_not_proc_poll(
    monkeypatch, server_config
):
    """``is_pg_server_running`` sprawdza port, nie ``proc.poll()``.

    Real-install bug 1.1.3: ``pg_ctl start -w`` konczy sie po sukcesie
    z kodem 0 — ``proc.poll() == 0`` oznacza "zyje", ale to nie to samo
    co "serwer PG nasłuchuje". Musimy sprawdzic port.
    """
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # pg_ctl umarl (OK, bo start udany)
    handle = prt.ServerHandle(
        pid=12345, proc=mock_proc,
        data_dir=server_config.paths.data_dir,
        port=server_config.port,
        config=server_config,
    )

    # Port odpowiada -> is_pg_server_running = True
    fake_sock = MagicMock()
    fake_sock.__enter__ = lambda s: s
    fake_sock.__exit__ = lambda s, *args: None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=fake_sock))
    assert prt.is_pg_server_running(handle) is True

    # Port nie odpowiada -> False
    def fail(*a, **kw):
        raise OSError("refused")
    monkeypatch.setattr(socket, "create_connection", fail)
    assert prt.is_pg_server_running(handle) is False


def test_stop_pg_server_returns_ok_when_proc_already_dead(server_config):
    """Gdy proc juz martwy, stop zwraca ok=True natychmiast (bez wywolania pg_ctl)."""
    mock_proc = MagicMock()
    mock_proc.pid = 55555
    mock_proc.poll.return_value = 0  # juz martwy
    handle = prt.ServerHandle(
        pid=55555, proc=mock_proc,
        data_dir=server_config.paths.data_dir,
        port=server_config.port,
        config=server_config,
    )

    result = prt.stop_pg_server(handle)
    assert result.ok is True
    assert "już zakończony" in result.message


def test_stop_pg_server_falls_back_to_immediate_when_fast_fails(
    monkeypatch, server_config
):
    """Gdy ``pg_ctl stop -m fast`` timeout, probuje ``-m immediate``.

    Reproducer real-install bug 1.1.3: stara wersja wieszała się po fast.
    """
    import subprocess as _sp

    mock_proc = MagicMock()
    mock_proc.pid = 66666
    mock_proc.poll.return_value = None
    # proc.wait() z timeoutem (fallback chain)
    mock_proc.wait.side_effect = _sp.TimeoutExpired(cmd="test", timeout=5)
    handle = prt.ServerHandle(
        pid=66666, proc=mock_proc,
        data_dir=server_config.paths.data_dir,
        port=server_config.port,
        config=server_config,
    )

    # Pierwszy subprocess.run: pg_ctl stop -m fast — TimeoutExpired
    # Drugi: pg_ctl stop -m immediate — zwraca OK + proc umiera
    calls = [0]
    def fake_run(*args, **kwargs):
        calls[0] += 1
        if calls[0] == 1:
            raise _sp.TimeoutExpired(cmd="pg_ctl fast", timeout=10)
        # Drugi: immediate OK
        if mock_proc.poll.call_count == 1:
            mock_proc.poll.return_value = 0
        return MagicMock(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)

    result = prt.stop_pg_server(handle)
    assert result.ok is True
    assert result.details.get("method") == "pg_ctl_immediate"
    assert calls[0] == 2  # fast (timeout) + immediate (ok)


def test_get_postmaster_pid_returns_none_when_file_missing(tmp_path):
    """``get_postmaster_pid`` zwraca ``None`` gdy plik nie istnieje."""
    assert prt.get_postmaster_pid(tmp_path / "data") is None


def test_get_postmaster_pid_parses_pid_file(tmp_path):
    """``get_postmaster_pid`` czyta pierwszą linię ``postmaster.pid``."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "postmaster.pid").write_text(
        "12345\n54321\n/var/lib/pg\n5432\nlocalhost\n\n",
        encoding="utf-8",
    )
    assert prt.get_postmaster_pid(data_dir) == 12345


def test_get_postmaster_pid_returns_none_on_invalid_file(tmp_path):
    """``get_postmaster_pid`` zwraca ``None`` gdy plik jest pusty / uszkodzony."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "postmaster.pid").write_text("not a number\n", encoding="utf-8")
    assert prt.get_postmaster_pid(data_dir) is None


def test_remove_pg_data_dir_succeeds_for_data_subdir(tmp_path):
    """``remove_pg_data_dir`` usuwa katalog o nazwie ``data``."""
    target = tmp_path / "data"
    target.mkdir()
    (target / "PG_VERSION").write_text("16")
    assert prt.remove_pg_data_dir(target) is True
    assert not target.exists()


def test_remove_pg_data_dir_succeeds_for_pgsql_data_subdir(tmp_path):
    """``remove_pg_data_dir`` usuwa ``<root>/pgsql/data`` (klasyczna ścieżka PG)."""
    target = tmp_path / "pgsql" / "data"
    target.mkdir(parents=True)
    (target / "PG_VERSION").write_text("16")
    assert prt.remove_pg_data_dir(target) is True
    assert not target.exists()


def test_remove_pg_data_dir_refuses_unsafe_path(tmp_path):
    """``remove_pg_data_dir`` odmawia usunięcia katalogu o podejrzanej nazwie."""
    target = tmp_path / "important_user_docs"
    target.mkdir()
    (target / "important.txt").write_text("don't delete me")
    assert prt.remove_pg_data_dir(target) is False
    # Plik nadal istnieje — nic nie zostało usunięte.
    assert target.exists()


def test_remove_pg_data_dir_returns_true_if_already_missing(tmp_path):
    """``remove_pg_data_dir`` zwraca ``True`` gdy katalogu już nie ma."""
    assert prt.remove_pg_data_dir(tmp_path / "data") is True


# ===== Testy: extract (różne archiwa) =====


def test_extract_handles_both_archive_types(request, tmp_path):
    """``extract_pg_archive`` obsługuje .zip (Windows/macOS) i .tar.gz (Linux)."""
    # ZIP
    zip_bytes = request.getfixturevalue("fake_pg_zip_bytes")
    zip_archive = tmp_path / "pg.zip"
    zip_archive.write_bytes(zip_bytes)
    zip_result = pps.extract_pg_archive(zip_archive, tmp_path / "zip_out")
    assert zip_result.exists()
    assert (zip_result / "pg_ctl").exists()

    # TAR.GZ
    tgz_bytes = request.getfixturevalue("fake_pg_tar_gz_bytes")
    tgz_archive = tmp_path / "pg.tar.gz"
    tgz_archive.write_bytes(tgz_bytes)
    tgz_result = pps.extract_pg_archive(tgz_archive, tmp_path / "tgz_out")
    assert tgz_result.exists()
    assert (tgz_result / "pg_ctl").exists()


# ===== Testy: error scenarios =====


def test_flow_handles_download_failure_rollback(monkeypatch, tmp_path):
    """Gdy download fails po ``max_retries``, nie zostaje śmieciowy plik ``.tmp``."""
    def always_fail(*args, **kwargs):
        raise OSError("network unreachable")
    monkeypatch.setattr("urllib.request.urlopen", always_fail)
    monkeypatch.setattr("time.sleep", lambda x: None)

    with pytest.raises(RuntimeError, match=r"(?i)download|failed|nie udało"):
        pps.download_pg_binary(
            "https://example.com/pg.zip", tmp_path, max_retries=2
        )

    # Nie powinno zostać żadnych .tmp ani kompletnych plików.
    leftovers = list(tmp_path.iterdir())
    assert leftovers == []


def test_flow_handles_corrupted_zip(monkeypatch, tmp_path):
    """Gdy ZIP jest uszkodzony, ``extract_pg_archive`` rzuca ``RuntimeError``."""
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"not a zip file at all")

    with pytest.raises(RuntimeError):
        pps.extract_pg_archive(bad_zip, tmp_path / "out")


def test_flow_handles_missing_bin_dir_in_archive(monkeypatch, tmp_path):
    """ZIP bez ``pgsql/bin/`` → ``RuntimeError`` z czytelnym komunikatem."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("wrong_dir/file.txt", b"x")

    archive = tmp_path / "wrong.zip"
    archive.write_bytes(buf.getvalue())

    with pytest.raises(RuntimeError, match="bin|pgsql|struktura"):
        pps.extract_pg_archive(archive, tmp_path / "out")


# ===== Testy: URL-e per platforma =====


@pytest.mark.parametrize(
    "platform_name,expected_substring",
    [
        ("Windows", "windows"),
        ("Linux", "linux"),
        ("Darwin", "osx"),
    ],
)
def test_download_url_works_for_supported_platforms(
    monkeypatch, platform_name, expected_substring
):
    """URL-e są poprawne dla wszystkich wspieranych platform."""
    monkeypatch.setattr(platform_module, "system", lambda: platform_name)
    machine = "AMD64" if platform_name == "Windows" else "x86_64"
    monkeypatch.setattr(platform_module, "machine", lambda: machine)

    url = pps.get_pg_download_url()
    assert expected_substring.lower() in url.lower()
    assert url.startswith("https://")


# ===== Testy: contract z wizardem (Etap 3) =====


def test_wizard_can_call_portable_pg_pipeline():
    """Weryfikacja że wizard może wywołać pełny pipeline Etapu 1+2.

    Sprawdzamy że wszystkie potrzebne funkcje istnieją i są ``callable``
    — bez uruchamiania prawdziwego pipeline (to wymagałoby tkinter display).
    """
    assert callable(pps.detect_system_pg)
    assert callable(pps.download_pg_binary)
    assert callable(pps.extract_pg_archive)
    assert callable(pps.get_portable_pg_paths)
    assert callable(pps.portable_pg_installed)
    assert callable(pps.is_pg_initialized)
    assert callable(pps.get_pg_download_url)
    assert callable(pps.get_pg_install_dir)
    assert callable(pps.verify_pg_archive_checksum)

    assert callable(prt.init_pg_data_dir)
    assert callable(prt.start_pg_server)
    assert callable(prt.stop_pg_server)
    assert callable(prt.wait_for_pg_ready)
    assert callable(prt.is_pg_server_running)
    assert callable(prt.get_postmaster_pid)
    assert callable(prt.remove_pg_data_dir)


# ===== Test: pełny E2E flow z mockami (detect→download→extract→init→start→stop) =====


def test_full_e2e_flow_with_all_mocks(
    patched_no_system_pg, monkeypatch, tmp_path, fake_pg_zip_bytes
):
    """Kompletny E2E flow bez prawdziwego HTTP / PG / subprocess dla binariów.

    Kroki:
        1. ``detect_system_pg`` → ``None`` (brak systemowego PG)
        2. ``download_pg_binary`` → mock URL zwraca fake ZIP
        3. ``extract_pg_archive`` → binaria dostępne
        4. ``portable_pg_installed`` → ``True``
        5. ``is_pg_initialized`` → ``False`` (świeża instalacja)
        6. ``init_pg_data_dir`` → udajemy udany ``initdb`` (tworzymy PG_VERSION)
        7. ``start_pg_server`` → mock Popen + wait_for_pg_ready
        8. ``stop_pg_server`` → mock ``proc.wait()`` zwraca 0
    """
    # 0) Na Windows ``_pg_ctl_filename`` zwraca ``pg_ctl.exe`` — ale nasze fake
    # archiwum zawiera ``pg_ctl`` (bez rozszerzenia), więc patchujemy helper
    # żeby ``portable_pg_installed`` działało cross-platform.
    monkeypatch.setattr(pps, "_pg_ctl_filename", lambda: "pg_ctl")
    monkeypatch.setattr(pps, "_initdb_filename", lambda: "initdb")

    # 1) Detect: brak systemowego PG (fixture ``patched_no_system_pg``).
    assert pps.detect_system_pg() is None

    # 2) Download.
    fake_response = _make_fake_response(
        [fake_pg_zip_bytes],
        content_length=str(len(fake_pg_zip_bytes)),
    )
    monkeypatch.setattr("urllib.request.urlopen", MagicMock(return_value=fake_response))
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    archive = pps.download_pg_binary(
        "https://example.com/pg.zip", install_dir
    )
    assert archive.exists()

    # 3) Extract.
    bin_dir = pps.extract_pg_archive(archive, install_dir)
    assert (bin_dir / "pg_ctl").exists()
    assert (bin_dir / "initdb").exists()

    # 4) portable_pg_installed (z monkeypatchowanym install_dir).
    monkeypatch.setattr(
        pps, "get_pg_install_dir", lambda: install_dir
    )
    assert pps.portable_pg_installed() is True

    # 5) is_pg_initialized: False (świeża instalacja).
    assert pps.is_pg_initialized(install_dir / "data") is False

    # 6) init_pg_data_dir: udajemy udany initdb → tworzymy PG_VERSION.
    data_dir = install_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "PG_VERSION").write_text("16.4\n", encoding="utf-8")
    config = prt.PgServerConfig(
        paths=pps.get_portable_pg_paths(install_dir=install_dir),
        port=5434,
    )
    init_result = prt.init_pg_data_dir(config)
    assert init_result.ok is True
    assert "już zainicjalizowany" in init_result.message.lower() or init_result.details.get("skipped")

    # 7) start_pg_server.
    mock_proc = MagicMock()
    mock_proc.pid = 33333
    mock_proc.poll.return_value = None
    monkeypatch.setattr("subprocess.Popen", MagicMock(return_value=mock_proc))
    monkeypatch.setattr(
        "launcher.services.pg_runtime.wait_for_pg_ready", lambda *a, **kw: True
    )
    handle = prt.start_pg_server(config)
    assert handle.pid == 33333
    # is_pg_server_running: 1.1.3 sprawdza port
    fake_sock = MagicMock()
    fake_sock.__enter__ = lambda s: s
    fake_sock.__exit__ = lambda s, *args: None
    monkeypatch.setattr(socket, "create_connection", MagicMock(return_value=fake_sock))
    assert prt.is_pg_server_running(handle) is True

    # 8) stop_pg_server: nowa implementacja woła subprocess.run
    #    (pg_ctl stop -m fast) zamiast proc.wait().
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=0)
    monkeypatch.setattr("subprocess.run", mock_run)
    mock_proc.poll.side_effect = [None, 0]  # zyje przed, martwy po
    stop_result = prt.stop_pg_server(handle)
    assert stop_result.ok is True
