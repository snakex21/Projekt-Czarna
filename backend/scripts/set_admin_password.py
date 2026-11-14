"""Ustawia hasło administratora (hash Werkzeug) w backend/.env.

Użycie (z katalogu głównego repozytorium):
    python -m backend.scripts.set_admin_password            # pyta o hasło (bez echa)
    python -m backend.scripts.set_admin_password --username admin
    python -m backend.scripts.set_admin_password --password-stdin < plik   # np. w CI

Hasło nie jest nigdy zapisywane jawnie - tylko jego hash. Po zmianie
zrestartuj serwer; wszystkie istniejące sesje zostaną unieważnione.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

MIN_LENGTH = 8
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = REPO_ROOT / "backend" / ".env"


def _update_env(env_path: Path, updates: dict[str, str]) -> None:
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ustaw hasło administratora")
    parser.add_argument("--username", default=None, help="login admina (domyślnie bez zmian / 'admin')")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV), help="plik .env do aktualizacji")
    parser.add_argument("--password-stdin", action="store_true", help="czytaj hasło z pierwszej linii stdin")
    args = parser.parse_args(argv)

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Nowe hasło administratora: ")
        if password != getpass.getpass("Powtórz hasło: "):
            print("Hasła nie są identyczne.")
            return 1

    from backend.auth.routes import WEAK_PASSWORDS

    if len(password) < MIN_LENGTH:
        print(f"Hasło musi mieć co najmniej {MIN_LENGTH} znaków.")
        return 1
    if password in WEAK_PASSWORDS:
        print("To hasło jest na liście haseł domyślnych - wybierz inne.")
        return 1

    from werkzeug.security import generate_password_hash

    updates = {"ADMIN_PASSWORD_HASH": generate_password_hash(password)}
    if args.username:
        updates["ADMIN_USERNAME"] = args.username
    env_path = Path(args.env_file)
    _update_env(env_path, updates)
    print(f"Zapisano ADMIN_PASSWORD_HASH w {env_path}. Zrestartuj serwer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
