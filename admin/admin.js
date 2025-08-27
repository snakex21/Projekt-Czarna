document.addEventListener('DOMContentLoaded', () => {
    let currentUser = null;
    let currentSection = 'dashboard';
    let allOwners = [];
    let allObjects = [];
    let allDemography = [];
    let allGenealogy = [];
    let allProtocols = [];
    
    const API = {
        login: '/api/admin/login',
        logout: '/api/admin/logout',
        stats: '/api/admin/dashboard-stats',
        owners: '/api/admin/wlasciciele',
        objects: '/api/admin/obiekty',
        allObjects: '/api/admin/wszystkie-obiekty',
        demography: '/api/admin/demografia',
        genealogy: '/api/admin/genealogia',
        protocols: '/api/admin/protocols',
        backup: '/api/admin/export-backup',
        authStatus: '/api/admin/auth-status'
    };

    const elements = {
        loginScreen: document.getElementById('loginScreen'),
        adminPanel: document.getElementById('adminPanel'),
        loginForm: document.getElementById('loginForm'),
        loginError: document.getElementById('loginError'),
        sidebar: document.querySelector('.sidebar'),
        sidebarToggle: document.querySelector('.sidebar-toggle'),
        menuItems: document.querySelectorAll('.menu-item'),
        sections: document.querySelectorAll('.section'),
        currentSection: document.getElementById('currentSection'),
        currentDate: document.getElementById('currentDate'),
        currentTime: document.getElementById('currentTime'),
        themeToggle: document.getElementById('themeToggle'),
        modalOverlay: document.getElementById('modalOverlay'),
        modalTitle: document.getElementById('modalTitle'),
        modalBody: document.getElementById('modalBody'),
        modalSave: document.getElementById('modalSave'),
        modalCancel: document.getElementById('modalCancel'),
        modalClose: document.getElementById('modalClose'),
        toastContainer: document.getElementById('toastContainer'),
        logoutBtn: document.getElementById('logoutBtn')
    };

    const init = () => {
        setupEventListeners();
        updateDateTime();
        setInterval(updateDateTime, 1000); // 1000ms = 1 sekunda
        checkAuth();
    };

// Funkcja normalizująca nazwiska (tylko do grupowania w tabeli)
const canonicalSurname = (raw) => {
    if (!raw) return "";
    let last = raw.trim().split(/\s+/).pop().toLowerCase();
    if (last.endsWith("ska")) last = last.slice(0, -3) + "ski";
    else if (last.endsWith("cka")) last = last.slice(0, -3) + "cki";
    else if (last.endsWith("dzka")) last = last.slice(0, -4) + "dzki";
    else if (last.endsWith("owa")) last = last.slice(0, -3);
    else if (last.endsWith("a") && last.length > 4) last = last.slice(0, -1);
    return last.charAt(0).toUpperCase() + last.slice(1);
};

    const checkAuth = async () => {
        try {
            // Zapytaj serwer, czy autoryzacja jest w ogóle włączona
            const response = await fetch(API.authStatus);
            if (!response.ok) throw new Error('Nie można sprawdzić statusu autoryzacji.');
            
            const authConfig = await response.json();

            if (!authConfig.enabled) {
                // Autoryzacja jest WYŁĄCZONA
                elements.logoutBtn.classList.add('hidden'); // Ukryj przycisk wylogowania
                showAdminPanel();
                return; // Zakończ dalsze sprawdzanie
            }
            
            // Autoryzacja jest WŁĄCZONA
            elements.logoutBtn.classList.remove('hidden'); // Upewnij się, że przycisk jest widoczny
            const isLoggedIn = localStorage.getItem('adminLoggedIn') === 'true';
            if (isLoggedIn) {
                showAdminPanel();
            } else {
                showLoginScreen();
            }

        } catch (error) {
            // W przypadku błędu sieci, bezpieczniej jest pokazać ekran logowania
            console.error('Błąd podczas sprawdzania autoryzacji:', error);
            elements.logoutBtn.classList.add('hidden'); // Ukryj przycisk również w razie błędu
            showLoginScreen();
            elements.loginError.textContent = 'Błąd połączenia z serwerem. Spróbuj odświeżyć stronę.';
            elements.loginError.classList.remove('hidden');
        }
    };

    const showLoginScreen = () => {
        elements.loginScreen.classList.remove('hidden');
        elements.adminPanel.classList.add('hidden');
    };

    const showAdminPanel = () => {
        elements.loginScreen.classList.add('hidden');
        elements.adminPanel.classList.remove('hidden');
        loadDashboardData();
    };

    const setupEventListeners = () => {
        elements.loginForm.addEventListener('submit', handleLogin);
        const treeModalClose = document.getElementById('treeModalClose');
        if (treeModalClose) {
            treeModalClose.addEventListener('click', () => {
                const modal = document.getElementById('treeModal');
                if (modal) {
                    modal.classList.add('hidden');
                    document.body.classList.remove('modal-open');
                    document.getElementById('treeContainer').innerHTML = '';
                }
            });
        }
        elements.sidebarToggle.addEventListener('click', () => {
            elements.sidebar.classList.toggle('collapsed');
        });
        
        elements.menuItems.forEach(item => {
            item.addEventListener('click', () => {
                const section = item.dataset.section;
                if (section) {
                    switchSection(section);
                } else if (item.id === 'backupBtn') {
                    downloadBackup();
                } else if (item.id === 'logoutBtn') {
                    handleLogout();
                }
            });
        });
        
        elements.themeToggle.addEventListener('click', toggleTheme);
        
        elements.modalClose.addEventListener('click', closeModal);
        elements.modalCancel.addEventListener('click', closeModal);
        elements.modalOverlay.addEventListener('click', (e) => {
            if (e.target === elements.modalOverlay) closeModal();
        });
                
        document.getElementById('addOwnerBtn')?.addEventListener('click', () => openOwnerModal());
        document.getElementById('searchOwners')?.addEventListener('input', (e) => filterOwners(e.target.value));
        
        document.getElementById('searchObjects')?.addEventListener('input', (e) => filterObjects(e.target.value));
        
        document.getElementById('addDemographyBtn')?.addEventListener('click', () => openDemographyModal());
        
        document.getElementById('addGenealogyBtn')?.addEventListener('click', () => openGenealogyModal());
        document.getElementById('searchGenealogy')?.addEventListener('input', (e) => filterGenealogy(e.target.value));
        document.getElementById('familyFilter')?.addEventListener('change', (e) => filterGenealogy('', e.target.value));
        
        document.querySelectorAll('.action-card').forEach(card => {
            card.addEventListener('click', () => {
                const action = card.dataset.action;
                handleQuickAction(action);
            });
        });
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        const login = document.getElementById('login').value;
        const password = document.getElementById('password').value;
        
        try {
            const response = await fetch(API.login, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: login, password })
            });
            
            const data = await response.json();
            
            if (data.status === 'ok') {
                localStorage.setItem('adminLoggedIn', 'true');
                currentUser = login;
                showAdminPanel();
                showToast('success', 'Zalogowano pomyślnie');
            } else {
                elements.loginError.textContent = data.message || 'Błędne dane logowania';
                elements.loginError.classList.remove('hidden');
            }
        } catch (error) {
            elements.loginError.textContent = 'Błąd połączenia z serwerem';
            elements.loginError.classList.remove('hidden');
        }
    };

    const handleLogout = async () => {
        if (confirm('Czy na pewno chcesz się wylogować?')) {
            try {
                await fetch(API.logout, { method: 'POST' });
            } catch (error) {
                console.error('Błąd wylogowania:', error);
            }
            
            localStorage.removeItem('adminLoggedIn');
            currentUser = null;
            showLoginScreen();
            showToast('info', 'Wylogowano z systemu');
        }
    };

    const switchSection = (section) => {
        elements.sections.forEach(s => s.classList.remove('active'));
        elements.menuItems.forEach(m => m.classList.remove('active'));
        
        document.getElementById(section)?.classList.add('active');
        document.querySelector(`[data-section="${section}"]`)?.classList.add('active');
        
        currentSection = section;
        elements.currentSection.textContent = getSectionName(section);
        
        loadSectionData(section);
    };

    const getSectionName = (section) => {
        const names = {
            dashboard: 'Pulpit',
            owners: 'Właściciele',
            objects: 'Obiekty',
            demography: 'Demografia',
            genealogy: 'Genealogia'
        };
        return names[section] || section;
    };

    const loadSectionData = async (section) => {
        switch (section) {
            case 'dashboard':
                loadDashboardData();
                break;
            case 'owners':
                loadOwners();
                break;
            case 'objects':
                loadObjects();
                break;
            case 'demography':
                loadDemography();
                break;
            case 'genealogy':
                loadGenealogy();
                break;
        }
    };

    const loadDashboardData = async () => {
        try {
            const response = await fetch(API.stats);
            const data = await response.json();
            
            document.getElementById('statOwners').textContent = data.total_owners || 0;
            document.getElementById('statObjects').textContent = data.total_objects || 0;
            
            const genealogyResponse = await fetch(API.genealogy);
            const genealogyData = await genealogyResponse.json();
            document.getElementById('statGenealogy').textContent = genealogyData.length || 0;
            
            const demographyResponse = await fetch(API.demography);
            const demographyData = await demographyResponse.json();
            document.getElementById('statDemography').textContent = demographyData.length || 0;
        } catch (error) {
            console.error('Błąd ładowania statystyk:', error);
        }
    };

    const loadOwners = async () => {
        try {
            const response = await fetch(API.owners);
            allOwners = await response.json();
            renderOwners(allOwners);
        } catch (error) {
            console.error('Błąd ładowania właścicieli:', error);
            showToast('error', 'Nie udało się załadować właścicieli');
        }
    };

    const renderOwners = (owners) => {
        const container = document.getElementById('ownersList');
        container.innerHTML = '';
        
        owners.forEach(owner => {
            const card = document.createElement('div');
            card.className = 'owner-card';
            card.innerHTML = `
                <div class="owner-card-header">
                    <div class="owner-name">${owner.nazwa_wlasciciela}</div>
                    <div class="owner-protocol">Lp. ${owner.numer_protokolu || 'N/A'}</div>
                </div>
                <div class="owner-details">
                    <div>Dom: ${owner.numer_domu || '-'}</div>
                    <div>Klucz: ${owner.unikalny_klucz}</div>
                </div>
                <div class="owner-actions">
                    <button class="edit-btn" onclick="editOwner(${owner.id})">
                        <i class="fas fa-edit"></i> Edytuj
                    </button>
                    <button class="delete-btn" onclick="deleteOwner(${owner.id})">
                        <i class="fas fa-trash"></i> Usuń
                    </button>
                </div>
            `;
            container.appendChild(card);
        });
    };

    const filterOwners = (searchTerm) => {
        const filtered = allOwners.filter(owner => 
            owner.nazwa_wlasciciela.toLowerCase().includes(searchTerm.toLowerCase()) ||
            owner.unikalny_klucz.toLowerCase().includes(searchTerm.toLowerCase())
        );
        renderOwners(filtered);
    };

    const loadObjects = async () => {
        try {
            const response = await fetch(API.objects);
            allObjects = await response.json();
            renderObjects(allObjects);
        } catch (error) {
            console.error('Błąd ładowania obiektów:', error);
            showToast('error', 'Nie udało się załadować obiektów');
        }
    };

    const renderObjects = (objects) => {
        const tbody = document.getElementById('objectsTableBody');
        tbody.innerHTML = '';
        
        objects.forEach(obj => {
            const row = document.createElement('tr');
            row.dataset.id = obj.id; // Przechowujemy ID obiektu w atrybucie data
            
            row.innerHTML = `
                <td data-field="nazwa_lub_numer">${obj.nazwa_lub_numer}</td>
                <td data-field="kategoria">${obj.kategoria}</td>
                <td>${obj.is_linked ? '<span style="color: var(--success-color);">Przypisany</span>' : '<span style="color: var(--text-secondary);">Wolny</span>'}</td>
                <td class="actions">
                    <button class="btn-warning edit-btn"><i class="fas fa-edit"></i> Edytuj</button>
                    <button class="btn-danger delete-btn"><i class="fas fa-trash"></i> Usuń</button>
                </td>
            `;
            tbody.appendChild(row);
        });

        // Delegacja zdarzeń dla całej tabeli
        tbody.querySelectorAll('.edit-btn').forEach(btn => btn.addEventListener('click', () => editObject(btn.closest('tr'))));
        tbody.querySelectorAll('.delete-btn').forEach(btn => btn.addEventListener('click', () => deleteObject(btn.closest('tr'))));
    };

    const filterObjects = (searchTerm) => {
        const filtered = allObjects.filter(obj =>
            obj.nazwa_lub_numer.toLowerCase().includes(searchTerm.toLowerCase()) ||
            obj.kategoria.toLowerCase().includes(searchTerm.toLowerCase())
        );
        renderObjects(filtered);
    };

    const loadDemography = async () => {
        try {
            const response = await fetch(API.demography);
            allDemography = await response.json();
            renderDemography(allDemography);
        } catch (error) {
            console.error('Błąd ładowania demografii:', error);
            showToast('error', 'Nie udało się załadować danych demograficznych');
        }
    };

    const renderDemography = (data) => {
        const tbody = document.getElementById('demographyTableBody');
        tbody.innerHTML = '';
        
        data.forEach(entry => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="number" value="${entry.rok}" data-field="rok"></td>
                <td><input type="number" value="${entry.populacja_ogolem || ''}" data-field="populacja_ogolem"></td>
                <td><input type="number" value="${entry.katolicy || ''}" data-field="katolicy"></td>
                <td><input type="number" value="${entry.zydzi || ''}" data-field="zydzi"></td>
                <td><input type="number" value="${entry.inni || ''}" data-field="inni"></td>
                <td><textarea data-field="opis">${entry.opis || ''}</textarea></td>
                <td class="actions">
                    <button class="btn-success" onclick="saveDemography(${entry.id})">Zapisz</button>
                    <button class="delete-btn" onclick="deleteDemography(${entry.id})">Usuń</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    };

    const loadGenealogy = async () => {
        try {
            const [genealogyResponse, protocolsResponse] = await Promise.all([
                fetch(API.genealogy),
                fetch(API.protocols)
            ]);
            
            allGenealogy = await genealogyResponse.json();
            allProtocols = await protocolsResponse.json();
            
            populateFamilyFilter();
            renderGenealogy(allGenealogy);
        } catch (error) {
            console.error('Błąd ładowania genealogii:', error);
            showToast('error', 'Nie udało się załadować danych genealogicznych');
        }
    };

    const populateFamilyFilter = () => {
        const filter = document.getElementById('familyFilter');
        const canonicalFamilyNames = new Set();
        
        allGenealogy.forEach(person => {
            // Dodaj ród pochodzenia (od ojca)
            if (person.id_ojca) {
                const father = allGenealogy.find(p => p.id_osoby === person.id_ojca);
                if (father && father.nazwisko) {
                    canonicalFamilyNames.add(canonicalSurname(father.nazwisko));
                }
            }
            
            // Dla mężczyzn - dodaj ich nazwisko
            if (person.plec === 'M' && person.nazwisko) {
                canonicalFamilyNames.add(canonicalSurname(person.nazwisko));
            }
            
            // Dla kobiet - sprawdź nazwisko panieńskie
            if (person.plec === 'F' && person.nazwisko) {
                const nazwisko = person.nazwisko;
                if (nazwisko.includes(' z ')) {
                    const parts = nazwisko.split(' z ');
                    if (parts[1]) {
                        const maidenName = parts[1].split(' ')[0];
                        canonicalFamilyNames.add(canonicalSurname(maidenName));
                    }
                }
            }
        });
        
        const sortedFamilies = Array.from(canonicalFamilyNames).sort();
        filter.innerHTML = '<option value="">— Wszystkie rodziny —</option>';
        sortedFamilies.forEach(familyName => {
            filter.innerHTML += `<option value="${familyName}">Ród ${familyName}</option>`;
        });
    };

const renderGenealogy = (data) => {
    const tbody = document.getElementById('genealogyTableBody');
    tbody.innerHTML = '';
    
    // Mapy pomocnicze
    const peopleMap = new Map(allGenealogy.map(p => [p.id_osoby, p]));
    const childrenMap = new Map();
    
    // Buduj mapę dzieci
    data.forEach(p => {
        if (p.id_ojca) {
            if (!childrenMap.has(p.id_ojca)) childrenMap.set(p.id_ojca, []);
            childrenMap.get(p.id_ojca).push(p);
        }
        if (p.id_matki) {
            if (!childrenMap.has(p.id_matki)) childrenMap.set(p.id_matki, []);
            childrenMap.get(p.id_matki).push(p);
        }
    });

    // Funkcja do wyznaczania rodów osoby (może zwrócić więcej niż jeden)
    const getPersonLineages = (person) => {
        const lineages = new Set();
        
        // Ród pochodzenia (od ojca lub z nazwiska panieńskiego)
        if (person.id_ojca) {
            const father = peopleMap.get(person.id_ojca);
            if (father && father.nazwisko) {
                lineages.add(canonicalSurname(father.nazwisko));
            }
        } else if (person.nazwisko) {
            // Jeśli nie ma ojca, sprawdź nazwisko panieńskie
            const nazwisko = person.nazwisko;
            if (nazwisko.includes(' z ')) {
                // np. "Katarzyna z Kowalskich Sakowa" -> dodaj "Kowalski"
                const parts = nazwisko.split(' z ');
                if (parts[1]) {
                    const maidenName = parts[1].split(' ')[0]; // "Kowalskich" -> "Kowalski"
                    lineages.add(canonicalSurname(maidenName));
                }
            } else if (!person.id_malzonka || person.plec === 'M') {
                // Dla mężczyzn lub niezamężnych kobiet użyj ich nazwiska
                lineages.add(canonicalSurname(nazwisko));
            }
        }
        
        // Dla zamężnej kobiety - dodaj także ród męża
        if (person.plec === 'F' && person.id_malzonka) {
            const spouse = peopleMap.get(person.id_malzonka);
            if (spouse && spouse.nazwisko) {
                lineages.add(canonicalSurname(spouse.nazwisko));
            }
        }
        
        // Jeśli nie znaleziono żadnego rodu
        if (lineages.size === 0) {
            if (person.nazwisko) {
                lineages.add(canonicalSurname(person.nazwisko));
            } else {
                lineages.add('Nieznany');
            }
        }
        
        return Array.from(lineages);
    };

    // Grupuj osoby po rodach (osoba może być w wielu rodach)
    const lineages = new Map();
    
    data.forEach(person => {
        const personLineages = getPersonLineages(person);
        personLineages.forEach(lineageName => {
            if (!lineages.has(lineageName)) {
                lineages.set(lineageName, []);
            }
            lineages.get(lineageName).push(person);
        });
    });
    
    // Sortuj rody alfabetycznie
    const sortedLineages = Array.from(lineages.keys()).sort();
    
    // Renderuj każdy ród
    sortedLineages.forEach(lineageName => {
        let members = lineages.get(lineageName);
        
        // Usuń duplikaty (ta sama osoba może być dodana wielokrotnie)
        const uniqueMembers = Array.from(new Map(members.map(m => [m.id_osoby, m])).values());
        
        // Sortuj członków rodu chronologicznie
        uniqueMembers.sort((a, b) => {
            // Najpierw po roku urodzenia
            const yearA = a.rok_urodzenia || 9999;
            const yearB = b.rok_urodzenia || 9999;
            if (yearA !== yearB) return yearA - yearB;
            
            // Potem po ID
            return (a.id_osoby || '').localeCompare(b.id_osoby || '');
        });
        
        // Nagłówek rodziny
        const headerRow = document.createElement('tr');
        headerRow.className = 'family-header';
        headerRow.innerHTML = `
            <td colspan="6">
                👨‍👩‍👧‍👦 Ród ${lineageName} [${uniqueMembers.length} ${uniqueMembers.length === 1 ? 'osoba' : 'osób'}]
            </td>
            <td class="actions">
                <button class="btn-success btn-tree" title="Pokaż drzewo genealogiczne">
                    🌳 Drzewo
                </button>
            </td>
        `;
        tbody.appendChild(headerRow);
        
        // Obsługa kliknięcia przycisku drzewa
        headerRow.querySelector('.btn-tree').addEventListener('click', () => {
            showFamilyTree(lineageName, uniqueMembers);
        });
        
        // Renderuj członków rodziny
        uniqueMembers.forEach(person => {
            const row = document.createElement('tr');
            
            // Ikona osoby
            let icon = '👤';
            if (person.id_malzonka) {
                icon = '💑';
            } else if (person.id_ojca || person.id_matki) {
                icon = '👶';
            }
            
            // Lata życia
            let years = '';
            if (person.rok_urodzenia || person.rok_smierci) {
                const birth = person.rok_urodzenia || '?';
                const death = person.rok_smierci || '?';
                years = `${birth}–${death}`;
                if (years === '?–?') years = '?';
                if (years.endsWith('–?')) years = years.replace('–?', '');
            }
            
            // Imiona rodziców
            const parents = [];
            if (person.id_ojca) {
                const father = peopleMap.get(person.id_ojca);
                if (father) parents.push(father.imie);
            }
            if (person.id_matki) {
                const mother = peopleMap.get(person.id_matki);
                if (mother) parents.push(mother.imie);
            }
            const parentsStr = parents.join(', ') || '-';
            
            // Imię małżonka/małżonki
            let spouseName = '-';
            if (person.id_malzonka) {
                const spouse = peopleMap.get(person.id_malzonka);
                if (spouse) {
                    spouseName = spouse.imie;
                }
            }
            
            // Dodaj info o małżeństwie
            const marriageInfo = person.id_malzonka ? ' <small style="color:#e74c3c;">(małżonek/a)</small>' : '';
            
            // Tworzymy link do protokołu z klasą CSS
            const protocolLinkHtml = person.protokol_klucz
                ? `<a href="../wlasciciele/protokol.html?ownerId=${person.protokol_klucz}" 
                    class="protocol-link" 
                    title="Otwórz protokół">${person.protokol_klucz}</a>`
                : '<span class="protocol-none">brak</span>';
            
            row.innerHTML = `
                <td>${person.id_osoby}</td>
                <td>
                    ${icon}
                    <strong>${person.imie}</strong> ${person.nazwisko || ''}${marriageInfo}
                </td>
                <td>${years}</td>
                <td><em>${parentsStr}</em></td>
                <td><em>${spouseName}</em></td>
                <td>${protocolLinkHtml}</td>
                <td class="actions">
                    <button class="btn-warning edit-btn" data-db-id="${person.db_id}" title="Edytuj">✏️</button>
                    <button class="btn-danger delete-btn" data-db-id="${person.db_id}" title="Usuń">🗑️</button>
                </td>
            `;
            
            tbody.appendChild(row);
            
            // Event listenery dla przycisków
            row.querySelector('.edit-btn').addEventListener('click', () => editGenealogy(person.db_id));
            row.querySelector('.delete-btn').addEventListener('click', () => deleteGenealogy(person.db_id));
        });
    });
};

    const showFamilyTree = (lineageName, members) => {
        // Elementy modala
        const modal = document.getElementById('treeModal');
        const modalTitle = document.getElementById('treeModalTitle');
        const treeContainer = document.getElementById('treeContainer');
        const closeBtn = document.getElementById('treeModalClose');
        
        if (!modal || !modalTitle || !treeContainer) {
            console.error('Nie znaleziono elementów modala');
            return;
        }
        
        // Rozszerz listę członków o brakujące osoby (rodziców, małżonków)
        const expandedMembers = new Set(members.map(m => m.id_osoby));
        const additionalMembers = [];
        
        members.forEach(person => {
            // Dodaj rodziców jeśli istnieją
            if (person.id_ojca && !expandedMembers.has(person.id_ojca)) {
                const father = allGenealogy.find(p => p.id_osoby === person.id_ojca);
                if (father) {
                    additionalMembers.push(father);
                    expandedMembers.add(father.id_osoby);
                }
            }
            if (person.id_matki && !expandedMembers.has(person.id_matki)) {
                const mother = allGenealogy.find(p => p.id_osoby === person.id_matki);
                if (mother) {
                    additionalMembers.push(mother);
                    expandedMembers.add(mother.id_osoby);
                }
            }
            // Dodaj małżonka jeśli istnieje
            if (person.id_malzonka && !expandedMembers.has(person.id_malzonka)) {
                const spouse = allGenealogy.find(p => p.id_osoby === person.id_malzonka);
                if (spouse) {
                    additionalMembers.push(spouse);
                    expandedMembers.add(spouse.id_osoby);
                    
                    // Dodaj również rodziców małżonka (teściów)
                    if (spouse.id_ojca && !expandedMembers.has(spouse.id_ojca)) {
                        const spouseFather = allGenealogy.find(p => p.id_osoby === spouse.id_ojca);
                        if (spouseFather) {
                            additionalMembers.push(spouseFather);
                            expandedMembers.add(spouseFather.id_osoby);
                        }
                    }
                    if (spouse.id_matki && !expandedMembers.has(spouse.id_matki)) {
                        const spouseMother = allGenealogy.find(p => p.id_osoby === spouse.id_matki);
                        if (spouseMother) {
                            additionalMembers.push(spouseMother);
                            expandedMembers.add(spouseMother.id_osoby);
                        }
                    }
                }
            }
        });
        
        // Połącz wszystkich członków
        const allFamilyMembers = [...members, ...additionalMembers];
        
        // Przygotuj dane dla drzewa
        const localPeople = allFamilyMembers.map(person => ({
            id: person.id_osoby,
            imie: person.imie,
            nazwisko: person.nazwisko,
            plec: person.plec,
            rok_urodzenia: person.rok_urodzenia,
            rok_smierci: person.rok_smierci,
            ojciec_id: person.id_ojca,
            matka_id: person.id_matki,
            malzonek_id: person.id_malzonka,
            unikalny_klucz: person.protokol_klucz,
            numer_domu: person.numer_domu,
            uwagi: person.uwagi
        }));
        
        // Ustaw tytuł i pokaż modal
        modalTitle.textContent = `Drzewo Genealogiczne - Ród ${lineageName}`;
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');
        
        // Obsługa zamykania modala
        const closeModal = () => {
            modal.classList.add('hidden');
            document.body.classList.remove('modal-open');
            treeContainer.innerHTML = '';
        };
        
        // Event listenery do zamykania
        closeBtn.onclick = closeModal;
        
        // Zamknięcie przez kliknięcie w tło
        modal.onclick = (e) => {
            if (e.target === modal) {
                closeModal();
            }
        };
        
        // Zamknięcie przez ESC
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
        
        // Wywołaj funkcję z genealogia_admin.js
        if (window.GenealogyAdmin && window.GenealogyAdmin.showClientTree) {
            // Ustaw kontener bezpośrednio
            window.GenealogyAdmin.setTreeContainer('treeContainer');
            window.GenealogyAdmin.showClientTree(localPeople, `Ród ${lineageName}`);
        } else {
            console.error('Moduł GenealogyAdmin nie jest załadowany');
            treeContainer.innerHTML = `
                <div style="text-align: center; padding: 50px; color: #e74c3c;">
                    <h3>Błąd ładowania modułu</h3>
                    <p>Nie można załadować modułu drzewa genealogicznego</p>
                </div>
            `;
        }
    };

    const getParentNames = (person) => {
        const parents = [];
        if (person.id_ojca) {
            const father = allGenealogy.find(p => p.id_osoby === person.id_ojca);
            if (father) parents.push(father.imie);
        }
        if (person.id_matki) {
            const mother = allGenealogy.find(p => p.id_osoby === person.id_matki);
            if (mother) parents.push(mother.imie);
        }
        return parents.join(', ') || '-';
    };

    const getSpouseName = (person) => {
        if (!person.id_malzonka) return '-';
        const spouse = allGenealogy.find(p => p.id_osoby === person.id_malzonka);
        return spouse ? spouse.imie : '-';
    };

    const filterGenealogy = (searchTerm = '', family = '') => {
        let filtered = allGenealogy;
        
        if (searchTerm) {
            filtered = filtered.filter(person =>
                `${person.imie} ${person.nazwisko}`.toLowerCase().includes(searchTerm.toLowerCase())
            );
        }
        
        if (family) {
            filtered = filtered.filter(person => person.nazwisko === family);
        }
        
        renderGenealogy(filtered);
    };

    const openOwnerModal = (owner = null) => {
        elements.modalTitle.textContent = owner ? 'Edytuj Właściciela' : 'Dodaj Właściciela';

        const formatDateForInput = (dateString) => {
            if (!dateString) return '';
            try {
                // Tworzymy obiekt daty i wyciągamy część YYYY-MM-DD
                return new Date(dateString).toISOString().split('T')[0];
            } catch (e) {
                return ''; // Zwróć pusty string w razie błędu
            }
        };
        const formatTextForTextarea = (text) => (text ? String(text).replace(/\\n/g, "\n") : "");

        elements.modalBody.innerHTML = `
            <form id="ownerForm">
                <div class="form-grid">
                    <!-- Pola podstawowe bez zmian -->
                    <div class="form-group"><label>Unikalny klucz</label><input type="text" name="unikalny_klucz" value="${owner?.unikalny_klucz || ''}" required></div>
                    <div class="form-group"><label>Nazwisko i imię</label><input type="text" name="nazwa_wlasciciela" value="${owner?.nazwa_wlasciciela || ''}" required></div>
                    <div class="form-group"><label>Numer protokołu</label><input type="text" name="numer_protokolu" value="${owner?.numer_protokolu || ''}"></div>
                    <div class="form-group"><label>Numer domu</label><input type="text" name="numer_domu" value="${owner?.numer_domu || ''}"></div>
                    <div class="form-group">
                        <label>Data protokołu</label>
                        <input type="date" name="data_protokolu" value="${formatDateForInput(owner?.data_protokolu)}">
                    </div>
                    <div class="form-group"><label>Miejsce protokołu</label><input type="text" name="miejsce_protokolu" value="${owner?.miejsce_protokolu || ''}"></div>
                </div>

                <!-- Przywrócony edytor działek -->
                <div class="parcel-editor" id="parcelEditorContainer">
                    <!-- Treść edytora działek zostanie wstawiona dynamicznie -->
                </div>

                <!-- Pola opisowe bez zmian -->
                <div class="form-group"><label>Genealogia</label><textarea name="genealogia">${formatTextForTextarea(owner?.genealogia)}</textarea></div>
                <div class="form-group"><label>Historia własności</label><textarea name="historia_wlasnosci">${formatTextForTextarea(owner?.historia_wlasnosci)}</textarea></div>
                <div class="form-group"><label>Ciąg dalszy / Uwagi</label><textarea name="uwagi">${formatTextForTextarea(owner?.uwagi)}</textarea></div>
                <div class="form-group"><label>Współwłasność / Służebność</label><textarea name="wspolwlasnosc">${formatTextForTextarea(owner?.wspolwlasnosc)}</textarea></div>
                <div class="form-group"><label>Powiązania i transakcje</label><textarea name="powiazania_i_transakcje">${formatTextForTextarea(owner?.powiazania_i_transakcje)}</textarea></div>
                <div class="form-group"><label>Interpretacja i wnioski</label><textarea name="interpretacja_i_wnioski">${formatTextForTextarea(owner?.interpretacja_i_wnioski)}</textarea></div>
            </form>
        `;

        // Populacja i obsługa edytora działek
        populateAndSetupParcelEditor(owner);
        
        elements.modalSave.onclick = () => saveOwner(owner?.id);
        elements.modalOverlay.classList.remove('hidden');
    };

    // Ta funkcja jest wywoływana z openOwnerModal
    const populateAndSetupParcelEditor = async (owner) => {
        const container = document.getElementById('parcelEditorContainer');
        if (!container) return;

        // Pobierz świeżą listę wszystkich obiektów
        const allObjectsResponse = await fetch(API.allObjects);
        const allParcels = await allObjectsResponse.json();

        // Podziel działki właściciela na dwie grupy
        const ownerParcels = owner?.dzialki_wszystkie || [];
        const realPlotIds = new Set(ownerParcels.filter(p => p.typ_posiadania === 'własność rzeczywista').map(p => p.id));
        const protocolPlotIds = new Set(ownerParcels.filter(p => p.typ_posiadania !== 'własność rzeczywista').map(p => p.id));
        
        // Funkcja do tworzenia opcji dla list <select>
        const createOptions = (assignedIds) => {
            let assignedHTML = '';
            let availableHTML = '';
            
            // Lista kategorii do ukrycia w edytorze działek
            const excludedCategories = ['budynek', 'kapliczka', 'obiekt_specjalny'];

            allParcels.forEach(p => {
                // Sprawdź, czy kategoria obiektu znajduje się na liście wykluczonych
                if (excludedCategories.includes(p.kategoria)) {
                    return; // Pomiń ten obiekt i przejdź do następnego
                }

                const option = `<option value="${p.id}">${p.nazwa_lub_numer} (${p.kategoria})</option>`;
                if (assignedIds.has(p.id)) {
                    assignedHTML += option;
                } else {
                    availableHTML += option;
                }
            });
            return { assignedHTML, availableHTML };
        };

        const realOptions = createOptions(realPlotIds);
        const protocolOptions = createOptions(protocolPlotIds);

        container.innerHTML = `
            <!-- Edytor dla działek rzeczywistych -->
            <div class="parcel-list">
                <label>Działki rzeczywiste (przypisane)</label>
                <select id="assigned-real" multiple>${realOptions.assignedHTML}</select>
            </div>
            <div class="parcel-buttons">
                <button type="button" data-type="real" data-action="add">&lt;&lt;</button>
                <button type="button" data-type="real" data-action="remove">&gt;&gt;</button>
            </div>
            <div class="parcel-list">
                <label>Dostępne</label>
                <select id="available-real" multiple>${realOptions.availableHTML}</select>
            </div>

            <!-- Edytor dla działek z protokołu -->
            <div class="parcel-list">
                <label>Działki z protokołu (przypisane)</label>
                <select id="assigned-protocol" multiple>${protocolOptions.assignedHTML}</select>
            </div>
            <div class="parcel-buttons">
                <button type="button" data-type="protocol" data-action="add">&lt;&lt;</button>
                <button type="button" data-type="protocol" data-action="remove">&gt;&gt;</button>
            </div>
            <div class="parcel-list">
                <label>Dostępne</label>
                <select id="available-protocol" multiple>${protocolOptions.availableHTML}</select>
            </div>
        `;

        // Dodaj event listenery do przycisków
        container.querySelectorAll('.parcel-buttons button').forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.type;
                const action = btn.dataset.action;
                const source = document.getElementById(action === 'add' ? `available-${type}` : `assigned-${type}`);
                const dest = document.getElementById(action === 'add' ? `assigned-${type}` : `available-${type}`);
                
                Array.from(source.selectedOptions).forEach(opt => dest.appendChild(opt));
            });
        });
    };

    const saveOwner = async (id) => {
        const form = document.getElementById('ownerForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        // Zbierz ID działek z list <select>
        data.dzialki_rzeczywiste_ids = Array.from(document.getElementById('assigned-real').options).map(o => o.value);
        data.dzialki_protokol_ids = Array.from(document.getElementById('assigned-protocol').options).map(o => o.value);

        try {
            const url = id ? `${API.owners}/${id}` : API.owners;
            const method = id ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                showToast('success', 'Właściciel został zapisany');
                closeModal();
                loadOwners();
                loadDashboardData(); // Odśwież statystyki na pulpicie
            } else {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Błąd zapisu');
            }
        } catch (error) {
            showToast('error', `Nie udało się zapisać właściciela: ${error.message}`);
        }
    };

    const openDemographyModal = () => {
        elements.modalTitle.textContent = 'Dodaj Wpis Demograficzny';
        
        elements.modalBody.innerHTML = `
            <form id="demographyForm">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Rok</label>
                        <input type="number" name="rok" required>
                    </div>
                    <div class="form-group">
                        <label>Populacja</label>
                        <input type="number" name="populacja_ogolem">
                    </div>
                    <div class="form-group">
                        <label>Katolicy</label>
                        <input type="number" name="katolicy">
                    </div>
                    <div class="form-group">
                        <label>Żydzi</label>
                        <input type="number" name="zydzi">
                    </div>
                    <div class="form-group">
                        <label>Inni</label>
                        <input type="number" name="inni">
                    </div>
                </div>
                <div class="form-group">
                    <label>Opis</label>
                    <textarea name="opis"></textarea>
                </div>
            </form>
        `;
        
        elements.modalSave.onclick = saveDemographyEntry;
        elements.modalOverlay.classList.remove('hidden');
    };

    const saveDemographyEntry = async () => {
        const form = document.getElementById('demographyForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        try {
            const response = await fetch(API.demography, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                showToast('success', 'Wpis demograficzny został dodany');
                closeModal();
                loadDemography();
            } else {
                throw new Error('Błąd zapisu');
            }
        } catch (error) {
            showToast('error', 'Nie udało się dodać wpisu');
        }
    };

    const openGenealogyModal = (person = null) => {
        elements.modalTitle.textContent = person ? 'Edytuj Osobę' : 'Dodaj Osobę';
        
        const peopleOptions = allGenealogy.map(p => 
            `<option value="${p.id_osoby}">${p.imie} ${p.nazwisko || ''}</option>`
        ).join('');
        
        const protocolOptions = allProtocols.map(p =>
            `<option value="${p.key}">${p.name}</option>`
        ).join('');
        
        elements.modalBody.innerHTML = `
            <form id="genealogyForm">
                <div class="form-grid">
                    <div class="form-group">
                        <label>ID Osoby</label>
                        <input type="text" name="id_osoby" value="${person?.id_osoby || ''}" required>
                    </div>
                    <div class="form-group">
                        <label>Imię</label>
                        <input type="text" name="imie" value="${person?.imie || ''}" required>
                    </div>
                    <div class="form-group">
                        <label>Nazwisko</label>
                        <input type="text" name="nazwisko" value="${person?.nazwisko || ''}">
                    </div>
                    <div class="form-group">
                        <label>Płeć</label>
                        <select name="plec">
                            <option value="M" ${person?.plec === 'M' ? 'selected' : ''}>Mężczyzna</option>
                            <option value="F" ${person?.plec === 'F' ? 'selected' : ''}>Kobieta</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Rok urodzenia</label>
                        <input type="number" name="rok_urodzenia" value="${person?.rok_urodzenia || ''}">
                    </div>
                    <div class="form-group">
                        <label>Rok śmierci</label>
                        <input type="number" name="rok_smierci" value="${person?.rok_smierci || ''}">
                    </div>
                    <div class="form-group">
                        <label>Ojciec</label>
                        <select name="id_ojca">
                            <option value="">Brak</option>
                            ${peopleOptions}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Matka</label>
                        <select name="id_matki">
                            <option value="">Brak</option>
                            ${peopleOptions}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Małżonek</label>
                        <select name="id_malzonka">
                            <option value="">Brak</option>
                            ${peopleOptions}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Protokół</label>
                        <select name="protokol_klucz">
                            <option value="">Brak</option>
                            ${protocolOptions}
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Uwagi</label>
                    <textarea name="uwagi">${person?.uwagi || ''}</textarea>
                </div>
            </form>
        `;
        
        if (person) {
            document.querySelector('[name="id_ojca"]').value = person.id_ojca || '';
            document.querySelector('[name="id_matki"]').value = person.id_matki || '';
            document.querySelector('[name="id_malzonka"]').value = person.id_malzonka || '';
            document.querySelector('[name="protokol_klucz"]').value = person.protokol_klucz || '';
        }
        
        elements.modalSave.onclick = () => saveGenealogy(person?.db_id);
        elements.modalOverlay.classList.remove('hidden');
    };

    const saveGenealogy = async (id) => {
        const form = document.getElementById('genealogyForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);
        
        Object.keys(data).forEach(key => {
            if (data[key] === '') data[key] = null;
        });
        
        try {
            const url = id ? `${API.genealogy}/${id}` : API.genealogy;
            const method = id ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                showToast('success', 'Osoba została zapisana');
                closeModal();
                loadGenealogy();
            } else {
                throw new Error('Błąd zapisu');
            }
        } catch (error) {
            showToast('error', 'Nie udało się zapisać osoby');
        }
    };

    const closeModal = () => {
        elements.modalOverlay.classList.add('hidden');
        elements.modalBody.innerHTML = '';
    };

    const showToast = (type, message) => {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        elements.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    const toggleTheme = () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        elements.themeToggle.innerHTML = `<i class="fas fa-${isDark ? 'sun' : 'moon'}"></i>`;
    };

    const updateDateTime = () => {
        const now = new Date();
        
        // Formatowanie daty (bez zmian)
        const options = { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        };
        elements.currentDate.textContent = now.toLocaleDateString('pl-PL', options);

        // Formatowanie czasu (nowa logika)
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        
        // Wyświetlenie zegara w formacie HH:MM:SS
        elements.currentTime.textContent = `${hours}:${minutes}:${seconds}`;
    };

    const downloadBackup = () => {
        window.location.href = API.backup;
        showToast('info', 'Rozpoczęto pobieranie backupu');
    };

    const handleQuickAction = (action) => {
        switch (action) {
            case 'add-owner':
                switchSection('owners');
                openOwnerModal();
                break;
            case 'view-map':
                window.location.href = '../mapa/mapa.html';
                break;
            case 'export-data':
                downloadBackup();
                break;
            case 'system-info':
                showSystemInfo();
                break;
        }
    };

    const showSystemInfo = () => {
        elements.modalTitle.textContent = 'Informacje o Systemie';
        elements.modalBody.innerHTML = `
            <div style="padding: 1rem;">
                <h3>System Zarządzania Mapą Katastralną</h3>
                <p><strong>Wersja:</strong> 2.0</p>
                <p><strong>Autor:</strong> Maksymilian Augustyn</p>
                <p><strong>Technologie:</strong> HTML5, CSS3, JavaScript, Node.js</p>
                <p><strong>Status:</strong> Aktywny</p>
            </div>
        `;
        elements.modalSave.style.display = 'none';
        elements.modalOverlay.classList.remove('hidden');
    };

    window.editOwner = async (id) => {
        const owner = allOwners.find(o => o.id === id);
        if (owner) {
            const response = await fetch(`${API.owners}/${id}`);
            const fullData = await response.json();
            openOwnerModal(fullData);
        }
    };

    window.deleteOwner = async (id) => {
        if (confirm('Czy na pewno chcesz usunąć tego właściciela?')) {
            try {
                const response = await fetch(`${API.owners}/${id}`, { method: 'DELETE' });
                if (response.ok) {
                    showToast('success', 'Właściciel został usunięty');
                    loadOwners();
                }
            } catch (error) {
                showToast('error', 'Nie udało się usunąć właściciela');
            }
        }
    };

    // Definiujemy dwie logiczne grupy kategorii
    const areaCategories = ['rolna', 'budowlana', 'las', 'pastwisko', 'droga', 'rzeka'];
    const pointCategories = ['budynek', 'kapliczka', 'obiekt_specjalny'];

    // Główna lista jest teraz sumą obu grup (na wszelki wypadek, gdyby była używana gdzieś indziej)
    const objectCategories = [...areaCategories, ...pointCategories].sort();

    const editObject = (row) => {
        const objId = row.dataset.id;
        const currentName = row.querySelector('[data-field="nazwa_lub_numer"]').textContent;
        const currentCategory = row.querySelector('[data-field="kategoria"]').textContent;

        // --- Określ, które kategorie są dozwolone ---
        let availableOptions;
        let tooltipText = '';

        if (pointCategories.includes(currentCategory)) {
            availableOptions = pointCategories;
            tooltipText = 'Można zmienić tylko na inny typ obiektu punktowego (pinezki).';
        } else {
            // Domyślnie traktujemy resztę jako obiekty powierzchniowe/liniowe
            availableOptions = areaCategories;
            tooltipText = 'Można zmienić tylko na inny typ działki (obiektu z geometrią).';
        }

        // Zamień komórki na pola edycji
        row.querySelector('[data-field="nazwa_lub_numer"]').innerHTML = `<input type="text" class="form-control" value="${currentName}">`;
        
        const categorySelectHTML = `
            <select class="form-control" title="${tooltipText}">
                ${availableOptions.map(cat => `<option value="${cat}" ${cat === currentCategory ? 'selected' : ''}>${cat}</option>`).join('')}
            </select>
        `;
        row.querySelector('[data-field="kategoria"]').innerHTML = categorySelectHTML;

        // Zmień przyciski (bez zmian)
        const actionsCell = row.querySelector('.actions');
        actionsCell.innerHTML = `
            <button class="btn-success save-btn"><i class="fas fa-save"></i> Zapisz</button>
            <button class="btn-cancel"><i class="fas fa-times"></i> Anuluj</button>
        `;

        actionsCell.querySelector('.save-btn').addEventListener('click', () => saveObject(row));
        actionsCell.querySelector('.btn-cancel').addEventListener('click', () => loadObjects());
    };

    const saveObject = async (row) => {
        const objId = row.dataset.id;
        const newName = row.querySelector('input[type="text"]').value;
        const newCategory = row.querySelector('select').value;
        
        try {
            const response = await fetch(`${API.objects}/${objId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nazwa_lub_numer: newName, kategoria: newCategory })
            });
            
            if (response.ok) {
                showToast('success', 'Obiekt został zaktualizowany');
                loadObjects(); // Odśwież widok
            } else {
                throw new Error('Błąd zapisu na serwerze.');
            }
        } catch (error) {
            showToast('error', 'Nie udało się zapisać obiektu.');
            loadObjects(); // Przywróć oryginalny stan w razie błędu
        }
    };

    const deleteObject = async (row) => {
        const objId = row.dataset.id;
        const objName = row.querySelector('[data-field="nazwa_lub_numer"]').textContent;

        if (confirm(`Czy na pewno chcesz usunąć obiekt "${objName}"?`)) {
            try {
                const response = await fetch(`${API.objects}/${objId}`, { method: 'DELETE' });
                if (response.ok) {
                    showToast('success', 'Obiekt został usunięty');
                    loadObjects(); // Odśwież widok
                } else {
                    throw new Error('Błąd usuwania na serwerze.');
                }
            } catch (error) {
                showToast('error', 'Nie udało się usunąć obiektu.');
            }
        }
    };

    window.saveDemography = async (id) => {
        const row = event.target.closest('tr');
        const inputs = row.querySelectorAll('input, textarea');
        const data = {};
        
        inputs.forEach(input => {
            data[input.dataset.field] = input.value || null;
        });
        
        try {
            const response = await fetch(`${API.demography}/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                showToast('success', 'Wpis został zapisany');
            }
        } catch (error) {
            showToast('error', 'Nie udało się zapisać wpisu');
        }
    };

    window.deleteDemography = async (id) => {
        if (confirm('Czy na pewno chcesz usunąć ten wpis?')) {
            try {
                const response = await fetch(`${API.demography}/${id}`, { method: 'DELETE' });
                if (response.ok) {
                    showToast('success', 'Wpis został usunięty');
                    loadDemography();
                }
            } catch (error) {
                showToast('error', 'Nie udało się usunąć wpisu');
            }
        }
    };

    const editGenealogy = (id) => {
        const person = allGenealogy.find(p => p.db_id === id);
        if (person) openGenealogyModal(person);
    };


    const deleteGenealogy = async (id) => {
        const person = allGenealogy.find(p => p.db_id === id);
        if (confirm(`Czy na pewno chcesz usunąć osobę: ${person.imie} ${person.nazwisko}?`)) {
            try {
                const response = await fetch(`${API.genealogy}/${id}`, { method: 'DELETE' });
                if (response.ok) {
                    showToast('success', 'Osoba została usunięta');
                    loadGenealogy();
                } else {
                    throw new Error('Błąd serwera podczas usuwania.');
                }
            } catch (error) {
                showToast('error', 'Nie udało się usunąć osoby.');
            }
        }
    };

    // === PRZENIESIONYMY TUTAJ PRZED init(); ===
    
    // Stałe konfiguracyjne dla rysowania drzewa
    const TREE_CONFIG = {
        NODE_HEIGHT: 80,
        NODE_MIN_W: 120,
        H_GAP: 80,
        V_GAP: 120,
        MARGIN: 80,
        FONT: '700 16px "Segoe UI", sans-serif',
        MARRIAGE_GAP: 20
    };

    // Pokazywanie drzewa genealogicznego na podstawie protokołu
    const showGenealogyTreeFromProtocol = async (protocolKey, familyName) => {
        try {
            const response = await fetch(`/api/genealogia/${protocolKey}`);
            if (!response.ok) throw new Error('Błąd pobierania danych');
            
            const data = await response.json();
            if (data.persons && Array.isArray(data.persons)) {
                const personsForTree = data.persons.map(person => ({
                    id: person.id,
                    name: person.name,
                    gender: person.gender,
                    birthDate: person.birthDate,
                    deathDate: person.deathDate,
                    fatherId: person.fatherId,
                    motherId: person.motherId,
                    spouseIds: person.spouseIds,
                    protocolKey: person.protocolKey,
                    houseNumber: person.houseNumber
                }));
                
                elements.treeModalTitle.textContent = `Drzewo Genealogiczne - ${familyName}`;
                elements.treeModal.classList.remove('hidden');
                AdvancedTreeRenderer.render(elements.treeContainer, personsForTree, data.rootId);
            }
        } catch (error) {
            console.error('Błąd ładowania drzewa:', error);
            showToast('error', 'Nie udało się załadować drzewa genealogicznego');
        }
    };

    // Pokazywanie lokalnego drzewa rodziny
    const showLocalFamilyTree = (lineName, members, peopleMap) => {
        const famCanon = canonicalSurname(lineName.replace(/\s*KATEX_INLINE_OPEN.*$/, ""));
        
        const coreMemberIds = new Set(
            allGenealogy
                .filter(p => canonicalSurname(p.nazwisko) === famCanon)
                .map(p => p.id_osoby)
        );
        
        const spouseIds = new Set(
            allGenealogy
                .filter(p => p.id_malzonka && coreMemberIds.has(p.id_malzonka))
                .map(p => p.id_osoby)
        );
        
        const childIds = new Set(
            allGenealogy
                .filter(p => 
                    (p.id_ojca && coreMemberIds.has(p.id_ojca)) ||
                    (p.id_matki && coreMemberIds.has(p.id_matki))
                )
                .map(p => p.id_osoby)
        );
        
        const includeIds = new Set([...coreMemberIds, ...spouseIds, ...childIds]);
        
        const localPeople = allGenealogy
            .filter(p => includeIds.has(p.id_osoby))
            .map(p => ({
                id: p.id_osoby,
                name: `${p.imie} ${p.nazwisko || ''}`.trim(),
                gender: p.plec,
                birthDate: { year: p.rok_urodzenia },
                deathDate: { year: p.rok_smierci },
                fatherId: p.id_ojca,
                motherId: p.id_matki,
                spouseIds: p.id_malzonka ? [p.id_malzonka] : [],
                protocolKey: p.protokol_klucz
            }));
        
        elements.treeModalTitle.textContent = `Drzewo Genealogiczne - ${lineName}`;
        elements.treeModal.classList.remove('hidden');
        AdvancedTreeRenderer.render(elements.treeContainer, localPeople);
    };

    // Moduł GenealogyTreeViewer
    const GenealogyTreeViewer = (() => {
        const showClientTree = (members, familyName) => {
            const personsForTree = members.map(person => ({
                id: person.id_osoby,
                name: `${person.imie} ${person.nazwisko || ''}`.trim(),
                gender: person.plec,
                birthDate: { year: person.rok_urodzenia },
                deathDate: { year: person.rok_smierci },
                fatherId: person.id_ojca,
                motherId: person.id_matki,
                spouseIds: person.id_malzonka ? [person.id_malzonka] : [],
                protocolKey: person.protokol_klucz,
                houseNumber: person.numer_domu
            }));
            
            AdvancedTreeRenderer.render(elements.treeContainer, personsForTree);
        };
        
        return { showClientTree };
    })();

    // Moduł AdvancedTreeRenderer
    const AdvancedTreeRenderer = (() => {
        const expandUnions = (rawPeople) => {
            const nodes = [];
            const unions = [];
            
            rawPeople.forEach(p => {
                if (p.spouseIds && p.spouseIds.length > 0) {
                    p.spouseIds.forEach((spouseId, idx) => {
                        const uid = `u_${p.id}_${spouseId}_${idx}`;
                        unions.push({
                            id: uid,
                            type: "union",
                            parents: [p.id, spouseId],
                            children: []
                        });
                    });
                }
                nodes.push(p);
            });
            
            return nodes.concat(unions);
        };
        
    const render = (container, persons, rootId = null) => {
        container.innerHTML = '';
        
        if (!persons || persons.length === 0) {
            container.innerHTML = '<div style="padding: 2rem; text-align: center;">Brak danych do wyświetlenia</div>';
            return;
        }
        
        // Filtruj osoby - usuń wszystkie z undefined ID lub nazwą
        const validPersons = persons.filter(p => 
            p && p.id && p.name && !p.name.includes('undefined')
        );
        
        // Przygotowanie canvas do pomiaru tekstu
        const ctx = document.createElement("canvas").getContext("2d");
        ctx.font = TREE_CONFIG.FONT;
        const textWidth = (t) => ctx.measureText(t).width;
        
        // Mapa osób - tylko istniejące osoby
        const personMap = new Map();
        const existingIds = new Set(validPersons.map(p => String(p.id)));
        
        validPersons.forEach(p => {
            // Filtruj rodziców i małżonków - tylko jeśli istnieją w danych
            const validFatherId = p.fatherId && existingIds.has(String(p.fatherId)) ? String(p.fatherId) : null;
            const validMotherId = p.motherId && existingIds.has(String(p.motherId)) ? String(p.motherId) : null;
            const validSpouseIds = (p.spouseIds || []).filter(id => existingIds.has(String(id)));
            
            const rec = {
                nodeId: String(p.id),
                name: p.name,
                birth: p.birthDate?.year,
                death: p.deathDate?.year,
                gender: p.gender,
                ojciec_id: validFatherId,
                matka_id: validMotherId,
                malzonek_ids: validSpouseIds,
                key: p.protocolKey,
                isRoot: p.id === rootId,
                boxW: Math.max(TREE_CONFIG.NODE_MIN_W, Math.ceil(textWidth(p.name || '')) + 30),
                generation: 0,
                x: 0,
                y: 0
            };
            personMap.set(String(p.id), rec);
        });
        
        // Pozycjonowanie węzłów
        const allNodes = positionTreeNodes(personMap);
        const { connections, marriages } = findTreeConnections(allNodes);
        
        if (allNodes.length === 0) {
            container.innerHTML = '<div style="padding: 2rem; text-align: center;">Brak danych do wyświetlenia</div>';
            return;
        }
        
        // Obliczenie wymiarów
        const xs = allNodes.map(n => [n.x, n.x + n.boxW]).flat();
        const ys = allNodes.map(n => n.y);
        const minX = Math.min(...xs) || 0;
        const maxX = Math.max(...xs) || 100;
        const minY = Math.min(...ys) || 0;
        const maxY = Math.max(...ys) || 100;
        const W = maxX - minX + 2 * TREE_CONFIG.MARGIN;
        const H = maxY - minY + TREE_CONFIG.NODE_HEIGHT + 2 * TREE_CONFIG.MARGIN;
        
        // Tworzenie SVG
        const svg = d3.create("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", `0 0 ${W} ${H}`)
            .call(
                d3.zoom()
                    .scaleExtent([0.2, 4])
                    .on("zoom", (e) => g.attr("transform", e.transform))
            );
        
        const g = svg.append("g")
            .attr("transform", `translate(${-minX + TREE_CONFIG.MARGIN}, ${-minY + TREE_CONFIG.MARGIN})`);
        
        // Rysowanie połączeń rodzic-dziecko
        g.append("g")
            .selectAll("path")
            .data(connections.filter(c => c.type === "parent-child"))
            .join("path")
            .attr("d", d => {
                const midY = (d.source.y + d.target.y) / 2;
                return `M${d.source.x},${d.source.y}V${midY}H${d.target.x}V${d.target.y}`;
            })
            .attr("stroke", "#999")
            .attr("stroke-width", 2)
            .attr("fill", "none");
        
        // Rysowanie linii małżeństw
        g.append("g")
            .selectAll("line")
            .data(marriages)
            .join("line")
            .attr("x1", ([left, right]) => left.x + left.boxW)
            .attr("y1", ([left, right]) => left.y + TREE_CONFIG.NODE_HEIGHT / 2)
            .attr("x2", ([left, right]) => right.x)
            .attr("y2", ([left, right]) => right.y + TREE_CONFIG.NODE_HEIGHT / 2)
            .attr("stroke", "#e74c3c")
            .attr("stroke-width", 3)
            .attr("stroke-dasharray", "5,5");
        
        // Kolory pokoleń
        const generationColors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"];
        const getColor = (generation) => generationColors[Math.abs(generation) % generationColors.length];
        
        // Rysowanie węzłów
        const ng = g.append("g")
            .selectAll("g")
            .data(allNodes)
            .join("g")
            .attr("transform", d => `translate(${d.x}, ${d.y})`)
            .style("cursor", "pointer")
            .on("click", (event, d) => {
                // Po kliknięciu pokaż info o osobie
                console.log('Kliknięto:', d.name);
            });
        
        // Prostokąty
        ng.append("rect")
            .attr("width", d => d.boxW)
            .attr("height", TREE_CONFIG.NODE_HEIGHT)
            .attr("rx", 8)
            .attr("fill", d => d.gender === 'F' ? "#FFE4E1" : "#E6F3FF")
            .attr("stroke", d => d.isRoot ? "#e74c3c" : getColor(d.generation))
            .attr("stroke-width", d => d.isRoot ? 3 : 2);
        
        // Ikona płci
        ng.append("text")
            .attr("x", 10)
            .attr("y", 25)
            .style("font-size", "18px")
            .text(d => d.gender === 'F' ? '♀' : '♂')
            .style("fill", d => d.gender === 'F' ? "#FF69B4" : "#4169E1");
        
        // Tekst - imię i nazwisko
        ng.append("text")
            .attr("x", d => d.boxW / 2)
            .attr("y", TREE_CONFIG.NODE_HEIGHT / 2 - 8)
            .attr("text-anchor", "middle")
            .style("font", "14px 'Segoe UI', sans-serif")
            .style("font-weight", "600")
            .text(d => d.name);
        
        // Daty
        ng.append("text")
            .attr("x", d => d.boxW / 2)
            .attr("y", TREE_CONFIG.NODE_HEIGHT / 2 + 12)
            .attr("text-anchor", "middle")
            .style("font-size", "12px")
            .style("fill", "#666")
            .text(d => {
                const b = d.birth, dd = d.death;
                return b && !dd ? `ur. ${b}` : 
                    dd && !b ? `† ${dd}` : 
                    b && dd ? `${b} – ${dd}` : "";
            });
        
        container.appendChild(svg.node());
    };
        
const positionTreeNodes = (personMap) => {
    // Najpierw ustal generacje na podstawie relacji rodzic-dziecko
    const setGenerations = () => {
        // Resetuj generacje
        personMap.forEach(p => p.generation = null);
        
        // Znajdź osoby bez rodziców (najstarsze pokolenie)
        const roots = Array.from(personMap.values()).filter(
            p => !p.ojciec_id && !p.matka_id
        );
        
        if (roots.length === 0) {
            // Jeśli nie ma korzeni, zacznij od najstarszej osoby
            const oldest = Array.from(personMap.values()).sort((a, b) => 
                (a.birth || 0) - (b.birth || 0)
            )[0];
            if (oldest) {
                oldest.generation = 0;
                roots.push(oldest);
            }
        } else {
            roots.forEach(r => r.generation = 0);
        }
        
        // BFS do ustalenia generacji
        const queue = [...roots];
        const visited = new Set(roots.map(r => r.nodeId));
        
        while (queue.length > 0) {
            const current = queue.shift();
            
            // Znajdź dzieci
            personMap.forEach(person => {
                if (!visited.has(person.nodeId)) {
                    if (person.ojciec_id === current.nodeId || 
                        person.matka_id === current.nodeId) {
                        person.generation = current.generation + 1;
                        queue.push(person);
                        visited.add(person.nodeId);
                    }
                }
            });
            
            // Ustaw małżonka na tym samym poziomie
            if (current.malzonek_ids && current.malzonek_ids.length > 0) {
                current.malzonek_ids.forEach(spouseId => {
                    const spouse = personMap.get(spouseId);
                    if (spouse && spouse.generation === null) {
                        spouse.generation = current.generation;
                        if (!visited.has(spouse.nodeId)) {
                            queue.push(spouse);
                            visited.add(spouse.nodeId);
                        }
                    }
                });
            }
        }
        
        // Dla osób które nie zostały przypisane
        personMap.forEach(p => {
            if (p.generation === null) {
                // Spróbuj ustalić na podstawie małżonka
                if (p.malzonek_ids && p.malzonek_ids.length > 0) {
                    for (const spouseId of p.malzonek_ids) {
                        const spouse = personMap.get(spouseId);
                        if (spouse && spouse.generation !== null) {
                            p.generation = spouse.generation;
                            break;
                        }
                    }
                }
                // Jeśli nadal null, ustaw na 0
                if (p.generation === null) {
                    p.generation = 0;
                }
            }
        });
    };
    
    setGenerations();
    
    // Grupuj osoby po generacjach
    const generations = new Map();
    personMap.forEach(p => {
        const gen = p.generation;
        if (!generations.has(gen)) {
            generations.set(gen, []);
        }
        generations.get(gen).push(p);
    });
    
    // Sortuj generacje
    const sortedGenerations = Array.from(generations.keys()).sort((a, b) => a - b);
    
    // Pozycjonuj węzły
    const positioned = [];
    let currentY = 0;
    
    sortedGenerations.forEach(genLevel => {
        const genMembers = generations.get(genLevel);
        
        // Grupuj małżeństwa razem
        const couples = [];
        const singles = [];
        const processed = new Set();
        
        genMembers.forEach(person => {
            if (processed.has(person.nodeId)) return;
            
            if (person.malzonek_ids && person.malzonek_ids.length > 0) {
                // Znajdź małżonka na tym samym poziomie
                const spouseId = person.malzonek_ids[0];
                const spouse = genMembers.find(m => m.nodeId === spouseId);
                
                if (spouse && !processed.has(spouse.nodeId)) {
                    couples.push([person, spouse]);
                    processed.add(person.nodeId);
                    processed.add(spouse.nodeId);
                } else if (!spouse) {
                    // Małżonek nie jest na tym poziomie
                    singles.push(person);
                    processed.add(person.nodeId);
                }
            } else {
                singles.push(person);
                processed.add(person.nodeId);
            }
        });
        
        // Pozycjonuj pary i single
        let currentX = TREE_CONFIG.MARGIN;
        
        // Najpierw pary małżeńskie
        couples.forEach(([person1, person2]) => {
            // Ustaw pierwszą osobę z pary
            person1.x = currentX;
            person1.y = currentY;
            positioned.push(person1);
            currentX += person1.boxW + TREE_CONFIG.MARRIAGE_GAP;
            
            // Ustaw drugą osobę z pary
            person2.x = currentX;
            person2.y = currentY;
            positioned.push(person2);
            currentX += person2.boxW + TREE_CONFIG.H_GAP;
        });
        
        // Potem osoby single
        singles.forEach(person => {
            person.x = currentX;
            person.y = currentY;
            positioned.push(person);
            currentX += person.boxW + TREE_CONFIG.H_GAP;
        });
        
        currentY += TREE_CONFIG.NODE_HEIGHT + TREE_CONFIG.V_GAP;
    });
    
    return positioned;
};
        
        return { render };
    })();

    // Sprawdzenie theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        elements.themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    }

const findTreeConnections = (allNodes) => {
    const connections = [];
    const marriages = [];
    const nodeById = new Map(allNodes.map(n => [n.nodeId, n]));
    
    // Znajdź małżeństwa - tylko między osobami na tym samym poziomie
    const processed = new Set();
    allNodes.forEach(person => {
        if (person.malzonek_ids && person.malzonek_ids.length > 0) {
            person.malzonek_ids.forEach(spouseId => {
                const spouse = nodeById.get(String(spouseId));
                if (spouse && 
                    person.generation === spouse.generation && 
                    !processed.has(`${person.nodeId}-${spouseId}`) &&
                    !processed.has(`${spouseId}-${person.nodeId}`)) {
                    
                    // Ustaw od lewej do prawej
                    const left = person.x < spouse.x ? person : spouse;
                    const right = person.x < spouse.x ? spouse : person;
                    marriages.push([left, right]);
                    processed.add(`${person.nodeId}-${spouseId}`);
                }
            });
        }
    });
    
    // Znajdź połączenia rodzic-dziecko
    allNodes.forEach(child => {
        const father = child.ojciec_id ? nodeById.get(child.ojciec_id) : null;
        const mother = child.matka_id ? nodeById.get(child.matka_id) : null;
        
        if (!father && !mother) return;
        
        let sourceX, sourceY;
        
        if (father && mother) {
            // Oboje rodzice istnieją
            // Sprawdź czy są małżeństwem na tym samym poziomie
            if (father.generation === mother.generation &&
                Math.abs(father.x - mother.x) < (TREE_CONFIG.H_GAP * 2)) {
                // Rodzice są obok siebie - linia schodzi z środka między nimi
                const leftParent = father.x < mother.x ? father : mother;
                const rightParent = father.x < mother.x ? mother : father;
                sourceX = (leftParent.x + leftParent.boxW + rightParent.x) / 2;
                sourceY = leftParent.y + TREE_CONFIG.NODE_HEIGHT;
            } else {
                // Rodzice nie są obok siebie - użyj środka między nimi
                sourceX = (father.x + father.boxW / 2 + mother.x + mother.boxW / 2) / 2;
                sourceY = Math.max(father.y, mother.y) + TREE_CONFIG.NODE_HEIGHT;
            }
        } else {
            // Tylko jeden rodzic
            const parent = father || mother;
            sourceX = parent.x + parent.boxW / 2;
            sourceY = parent.y + TREE_CONFIG.NODE_HEIGHT;
        }
        
        connections.push({
            type: "parent-child",
            source: { x: sourceX, y: sourceY },
            target: { x: child.x + child.boxW / 2, y: child.y },
            child: child
        });
    });
    
    return { connections, marriages };
};



    // INICJALIZACJA
    init();
}); // <-- Tutaj kończy się DOMContentLoaded