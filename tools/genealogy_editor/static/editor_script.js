// --- INFORMACJE O PLIKU ---
// Plik: tools/genealogy_editor/static/editor_script.js
// Opis: Główny skrypt obsługujący edytor genealogiczny w przeglądarce.
//       Zarządza tabelą osób, filtrowaniem, edycją, kopiami zapasowymi
//       oraz wizualizacją drzew genealogicznych.

document.addEventListener("DOMContentLoaded", () => {
  // --- KONFIGURACJA I ZMIENNE GLOBALNE ---
  
  // Adresy URL do komunikacji z API backendowym
  const GENEALOGIA_API_URL = "/api/genealogia";
  const PROTOCOLS_API_URL = "/api/protocols"; // Endpoint do pobierania listy protokołów
  
  // Referencje do elementów DOM używanych w aplikacji
  const tableBody = document.getElementById("genealogyTableBody");
  const searchInput = document.getElementById("searchGenealogyInput");
  const familyFilter = document.getElementById("familyFilter");
  
  // Elementy modala do edycji/dodawania osób
  const showAddBtn = document.getElementById("showAddFormBtn");
  const modal = document.getElementById("editGenealogyModal");
  const modalTitle = document.getElementById("modalTitle");
  const editForm = document.getElementById("editGenealogyForm");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const cancelEditBtn = document.getElementById("cancelEditBtn");
  const saveAndCloseBtn = document.getElementById("saveAndCloseBtn");
  
  // Główne struktury danych przechowujące stan aplikacji
  let allPeople = [];     // Tablica wszystkich osób w genealogii
  let allProtocols = [];  // Tablica dostępnych protokołów właścicieli

  // --- STYLE CSS DLA ELEMENTÓW NAWIGACJI ---

  // Tworzenie elementu style z definicjami CSS dla systemu nawigacji do protokołów
  const navigationStyles = document.createElement("style");
  navigationStyles.textContent = `
    /* Nakładka wyświetlana podczas ładowania */
    .loading-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 10000;
    }
    
    /* Kontener z komunikatem ładowania */
    .loading-content {
      background: white;
      padding: 30px;
      border-radius: 10px;
      text-align: center;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Nagłówek komunikatu */
    .loading-content h3 {
      margin: 0 0 20px 0;
      color: #333;
    }
    
    /* Animowany spinner ładowania */
    .spinner {
      border: 4px solid #f3f3f3;
      border-top: 4px solid #3498db;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 0 auto;
    }
    
    /* Animacja obracania spinnera */
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    
    /* Stylizacja linków do protokołów */
    .protocol-link {
      color: #007bff;
      text-decoration: underline;
      cursor: pointer;
    }
    
    /* Stan hover linku protokołu */
    .protocol-link:hover {
      color: #0056b3;
    }
  `;

  // Dodanie stylów do dokumentu
  document.head.appendChild(navigationStyles);

  // --- FUNKCJE RENDERUJĄCE I POMOCNICZE ---

  /**
   * Wypełnia listę <datalist> protokołami do autouzupełniania.
   * 
   * Tworzy opcje zawierające klucz protokołu oraz jego numer porządkowy
   * i nazwę właściciela dla lepszej identyfikacji.
   */
  function populateProtocolsDatalist() {
    const datalist = document.getElementById("protocols-list");
    datalist.innerHTML = ""; // Wyczyść stare dane
    
    allProtocols.forEach((protocol) => {
      const option = document.createElement("option");
      // Wartością jest klucz, np. "Piotr_Augustyn"
      option.value = protocol.key;
      // Etykieta pokazuje numer i nazwę, np. "(5) Piotr Augustyn"
      option.textContent = `(${protocol.orderNumber}) ${protocol.name}`;
      datalist.appendChild(option);
    });
  }

  /**
   * Wypełnia listę <datalist> osobami do autouzupełniania pól relacji.
   * 
   * Używane w polach wyboru ojca, matki i małżonka, aby ułatwić
   * powiązywanie osób poprzez podpowiedzi podczas pisania.
   */
  function populatePeopleDatalist() {
    const datalist = document.getElementById("people-list");
    if (!datalist) return;
    datalist.innerHTML = ""; // Wyczyść stare dane

    // Sortujemy alfabetycznie dla lepszej czytelności podpowiedzi
    const sortedPeople = [...allPeople].sort((a, b) =>
      (a.imie || "").localeCompare(b.imie || ""),
    );

    sortedPeople.forEach((person) => {
      const option = document.createElement("option");
      // Wartością opcji jest ID osoby, np. "Piotr_Augustyn_1822"
      option.value = person.id_osoby;
      // Etykieta zawiera pełne informacje dla łatwiejszej identyfikacji
      option.textContent = `${person.imie} ${person.nazwisko} (ur. ${person.rok_urodzenia || "?"})`;
      datalist.appendChild(option);
    });
  }

  /**
   * Ekstraktuje unikalne nazwiska rodzin z danych.
   * 
   * Pomija osoby z przedrostkiem "z" (żony przyjmujące nazwisko męża)
   * oraz normalizuje nazwisko "Barnasi" na "Barnaś".
   * @deprecated - zastąpione przez populateFamilyFilter()
   */
  function getFamilies(data) {
    const families = new Set();
    data.forEach((person) => {
      if (person.nazwisko && !person.nazwisko.startsWith("z ")) {
        families.add(
          person.nazwisko === "Barnasi" ? "Barnaś" : person.nazwisko,
        );
      }
    });
    return Array.from(families).sort();
  }

  /**
   * Wypełnia listę rozwijaną filtra rodzin znormalizowanymi nazwiskami.
   * 
   * Normalizuje nazwiska żeńskie do formy męskiej (np. Kowalska -> Kowalski)
   * i usuwa duplikaty, aby każda rodzina pojawiła się tylko raz.
   */
  function populateFamilyFilter() {
    const canonicalFamilyNames = new Set();

    /**
     * Normalizuje nazwisko, sprowadzając je do męskiej, bazowej formy.
     * Obsługuje polskie feminatywy i złożone nazwiska.
     * 
     * @param {string} surname - Surowe nazwisko z bazy
     * @returns {string|null} - Znormalizowane nazwisko lub null
     */
    function getCanonicalSurname(surname) {
      if (!surname || typeof surname !== "string") {
        return null;
      }

      // Bierzemy ostatni człon nazwiska (ważne dla "z Nowaków Sakowa")
      let baseName = surname.trim().split(" ").pop().toLowerCase();

      // Reguły normalizacji dla polskich nazwisk żeńskich
      if (baseName.endsWith("ska")) {
        baseName = baseName.slice(0, -3) + "ski";
      } else if (baseName.endsWith("cka")) {
        baseName = baseName.slice(0, -3) + "cki";
      } else if (baseName.endsWith("dzka")) {
        baseName = baseName.slice(0, -4) + "dzki";
      } else if (baseName.endsWith("owa")) {
        baseName = baseName.slice(0, -3);
      }

      // Zwróć z wielką literą
      return baseName.charAt(0).toUpperCase() + baseName.slice(1);
    }

    // Przechodzimy przez wszystkie osoby i zbieramy znormalizowane nazwiska
    allPeople.forEach((person) => {
      const canonicalName = getCanonicalSurname(person.nazwisko);
      if (canonicalName) {
        canonicalFamilyNames.add(canonicalName);
      }
    });

    // Sortowanie alfabetyczne nazwisk
    const sortedFamilies = Array.from(canonicalFamilyNames).sort((a, b) =>
      a.localeCompare(b),
    );

    // Wypełniamy listę rozwijaną
    familyFilter.innerHTML = '<option value="">— Wszystkie rodziny —</option>';
    sortedFamilies.forEach((familyName) => {
      const option = document.createElement("option");
      option.value = familyName;
      option.textContent = `Rodzina ${familyName}`;
      familyFilter.appendChild(option);
    });
  }

  // --- GŁÓWNA FUNKCJA RENDEROWANIA TABELI ---
  
  /**
   * Renderuje tabelę genealogiczną z grupowaniem po rodach.
   * 
   * Funkcja wykonuje następujące kroki:
   * 1. Wyznacza pokolenia używając algorytmu BFS
   * 2. Grupuje osoby według rodów (kanonicznych nazwisk)
   * 3. Renderuje każdy ród z nagłówkiem i członkami
   * 4. Dodaje wizualne oznaczenia pokoleń i relacji
   * 
   * @param {Array} data - Tablica osób do wyświetlenia
   */
  function renderTableGrouped(data) {
    tableBody.innerHTML = "";

    // Tworzenie map dla szybkiego dostępu do danych
    const peopleMap = new Map(allPeople.map((p) => [p.id_osoby, p]));
    
    // Mapa dzieci - kto jest czyim dzieckiem
    const childrenMap = new Map();
    data.forEach((p) => {
      if (p.id_ojca)
        childrenMap.set(
          p.id_ojca,
          (childrenMap.get(p.id_ojca) || []).concat(p),
        );
      if (p.id_matki)
        childrenMap.set(
          p.id_matki,
          (childrenMap.get(p.id_matki) || []).concat(p),
        );
    });

    /* --- KROK 1: WYZNACZANIE POKOLEŃ (algorytm BFS) --- */
    const generationMap = new Map();
    
    // Znajdź osoby-korzenie (bez rodziców)
    const roots = data
      .filter((p) => !p.id_ojca && !p.id_matki)
      .map((p) => p.id_osoby);
    roots.forEach((id) => generationMap.set(id, 0));

    // BFS - przeszukiwanie wszerz drzewa genealogicznego
    const q = [...roots];
    while (q.length) {
      const currId = q.shift();
      const gen = generationMap.get(currId);

      // Przypisz pokolenie dzieciom
      (childrenMap.get(currId) || []).forEach((ch) => {
        if (
          !generationMap.has(ch.id_osoby) ||
          generationMap.get(ch.id_osoby) > gen + 1
        ) {
          generationMap.set(ch.id_osoby, gen + 1);
          q.push(ch.id_osoby);
        }
      });

      // Małżonkowie są w tym samym pokoleniu
      const curr = peopleMap.get(currId);
      if (curr && curr.id_malzonka) {
        const spouseId = curr.id_malzonka;
        if (!generationMap.has(spouseId) || generationMap.get(spouseId) > gen) {
          generationMap.set(spouseId, gen);
          q.push(spouseId);
        }
      }
    }

    /* --- KROK 2: FUNKCJE DO WYZNACZANIA RODU --- */
    
    /**
     * Normalizuje nazwisko do formy kanonicznej (masculinum).
     * Usuwa przedrostki typu "z" i konwertuje formy żeńskie.
     */
    function canonicalSurname(raw) {
      if (!raw) return "";
      raw = raw.trim();

      // Usuń przedrostek „z …" (np. "z Kowalskich")
      if (raw.toLowerCase().startsWith("z ")) {
        raw = raw.slice(2).trim();
      }

      // Bierzemy OSTATNI wyraz (np. „Sakowa" z „z Nowaków Sakowa")
      let last = raw.split(/\s+/).pop().toLowerCase();

      // Podstawowe reguły feminatywów polskich
      if (last.endsWith("ska")) last = last.slice(0, -3) + "ski";
      else if (last.endsWith("cka")) last = last.slice(0, -3) + "cki";
      else if (last.endsWith("dzka")) last = last.slice(0, -4) + "dzki";
      else if (last.endsWith("owa")) last = last.slice(0, -3); // Sakowa → Sak
      else if (last.endsWith("a") && last.length > 4) last = last.slice(0, -1);

      // Wielka litera na początku
      return last.charAt(0).toUpperCase() + last.slice(1);
    }

    /**
     * Znajduje nazwę rodu dla danej osoby.
     * Śledzi linię męską wstecz do korzenia rodu.
     */
    function findLineageName(person) {
      const visited = new Set(); // Zapobiega nieskończonym pętlom

      // Funkcja rekurencyjna do szukania "korzenia" rodu
      function findRoot(currentPerson) {
        if (!currentPerson || visited.has(currentPerson.id_osoby)) {
          return currentPerson; // Zwróć bieżącą osobę, jeśli koniec ścieżki lub pętla
        }
        visited.add(currentPerson.id_osoby);

        // Priorytet 1: Idź w górę po linii męskiej (ojciec)
        if (currentPerson.id_ojca && peopleMap.has(currentPerson.id_ojca)) {
          return findRoot(peopleMap.get(currentPerson.id_ojca));
        }

        // Priorytet 2: Jeśli nie ma ojca, ale jest matka, idź po jej linii
        if (currentPerson.id_matki && peopleMap.has(currentPerson.id_matki)) {
          return findRoot(peopleMap.get(currentPerson.id_matki));
        }

        // Jeśli nie ma żadnych połączeń w górę, ta osoba jest "korzeniem"
        return currentPerson;
      }

      const rootPerson = findRoot(person);
      const lineageName = canonicalSurname(
        rootPerson.nazwisko || person.nazwisko,
      );

      // Sprawdź, czy osoba jest całkowicie odizolowana
      const isIsolated =
        !person.id_ojca &&
        !person.id_matki &&
        !person.id_malzonka &&
        !(
          childrenMap.has(person.id_osoby) &&
          childrenMap.get(person.id_osoby).length > 0
        );

      // Osoby izolowane otrzymują specjalne oznaczenie
      if (isIsolated) {
        return `${person.imie} ${person.nazwisko} (osobna linia)`;
      }

      return lineageName;
    }

    /* --- KROK 3: GRUPOWANIE PO RODACH --- */
    const lineages = new Map();
    data.forEach((p) => {
      const lin = findLineageName(p);
      if (!lineages.has(lin)) lineages.set(lin, []);
      lineages.get(lin).push(p);
    });

    /* --- KROK 4: RENDEROWANIE TABELI --- */
    [...lineages.keys()].sort().forEach((lineName) => {
      // Sortuj członków rodu chronologicznie
      const members = lineages
        .get(lineName)
        .sort((a, b) => (a.rok_urodzenia || 9999) - (b.rok_urodzenia || 9999));

      // Zbierz członków + „dopisanych" małżonków
      const display = new Map();
      members.forEach((p) => {
        display.set(p.id_osoby, p);
        // Dodaj małżonków spoza rodu
        const spouse = peopleMap.get(p.id_malzonka);
        if (
          spouse &&
          !display.has(spouse.id_osoby) &&
          p.nazwisko === lineName
        ) {
          display.set(spouse.id_osoby, { ...spouse, _isSpouseInLaw: true });
        }
      });

      /* --- NAGŁÓWEK RODU/OSOBY Z PRZYCISKIEM DRZEWA --- */
      const isSingle = display.size === 1;
      const fetchKey = isSingle ? [...display.keys()][0] : lineName;

      const hdr = document.createElement("tr");
      hdr.classList.add("family-header");
      hdr.style.cursor = "pointer";
      hdr.innerHTML = `
            <td colspan="6">
              ${isSingle ? "👤 Osoba" : "👨‍👩‍👧‍👦 Ród"} ${lineName}
              [${display.size} ${display.size === 1 ? "osoba" : "osób"}]
            </td>
            <td class="family-tree-actions">
              <button class="btn btn-tree"
                      data-family="${fetchKey}"
                      title="Pokaż drzewo ${isSingle ? "osoby" : "rodziny"} ${lineName}">
                🌳 Drzewo${isSingle ? " osoby" : ""}
              </button>
            </td>
        `;
      tableBody.appendChild(hdr);

      /* --- WIERSZE CZŁONKÓW RODU --- */
      const rows = [];
      [...display.values()].forEach((p) => {
        const row = document.createElement("tr");
        row.classList.add("family-member");
        row.classList.add(`gen-${generationMap.get(p.id_osoby) || 0}`);
        if (p.id_malzonka || p._isSpouseInLaw) row.classList.add("spouse-row");

        // Formatowanie lat życia
        const years = `${p.rok_urodzenia || "?"} – ${p.rok_smierci || "?"}`
          .replace(/– \?$/, "")
          .replace(/^\? –/, "");
        
        // Pobieranie imion rodziców
        const parents = [
          peopleMap.get(p.id_ojca)?.imie,
          peopleMap.get(p.id_matki)?.imie,
        ]
          .filter(Boolean)
          .join(", ");
        
        // Imię małżonka
        const spouseName = peopleMap.get(p.id_malzonka)?.imie || "";

        // Tworzenie wiersza tabeli
        row.innerHTML = `
                <td>${p.id_osoby}</td>
                <td>
                  ${
                    p.id_malzonka || p._isSpouseInLaw
                      ? "💑"
                      : p.id_ojca || p.id_matki
                        ? "👶"
                        : "👤"
                  }
                  <strong>${p.imie || ""}</strong> ${p.nazwisko || ""}
                  ${
                    p.id_malzonka || p._isSpouseInLaw
                      ? '<small style="color:#e74c3c;">(małżonek/a)</small>'
                      : ""
                  }
                </td>
                <td>${years}</td>
                <td><em>${parents}</em></td>
                <td><em>${spouseName}</em></td>
                <td>${
                  p.protokol_klucz
                    ? `<span class="protocol-link" data-protocol="${p.protokol_klucz}">${p.protokol_klucz}</span>`
                    : "brak"
                }</td>
                <td class="actions">
                  <button class="edit-btn"   data-id="${p.id_osoby}">✏️</button>
                  <button class="delete-btn" data-id="${p.id_osoby}">🗑️</button>
                </td>
            `;
        rows.push(row);
        tableBody.appendChild(row);
      });

      /* --- MECHANIZM ZWIJANIA/ROZWIJANIA NAGŁÓWKÓW --- */
      hdr.querySelector("td:first-child").addEventListener("click", () => {
        const collapsed = hdr.classList.toggle("collapsed");
        rows.forEach((r) => (r.style.display = collapsed ? "none" : ""));
      });
    });
  }

  /**
   * Aplikuje filtry wyszukiwania i rodziny do danych.
   * 
   * Filtruje osoby według wprowadzonego tekstu i wybranej rodziny,
   * a następnie renderuje przefiltrowane dane.
   */
  function applyFilters() {
    const term = searchInput.value.toLowerCase();
    const family = familyFilter.value;
    
    const filteredData = allPeople.filter((p) => {
      // Filtrowanie po imieniu i nazwisku
      const nameMatch = `${p.imie || ""} ${p.nazwisko || ""}`
        .toLowerCase()
        .includes(term);
      
      // Filtrowanie po rodzinie (nazwisko lub nazwisko ojca)
      const familyMatch =
        !family ||
        p.nazwisko === family ||
        (p.id_ojca &&
          allPeople.find((f) => f.id_osoby === p.id_ojca)?.nazwisko === family);
      
      return nameMatch && familyMatch;
    });
    
    renderTableGrouped(filteredData);
  }

  /**
   * Wypełnia pole wyboru relacji (ojciec/matka/małżonek).
   * 
   * @param {HTMLSelectElement} selectElement - Element <select> do wypełnienia
   * @param {Array} people - Lista osób do wyboru
   * @param {string} placeholder - Tekst dla pustej opcji
   * @param {string} currentPersonId - ID aktualnie edytowanej osoby (do wykluczenia)
   */
  function populateRelationSelect(
    selectElement,
    people,
    placeholder,
    currentPersonId,
  ) {
    selectElement.innerHTML = `<option value="">${placeholder}</option>`;
    
    // Wyklucz aktualną osobę z listy
    const filteredPeople = people.filter((p) => p.id_osoby !== currentPersonId);
    
    // Sortuj alfabetycznie
    filteredPeople.sort((a, b) => (a.imie || "").localeCompare(b.imie || ""));
    
    // Dodaj opcje
    filteredPeople.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.id_osoby;
      opt.textContent = `${p.imie} ${p.nazwisko} (${p.id_osoby})`;
      selectElement.appendChild(opt);
    });
  }

  /**
   * Otwiera modal edycji/dodawania osoby.
   * 
   * @param {Object|null} person - Obiekt osoby do edycji, lub null dla nowej osoby
   */
  function openModal(person = null) {
    // Czyścimy poprzednie walidacje (czerwone obramowania)
    editForm
      .querySelectorAll("input")
      .forEach((input) => (input.style.borderColor = ""));

    if (person) {
      // --- TRYB EDYCJI ---
      modalTitle.textContent = `Edytuj osobę: ${person.imie} ${person.nazwisko}`;
      
      // Zapisujemy oryginalne ID, aby wiedzieć, który rekord aktualizujemy
      editForm["edit-person-id"].value = person.id_osoby;
      
      // Wypełniamy wszystkie pola formularza
      editForm["edit-id-osoby"].value = person.id_osoby;
      editForm["edit-imie"].value = person.imie || "";
      editForm["edit-nazwisko"].value = person.nazwisko || "";
      editForm["edit-rok_urodzenia"].value = person.rok_urodzenia || "";
      editForm["edit-rok_smierci"].value = person.rok_smierci || "";
      editForm["edit-plec"].value = person.plec || "M";
      editForm["edit-numer_domu"].value = person.numer_domu || "";
      editForm["edit-uwagi"].value = person.uwagi || "";
      editForm["edit-ojciec-id"].value = person.id_ojca || "";
      editForm["edit-matka-id"].value = person.id_matki || "";
      editForm["edit-malzonek-id"].value = person.id_malzonka || "";
      editForm["edit-wlasciciel-id"].value = person.protokol_klucz || "";
    } else {
      // --- TRYB DODAWANIA ---
      modalTitle.textContent = "Dodaj nową osobę";
      editForm.reset();
      // Czyścimy ukryte pole, bo to nowa osoba
      editForm["edit-person-id"].value = "";
    }
    
    // Pokazujemy modal i ustawiamy fokus na pierwsze pole
    modal.classList.remove("hidden");
    document.getElementById("edit-id-osoby").focus();
  }

  // --- LOGIKA APLIKACJI (OBSŁUGA ZDARZEŃ) ---

  /**
   * Pobiera dane z API i inicjalizuje aplikację.
   * 
   * Ładuje listę osób i protokołów, wypełnia filtry
   * i renderuje początkowy widok tabeli.
   */
  async function fetchData() {
    try {
      // Równoległe pobieranie danych z obu endpointów
      const [genealogyRes, protocolsRes] = await Promise.all([
        fetch(GENEALOGIA_API_URL),
        fetch(PROTOCOLS_API_URL),
      ]);
      
      // Sprawdzenie statusów odpowiedzi
      if (!genealogyRes.ok)
        throw new Error(`Błąd wczytywania genealogii: ${genealogyRes.status}`);
      if (!protocolsRes.ok)
        throw new Error(`Błąd wczytywania protokołów: ${protocolsRes.status}`);

      // Parsowanie danych JSON
      const rawData = await genealogyRes.json();
      // Sprawdź, czy dane są w formacie { persons: [...] } czy bezpośrednio tablicą
      allPeople = Array.isArray(rawData) ? rawData : rawData.persons || [];
      allProtocols = await protocolsRes.json();
      
      // Inicjalizacja interfejsu
      populateProtocolsDatalist();  // Lista protokołów
      populatePeopleDatalist();      // Lista osób do relacji
      populateFamilyFilter();        // Filtr rodzin
      renderTableGrouped(allPeople); // Renderowanie tabeli
    } catch (err) {
      console.error("Błąd ładowania danych:", err);
      tableBody.innerHTML = `<tr><td colspan="7" style="color: red; text-align: center;">${err.message}</td></tr>`;
    }
  }

  /**
   * Obsługa wysyłania formularza edycji/dodawania osoby.
   * 
   * Wykonuje walidację danych, sprawdza unikalność ID,
   * aktualizuje lokalną tablicę i opcjonalnie zmienia powiązania.
   */
  editForm.addEventListener("submit", (e) => {
    e.preventDefault();

    // --- KROK 1: Pobieranie danych z formularza ---
    const originalId = editForm["edit-person-id"].value;
    const newId = editForm["edit-id-osoby"].value.trim();

    // --- KROK 2: Walidacja ---
    if (!newId) {
      alert('Pole "Unikalne ID Osoby" jest wymagane!');
      editForm["edit-id-osoby"].style.borderColor = "red";
      return;
    }

    // Sprawdzamy, czy nowe ID nie jest już zajęte przez INNĄ osobę
    const isIdTaken = allPeople.some(
      (p) => p.id_osoby === newId && p.id_osoby !== originalId,
    );
    if (isIdTaken) {
      alert(`ID "${newId}" jest już używane przez inną osobę! Wybierz inne.`);
      editForm["edit-id-osoby"].style.borderColor = "red";
      return;
    }

    // --- KROK 3: Tworzenie obiektu z danymi (payload) ---
    const payload = {
      id_osoby: newId,
      imie: editForm["edit-imie"].value.trim(),
      nazwisko: editForm["edit-nazwisko"].value.trim() || null,
      plec: editForm["edit-plec"].value,
      numer_domu: editForm["edit-numer_domu"].value.trim() || null,
      rok_urodzenia: parseInt(editForm["edit-rok_urodzenia"].value, 10) || null,
      rok_smierci: parseInt(editForm["edit-rok_smierci"].value, 10) || null,
      uwagi: editForm["edit-uwagi"].value.trim() || null,
      id_ojca: editForm["edit-ojciec-id"].value.trim() || null,
      id_matki: editForm["edit-matka-id"].value.trim() || null,
      id_malzonka: editForm["edit-malzonek-id"].value.trim() || null,
      protokol_klucz: editForm["edit-wlasciciel-id"].value.trim() || null,
    };

    // --- KROK 4: Aktualizacja danych w lokalnej tablicy ---
    if (originalId) {
      // Jeśli edytujemy istniejącą osobę
      const personIndex = allPeople.findIndex((p) => p.id_osoby === originalId);
      if (personIndex > -1) {
        allPeople[personIndex] = payload;

        // WAŻNE: Jeśli ID zostało zmienione, musimy zaktualizować wszystkie powiązania!
        if (originalId !== newId) {
          allPeople.forEach((p) => {
            if (p.id_ojca === originalId) p.id_ojca = newId;
            if (p.id_matki === originalId) p.id_matki = newId;
            if (p.id_malzonka === originalId) p.id_malzonka = newId;
          });
        }
      }
    } else {
      // Jeśli dodajemy nową osobę
      allPeople.push(payload);
    }

    // --- KROK 5: Zamknięcie modala i odświeżenie widoku ---
    modal.classList.add("hidden");
    populatePeopleDatalist(); // Odśwież listę podpowiedzi
    applyFilters();           // Odśwież tabelę
  });

  /**
   * Obsługa przycisku "Zapisz i zamknij".
   * 
   * Wysyła wszystkie dane do API, zapisuje je na serwerze,
   * a następnie zamyka serwer i okno przeglądarki.
   */
  saveAndCloseBtn.addEventListener("click", async () => {
    if (!confirm("Czy na pewno chcesz zapisać wszystkie zmiany i zamknąć edytor?"))
      return;

    try {
      // 1) Usuń pola pomocnicze
      let cleaned = allPeople.map((p) => {
        const { _isWifeInHusbandLineage, ...rest } = p;
        return rest;
      });

      // 2) Sanity-check: wyczyść referencje do nieistniejących osób
      const ids = new Set(cleaned.map((p) => String(p.id_osoby)));
      cleaned = cleaned.map((p) => ({
        ...p,
        id_ojca: p.id_ojca && ids.has(String(p.id_ojca)) ? p.id_ojca : null,
        id_matki: p.id_matki && ids.has(String(p.id_matki)) ? p.id_matki : null,
        id_malzonka: p.id_malzonka && ids.has(String(p.id_malzonka)) ? p.id_malzonka : null,
      }));

      // 3) Zapis
      const saveResponse = await fetch(GENEALOGIA_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cleaned),
      });

      if (!saveResponse.ok) throw new Error("Błąd podczas zapisywania danych.");

      alert("Dane zapisane pomyślnie!");
      await fetch("/shutdown", { method: "POST" });
      window.close();
    } catch (error) {
      console.error("Błąd zapisu i zamykania:", error);
      alert("Wystąpił błąd podczas zapisu.");
    }
  });

  /**
   * Delegacja zdarzeń dla przycisków w tabeli.
   * 
   * Obsługuje przyciski drzewa, edycji i usuwania
   * używając jednego nasłuchiwacza na całej tabeli.
   */
  tableBody.addEventListener("click", async (e) => {
    const button = e.target.closest("button");
    
    // --- Obsługa przycisków drzewa rodziny ---
    if (button && button.classList.contains("btn-tree")) {
      e.preventDefault();
      e.stopPropagation();
      
      const familyName = button.dataset.family;
      console.log("Kliknięto przycisk drzewa dla:", familyName);
      
      if (familyName) {
        await showFamilyTree(familyName);
      }
      return;
    }

    // --- Obsługa przycisku edycji ---
    if (button && button.classList.contains("edit-btn")) {
      const id = button.dataset.id;
      const person = allPeople.find((p) => p.id_osoby === id);
      if (person) openModal(person);
      return;
    }
    
    // --- Obsługa przycisku usuwania ---
    if (button && button.classList.contains("delete-btn")) {
      const id = button.dataset.id;
      if (confirm(`Czy na pewno chcesz usunąć osobę o ID: ${id}?`)) {
        // Usuń wpis z listy
        allPeople = allPeople.filter((p) => p.id_osoby !== id);

        // Odwiąż relacje do usuniętej osoby
        allPeople.forEach((p) => {
          if (p.id_ojca === id) p.id_ojca = null;
          if (p.id_matki === id) p.id_matki = null;
          if (p.id_malzonka === id) p.id_malzonka = null;
        });

        // Odśwież listy podpowiedzi i widok
        populatePeopleDatalist();
        applyFilters();
      }
      return;
    }

    // --- Obsługa linków protokołów ---
    if (e.target.classList.contains("protocol-link")) {
      e.preventDefault();

      const protocolKey = e.target.dataset.protocol;
      let loadingOverlay = null;

      try {
        loadingOverlay = document.createElement("div");
        loadingOverlay.className = "loading-overlay";
        loadingOverlay.innerHTML = `
          <div class="loading-content">
            <h3>Sprawdzanie backendu…</h3>
            <div class="spinner"></div>
          </div>
        `;
        document.body.appendChild(loadingOverlay);

        // Sprawdzamy znany adres „głównego” (127.0.0.1:5000) – jeśli nie działa, informujemy o innym IP/porcie
        const checkResponse = await fetch("/api/editor/check-main");
        const checkData = await checkResponse.json();

        if (checkData.available && checkData.url) {
          const backendURL = new URL(checkData.url);
          const sameHost = backendURL.hostname === window.location.hostname;
          const samePort = backendURL.port === '5000' || backendURL.port === window.location.port;

          if (!sameHost || !samePort) {
            alert(
              `Nie można przejść do protokołu.\n` +
              `Backend działa pod innym adresem: ${backendURL.origin}\n\n` +
              `Zmień FLASK_HOST/FLASK_PORT w .env backendu albo uruchom frontend z tego samego IP/portu.`
            );
            return;
          }

          // Host/port w porządku – nawiguj
          window.location.href = `${checkData.url}/wlasciciele/protokol.html?ownerId=${protocolKey}`;
          return;
        }

        // Brak backendu pod standardem – pokaż komunikat
        alert(
          "Nie można przejść do protokołu.\n" +
          "Backend nie jest osiągalny pod domyślnym adresem (127.0.0.1:5000).\n\n" +
          "Wygląda na to, że działa na innym porcie/IP.\n" +
          "Zaktualizuj FLASK_HOST/FLASK_PORT w .env backendu lub uruchom go na 127.0.0.1:5000."
        );
      } catch (error) {
        console.error("Błąd podczas otwierania protokołu:", error);
        alert("Wystąpił błąd podczas sprawdzania backendu.");
      } finally {
        if (loadingOverlay && loadingOverlay.parentNode) loadingOverlay.remove();
      }
    }
  });

  /**
   * Wyświetla drzewo genealogiczne dla wybranej rodziny.
   * 
   * Otwiera modal, ładuje bibliotekę D3.js i renderuje
   * interaktywne drzewo genealogiczne.
   */
  async function showFamilyTree(familyName) {
    console.log("showFamilyTree wywołane dla:", familyName);
    
    const genealogyModal = document.getElementById("genealogyModal");
    const genealogyChart = document.getElementById("genealogy-chart");

    // Sprawdzenie czy elementy modala istnieją
    if (!genealogyModal || !genealogyChart) {
      console.error("Brak elementów modala drzewa genealogicznego");
      alert("Błąd: Nie znaleziono elementów interfejsu dla drzewa genealogicznego");
      return;
    }

    // Sprawdzenie czy biblioteka D3 jest załadowana
    if (!window.genealogiaD3) {
      console.error("Biblioteka genealogiaD3 nie jest załadowana");
      alert("Błąd: Biblioteka wizualizacji drzewa nie została załadowana. Odśwież stronę.");
      return;
    }

    // Otwarcie modala z komunikatem ładowania
    genealogyModal.classList.add("visible");
    genealogyChart.innerHTML = `<h2>Ładowanie drzewa rodziny ${familyName}...</h2>`;

    try {
      console.log("Ładowanie bibliotek D3...");
      // Załaduj biblioteki D3 jeśli potrzebne
      await window.genealogiaD3.ensureLibs();

      console.log("Pobieranie danych rodziny...");
      // Pobierz dane dla danej rodziny
      await window.genealogiaD3.fetchData(familyName);

      console.log("Rysowanie drzewa...");
      // Narysuj drzewo
      window.genealogiaD3.drawTree();
      
      console.log("Drzewo rodziny", familyName, "zostało wyświetlone");
    } catch (err) {
      // Wyświetlenie błędu w modalu
      genealogyChart.innerHTML = `
        <div style="color: red; padding: 20px;">
          <h2>Błąd podczas ładowania drzewa</h2>
          <p>${err.message}</p>
          <p style="font-size: 12px; color: #666;">Sprawdź konsolę przeglądarki dla szczegółów</p>
        </div>
      `;
      console.error("Błąd podczas wyświetlania drzewa rodziny:", err);
    }
  }

  // --- POZOSTAŁE ZDARZENIA INTERFEJSU ---
  
  // Przycisk dodawania nowej osoby
  showAddBtn.addEventListener("click", () => openModal(null));
  
  // Przyciski zamykania modala
  closeModalBtn.addEventListener("click", () => modal.classList.add("hidden"));
  cancelEditBtn.addEventListener("click", () => modal.classList.add("hidden"));
  
  // Zamykanie modala przez kliknięcie w tło
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
  
  // Filtry w czasie rzeczywistym
  searchInput.addEventListener("input", applyFilters);
  familyFilter.addEventListener("change", applyFilters);

  // --- LOGIKA MENEDŻERA KOPII ZAPASOWYCH ---
  
  // Elementy interfejsu menedżera kopii
  const showBackupManagerBtn = document.getElementById("showBackupManagerBtn");
  const backupModal = document.getElementById("backupManagerModal");
  const closeBackupModalBtn = document.getElementById("closeBackupModalBtn");
  const createBackupBtn = document.getElementById("createBackupBtn");
  const backupListBody = document.getElementById("backupListBody");

  // Otwieranie modala kopii zapasowych
  showBackupManagerBtn.addEventListener("click", async () => {
    backupModal.classList.remove("hidden");
    await refreshBackupList();
  });

  // Zamykanie modala kopii zapasowych
  closeBackupModalBtn.addEventListener("click", () =>
    backupModal.classList.add("hidden"),
  );
  backupModal.addEventListener("click", (e) => {
    if (e.target === backupModal) backupModal.classList.add("hidden");
  });

  /**
   * Odświeża listę dostępnych kopii zapasowych.
   * 
   * Pobiera listę plików z serwera i renderuje je w tabeli
   * z przyciskami do przywracania i usuwania.
   */
  async function refreshBackupList() {
    try {
      backupListBody.innerHTML = '<tr><td colspan="2">Ładowanie...</td></tr>';
      
      // Pobranie listy plików z API
      const response = await fetch("/api/genealogy/backups");
      const files = await response.json();

      // Obsługa pustej listy
      if (files.length === 0) {
        backupListBody.innerHTML =
          '<tr><td colspan="2">Brak dostępnych kopii zapasowych.</td></tr>';
        return;
      }

      // Renderowanie listy kopii
      backupListBody.innerHTML = "";
      files.forEach((filename) => {
        const row = document.createElement("tr");
        row.innerHTML = `
                    <td>${filename}</td>
                    <td class="actions">
                        <button class="btn save-btn restore-backup-btn" data-filename="${filename}">Przywróć</button>
                        <button class="btn delete-btn delete-backup-btn" data-filename="${filename}">Usuń</button>
                    </td>
                `;
        backupListBody.appendChild(row);
      });
    } catch (error) {
      backupListBody.innerHTML =
        '<tr><td colspan="2" style="color: red;">Błąd ładowania listy.</td></tr>';
      console.error("Błąd odświeżania listy backupów:", error);
    }
  }

  /**
   * Obsługa tworzenia nowej kopii zapasowej.
   * 
   * Wysyła żądanie do serwera o utworzenie kopii aktualnego stanu
   * pliku genealogia.json z timestampem w nazwie.
   */
  createBackupBtn.addEventListener("click", async () => {
    if (!confirm(
        "Czy na pewno chcesz utworzyć nową kopię zapasową aktualnego stanu danych genealogii?",
      ))
      return;

    // Blokada przycisku na czas operacji
    createBackupBtn.disabled = true;
    createBackupBtn.textContent = "Tworzenie...";
    
    try {
      const response = await fetch("/api/genealogy/backups/create", {
        method: "POST",
      });
      if (!response.ok) throw new Error("Błąd serwera przy tworzeniu kopii.");
      
      alert("Kopia zapasowa została utworzona pomyślnie!");
      await refreshBackupList();
    } catch (error) {
      alert(`Błąd: ${error.message}`);
    } finally {
      // Przywrócenie przycisku
      createBackupBtn.disabled = false;
      createBackupBtn.textContent = "Stwórz nową kopię zapasową";
    }
  });

  /**
   * Delegacja zdarzeń dla przycisków w tabeli kopii zapasowych.
   * 
   * Obsługuje przywracanie i usuwanie kopii zapasowych.
   */
  backupListBody.addEventListener("click", async (e) => {
    const target = e.target;
    const filename = target.dataset.filename;
    if (!filename) return;

    // --- Przywracanie kopii ---
    if (target.classList.contains("restore-backup-btn")) {
      const msg = `UWAGA!\n\nCzy na pewno chcesz przywrócić kopię '${filename}'?\n\n` +
                  `Spowoduje to nadpisanie aktualnego pliku roboczego. ` +
                  `Wszystkie niezapisane zmiany zostaną utracone.`;
      
      if (confirm(msg)) {
        try {
          const response = await fetch("/api/genealogy/backups/restore", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename }),
          });
          if (!response.ok)
            throw new Error("Błąd serwera przy przywracaniu kopii.");
          
          alert("Kopia zapasowa przywrócona. Strona zostanie teraz odświeżona.");
          window.location.reload();
        } catch (error) {
          alert(`Błąd: ${error.message}`);
        }
      }
    }

    // --- Usuwanie kopii ---
    if (target.classList.contains("delete-backup-btn")) {
      if (confirm(`Czy na pewno chcesz trwale usunąć kopię zapasową '${filename}'?`)) {
        try {
          const response = await fetch(`/api/genealogy/backups/${filename}`, {
            method: "DELETE",
          });
          if (!response.ok)
            throw new Error("Błąd serwera przy usuwaniu kopii.");
          
          alert("Kopia zapasowa usunięta.");
          await refreshBackupList();
        } catch (error) {
          alert(`Błąd: ${error.message}`);
        }
      }
    }
  });
  
  // --- INICJALIZACJA APLIKACJI ---
  // Pierwsze uruchomienie - pobranie danych i renderowanie
  fetchData();
});

// --- OBSŁUGA DRZEWA GENEALOGICZNEGO PO ZAŁADOWANIU STRONY ---

window.addEventListener("load", () => {
  // Zbieramy potrzebne elementy DOM
  const showBtn = document.getElementById("showGenealogyTreeBtn");
  const genealogyModal = document.getElementById("genealogyModal");
  const genealogyChart = document.getElementById("genealogy-chart");
  const closeBtn = document.getElementById("closeGenealogyModalBtn");

  // Jeśli czegoś brakuje w danym widoku – wychodzimy
  if (!showBtn || !genealogyModal || !genealogyChart || !closeBtn) return;

  // Odsłaniamy przycisk dopiero gdy biblioteka drzewa jest załadowana
  if (window.genealogiaD3) showBtn.classList.remove("hidden");

  /**
   * Obsługa przycisku wyświetlania głównego drzewa genealogicznego.
   * 
   * Otwiera modal i renderuje kompletne drzewo wszystkich osób.
   */
  showBtn.addEventListener("click", async () => {
    genealogyModal.classList.add("visible");
    genealogyChart.innerHTML = "<h2>Ładowanie drzewa…</h2>";
    
    try {
      // Załaduj biblioteki D3 jeśli potrzebne
      await window.genealogiaD3.ensureLibs();
      // Narysuj drzewo
      window.genealogiaD3.drawTree();
    } catch (err) {
      genealogyChart.innerHTML = `<h2>Błąd: ${err.message}</h2>`;
      console.error(err);
    }
  });

  // Zamykanie modala drzewa
  closeBtn.addEventListener("click", () =>
    genealogyModal.classList.remove("visible"),
  );
  
  // Zamykanie przez kliknięcie w tło
  genealogyModal.addEventListener("click", (e) => {
    if (e.target === genealogyModal) genealogyModal.classList.remove("visible");
  });
});

/**
 * Obsługa przycisku "Wyjdź bez zapisu".
 * 
 * Zamyka serwer bez zapisywania zmian.
 * Używane gdy użytkownik chce anulować wszystkie modyfikacje.
 */
document.getElementById("exit-no-save").addEventListener("click", () => {
  // Wywołujemy tylko shutdown, bez zapisu danych
  fetch("/shutdown", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => {
      if (response.ok) {
        // Zamknij okno dopiero po otrzymaniu potwierdzenia
        window.close();
      } else {
        alert("Nie udało się zamknąć serwera: " + response.statusText);
      }
    })
    .catch((err) => {
      console.error("Błąd przy shutdown:", err);
      alert("Wystąpił błąd podczas zamykania.");
    });
});