"""Bezpieczne rozwiązywanie ścieżek plików publicznych."""
from pathlib import Path


def resolve_public_path(root: Path, filename: str) -> Path:
    """Odrzuca ścieżki i dowiązania wychodzące poza wskazany katalog."""
    if '\\' in filename or '\x00' in filename:
        raise ValueError('Nieprawidłowa ścieżka pliku')
    base = root.resolve()
    candidate = (base / filename).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError('Ścieżka poza katalogiem publicznym')
    return candidate
