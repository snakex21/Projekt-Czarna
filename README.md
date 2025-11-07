# 🗺️ Interaktywna Mapa Katastralna Gminy Czarna

> Kompleksowy system do wizualizacji i analizy historycznych danych katastralnych z XIX wieku

## 📖 O Projekcie

System łączący historię z nowoczesną technologią - umożliwia eksplorację map katastralnych, danych właścicielskich i genealogicznych gminy Czarna z 1882 roku. Projekt bazuje na autentycznych materiałach archiwalnych z Archiwum Państwowego w Tarnowie oraz księgach metrykalnych z Archiwum Diecezjalnego.

**Autor:** Maksymilian Augustyn
**Opiekun:** dr inż. Adam Pieprzycki
**Uczelnia:** Akademia Tarnowska

### ✨ Możliwości

- 🗺️ **Interaktywna mapa katastralna** - wizualizacja działek, obiektów specjalnych i infrastruktury
- 👥 **System genealogiczny** - przeglądanie drzew genealogicznych mieszkańców
- 📊 **Analizy demograficzne** - statystyki dotyczące własności i struktury społecznej
- 📜 **Protokoły katastralne** - dostęp do oryginalnych dokumentów własnościowych
- 🔍 **Narzędzia analityczne** - porównywanie danych, eksploracja powiązań i transakcji

## 🚀 Szybki Start

### Wymagania

- Python 3.8+
- PostgreSQL 12+ z rozszerzeniem PostGIS
- Przeglądarka internetowa (preferowana Chrome/Firefox)

### Instalacja

1. **Sklonuj repozytorium**
```bash
git clone https://github.com/snakex21/Projekt-Czarna.git
cd Projekt-Czarna
```

2. **Zainstaluj zależności**
```bash
pip install -r requirements.txt
```

3. **Uruchom Centrum Zarządzania i przejdź przez konfigurację**

```bash
python launcher/launcher_app.py
```

Launcher przeprowadzi Cię przez intuicyjną konfigurację graficzną (GUI), gdzie:
- Skonfigurujesz połączenie z bazą danych PostgreSQL
- Zweryfikujesz poprawność konfiguracji
- Uruchomisz serwer backendu
- Otworzysz aplikację w przeglądarce

Wszystko w jednym miejscu, bez ręcznej edycji plików konfiguracyjnych!

## 🏗️ Architektura

Projekt oparty jest na nowoczesnej architekturze full-stack:

- **Backend:** Flask REST API z PostgreSQL/PostGIS
- **Frontend:** Aplikacje webowe (HTML/CSS/JavaScript + Leaflet.js)
- **Desktop:** Centrum zarządzania (Python/Tkinter)
- **Narzędzia:** Dedykowane edytory GUI do zarządzania danymi

### Stack Technologiczny

- **Backend:** Python, Flask, Flask-CORS, psycopg2
- **Baza danych:** PostgreSQL + PostGIS (dane przestrzenne)
- **Frontend:** HTML5, CSS3, JavaScript (ES6+), Leaflet.js
- **Desktop:** Python Tkinter, Pillow

## 📁 Struktura Projektu

Projekt zorganizowany jest w sposób modularny - każdy katalog odpowiada za konkretną funkcjonalność systemu. Szczegółowy opis struktury dostępny jest w dokumentacji technicznej w katalogu `dokumentacja/`.

## 📚 Dokumentacja

Pełna dokumentacja projektu, w tym opis techniczny, proces digitalizacji danych oraz szczegółowa analiza implementacji, znajduje się w:
- `dokumentacja/dokumentacja.pdf` - wersja finalna
- `dokumentacja/dokumentacja.md` - wersja tekstowa

## 🛠️ Dla Deweloperów

### Testowanie
```bash
pytest backend/tests/
```

### Dodawanie nowych funkcjonalności

System zaprojektowany jest modularnie - nowe moduły mogą być dodawane niezależnie. Backend udostępnia RESTful API z endpointami JSON, co ułatwia tworzenie nowych frontendów lub integracji.

## 🤝 Współpraca

Projekt jest otwarty na rozszerzenia i ulepszenia. Jeśli chcesz przyczynić się do rozwoju:

1. Forkuj repozytorium
2. Stwórz branch dla swojej funkcjonalności (`git checkout -b feature/AmazingFeature`)
3. Commituj zmiany (`git commit -m 'Add some AmazingFeature'`)
4. Wypchnij do brancha (`git push origin feature/AmazingFeature`)
5. Otwórz Pull Request

## 📄 Licencja

Projekt edukacyjny stworzony w ramach pracy inżynierskiej.

## 🙏 Podziękowania

- Archiwum Państwowe w Tarnowie - za udostępnienie protokołów katastralnych
- Archiwum Diecezjalne w Tarnowie - za dostęp do ksiąg metrykalnych
- dr inż. Adam Pieprzycki - za opiekę naukową nad pracą

---

**Projekt powstał z pasji do historii lokalnej i chęci zachowania dziedzictwa kulturowego dla przyszłych pokoleń.**
