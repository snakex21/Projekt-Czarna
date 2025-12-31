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
    backups: '/api/genealogy/backups'
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
    setupDateTime();
    setupExitButton();
    await loadData();
  };

  // --- DATA I CZAS ---
  const setupDateTime = () => {
    const updateDateTime = () => {
      const now = new Date();
      const dateEl = document.getElementById('currentDate');
      const timeEl = document.getElementById('currentTime');

      if (dateEl) {
        dateEl.textContent = now.toLocaleDateString('pl-PL', {
          weekday: 'long',
          year: 'numeric',
          month: 'long',
          day: 'numeric'
        });
      }
      if (timeEl) {
        timeEl.textContent = now.toLocaleTimeString('pl-PL', {
          hour: '2-digit',
          minute: '2-digit'
        });
      }
    };

    updateDateTime();
    setInterval(updateDateTime, 1000);
  };

  // --- PRZYCISK WYJŚCIA (SHUTDOWN) ---
  const setupExitButton = () => {
    const exitBtn = document.getElementById('exitServerBtn');
    const exitModal = document.getElementById('exitModal');
    const confirmBtn = document.getElementById('confirmExitBtn');
    const cancelBtn = document.getElementById('cancelExitBtn');
    const closeBtn = document.getElementById('closeExitModal');

    if (exitBtn && exitModal) {
      exitBtn.addEventListener('click', () => {
        exitModal.classList.remove('hidden');
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        exitModal.classList.add('hidden');
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        exitModal.classList.add('hidden');
      });
    }

    if (confirmBtn) {
      confirmBtn.addEventListener('click', async () => {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Zamykanie...';

        try {
          const response = await fetch('/shutdown', { method: 'POST' });
          if (response.ok) {
            showToast('success', 'Serwer jest zamykany...');
            setTimeout(() => {
              document.body.innerHTML = `
                <div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0;font-family:Inter,sans-serif;flex-direction:column;">
                  <i class="fas fa-check-circle" style="font-size:4rem;color:#48bb78;margin-bottom:1rem;"></i>
                  <h1 style="margin-bottom:0.5rem;">Serwer zamknięty</h1>
                  <p style="color:#94a3b8;">Ta karta zamknie się automatycznie...</p>
                  <p style="color:#64748b;font-size:0.85rem;margin-top:1rem;">Zamykanie za <span id="countdown">3</span>s</p>
                </div>
              `;
              // Auto zamknij kartę po 3 sekundach
              let countdown = 3;
              const countdownEl = document.getElementById('countdown');
              const timer = setInterval(() => {
                countdown--;
                if (countdownEl) countdownEl.textContent = countdown;
                if (countdown <= 0) {
                  clearInterval(timer);
                  window.close();
                  // Fallback jeśli window.close() nie zadziała (ograniczenia przeglądarki)
                  setTimeout(() => {
                    document.body.innerHTML = `
                      <div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#0f172a;color:#e2e8f0;font-family:Inter,sans-serif;flex-direction:column;">
                        <i class="fas fa-check-circle" style="font-size:4rem;color:#48bb78;margin-bottom:1rem;"></i>
                        <h1>Serwer zamknięty</h1>
                        <p style="color:#94a3b8;">Możesz teraz zamknąć tę kartę ręcznie.</p>
                      </div>
                    `;
                  }, 500);
                }
              }, 1000);
            }, 1000);
          } else {
            throw new Error('Nie udało się zamknąć serwera');
          }
        } catch (err) {
          showToast('error', err.message);
          confirmBtn.disabled = false;
          confirmBtn.innerHTML = '<i class="fas fa-power-off"></i> Zamknij serwer';
        }
      });
    }

    // Zamknij modal po kliknięciu w tło
    if (exitModal) {
      exitModal.addEventListener('click', (e) => {
        if (e.target === exitModal) {
          exitModal.classList.add('hidden');
        }
      });
    }
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
          const res = await fetch(`${API.backups}/create`, { method: 'POST' });
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
        const res = await fetch(`${API.backups}/restore`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: filename })
        });
        if (res.ok) {
          showToast('success', 'Przywrócono dane z kopii');
          backupModal.classList.add('hidden');
          loadData();
        } else showToast('error', 'Błąd przywracania');
      } catch (e) { showToast('error', e.message); }
    };

    window.deleteBackup = async (filename) => {
      if (!confirm(`Czy na pewno usunąć kopię ${filename}?`)) return;
      try {
        const res = await fetch(`${API.backups}/${filename}`, { method: 'DELETE' });
        if (res.ok) {
          showToast('success', 'Usunięto kopię zapasową');
          loadBackups();
        } else showToast('error', 'Błąd usuwania kopii');
      } catch (e) { showToast('error', e.message); }
    };

    const loadBackups = async () => {
      const listEl = document.getElementById('backupList');
      listEl.innerHTML = '<div class="loader">Ładowanie...</div>';
      try {
        const res = await fetch(API.backups);
        const files = await res.json();
        listEl.innerHTML = files.map(f => `
                    <li class="backup-item">
                        <span class="backup-name">${f}</span>
                        <div class="backup-actions">
                            <button class="btn-success small" onclick="window.restoreBackup('${f}')"><i class="fas fa-undo"></i> Przywróć</button>
                            <button class="btn-danger small" onclick="window.deleteBackup('${f}')"><i class="fas fa-trash"></i> Usuń</button>
                        </div>
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

      filteredPeople = [...allPeople];

      // Wywołaj sortData() dla właściwego sortowania (A-Z po imieniu)
      sortData();

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
  let currentDisplayLimit = 200;

  const renderList = () => {
    els.listContainer.innerHTML = '';
    if (filteredPeople.length === 0) {
      els.listContainer.innerHTML = '<div style="padding:10px;text-align:center;color:#888;">Brak wyników</div>';
      return;
    }

    // Renderuj do limitu
    const limit = currentDisplayLimit;
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
      const remaining = filteredPeople.length - limit;
      const moreBtn = document.createElement('button');
      moreBtn.className = 'btn-primary';
      moreBtn.style.cssText = 'width:100%; margin:10px 0; padding:12px; border-radius:8px; cursor:pointer;';
      moreBtn.innerHTML = `<i class="fas fa-plus-circle"></i> Załaduj więcej (${remaining} pozostało)`;
      moreBtn.addEventListener('click', () => {
        currentDisplayLimit += 200;
        renderList();
      });
      els.listContainer.appendChild(moreBtn);
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
                <h1>${genderIcon} ${person.imie} ${person.nazwisko} <span class="person-id-badge">ID: ${person.id_osoby}</span></h1>
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
    window.showTreeForCurrent = () => showFamilyTree(person.nazwisko, person.id_osoby);
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
                        <input type="number" name="id_osoby" id="idOsobyInput" value="${safe(person?.id_osoby)}" required>
                        <small style="color:var(--text-secondary);margin-top:4px;">⚠️ Zmiana ID może wpłynąć na powiązania rodzinne</small>
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
                <button type="button" class="btn-remove-spouse" onclick="this.parentElement.remove()" title="Usuń małżonka">
                    <i class="fas fa-times"></i>
                </button>
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

      // Walidacja unikalności ID
      const newId = data.id_osoby;
      const originalId = person?.id_osoby;

      // Sprawdź czy ID się zmieniło i czy nowe ID jest już zajęte
      if (String(newId) !== String(originalId)) {
        const existingPerson = allPeople.find(p => String(p.id_osoby) === String(newId));
        if (existingPerson) {
          showToast('error', `ID ${newId} jest już zajęte przez: ${existingPerson.imie} ${existingPerson.nazwisko}`);
          document.getElementById('idOsobyInput').focus();
          document.getElementById('idOsobyInput').style.borderColor = '#f87171';
          return;
        }
      }

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

      // ID osoby którą dodaliśmy/edytowaliśmy
      const savedPersonId = data.id_osoby || id;

      await loadData(); // Reload list

      // Po dodaniu nowej osoby - przejdź do jej widoku
      if (savedPersonId) {
        const savedPerson = allPeople.find(p => String(p.id_osoby) === String(savedPersonId));
        if (savedPerson) {
          showDetails(savedPerson);
          // Scroll do osoby na liście
          setTimeout(() => {
            const listItems = document.querySelectorAll('.person-list-item');
            listItems.forEach(item => {
              if (item.textContent.includes(`ID: ${savedPersonId}`)) {
                item.classList.add('active');
                item.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            });
          }, 100);
        }
      }
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

  window.showFamilyTree = async (familyName, personId) => {
    if (!familyName) {
      showToast('error', 'Osoba nie ma nazwiska, nie można wygenerować drzewa rodu.');
      return;
    }

    const treeHeader = document.querySelector('.tree-dialog-header h2');
    if (treeHeader) {
      treeHeader.innerHTML = `<i class="fas fa-tree"></i> Drzewo: ${familyName} <span class="tree-legend-inline">💙 Mężczyzna | 💗 Kobieta | 💛 Główna osoba | 💕 Małżeństwo</span>`;
    }

    els.treeContainer.innerHTML = '<div class="loader">Generowanie drzewa...</div>';

    // Open Dialog
    if (els.treeDialog.showModal) els.treeDialog.showModal();
    else els.treeDialog.classList.remove('hidden');

    try {
      const response = await fetch(`${API.tree}/${familyName}`);
      if (!response.ok) throw new Error('Błąd pobierania drzewa');
      const data = await response.json(); // { people: [...], start_node_id: ... }

      // Użyj personId (ID wybranej osoby) zamiast start_node_id z API
      const rootId = personId || data.start_node_id;
      drawGenealogyTree_Impl(data.people, rootId, els.treeContainer);
    } catch (error) {
      console.error("Tree Error:", error);
      els.treeContainer.innerHTML = `<div class="error">Błąd: ${error.message}</div>`;
    }
  };

  // --- FUNKCJE RYSOWANIA DRZEWA (HTML Version from protokol.js) ---
  function drawGenealogyTree_Impl(peopleList, rootId, container) {
    console.log('drawGenealogyTree_Impl called with:', { peopleCount: peopleList?.length, rootId, firstPerson: peopleList?.[0] });

    container.innerHTML = '';
    if (!peopleList || !peopleList.length) {
      container.innerHTML = '<div style="padding:50px;text-align:center;">Brak danych do wyświetlenia</div>';
      return;
    }

    // Mapowanie danych z formatu backendu
    const personMap = new Map();
    const childrenMap = new Map();

    peopleList.forEach(p => {
      // API zwraca: ojciec_id, matka_id, malzonek_id (format polski)
      // Lub: id_ojca, id_matki, id_malzonka (format alternatywny)
      const person = {
        id: p.id || p.id_osoby,
        name: `${p.imie || ''} ${p.nazwisko || ''}`.trim() || p.name || 'Nieznany',
        gender: p.plec || p.gender || 'M',
        birthYear: p.rok_urodzenia || p.birthDate?.year,
        deathYear: p.rok_smierci || p.deathDate?.year,
        fatherId: p.ojciec_id || p.id_ojca || p.fatherId,
        motherId: p.matka_id || p.id_matki || p.motherId,
        spouseId: p.malzonek_id || p.id_malzonka || (p.spouseIds && p.spouseIds[0]),
        spouseIds: p.spouseIds || (p.malzonek_id ? [p.malzonek_id] : (p.id_malzonka ? [p.id_malzonka] : []))
      };
      personMap.set(String(person.id), person);

      if (person.fatherId) {
        const fKey = String(person.fatherId);
        if (!childrenMap.has(fKey)) childrenMap.set(fKey, []);
        childrenMap.get(fKey).push(person.id);
      }
      if (person.motherId) {
        const mKey = String(person.motherId);
        if (!childrenMap.has(mKey)) childrenMap.set(mKey, []);
        childrenMap.get(mKey).push(person.id);
      }
    });

    // Szukaj rootPerson - próbuj różne formaty ID
    // Funkcja pomocnicza dla spójnego wyszukiwania
    const getPerson = (id) => id ? personMap.get(String(id)) : null;

    let rootPerson = getPerson(rootId);
    if (!rootPerson) {
      // Fallback - szukaj po id_osoby w oryginalnej liście
      const found = peopleList.find(p => String(p.id_osoby) === String(rootId) || String(p.id) === String(rootId));
      if (found) {
        rootPerson = getPerson(found.id || found.id_osoby);
      }
    }
    if (!rootPerson) {
      rootPerson = personMap.values().next().value;
    }
    if (!rootPerson) {
      container.innerHTML = '<div style="padding:50px;text-align:center;">Nie znaleziono osoby głównej</div>';
      return;
    }

    const getParentRole = (p) => p?.gender === 'M' ? 'Ojciec' : (p?.gender === 'F' ? 'Matka' : 'Rodzic');
    const getGrandparentRole = (p) => p?.gender === 'M' ? 'Dziadek' : (p?.gender === 'F' ? 'Babcia' : 'Dziadek/Babcia');
    const formatYears = (p) => {
      if (!p) return '';
      return `${p.birthYear || '?'} - ${p.deathYear || '?'}`;
    };

    const father = getPerson(rootPerson.fatherId);
    const mother = getPerson(rootPerson.motherId);
    const parents = [];
    if (father) parents.push({ role: getParentRole(father), ...father });
    if (mother) parents.push({ role: getParentRole(mother), ...mother });

    const grandparentsFather = [];
    const grandparentsMother = [];
    if (father) {
      const gf = getPerson(father.fatherId);
      const gm = getPerson(father.motherId);
      if (gf) grandparentsFather.push({ role: getGrandparentRole(gf), ...gf });
      if (gm) grandparentsFather.push({ role: getGrandparentRole(gm), ...gm });
    }
    if (mother) {
      const gf = getPerson(mother.fatherId);
      const gm = getPerson(mother.motherId);
      if (gf) grandparentsMother.push({ role: getGrandparentRole(gf), ...gf });
      if (gm) grandparentsMother.push({ role: getGrandparentRole(gm), ...gm });
    }

    const spouses = (rootPerson.spouseIds || []).map(sid => getPerson(sid)).filter(s => s).map(s => ({ role: 'Małżonek', ...s }));
    const children = (childrenMap.get(String(rootPerson.id)) || []).map(cid => getPerson(cid)).filter(c => c).map(c => ({ role: 'Dziecko', ...c }));

    const siblingIds = new Set();
    if (rootPerson.fatherId) (childrenMap.get(String(rootPerson.fatherId)) || []).forEach(id => { if (String(id) !== String(rootPerson.id)) siblingIds.add(id); });
    if (rootPerson.motherId) (childrenMap.get(String(rootPerson.motherId)) || []).forEach(id => { if (String(id) !== String(rootPerson.id)) siblingIds.add(id); });
    const siblings = Array.from(siblingIds).map(sid => getPerson(sid)).filter(s => s).map(s => ({ role: 'Rodzeństwo', ...s }));

    const renderTreeNode = (person, isRoot = false, showRole = true) => {
      if (!person) return '';
      const bgColor = isRoot ? '#fff3cd' : (person.gender === 'M' ? '#e3f2fd' : '#fce4ec');
      const borderColor = isRoot ? '#f57f17' : (person.gender === 'M' ? '#1976d2' : '#c2185b');
      return `<div style="background:${bgColor};border:2px solid ${borderColor};border-radius:10px;padding:0.75rem 1rem;min-width:140px;max-width:180px;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        ${showRole && person.role ? `<div style="font-size:0.6rem;text-transform:uppercase;color:#888;margin-bottom:0.2rem;">${person.role}</div>` : ''}
        <div style="font-weight:700;font-size:0.85rem;color:#333;">${person.name}</div>
        <div style="font-size:0.7rem;color:#666;margin-top:0.2rem;">${formatYears(person)}</div>
      </div>`;
    };

    let html = `<style>
      .tree-scroll-area{flex:1;overflow:auto;padding:1rem;display:flex;justify-content:center;}
      .tree-content{display:flex;flex-direction:column;align-items:center;padding:1.5rem;min-width:max-content;}
      .tree-level{display:flex;justify-content:center;gap:2rem;}
      .tree-connector-down{width:2px;height:30px;background:#ccc;margin:0 auto;}
      .tree-pair{display:flex;align-items:center;gap:0.5rem;}
      .tree-pair-connector{width:30px;height:2px;background:#e74c3c;position:relative;}
      .tree-pair-connector::after{content:'💕';position:absolute;top:-10px;left:50%;transform:translateX(-50%);font-size:14px;}
      .tree-branch{display:flex;flex-direction:column;align-items:center;}
      .tree-main-column{display:flex;flex-direction:column;align-items:center;}
      .tree-with-siblings{display:flex;align-items:flex-start;gap:2rem;}
      .tree-siblings-section{display:flex;flex-direction:column;align-items:center;opacity:0.8;padding-top:1.5rem;}
      .tree-siblings-grid{display:flex;flex-wrap:wrap;gap:0.5rem;max-width:400px;justify-content:center;}
      .tree-children{display:flex;justify-content:center;gap:1rem;position:relative;padding-top:30px;flex-wrap:wrap;}
      .tree-child-branch{display:flex;flex-direction:column;align-items:center;}
      .tree-child-branch::before{content:'';width:2px;height:15px;background:#ccc;}
      .generation-label{font-size:0.8rem;text-transform:uppercase;letter-spacing:1px;color:#888;margin:1rem 0 0.5rem;font-weight:700;}
      .section-label{font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;color:#999;margin-bottom:0.5rem;font-weight:600;}
    </style>`;

    html += '<div class="tree-scroll-area"><div class="tree-content">';

    if (grandparentsFather.length > 0 || grandparentsMother.length > 0) {
      html += '<div class="generation-label">Dziadkowie</div><div class="tree-level" style="gap:4rem;">';
      if (grandparentsFather.length > 0) {
        html += '<div class="tree-branch"><div style="font-size:0.6rem;color:#888;margin-bottom:0.25rem;">od ojca</div><div class="tree-pair">';
        grandparentsFather.forEach((gp, i) => { if (i > 0) html += '<div class="tree-pair-connector"></div>'; html += renderTreeNode(gp, false, false); });
        html += '</div></div>';
      }
      if (grandparentsMother.length > 0) {
        html += '<div class="tree-branch"><div style="font-size:0.6rem;color:#888;margin-bottom:0.25rem;">od matki</div><div class="tree-pair">';
        grandparentsMother.forEach((gp, i) => { if (i > 0) html += '<div class="tree-pair-connector"></div>'; html += renderTreeNode(gp, false, false); });
        html += '</div></div>';
      }
      html += '</div><div class="tree-connector-down"></div>';
    }

    if (parents.length > 0) {
      html += '<div class="generation-label">Rodzice</div><div class="tree-level"><div class="tree-pair">';
      parents.forEach((p, i) => { if (i > 0) html += '<div class="tree-pair-connector"></div>'; html += renderTreeNode(p); });
      html += '</div></div><div class="tree-connector-down"></div>';
    }

    html += '<div class="tree-with-siblings">';
    if (siblings.length > 0) {
      html += '<div class="tree-siblings-section"><div class="section-label">Rodzeństwo</div><div class="tree-siblings-grid">';
      siblings.forEach(s => { html += renderTreeNode(s); });
      html += '</div></div>';
    }

    html += '<div class="tree-main-column"><div class="generation-label">Główna osoba</div><div class="tree-pair">';
    html += renderTreeNode(rootPerson, true);
    if (spouses.length > 0) { html += '<div class="tree-pair-connector"></div>'; html += renderTreeNode(spouses[0]); }
    html += '</div>';

    if (children.length > 0) {
      html += '<div class="tree-connector-down"></div><div class="generation-label">Dzieci</div><div class="tree-children">';
      children.forEach(child => { html += '<div class="tree-child-branch">' + renderTreeNode(child) + '</div>'; });
      html += '</div>';
    }

    html += '</div></div></div></div>';
    container.innerHTML = html;
  }

  // Inicjalizacja
  init();
});
