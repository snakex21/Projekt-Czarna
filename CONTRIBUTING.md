# CONTRIBUTING

Dziękujemy za chęć pomocy przy projekcie **Mapa Katastralna Czarna**.

Projekt jest lokalnym systemem historyczno-katastralnym: backend **FastAPI**,
launcher **Tkinter**, frontend bez bundlerów oraz testy `pytest`.

## Zanim zaczniesz

1. Przeczytaj `PROJECT_SKILL.md` — to główny dokument konwencji dla kodu i
   agentów AI.
2. Przeczytaj dokumentację techniczną w `docs/technical/`.
3. Sprawdź `TODO.md` oraz `docs/technical/ROADMAP.md`, żeby nie dublować pracy.

## Środowisko

- Python 3.11+ (projekt testowany także na Python 3.13)
- FastAPI + SQLAlchemy async po stronie backendu
- Tkinter po stronie launchera
- JavaScript ES6 bez bundlerów po stronie frontendu

Instalacja:

```bash
pip install -r requirements.txt
```

## Zasady pracy

- Stosuj **TDD**: najpierw test, potem kod, potem regresja.
- UI i komunikaty użytkownika pisz po polsku.
- Identyfikatory, nazwy funkcji, zmiennych i kluczy JSON pisz po angielsku.
- Backend: routery FastAPI są cienkie, logika idzie do `backend/services/`.
- Launcher: `launcher/ui/*` deleguje do `launcher/services/*`; nie dodawaj I/O do UI.
- Frontend admina: nowe moduły jako `window.AdminFeature = Object.freeze({...})`.
- Nie dodawaj lazy importów bez uzasadnienia testowalnością.

## Testy

Podstawowe testy:

```bash
python -m pytest backend/tests/unit backend/tests/integration
```

Stabilny zestaw CI pomija znane testy środowiskowe/flaky opisane w
`docs/technical/TESTING.md` i w komentarzu workflow.

## Sekrety i dane lokalne

Nie commituj sekretów:

- `.env`
- `.postgres.env`
- `data/locations/*/.env`
- lokalnych baz i logów

Nie commituj też prywatnych materiałów, jeżeli nie są przeznaczone do publikacji.

## Pull request / zmiana

Każda zmiana powinna zawierać:

1. Krótki opis problemu.
2. Opis rozwiązania.
3. Listę uruchomionych testów.
4. Aktualizację dokumentacji, jeśli zmienia się architektura lub workflow.

## Konwencja commitów

Preferowane krótkie komunikaty:

```text
Add historical points contract tests
Refactor admin demography module
Fix launcher database wizard validation
```

## Kontakt

Projekt ma charakter edukacyjno-historyczny. Zmiany powinny szanować lokalny
kontekst danych oraz czytelność dla przyszłych opiekunów projektu.
