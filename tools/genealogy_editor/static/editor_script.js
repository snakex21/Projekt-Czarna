document.addEventListener('DOMContentLoaded', () => {
  // --- STAN APLIKACJI ---
  let allPeople = []; // Pełna lista z backendu
  let filteredPeople = []; // Aktualnie wyświetlana lista
  let currentPerson = null; // Aktualnie wybrana osoba (szczegóły)

  // --- KONFIGURACJA API ---
  // Dostosowana do endpointów w editor_app.py
  const API = {
    list: '/api/genealogia',       // GET (wszyscy), POST (dodaj jeden)
    resource: '/api/genealogia',   // + /<id> dla PUT/DELETE
    tree: '/api/genealogia/drzewo', // + /<nazwisko>
    protocols: '/api/protocols',
    backups: '/api/backups'
  };

  // --- ELEMENTY DOM ---
  const els = {
    listContainer: document.getElementById('personsListContainer'),
    detailsPanel: document.getElementById('personDetailsPanel'),
    searchInput: document.getElementById('searchGenealogy'),
    filters: document.querySelectorAll('.filter-btn'),
    sortSelect: document.getElementById('sortFilter'),
    houseFilter: document.getElementById('filterHouse'),
    countBadge: document.getElementById('totalCount'),
    addBtn: document.getElementById('addGenealogyBtn'),

    // Modale
    editModal: document.getElementById('genealogyModal'),
    modalBody: document.getElementById('modalBody'),
    modalTitle: document.getElementById('modalTitle'),
    modalSave: document.getElementById('modalSave'),
    modalCancel: document.getElementById('modalCancel'),
    modalClose: document.getElementById('modalClose'),

    treeDialog: document.getElementById('treeDialog'),
    treeContainer: document.getElementById('treeContainer'),
    closeTreeBtn: document.getElementById('closeTreeBtn'),

    toastContainer: document.getElementById('toastContainer')
  };

  // --- INICJALIZACJA ---
  const init = async () => {
    // Theme Load
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
      document.body.classList.add('dark-mode');
      const btn = document.getElementById('themeToggle');
      if (btn) btn.innerHTML = '<i class="fas fa-sun"></i>';
    }

    setupEventListeners();
    await loadData();
  };

  const setupEventListeners = () => {
    // Wyszukiwanie i filtrowanie
    els.searchInput.addEventListener('input', filterData);
    els.houseFilter.addEventListener('input', filterData);
    els.sortSelect.addEventListener('change', () => {
      sortData();
      renderList();
    });

    els.filters.forEach(btn => {
      btn.addEventListener('click', () => {
        els.filters.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterData();
      });
    });

    // Modal Edycji
    els.addBtn.addEventListener('click', () => openEditModal(null));
    els.modalClose.addEventListener('click', closeModal);
    els.modalCancel.addEventListener('click', closeModal);
    // Klik poza modal zamyka? W adminie tak, ale tu mamy overlay
    els.editModal.addEventListener('click', (e) => {
      if (e.target === els.editModal) closeModal();
    });

    // Drzewo
    if (els.closeTreeBtn) {
      els.closeTreeBtn.addEventListener('click', () => {
        if (els.treeDialog.close) els.treeDialog.close();
        else els.treeDialog.classList.add('hidden'); // Fallback
      });
    }

    // Theme Toggle
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        themeBtn.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
      });
    }

    // --- BACKUPY ---
    const backupModal = document.getElementById('backupModal');
    if (document.getElementById('manageBackupsBtn')) {
      document.getElementById('manageBackupsBtn').addEventListener('click', () => {
        loadBackups();
        backupModal.classList.remove('hidden');
      });
    }
    if (document.getElementById('closeBackupModal')) {
      document.getElementById('closeBackupModal').addEventListener('click', () => {
        backupModal.classList.add('hidden');
      });
    }
    if (document.getElementById('createBackupBtn')) {
      document.getElementById('createBackupBtn').addEventListener('click', async () => {
        try {
          const res = await fetch(API.backups, { method: 'POST' });
          if (res.ok) {
            showToast('success', 'Utworzono kopię zapasową');
            loadBackups();
          } else showToast('error', 'Błąd tworzenia kopii');
        } catch (e) { showToast('error', e.message); }
      });
    }

    window.restoreBackup = async (filename) => {
      if (!confirm(`Czy na pewno przywrócić kopię ${filename}? Aktualne dane zostaną nadpisane.`)) return;
      try {
        const res = await fetch(`${API.backups}/${filename}`, { method: 'POST' });
        if (res.ok) {
          showToast('success', 'Przywrócono dane z kopii');
          backupModal.classList.add('hidden');
          loadData();
        } else showToast('error', 'Błąd przywracania');
      } catch (e) { showToast('error', e.message); }
    };

    const loadBackups = async () => {
      const listEl = document.getElementById('backupList');
      listEl.innerHTML = '<div class="loader">Ładowanie...</div>';
      try {
        const res = await fetch(API.backups);
        const files = await res.json();
        listEl.innerHTML = files.map(f => `
                    <li style="display:flex;justify-content:space-between;padding:8px;border-bottom:1px solid #eee;">
                        <span>${f}</span>
                        <button class="btn-secondary small" onclick="window.restoreBackup('${f}')">Przywróć</button>
                    </li>
                `).join('');
        if (files.length === 0) listEl.innerHTML = '<li style="padding:10px;">Brak kopii zapasowych</li>';
      } catch (e) {
        listEl.innerHTML = '<li class="error">Błąd ładowania listy</li>';
      }
    };
  };

  // --- OBSŁUGA DANYCH ---
  const loadData = async () => {
    try {
      els.listContainer.innerHTML = '<div class="loader">Pobieranie danych...</div>';
      const res = await fetch(API.list);
      if (!res.ok) throw new Error('Błąd sieci');
      allPeople = await res.json();

      // Wstępne sortowanie A-Z
      allPeople.sort((a, b) => (a.nazwisko || '').localeCompare(b.nazwisko || ''));

      filteredPeople = [...allPeople];
      updateCount();
      renderList();

      // Jeśli była wybrana osoba, odśwież jej widok
      if (currentPerson) {
        const refreshed = allPeople.find(p => String(p.id_osoby) === String(currentPerson.id_osoby));
        if (refreshed) showDetails(refreshed);
        else els.detailsPanel.innerHTML = '<div class="no-selection-placeholder"><h3>Osoba usunięta</h3></div>';
      }
    } catch (err) {
      console.error(err);
      showToast('error', 'Nie udało się pobrać listy osób');
      els.listContainer.innerHTML = '<div class="error">Błąd pobierania danych</div>';
    }
  };

  const filterData = () => {
    const query = els.searchInput.value.toLowerCase();
    const houseQuery = els.houseFilter.value.trim();
    const activeFilter = document.querySelector('.filter-btn.active').dataset.filter; // all, male, female

    filteredPeople = allPeople.filter(p => {
      const fullName = `${p.imie} ${p.nazwisko} ${p.rok_urodzenia || ''}`.toLowerCase();
      const matchesQuery = fullName.includes(query) || String(p.id_osoby).includes(query);

      let matchesHouse = true;
      if (houseQuery) {
        matchesHouse = String(p.numer_domu || '').includes(houseQuery);
      }

      let matchesType = true;
      if (activeFilter === 'male' && p.plec !== 'M') matchesType = false;
      if (activeFilter === 'female' && p.plec !== 'F') matchesType = false;

      return matchesQuery && matchesHouse && matchesType;
    });

    sortData();
    updateCount();
    renderList();
  };

  const sortData = () => {
    const type = els.sortSelect.value;

    filteredPeople.sort((a, b) => {
      if (type === 'id_asc') return parseInt(a.id_osoby) - parseInt(b.id_osoby);
      if (type === 'id_desc') return parseInt(b.id_osoby) - parseInt(a.id_osoby);

      const nazwiskoA = (a.nazwisko || '').trim().toLowerCase();
      const nazwiskoB = (b.nazwisko || '').trim().toLowerCase();
      const imieA = (a.imie || '').trim().toLowerCase();
      const imieB = (b.imie || '').trim().toLowerCase();

      // Logika: Puste nazwiska ZAWSZE na koniec (dla A-Z)
      const hasNazwiskoA = nazwiskoA.length > 0;
      const hasNazwiskoB = nazwiskoB.length > 0;

      if (hasNazwiskoA && !hasNazwiskoB) return -1;
      if (!hasNazwiskoA && hasNazwiskoB) return 1;
      if (!hasNazwiskoA && !hasNazwiskoB) {
        // Obaj bez nazwiska -> po imieniu
        return type === 'az' ? imieA.localeCompare(imieB) : imieB.localeCompare(imieA);
      }

      // Obaj mają nazwisko.
      // Sortujemy PRIMARY po IMIENIU (żeby Adam Był pierwszy)
      const cmpName = type === 'az' ? imieA.localeCompare(imieB) : imieB.localeCompare(imieA);
      if (cmpName !== 0) return cmpName;

      // Jeśli imiona takie same -> po nazwisku
      return type === 'az' ? nazwiskoA.localeCompare(nazwiskoB) : nazwiskoB.localeCompare(nazwiskoA);
    });

    // renderList() is implicitly needed or called by caller. 
    // But in previous replacement we left it out. Wait, original code had renderList();
    // Let's add renderList() call to be safe as original function ended with it.
    renderList();
  };

  const updateCount = () => {
    els.countBadge.textContent = filteredPeople.length;
  };

  // --- RENDEROWANIE LISTY ---
  const renderList = () => {
    els.listContainer.innerHTML = '';
    if (filteredPeople.length === 0) {
      els.listContainer.innerHTML = '<div style="padding:10px;text-align:center;color:#888;">Brak wyników</div>';
      return;
    }

    // Renderuj pierwsze 100, reszta lazy loading? Na razie 200 hard limit dla wydajności
    const limit = 200;
    filteredPeople.slice(0, limit).forEach(p => {
      const el = document.createElement('div');
      el.className = 'person-list-item';
      if (currentPerson && String(currentPerson.id_osoby) === String(p.id_osoby)) {
        el.classList.add('active');
      }

      const lifeYears = (p.rok_urodzenia || p.rok_smierci)
        ? `${p.rok_urodzenia || '?'} - ${p.rok_smierci || '?'}`
        : '';

      el.innerHTML = `
                <div class="person-info">
                    <div class="person-name ${p.plec === 'M' ? 'male' : 'female'}">
                        ${p.imie} ${p.nazwisko}
                    </div>
                    <div class="person-details-mini">
                        ${lifeYears} ${p.numer_domu ? `🏠 ${p.numer_domu}` : ''}
                    </div>
                </div>
                <div class="person-id">ID: ${p.id_osoby}</div>
            `;

      el.addEventListener('click', () => showDetails(p));
      els.listContainer.appendChild(el);
    });

    if (filteredPeople.length > limit) {
      const more = document.createElement('div');
      more.style.textAlign = 'center';
      more.style.padding = '10px';
      more.style.color = '#888';
      more.textContent = `... i ${filteredPeople.length - limit} więcej (użyj wyszukiwania)`;
      els.listContainer.appendChild(more);
    }
  };

  // --- WIDOK SZCZEGÓŁÓW (SIDEBAR + DETAILS MATCH) ---
  const showDetails = (person) => {
    currentPerson = person;

    // Highlight active item
    document.querySelectorAll('.person-list-item').forEach(el => el.classList.remove('active'));
    // (Active class adding logic can be handled by click event loosely or here if needed, but keeping it simple)

    const genderIcon = person.plec === 'M' ? '<i class="fas fa-mars gender-icon"></i>' : '<i class="fas fa-venus gender-icon"></i>';
    const years = (person.rok_urodzenia || person.rok_smierci)
      ? `(${person.rok_urodzenia || '?'} - ${person.rok_smierci || '?'})` : '';

    // --- LOGIKA RELACJI (EXTENDED) ---
    const getP = (id) => id ? allPeople.find(p => String(p.id_osoby) === String(id)) : null;

    // Rodzice
    const father = getP(person.id_ojca);
    const mother = getP(person.id_matki);

    // Dziadkowie
    const grandparents = [];
    if (father) {
      if (father.id_ojca) grandparents.push({ p: getP(father.id_ojca), role: 'Dziadek (od ojca)' });
      if (father.id_matki) grandparents.push({ p: getP(father.id_matki), role: 'Babcia (od ojca)' });
    }
    if (mother) {
      if (mother.id_ojca) grandparents.push({ p: getP(mother.id_ojca), role: 'Dziadek (od matki)' });
      if (mother.id_matki) grandparents.push({ p: getP(mother.id_matki), role: 'Babcia (od matki)' });
    }

    // Rodzeństwo (Ta sama matka LUB ten sam ojciec, ale nie ja sam)
    const siblings = allPeople.filter(p => {
      if (String(p.id_osoby) === String(person.id_osoby)) return false;
      const sameFather = person.id_ojca && String(p.id_ojca) === String(person.id_ojca);
      const sameMother = person.id_matki && String(p.id_matki) === String(person.id_matki);
      return sameFather || sameMother;
    });

    // Kuzynowie: Dzieci rodzeństwa rodziców
    const cousins = [];
    const getSiblingsOf = (parent) => {
      if (!parent) return [];
      return allPeople.filter(p =>
        String(p.id_osoby) !== String(parent.id_osoby) && (
          (parent.id_ojca && String(p.id_ojca) === String(parent.id_ojca)) ||
          (parent.id_matki && String(p.id_matki) === String(parent.id_matki))
        )
      );
    };

    const unclesAunts = [...getSiblingsOf(father), ...getSiblingsOf(mother)];
    // Unique uncles/aunts (remove dupes just in case)
    const uniqueUncles = [...new Map(unclesAunts.map(item => [item['id_osoby'], item])).values()];

    uniqueUncles.forEach(ua => {
      const uKids = allPeople.filter(k => String(k.id_ojca) === String(ua.id_osoby) || String(k.id_matki) === String(ua.id_osoby));
      uKids.forEach(k => cousins.push({ p: k, role: `Kuzyn/ka (od ${ua.imie})` }));
    });


    // --- GENEROWANIE HTML ---

    const createCard = (p, role) => p ? createRelationCard(p.id_osoby, role, p.plec) : '';

    let parentsHtml = '';
    if (father) parentsHtml += createCard(father, 'OJCIEC');
    if (mother) parentsHtml += createCard(mother, 'MATKA');

    let gparentsHtml = grandparents.map(g => createCard(g.p, g.role.toUpperCase())).join('');

    let siblingsHtml = siblings.map(s => createCard(s, 'RODZEŃSTWO')).join('');

    let cousinsHtml = cousins.map(c => createCard(c.p, c.role.toUpperCase())).join('');

    // Małżonkowie
    let spousesHtml = '';
    const spousesList = person.marriages || [];
    if (spousesList.length === 0 && person.id_malzonka) spousesList.push({ spouseId: person.id_malzonka });
    spousesList.forEach(m => spousesHtml += createRelationCard(m.spouseId, 'MAŁŻONEK', 'neutral'));

    // Dzieci
    const children = allPeople.filter(p => String(p.id_ojca) === String(person.id_osoby) || String(p.id_matki) === String(person.id_osoby));
    let childrenHtml = children.sort((a, b) => (a.rok_urodzenia || 0) - (b.rok_urodzenia || 0))
      .map(c => createRelationCard(c.id_osoby, 'DZIECKO', c.plec, c.rok_urodzenia)).join('');

    // RENDER
    els.detailsPanel.innerHTML = `
        <div class="detail-header">
            <div class="person-title">
                <h1>${genderIcon} ${person.imie} ${person.nazwisko}</h1>
                <div class="dates">${years}</div>
                ${person.numer_domu ? `<div style="margin-top:5px;"><strong>Dom:</strong> ${person.numer_domu}</div>` : ''}
                ${person.uwagi ? `<div style="margin-top:10px;font-style:italic;">"${person.uwagi}"</div>` : ''}
            </div>
            <div class="detail-actions">
                <button class="btn-primary" onclick="window.editCurrentPerson()"><i class="fas fa-edit"></i> Edytuj</button>
                ${person.nazwisko ? `<button class="btn-secondary" onclick="window.showTreeForCurrent()"><i class="fas fa-sitemap"></i> Drzewo</button>` : ''}
                <button class="btn-secondary" style="color:var(--danger-color);border-color:var(--danger-color);" onclick="window.deleteCurrentPerson()"><i class="fas fa-trash"></i> Usuń</button>
            </div>
        </div>

        <div class="detail-grid">
            <div class="relation-group">
                <h3><i class="fas fa-users"></i> RODZINA</h3>
            </div>

            ${gparentsHtml ? `
            <div class="relation-group">
                <h3>DZIADKOWIE</h3>
                <div class="modern-grid">
                    ${gparentsHtml}
                </div>
            </div>` : ''}

            <div class="relation-group">
                <h3>RODZICE</h3>
                <div class="modern-grid">
                    ${parentsHtml || '<div class="text-muted">Brak danych</div>'}
                </div>
            </div>
            
            <div class="relation-group">
                <h3>MAŁŻONKOWIE</h3>
                <div class="modern-grid">
                    ${spousesList.length ? spousesHtml : '<div class="text-muted">Brak małżeństw</div>'}
                </div>
            </div>
            
            <div class="relation-group">
                <h3>DZIECI (${children.length})</h3>
                <div class="modern-grid">
                    ${childrenHtml || '<div class="text-muted">Brak dzieci w bazie</div>'}
                </div>
            </div>

            ${siblingsHtml ? `
            <div class="relation-group">
                <h3>RODZEŃSTWO (${siblings.length})</h3>
                <div class="modern-grid">
                    ${siblingsHtml}
                </div>
            </div>` : ''}
            
            ${cousinsHtml ? `
            <div class="relation-group">
                <h3>KUZYNOSTWO (${cousins.length})</h3>
                <div class="modern-grid">
                    ${cousinsHtml}
                </div>
            </div>` : ''}
            
            ${person.protokol_klucz ? `
                <div class="relation-group">
                    <h3>Protokół</h3>
                    <div class="relation-card" onclick="window.openProtocol('${person.protokol_klucz}')">
                         <div><strong><i class="fas fa-file-alt"></i> Protokół ${person.protokol_klucz}</strong></div>
                         <div><i class="fas fa-external-link-alt"></i></div>
                    </div>
                </div>` : ''}
        </div>
    `;

    // Globalne handlery
    window.editCurrentPerson = () => openEditModal(currentPerson);
    window.deleteCurrentPerson = () => deletePerson(currentPerson.id_osoby);
    window.showTreeForCurrent = () => showFamilyTree(person.nazwisko);
    window.openProtocol = (key) => window.open(`../wlasciciele/protokol.html?ownerId=${key}`, '_blank');
    window.goToPerson = (id) => {
      const target = allPeople.find(p => String(p.id_osoby) === String(id));
      if (target) showDetails(target);
    };
  };

  const createRelationCard = (id, role, genderClass, yearInfo = null) => {
    const p = allPeople.find(x => String(x.id_osoby) === String(id));
    // Fallback if not found
    if (!p) {
      return `
        <div class="modern-card">
            <div class="card-role">${role}</div>
            <div class="card-name">ID ${id}</div>
            <div class="card-dates">Nie znaleziono</div>
        </div>`;
    }

    const click = `onclick="window.goToPerson('${p.id_osoby}')"`;
    const gStyle = p.plec === 'M' ? 'male' : 'female';

    return `
        <div class="modern-card" ${click}>
            <div class="card-role">${role}</div>
            <div class="card-name ${gStyle}">${p.imie} ${p.nazwisko}</div>
            <div class="card-dates">
                ${p.rok_urodzenia || '?'} - ${p.rok_smierci || '?'}
                ${yearInfo ? `(ur. ${yearInfo})` : ''}
            </div>
        </div>
    `;
  };

  // --- MODAL EDYCJI / DODAWANIA (Z ADMIN.JS LOGIC) ---
  const openEditModal = (person) => {
    // Tytuł
    els.modalTitle.textContent = person ? `Edycja: ${person.imie} ${person.nazwisko}` : 'Dodaj Nową Osobę';

    // Budowanie formularza - wierna kopia z logic admina (autocomplete etc)
    // Dla uproszczenia tutaj wklejam gotowy HTML formularza, normalnie w Admin.js jest template string.

    const safe = (val) => val || '';

    els.modalBody.innerHTML = `
            <form id="genealogyForm">
                <input type="hidden" name="db_id" value="${safe(person?.db_id || person?.id_osoby)}">
                
                <div class="form-grid">
                    <div class="form-group">
                        <label>ID Osoby (Unikalne)</label>
                        <input type="number" name="id_osoby" value="${safe(person?.id_osoby)}" required ${person ? 'readonly style="background:#f7fafc;"' : ''}>
                    </div>
                </div>

                <div class="form-grid">
                    <div class="form-group">
                        <label>Imię</label>
                        <input type="text" name="imie" value="${safe(person?.imie)}" required>
                    </div>
                    <div class="form-group">
                        <label>Nazwisko</label>
                        <input type="text" name="nazwisko" value="${safe(person?.nazwisko)}" required>
                    </div>
                </div>

                <div class="form-grid">
                     <div class="form-group">
                        <label>Płeć</label>
                        <select name="plec">
                            <option value="M" ${person?.plec === 'M' ? 'selected' : ''}>Mężczyzna</option>
                            <option value="F" ${person?.plec === 'F' ? 'selected' : ''}>Kobieta</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Nr Domu</label>
                        <input type="text" name="numer_domu" value="${safe(person?.numer_domu)}">
                    </div>
                </div>

                <div class="form-grid">
                    <div class="form-group">
                        <label>Rok urodzenia</label>
                        <input type="number" name="rok_urodzenia" value="${safe(person?.rok_urodzenia)}">
                    </div>
                    <div class="form-group">
                        <label>Rok śmierci</label>
                        <input type="number" name="rok_smierci" value="${safe(person?.rok_smierci)}">
                    </div>
                </div>

                <!-- Rodzice - Autocomplete -->
                <div class="form-grid">
                    <div class="form-group">
                        <label>Ojciec</label>
                        <div style="position:relative;">
                            <input type="hidden" name="id_ojca" id="fatherIdInput" value="${safe(person?.id_ojca)}">
                            <input type="text" id="fatherAutocomplete" placeholder="Wpisz imię..." autocomplete="off">
                            <div id="fatherSuggestions" class="autocomplete-suggestions hidden"></div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Matka</label>
                        <div style="position:relative;">
                            <input type="hidden" name="id_matki" id="motherIdInput" value="${safe(person?.id_matki)}">
                            <input type="text" id="motherAutocomplete" placeholder="Wpisz imię..." autocomplete="off">
                            <div id="motherSuggestions" class="autocomplete-suggestions hidden"></div>
                        </div>
                    </div>
                </div>

                <!-- Małżeństwa -->
                <div class="form-group">
                     <label>Małżonkowie</label>
                     <div id="spousesContainer"></div>
                     <button type="button" class="btn-secondary small" id="addSpouseBtn">+ Dodaj małżonka</button>
                </div>

                <div class="form-group">
                    <label>Protokół (Klucz)</label>
                     <input type="text" name="protokol_klucz" value="${safe(person?.protokol_klucz)}">
                </div>

                <div class="form-group">
                    <label>Uwagi</label>
                    <textarea name="uwagi" rows="3">${safe(person?.uwagi)}</textarea>
                </div>
            </form>
        `;

    // Logika Autocomplete dla Rodziców
    setupAutocomplete('fatherAutocomplete', 'fatherIdInput', 'fatherSuggestions', 'M');
    setupAutocomplete('motherAutocomplete', 'motherIdInput', 'motherSuggestions', 'F');

    // Logika Małżonków
    const spousesContainer = document.getElementById('spousesContainer');
    const mkSpouseRow = (sid, year) => {
      const row = document.createElement('div');
      row.className = 'spouse-row';
      row.style.cssText = 'display:flex;gap:10px;margin-bottom:10px;align-items:center;';
      const uniq = Date.now() + Math.random().toString().slice(2, 5);

      // Znajdź nazwę jeśli jest ID
      let initName = '';
      if (sid) {
        const sp = allPeople.find(p => String(p.id_osoby) === String(sid));
        if (sp) initName = `${sp.imie} ${sp.nazwisko} (ID:${sp.id_osoby})`;
      }

      row.innerHTML = `
                <div style="position:relative;flex:2;">
                    <input type="hidden" class="spouse-id" value="${sid || ''}">
                    <input type="text" class="spouse-ac" id="sac_${uniq}" value="${initName}" placeholder="Imię małżonka..." autocomplete="off">
                    <div id="ssug_${uniq}" class="autocomplete-suggestions hidden"></div>
                </div>
                <button type="button" class="btn-icon" style="color:red;" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
             `;
      spousesContainer.appendChild(row);
      // Setup AC
      setupAutocomplete(`sac_${uniq}`, null, `ssug_${uniq}`, null, row.querySelector('.spouse-id'));
    };

    document.getElementById('addSpouseBtn').onclick = () => mkSpouseRow();

    // Wypełnianie istniejących małżonków
    const existingSpouses = person?.marriages || [];
    // Compat
    if (existingSpouses.length === 0 && person?.id_malzonka) {
      existingSpouses.push({ spouseId: person.id_malzonka });
    }
    existingSpouses.forEach(m => mkSpouseRow(m.spouseId, m.date));

    // Pre-fill parent names in inputs
    if (person?.id_ojca) {
      const f = allPeople.find(p => String(p.id_osoby) == String(person.id_ojca));
      if (f) document.getElementById('fatherAutocomplete').value = `${f.imie} ${f.nazwisko} (ID:${f.id_osoby})`;
    }
    if (person?.id_matki) {
      const m = allPeople.find(p => String(p.id_osoby) == String(person.id_matki));
      if (m) document.getElementById('motherAutocomplete').value = `${m.imie} ${m.nazwisko} (ID:${m.id_osoby})`;
    }

    // Pokaż modal
    els.editModal.classList.remove('hidden');

    // Obsługa Zapisz
    els.modalSave.onclick = async () => {
      const form = document.getElementById('genealogyForm');
      if (!form.checkValidity()) { form.reportValidity(); return; }

      const fd = new FormData(form);
      const data = Object.fromEntries(fd.entries());

      // Collect spouses
      const spouseRows = document.querySelectorAll('.spouse-row');
      const marriages = [];
      spouseRows.forEach(row => {
        const sid = row.querySelector('.spouse-id').value;
        if (sid) marriages.push({ spouse_json_id: sid });
      });
      data.marriages = marriages; // Backend expect this structure (from editor_app.py update)

      // Walidacje
      // ...

      if (person) {
        // UPDATE
        await savePerson(person.id_osoby, data, 'PUT');
      } else {
        // CREATE
        await savePerson(null, data, 'POST');
      }
    };
  };

  const setupAutocomplete = (inputId, hiddenIdId, suggId, genderFilter, hiddenInputRef = null) => {
    const input = document.getElementById(inputId);
    const hiddenInfo = hiddenInputRef || document.getElementById(hiddenIdId);
    const suggBox = document.getElementById(suggId);
    if (!input || !suggBox) return;

    input.addEventListener('input', () => {
      const val = input.value.toLowerCase().trim();
      suggBox.innerHTML = '';
      if (val.length < 1) { suggBox.classList.add('hidden'); return; }

      let matches = allPeople.filter(p => {
        const txt = `${p.imie} ${p.nazwisko} ${p.id_osoby}`.toLowerCase();
        return txt.includes(val);
      });
      if (genderFilter) matches = matches.filter(p => p.plec === genderFilter);

      matches = matches.slice(0, 10); // Limit

      if (matches.length > 0) {
        matches.forEach(p => {
          const div = document.createElement('div');
          div.className = 'autocomplete-suggestion';
          div.innerHTML = `<strong>${p.imie} ${p.nazwisko}</strong> (ID: ${p.id_osoby})`;
          div.onclick = () => {
            input.value = `${p.imie} ${p.nazwisko} (ID: ${p.id_osoby})`;
            if (hiddenInfo) hiddenInfo.value = p.id_osoby;
            suggBox.classList.add('hidden');
          };
          suggBox.appendChild(div);
        });
        suggBox.classList.remove('hidden');
      } else {
        suggBox.classList.add('hidden');
      }
    });

    // Hide on click outside
    document.addEventListener('click', (e) => {
      if (!input.contains(e.target) && !suggBox.contains(e.target)) {
        suggBox.classList.add('hidden');
      }
    });
  };

  const closeModal = () => {
    els.editModal.classList.add('hidden');
    els.modalBody.innerHTML = '';
  };

  // --- API CALLS ---
  const savePerson = async (id, data, method) => {
    try {
      const url = id ? `${API.resource}/${id}` : API.list;
      const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || 'Błąd zapisu');

      showToast('success', 'Zapisano pomyślnie');
      closeModal();
      await loadData(); // Reload list
    } catch (e) {
      console.error(e);
      showToast('error', e.message);
    }
  };

  const deletePerson = async (id) => {
    if (!confirm(`Czy na pewno usunąć osobę ID ${id}?`)) return;
    try {
      const res = await fetch(`${API.resource}/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Błąd usuwania');
      showToast('success', 'Usunięto osobę');

      if (currentPerson && String(currentPerson.id_osoby) === String(id)) {
        currentPerson = null;
        els.detailsPanel.innerHTML = '<div class="no-selection-placeholder"><h3>Wybierz osobę</h3></div>';
      }
      await loadData();
    } catch (e) {
      showToast('error', e.message);
    }
  };

  const showToast = (type, msg) => {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : 'exclamation-circle'}"></i> <span>${msg}</span>`;
    els.toastContainer.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  };

  // --- DRZEWO GENEALOGICZNE (HTML Version) ---
  // Ported from previous implementation

  window.showFamilyTree = async (familyName) => {
    if (!familyName) {
      showToast('error', 'Osoba nie ma nazwiska, nie można wygenerować drzewa rodu.');
      return;
    }

    const treeHeader = document.querySelector('.tree-dialog-header h2');
    if (treeHeader) treeHeader.textContent = `Drzewo: Rodzina ${familyName}`;

    els.treeContainer.innerHTML = '<div class="loader">Generowanie drzewa...</div>';

    // Open Dialog
    if (els.treeDialog.showModal) els.treeDialog.showModal();
    else els.treeDialog.classList.remove('hidden');

    try {
      const response = await fetch(`${API.tree}/${familyName}`);
      if (!response.ok) throw new Error('Błąd pobierania drzewa');
      const data = await response.json(); // { people: [...], start_node_id: ... }

      drawGenealogyTree_Impl(data.people, data.start_node_id, els.treeContainer);
    } catch (error) {
      console.error("Tree Error:", error);
      els.treeContainer.innerHTML = `<div class="error">Błąd: ${error.message}</div>`;
    }
  };

  // --- FUNKCJE RYSOWANIA DRZEWA (D3 z Admina) ---
  function drawGenealogyTree_Impl(peopleList, rootId, container) {
    container.innerHTML = '';
    if (!peopleList || !peopleList.length) {
      container.innerHTML = '<div style="padding:50px;text-align:center;">Brak danych do wyświetlenia</div>';
      return;
    }

    // Konfiguracja
    const CFG = {
      NODE_H: 80,
      NODE_W_MIN: 140,
      GAP_H: 60,
      GAP_V: 100,
      MARGIN: 50,
      FONT: '14px Inter, sans-serif'
    };

    // 1. Mapowanie danych (Backend PL format -> D3 friendly)
    // peopleList items: {id, imie, nazwisko, plec, rok_urodzenia, rok_smierci, id_ojca, id_matki, id_malzonka, ...}

    const nodes = peopleList.map(p => ({
      id: String(p.id),
      name: `${p.imie} ${p.nazwisko}`,
      gender: p.plec,
      birth: p.rok_urodzenia,
      death: p.rok_smierci,
      fatherId: p.id_ojca ? String(p.id_ojca) : null,
      motherId: p.id_matki ? String(p.id_matki) : null,
      spouseId: p.id_malzonka ? String(p.id_malzonka) : null,
      isRoot: String(p.id) === String(rootId),

      // Layout props
      w: 0, h: CFG.NODE_H, x: 0, y: 0, gen: 0
    }));

    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    // 2. Obliczanie szerokości węzłów
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    ctx.font = CFG.FONT; // approximate
    nodes.forEach(n => {
      const txtW = ctx.measureText(n.name).width;
      n.w = Math.max(CFG.NODE_W_MIN, txtW + 40);
    });

    // 3. Ustalanie Generacji (BFS od roota lub najstarszego)
    // Jeśli rootId nie jest podany, znajdź "protoplastę" (brak rodziców, najstarszy)
    let chartRoot = nodes.find(n => n.id === String(rootId));
    if (!chartRoot) {
      // Find oldest without parents
      const roots = nodes.filter(n => !n.fatherId && !n.motherId);
      roots.sort((a, b) => (a.birth || 0) - (b.birth || 0));
      chartRoot = roots[0] || nodes[0];
    }

    // Reset Generations
    nodes.forEach(n => n.gen = null);
    if (chartRoot) chartRoot.gen = 0;

    const queue = [chartRoot];
    const visited = new Set([chartRoot.id]);

    // Prosty BFS do ustawienia generacji w dół
    let head = 0;
    while (head < queue.length) {
      const curr = queue[head++];

      // Find children
      nodes.forEach(n => {
        if ((n.fatherId === curr.id || n.motherId === curr.id) && !visited.has(n.id)) {
          n.gen = curr.gen + 1;
          visited.add(n.id);
          queue.push(n);
        }
      });

      // Find spouses (same Gen)
      if (curr.spouseId && nodeMap.has(curr.spouseId)) {
        const sp = nodeMap.get(curr.spouseId);
        if (!visited.has(sp.id)) {
          sp.gen = curr.gen;
          visited.add(sp.id);
          queue.push(sp);
        }
      }
    }

    // Fix null generations (orphan nodes) -> set to 0 or derive from spouse
    nodes.forEach(n => {
      if (n.gen === null) {
        if (n.spouseId && nodeMap.has(n.spouseId) && nodeMap.get(n.spouseId).gen !== null) {
          n.gen = nodeMap.get(n.spouseId).gen;
        } else {
          n.gen = 0;
        }
      }
    });

    // 4. Pozycjonowanie (Proste: Generacje wierszami)
    const gens = new Map();
    nodes.forEach(n => {
      if (!gens.has(n.gen)) gens.set(n.gen, []);
      gens.get(n.gen).push(n);
    });

    const sortedGens = Array.from(gens.keys()).sort((a, b) => a - b);
    let currentY = CFG.MARGIN;

    sortedGens.forEach(g => {
      const rowNodes = gens.get(g);
      // Grupuj małżeństwa
      const couples = [];
      const singles = [];
      const processed = new Set();

      rowNodes.forEach(n => {
        if (processed.has(n.id)) return;

        if (n.spouseId && nodeMap.has(n.spouseId)) {
          const sp = nodeMap.get(n.spouseId);
          // Check if spouse is in same gen (should be)
          if (sp.gen === g && !processed.has(sp.id)) {
            couples.push([n, sp]);
            processed.add(n.id);
            processed.add(sp.id);
          } else {
            singles.push(n);
            processed.add(n.id);
          }
        } else {
          singles.push(n);
          processed.add(n.id);
        }
      });

      // Sort inside row by birth or name?
      // (Skipped for brevity)

      let currentX = CFG.MARGIN;

      // Render Couples
      couples.forEach(([n1, n2]) => {
        n1.x = currentX; n1.y = currentY;
        currentX += n1.w + 20; // 20px gap between spouses
        n2.x = currentX; n2.y = currentY;
        currentX += n2.w + CFG.GAP_H;
      });

      // Render Singles
      singles.forEach(n => {
        n.x = currentX; n.y = currentY;
        currentX += n.w + CFG.GAP_H;
      });

      currentY += CFG.NODE_H + CFG.GAP_V;
    });

    // 5. Rysowanie SVG (D3)
    // Oblicz rozmiar sceny
    const allX = nodes.map(n => n.x + n.w);
    const allY = nodes.map(n => n.y + n.h);
    const maxW = Math.max(...allX) + CFG.MARGIN;
    const maxH = Math.max(...allY) + CFG.MARGIN;

    const svg = d3.create("svg")
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("viewBox", `0 0 ${maxW} ${maxH}`)
      .style("font-family", "Inter, sans-serif");

    // Zoom behavior
    const g = svg.append("g");
    svg.call(d3.zoom().scaleExtent([0.1, 3]).on("zoom", (e) => {
      g.attr("transform", e.transform);
    }));

    // --- Connections ---
    // Lines for Spouses
    nodes.forEach(n => {
      if (n.spouseId && nodeMap.has(n.spouseId)) {
        const sp = nodeMap.get(n.spouseId);
        // Draw only once (if n.x < sp.x)
        if (n.x < sp.x) {
          g.append("line")
            .attr("x1", n.x + n.w)
            .attr("y1", n.y + n.h / 2)
            .attr("x2", sp.x)
            .attr("y2", sp.h / 2 + sp.y)
            .attr("stroke", "#e53e3e")
            .attr("stroke-width", 2)
            .attr("stroke-dasharray", "4");
        }
      }
    });

    // Lines for Children
    nodes.forEach(n => {
      // Find parents
      const f = n.fatherId ? nodeMap.get(n.fatherId) : null;
      const m = n.motherId ? nodeMap.get(n.motherId) : null;

      if (!f && !m) return;

      let startX, startY;

      if (f && m && Math.abs(f.y - m.y) < 10) {
        // Both parents in same row -> start from middle of spouse link
        const left = f.x < m.x ? f : m;
        const right = f.x < m.x ? m : f;
        startX = (left.x + left.w + right.x) / 2;
        startY = left.y + left.h / 2;
      } else {
        // Single parent or diff rows -> start from bottom of parent
        const p = f || m;
        startX = p.x + p.w / 2;
        startY = p.y + p.h;
      }

      const endX = n.x + n.w / 2;
      const endY = n.y;

      // Elbow Link
      const path = d3.path();
      path.moveTo(startX, startY);
      if (Math.abs(f?.y - m?.y) < 10) {
        // From spouse line center
        path.lineTo(startX, startY + CFG.GAP_V / 2);
        path.lineTo(endX, startY + CFG.GAP_V / 2);
        path.lineTo(endX, endY);
      } else {
        // Direct from parent bottom
        path.lineTo(startX, startY + CFG.GAP_V / 2);
        path.lineTo(endX, startY + CFG.GAP_V / 2);
        path.lineTo(endX, endY);
      }

      g.append("path")
        .attr("d", path.toString())
        .attr("fill", "none")
        .attr("stroke", "#cbd5e0")
        .attr("stroke-width", 2);
    });

    // --- Nodes ---
    const nodeG = g.selectAll(".node")
      .data(nodes)
      .enter()
      .append("g")
      .attr("transform", d => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer")
      .on("click", (e, d) => {
        // Optional: Pokazanie szczegółów po kliknięciu
        console.log("Clicked:", d.name);
      });

    // Card Rect
    nodeG.append("rect")
      .attr("width", d => d.w)
      .attr("height", d => d.h)
      .attr("rx", 6)
      .attr("fill", d => d.gender === 'M' ? '#ebf8ff' : '#fff5f7')
      .attr("stroke", d => d.isRoot ? '#ed8936' : (d.gender === 'M' ? '#90cdf4' : '#f687b3'))
      .attr("stroke-width", d => d.isRoot ? 3 : 1)
      .style("filter", "drop-shadow(0 2px 3px rgba(0,0,0,0.1))");

    // Name
    nodeG.append("text")
      .attr("x", d => d.w / 2)
      .attr("y", 30)
      .attr("text-anchor", "middle")
      .style("font-weight", "600")
      .style("fill", "#2d3748")
      .text(d => d.name);

    // Date
    nodeG.append("text")
      .attr("x", d => d.w / 2)
      .attr("y", 50)
      .attr("text-anchor", "middle")
      .style("font-size", "0.85em")
      .style("fill", "#718096")
      .text(d => {
        const b = d.birth || '?';
        const dd = d.death || (d.birth && (2025 - d.birth > 100) ? '?' : '');
        return dd ? `${b} - ${dd}` : `ur. ${b}`;
      });

    // Gender Icon
    nodeG.append("text")
      .attr("x", 12)
      .attr("y", 20)
      .style("font-size", "12px")
      .style("fill", d => d.gender === 'M' ? '#3182ce' : '#d53f8c')
      .text(d => d.gender === 'M' ? '♂' : '♀');

    container.appendChild(svg.node());
  }

  // Inicjalizacja
  init();
});