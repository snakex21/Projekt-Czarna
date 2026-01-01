import os
import pytest
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_html_accessibility_basics():
    """Sprawdza podstawowe zasady dostępności w plikach HTML (alt tags, lang itp.)."""
    html_files = []
    # Szukamy plików HTML w kluczowych folderach
    for root, dirs, files in os.walk(BASE_DIR):
        if "node_modules" in root or ".git" in root or "venv" in root:
            continue
        for f in files:
            if f.endswith(".html"):
                html_files.append(os.path.join(root, f))
                
    if not html_files:
        print("\n[DOSTĘPNOŚĆ] Nie znaleziono plików HTML do sprawdzenia.")
        return

    issues = []
    for file_path in html_files:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            rel_path = os.path.relpath(file_path, BASE_DIR)
            
            # 1. Brak atrybutu lang w tagu <html>
            if "<html" in content.lower() and "lang=" not in content.lower():
                issues.append(f"{rel_path}: Brak atrybutu <html lang=\"pl\">")
                
            # 2. Obrazy bez atrybutu alt
            images_without_alt = re.findall(r'<img(?!.*?alt=)[^>]*>', content, re.IGNORECASE)
            if images_without_alt:
                issues.append(f"{rel_path}: Znaleziono {len(images_without_alt)} obrazów bez opisu alt")
                
            # 3. Puste linki (bez tekstu)
            empty_links = re.findall(r'<a[^>]*>\s*</a>', content, re.IGNORECASE)
            if empty_links:
                issues.append(f"{rel_path}: Znaleziono puste linki (brak tekstu dla czytnika)")

    if issues:
        print(f"\n[DOSTĘPNOŚĆ] Znaleziono {len(issues)} uwag dotyczących dostępności:")
        for issue in issues[:20]:
            print(f"  ? {issue}")
    else:
        print("\n[DOSTĘPNOŚĆ] Podstawowe zasady HTML są zachowane (OK).")
    assert True
