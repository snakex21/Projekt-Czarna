/**
 * ==========================================================================
 * Plik: editor_script.js
 * Opis: Edytor genealogiczny - zarządzanie danymi genealogicznymi.
 *       Obsługa tabeli osób, relacji rodzinnych i wizualizacji drzew.
 * ==========================================================================
 */

document.addEventListener("DOMContentLoaded", () => {
  // ==========================================================================
  // KONFIGURACJA I ZMIENNE GLOBALNE
  // ==========================================================================
  
  const GENEALOGIA_API_URL = "/api/genealogia";
  const PROTOCOLS_API_URL = "/api/protocols";
  
  // Elementy DOM
  const tableBody = document.getElementById("genealogyTableBody");
  const searchInput = document.getElementById("searchGenealogyInput");
  const familyFilter = document.getElementById("familyFilter");
  
  // Elementy modala
  const showAddBtn = document.getElementById("showAddFormBtn");
  const modal = document.getElementById("editGenealogyModal");
  const modalTitle = document.getElementById("modalTitle");
  const editForm = document.getElementById("editGenealogyForm");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const cancelEditBtn = document.getElementById("cancelEditBtn");
  const saveAndCloseBtn = document.getElementById("saveAndCloseBtn");

  // Elementy dynamiczne małżonków
  const spousesContainer = document.getElementById("spouses-container");
  const addSpouseBtn = document.getElementById("addSpouseBtn");
  
  // Dane aplikacji
  let allPeople = [];
  let allProtocols = [];

  // ==========================================================================
  // STYLE DYNAMICZNE
  // ==========================================================================

  const navigationStyles = document.createElement("style");
  navigationStyles.textContent = `
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
    
    .loading-content {
      background: white;
      padding: 30px;
      border-radius: 10px;
      text-align: center;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .loading-content h3 {
      margin: 0 0 20px 0;
      color: #333;
    }
    
    .spinner {
      border: 4px solid #f3f3f3;
      border-top: 4px solid #3498db;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 0 auto;
    }
    
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    
    .protocol-link {
      color: #007bff;
      text-decoration: underline;
      cursor: pointer;
    }
    
    .protocol-link:hover {
      color: #0056b3;
    }
  `;
  document.head.appendChild(navigationStyles);

  // ==========================================================================
  // FUNKCJE WYPEŁNIANIA LIST
  // ==========================================================================

  /**
   * Wypełnia listę protokołów do autouzupełniania.
   */
  function populateProtocolsDatalist() {
    const datalist = document.getElementById("protocols-list");
    datalist.innerHTML = "";
    
    allProtocols.forEach((protocol) => {
      const option = document.createElement("option");
      option.value = protocol.key;
      option.textContent = `(${protocol.orderNumber}) ${protocol.name}`;
      datalist.appendChild(option);
    });
  }

  /**
   * Wypełnia listę osób do autouzupełniania relacji.
   */
  function populatePeopleDatalist() {
    const datalist = document.getElementById("people-list");
    if (!datalist) return;
    datalist.innerHTML = "";

    const sortedPeople = [...allPeople].sort((a, b) =>
      (a.imie || "").localeCompare(b.imie || ""),
    );

    sortedPeople.forEach((person) => {
      const option = document.createElement("option");
      option.value = person.id_osoby;
      option.textContent = `${person.imie} ${person.nazwisko} (ur. ${person.rok_urodzenia || "?"})`;
      datalist.appendChild(option);
    });
  }

  /**
   * Wypełnia filtr rodzin znormalizowanymi nazwiskami.
   */
  function populateFamilyFilter() {
    const canonicalFamilyNames = new Set();

    function getCanonicalSurname(surname) {
      if (!surname || typeof surname !== "string") {
        return null;
      }

      let baseName = surname.trim().split(" ").pop().toLowerCase();

      // Normalizacja feminatywów
      if (baseName.endsWith("ska")) {
        baseName = baseName.slice(0, -3) + "ski";
      } else if (baseName.endsWith("cka")) {
        baseName = baseName.slice(0, -3) + "cki";
      } else if (baseName.endsWith("dzka")) {
        baseName = baseName.slice(0, -4) + "dzki";
      } else if (baseName.endsWith("owa")) {
        baseName = baseName.slice(0, -3);
      }

      return baseName.charAt(0).toUpperCase() + baseName.slice(1);
    }

    allPeople.forEach((person) => {
      const canonicalName = getCanonicalSurname(person.nazwisko);
      if (canonicalName) {
        canonicalFamilyNames.add(canonicalName);
      }
    });

    const sortedFamilies = Array.from(canonicalFamilyNames).sort((a, b) =>
      a.localeCompare(b),
    );

    familyFilter.innerHTML = '<option value="">— Wszystkie rodziny —</option>';
    sortedFamilies.forEach((familyName) => {
      const option = document.createElement("option");
      option.value = familyName;
      option.textContent = `Rodzina ${familyName}`;
      familyFilter.appendChild(option);
    });
  }

  // ==========================================================================
  // RENDEROWANIE TABELI
  // ==========================================================================
  
  /**
   * Renderuje tabelę genealogiczną z grupowaniem po rodach.
   */
  function renderTableGrouped(data) {
    tableBody.innerHTML = "";

    const peopleMap = new Map(allPeople.map((p) => [p.id_osoby, p]));
    
    // Mapa dzieci
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

    // Wyznaczanie pokoleń (BFS)
    const generationMap = new Map();
    const roots = data
      .filter((p) => !p.id_ojca && !p.id_matki)
      .map((p) => p.id_osoby);
    roots.forEach((id) => generationMap.set(id, 0));

    const q = [...roots];
    while (q.length) {
      const currId = q.shift();
      const gen = generationMap.get(currId);

      (childrenMap.get(currId) || []).forEach((ch) => {
        if (
          !generationMap.has(ch.id_osoby) ||
          generationMap.get(ch.id_osoby) > gen + 1
        ) {
          generationMap.set(ch.id_osoby, gen + 1);
          q.push(ch.id_osoby);
        }
      });

      const curr = peopleMap.get(currId);
      if (curr && curr.id_malzonka) {
        const spouseId = curr.id_malzonka;
        if (!generationMap.has(spouseId) || generationMap.get(spouseId) > gen) {
          generationMap.set(spouseId, gen);
          q.push(spouseId);
        }
      }
    }

    // Funkcje pomocnicze dla rodów
    function canonicalSurname(raw) {
      if (!raw) return "";
      raw = raw.trim();

      if (raw.toLowerCase().startsWith("z ")) {
        raw = raw.slice(2).trim();
      }

      let last = raw.split(/\s+/).pop().toLowerCase();

      if (last.endsWith("ska")) last = last.slice(0, -3) + "ski";
      else if (last.endsWith("cka")) last = last.slice(0, -3) + "cki";
      else if (last.endsWith("dzka")) last = last.slice(0, -4) + "dzki";
      else if (last.endsWith("owa")) last = last.slice(0, -3);
      else if (last.endsWith("a") && last.length > 4) last = last.slice(0, -1);

      return last.charAt(0).toUpperCase() + last.slice(1);
    }

    function findLineageName(person) {
      const visited = new Set();

      function findRoot(currentPerson) {
        if (!currentPerson || visited.has(currentPerson.id_osoby)) {
          return currentPerson;
        }
        visited.add(currentPerson.id_osoby);

        if (currentPerson.id_ojca && peopleMap.has(currentPerson.id_ojca)) {
          return findRoot(peopleMap.get(currentPerson.id_ojca));
        }

        if (currentPerson.id_matki && peopleMap.has(currentPerson.id_matki)) {
          return findRoot(peopleMap.get(currentPerson.id_matki));
        }

        return currentPerson;
      }

      const rootPerson = findRoot(person);
      const lineageName = canonicalSurname(
        rootPerson.nazwisko || person.nazwisko,
      );

      const isIsolated =
        !person.id_ojca &&
        !person.id_matki &&
        !person.id_malzonka &&
        !(
          childrenMap.has(person.id_osoby) &&
          childrenMap.get(person.id_osoby).length > 0
        );

      if (isIsolated) {
        return `${person.imie} ${person.nazwisko} (osobna linia)`;
      }

      return lineageName;
    }

    // Grupowanie po rodach
    const lineages = new Map();
    data.forEach((p) => {
      const lin = findLineageName(p);
      if (!lineages.has(lin)) lineages.set(lin, []);
      lineages.get(lin).push(p);
    });

    // Renderowanie grup
    [...lineages.keys()].sort().forEach((lineName) => {
      const members = lineages
        .get(lineName)
        .sort((a, b) => (a.rok_urodzenia || 9999) - (b.rok_urodzenia || 9999));

      const display = new Map();
      members.forEach((p) => {
        display.set(p.id_osoby, p);
        const spouse = peopleMap.get(p.id_malzonka);
        if (
          spouse &&
          !display.has(spouse.id_osoby) &&
          p.nazwisko === lineName
        ) {
          display.set(spouse.id_osoby, { ...spouse, _isSpouseInLaw: true });
        }
      });

      // Nagłówek rodu
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

      // Wiersze członków
      const rows = [];
      [...display.values()].forEach((p) => {
        const row = document.createElement("tr");
        row.classList.add("family-member");
        row.classList.add(`gen-${generationMap.get(p.id_osoby) || 0}`);
        if (p.id_malzonka || p._isSpouseInLaw) row.classList.add("spouse-row");

        const years = `${p.rok_urodzenia || "?"} – ${p.rok_smierci || "?"}`
          .replace(/– \?$/, "")
          .replace(/^\? –/, "");
        
        const parents = [
          peopleMap.get(p.id_ojca)?.imie,
          peopleMap.get(p.id_matki)?.imie,
        ]
          .filter(Boolean)
          .join(", ");
        
        const spouseName = peopleMap.get(p.id_malzonka)?.imie || "";

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

      // Zwijanie/rozwijanie
      hdr.querySelector("td:first-child").addEventListener("click", () => {
        const collapsed = hdr.classList.toggle("collapsed");
        rows.forEach((r) => (r.style.display = collapsed ? "none" : ""));
      });
    });
  }

  /**
   * Aplikuje filtry do tabeli.
   */
  function applyFilters() {
    const term = searchInput.value.toLowerCase();
    const family = familyFilter.value;
    
    const filteredData = allPeople.filter((p) => {
      const nameMatch = `${p.imie || ""} ${p.nazwisko || ""}`
        .toLowerCase()
        .includes(term);
      
      const familyMatch =
        !family ||
        p.nazwisko === family ||
        (p.id_ojca &&
          allPeople.find((f) => f.id_osoby === p.id_ojca)?.nazwisko === family);
      
      return nameMatch && familyMatch;
    });
    
    renderTableGrouped(filteredData);
  }

  // ==========================================================================
  // OBSŁUGA MODALA EDYCJI
  // ==========================================================================

  /**
   * Tworzy wiersz edycji małżonka.
   */
  function createSpouseRow(spouseId = "", weddingYear = "") {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.gap = "10px";
    row.style.marginBottom = "8px";
    row.className = "spouse-row-entry";

    // Input ID małżonka
    const idInput = document.createElement("input");
    idInput.type = "text";
    idInput.placeholder = "ID Małżonka";
    idInput.setAttribute("list", "people-list"); // Podpinamy autouzupełnianie
    idInput.value = spouseId;
    idInput.style.flex = "2";
    idInput.className = "spouse-id-input";

    // Input Rok Ślubu
    const dateInput = document.createElement("input");
    dateInput.type = "number";
    dateInput.placeholder = "Rok ślubu";
    dateInput.value = weddingYear;
    dateInput.style.flex = "1";
    dateInput.className = "spouse-date-input";

    // Przycisk usuwania
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.textContent = "🗑️";
    delBtn.className = "btn delete-btn";
    delBtn.style.padding = "5px 10px";
    delBtn.onclick = () => row.remove();

    row.appendChild(idInput);
    row.appendChild(dateInput);
    row.appendChild(delBtn);

    spousesContainer.appendChild(row);
  }

  // Obsługa przycisku dodawania małżonka
  if (addSpouseBtn) {
    addSpouseBtn.addEventListener("click", () => createSpouseRow());
  }

  /**
   * Otwiera modal edycji/dodawania osoby.
   */
  function openModal(person = null) {
    editForm
      .querySelectorAll("input")
      .forEach((input) => (input.style.borderColor = ""));
    
    // Wyczyść listę małżonków
    spousesContainer.innerHTML = "";

    if (person) {
      // Tryb edycji
      modalTitle.textContent = `Edytuj osobę: ${person.imie} ${person.nazwisko}`;
      editForm["edit-person-id"].value = person.id_osoby;
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
      editForm["edit-wlasciciel-id"].value = person.protokol_klucz || "";

      // Wypełnij małżonków
      if (person.malzenstwa && Array.isArray(person.malzenstwa)) {
        person.malzenstwa.forEach(m => {
          // Obsługa formatu backendu (key: spouseId, date/weddingDate)
          const date = m.date || m.weddingDate || ""; 
          createSpouseRow(m.spouseId, date);
        });
      } else if (person.id_malzonka) {
        // Fallback dla starego formatu
        createSpouseRow(person.id_malzonka, "");
      }

    } else {
      // Tryb dodawania
      modalTitle.textContent = "Dodaj nową osobę";
      editForm.reset();
      editForm["edit-person-id"].value = "";
      // Domyślnie jeden pusty wiersz małżonka? Niekoniecznie.
    }
    
    modal.classList.remove("hidden");
    document.getElementById("edit-id-osoby").focus();
  }

  // ==========================================================================
  // POBIERANIE DANYCH
  // ==========================================================================

  /**
   * Pobiera dane z API i inicjalizuje aplikację.
   */
  async function fetchData() {
    try {
      const [genealogyRes, protocolsRes] = await Promise.all([
        fetch(GENEALOGIA_API_URL),
        fetch(PROTOCOLS_API_URL),
      ]);
      
      if (!genealogyRes.ok)
        throw new Error(`Błąd wczytywania genealogii: ${genealogyRes.status}`);
      if (!protocolsRes.ok)
        throw new Error(`Błąd wczytywania protokołów: ${protocolsRes.status}`);

      const rawData = await genealogyRes.json();
      allPeople = Array.isArray(rawData) ? rawData : rawData.persons || [];
      allProtocols = await protocolsRes.json();
      
      populateProtocolsDatalist();
      populatePeopleDatalist();
      populateFamilyFilter();
      renderTableGrouped(allPeople);
    } catch (err) {
      console.error("Błąd ładowania danych:", err);
      tableBody.innerHTML = `<tr><td colspan="7" style="color: red; text-align: center;">${err.message}</td></tr>`;
    }
  }

  // ==========================================================================
  // OBSŁUGA FORMULARZA
  // ==========================================================================

  /**
   * Zapisuje dane z formularza edycji.
   */
  editForm.addEventListener("submit", (e) => {
    e.preventDefault();

    const originalId = editForm["edit-person-id"].value;
    const newId = editForm["edit-id-osoby"].value.trim();

    // Walidacja
    if (!newId) {
      alert('Pole "Unikalne ID Osoby" jest wymagane!');
      editForm["edit-id-osoby"].style.borderColor = "red";
      return;
    }

    const isIdTaken = allPeople.some(
      (p) => p.id_osoby === newId && p.id_osoby !== originalId,
    );
    if (isIdTaken) {
      alert(`ID "${newId}" jest już używane przez inną osobę!`);
      editForm["edit-id-osoby"].style.borderColor = "red";
      return;
    }

    // Zbieranie danych o małżonkach
    const spouseRows = document.querySelectorAll(".spouse-row-entry");
    const marriagesList = [];
    
    spouseRows.forEach(row => {
      const sid = row.querySelector(".spouse-id-input").value.trim();
      const sdate = row.querySelector(".spouse-date-input").value.trim();
      if (sid) {
        marriagesList.push({
          spouseId: sid,
          date: sdate ? parseInt(sdate, 10) : null
        });
      }
    });

    // Kompatybilność wsteczna: główny małżonek to pierwszy z listy
    const primarySpouseId = marriagesList.length > 0 ? marriagesList[0].spouseId : null;

    // Tworzenie obiektu danych
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
      id_malzonka: primarySpouseId, 
      malzenstwa: marriagesList, // Nowe pole z listą
      protokol_klucz: editForm["edit-wlasciciel-id"].value.trim() || null,
    };

    // Aktualizacja danych lokalnych
    if (originalId) {
      const personIndex = allPeople.findIndex((p) => p.id_osoby === originalId);
      if (personIndex > -1) {
        allPeople[personIndex] = payload;

        // Aktualizacja powiązań przy zmianie ID
        if (originalId !== newId) {
          allPeople.forEach((p) => {
            if (p.id_ojca === originalId) p.id_ojca = newId;
            if (p.id_matki === originalId) p.id_matki = newId;
            if (p.id_malzonka === originalId) p.id_malzonka = newId;
          });
        }
      }
    } else {
      allPeople.push(payload);
    }

    modal.classList.add("hidden");
    populatePeopleDatalist();
    applyFilters();
  });

  /**
   * Zapisuje i zamyka edytor.
   */
  saveAndCloseBtn.addEventListener("click", async () => {
    if (!confirm("Czy na pewno chcesz zapisać wszystkie zmiany i zamknąć edytor?"))
      return;

    try {
      // Czyszczenie danych
      let cleaned = allPeople.map((p) => {
        const { _isWifeInHusbandLineage, ...rest } = p;
        return rest;
      });

      // Walidacja referencji
      const ids = new Set(cleaned.map((p) => String(p.id_osoby)));
      cleaned = cleaned.map((p) => ({
        ...p,
        id_ojca: p.id_ojca && ids.has(String(p.id_ojca)) ? p.id_ojca : null,
        id_matki: p.id_matki && ids.has(String(p.id_matki)) ? p.id_matki : null,
        id_malzonka: p.id_malzonka && ids.has(String(p.id_malzonka)) ? p.id_malzonka : null,
      }));

      // Zapis
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

  // ==========================================================================
  // DELEGACJA ZDARZEŃ TABELI
  // ==========================================================================

  tableBody.addEventListener("click", async (e) => {
    const button = e.target.closest("button");
    
    // Przycisk drzewa
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

    // Przycisk edycji
    if (button && button.classList.contains("edit-btn")) {
      const id = button.dataset.id;
      const person = allPeople.find((p) => p.id_osoby === id);
      if (person) openModal(person);
      return;
    }
    
    // Przycisk usuwania
    if (button && button.classList.contains("delete-btn")) {
      const id = button.dataset.id;
      if (confirm(`Czy na pewno chcesz usunąć osobę o ID: ${id}?`)) {
        allPeople = allPeople.filter((p) => p.id_osoby !== id);

        allPeople.forEach((p) => {
          if (p.id_ojca === id) p.id_ojca = null;
          if (p.id_matki === id) p.id_matki = null;
          if (p.id_malzonka === id) p.id_malzonka = null;
        });

        populatePeopleDatalist();
        applyFilters();
      }
      return;
    }

    // Link protokołu
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
              `Zmień FLASK_HOST/FLASK_PORT w .env backendu.`
            );
            return;
          }

          window.location.href = `${checkData.url}/wlasciciele/protokol.html?ownerId=${protocolKey}`;
          return;
        }

        alert(
          "Nie można przejść do protokołu.\n" +
          "Backend nie jest osiągalny pod domyślnym adresem (127.0.0.1:5000)."
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
   * Wyświetla drzewo genealogiczne rodziny.
   */
  async function showFamilyTree(familyName) {
    console.log("showFamilyTree wywołane dla:", familyName);
    
    const genealogyModal = document.getElementById("genealogyModal");
    const genealogyChart = document.getElementById("genealogy-chart");

    if (!genealogyModal || !genealogyChart) {
      console.error("Brak elementów modala drzewa genealogicznego");
      alert("Błąd: Nie znaleziono elementów interfejsu dla drzewa genealogicznego");
      return;
    }

    if (!window.genealogiaD3) {
      console.error("Biblioteka genealogiaD3 nie jest załadowana");
      alert("Błąd: Biblioteka wizualizacji drzewa nie została załadowana.");
      return;
    }

    genealogyModal.classList.add("visible");
    genealogyChart.innerHTML = `<h2>Ładowanie drzewa rodziny ${familyName}...</h2>`;

    try {
      console.log("Ładowanie bibliotek D3...");
      await window.genealogiaD3.ensureLibs();

      console.log("Pobieranie danych rodziny...");
      await window.genealogiaD3.fetchData(familyName);

      console.log("Rysowanie drzewa...");
      window.genealogiaD3.drawTree();
      
      console.log("Drzewo rodziny", familyName, "zostało wyświetlone");
    } catch (err) {
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

  // ==========================================================================
  // ZDARZENIA INTERFEJSU
  // ==========================================================================
  
  showAddBtn.addEventListener("click", () => openModal(null));
  closeModalBtn.addEventListener("click", () => modal.classList.add("hidden"));
  cancelEditBtn.addEventListener("click", () => modal.classList.add("hidden"));
  
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
  
  searchInput.addEventListener("input", applyFilters);
  familyFilter.addEventListener("change", applyFilters);

  // ==========================================================================
  // MENEDŻER KOPII ZAPASOWYCH
  // ==========================================================================
  
  const showBackupManagerBtn = document.getElementById("showBackupManagerBtn");
  const backupModal = document.getElementById("backupManagerModal");
  const closeBackupModalBtn = document.getElementById("closeBackupModalBtn");
  const createBackupBtn = document.getElementById("createBackupBtn");
  const backupListBody = document.getElementById("backupListBody");

  showBackupManagerBtn.addEventListener("click", async () => {
    backupModal.classList.remove("hidden");
    await refreshBackupList();
  });

  closeBackupModalBtn.addEventListener("click", () =>
    backupModal.classList.add("hidden"),
  );
  backupModal.addEventListener("click", (e) => {
    if (e.target === backupModal) backupModal.classList.add("hidden");
  });

  /**
   * Odświeża listę kopii zapasowych.
   */
  async function refreshBackupList() {
    try {
      backupListBody.innerHTML = '<tr><td colspan="2">Ładowanie...</td></tr>';
      
      const response = await fetch("/api/genealogy/backups");
      const files = await response.json();

      if (files.length === 0) {
        backupListBody.innerHTML =
          '<tr><td colspan="2">Brak dostępnych kopii zapasowych.</td></tr>';
        return;
      }

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
   * Tworzy nową kopię zapasową.
   */
  createBackupBtn.addEventListener("click", async () => {
    if (!confirm(
        "Czy na pewno chcesz utworzyć nową kopię zapasową aktualnego stanu danych genealogii?",
      ))
      return;

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
      createBackupBtn.disabled = false;
      createBackupBtn.textContent = "Stwórz nową kopię zapasową";
    }
  });

  /**
   * Obsługa przycisków w tabeli kopii.
   */
  backupListBody.addEventListener("click", async (e) => {
    const target = e.target;
    const filename = target.dataset.filename;
    if (!filename) return;

    // Przywracanie kopii
    if (target.classList.contains("restore-backup-btn")) {
      const msg = `UWAGA!\n\nCzy na pewno chcesz przywrócić kopię '${filename}'?\n\n` +
                  `Spowoduje to nadpisanie aktualnego pliku roboczego.`;
      
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

    // Usuwanie kopii
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
  
  // ==========================================================================
  // INICJALIZACJA
  // ==========================================================================
  
  fetchData();
});

// ==========================================================================
// OBSŁUGA DRZEWA GENEALOGICZNEGO
// ==========================================================================

window.addEventListener("load", () => {
  const showBtn = document.getElementById("showGenealogyTreeBtn");
  const genealogyModal = document.getElementById("genealogyModal");
  const genealogyChart = document.getElementById("genealogy-chart");
  const closeBtn = document.getElementById("closeGenealogyModalBtn");

  if (!showBtn || !genealogyModal || !genealogyChart || !closeBtn) return;

  if (window.genealogiaD3) showBtn.classList.remove("hidden");

  /**
   * Wyświetla główne drzewo genealogiczne.
   */
  showBtn.addEventListener("click", async () => {
    genealogyModal.classList.add("visible");
    genealogyChart.innerHTML = "<h2>Ładowanie drzewa…</h2>";
    
    try {
      await window.genealogiaD3.ensureLibs();
      window.genealogiaD3.drawTree();
    } catch (err) {
      genealogyChart.innerHTML = `<h2>Błąd: ${err.message}</h2>`;
      console.error(err);
    }
  });

  closeBtn.addEventListener("click", () =>
    genealogyModal.classList.remove("visible"),
  );
  
  genealogyModal.addEventListener("click", (e) => {
    if (e.target === genealogyModal) genealogyModal.classList.remove("visible");
  });
});

/**
 * Zamyka edytor bez zapisu.
 */
document.getElementById("exit-no-save").addEventListener("click", () => {
  fetch("/shutdown", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => {
      if (response.ok) {
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