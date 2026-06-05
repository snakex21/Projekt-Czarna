document.addEventListener('DOMContentLoaded', () => {
    let currentSection = 'dashboard';
    // allOwners przeniesiony do js/owners.js (P2.5 Etap 3) - stan modułu właścicieli
    // allDemography przeniesiony do js/demography.js (P2.5 Etap 3) - stan modułu demografii
    let allGenealogy = [];
    let allProtocols = [];
    let showPersonDetails = null; // Zmienna globalna w ramach modułu

    // === Moduły (static/admin/js/*.js) muszą być załadowane PRZED admin.js ===
    // Te referencje są cienkimi aliasami do modułów, dzięki czemu reszta
    // admin.js może pisać `API.foo`, `escapeHtml(x)` itd. bez zmian.
    if (!window.AdminAPI) {
        throw new Error('admin.js wymaga js/api.js załadowanego wcześniej');
    }
    if (!window.AdminUtils) {
        throw new Error('admin.js wymaga js/utils.js załadowanego wcześniej');
    }
    if (!window.AdminNotifications) {
        throw new Error('admin.js wymaga js/notifications.js załadowanego wcześniej');
    }
    if (!window.AdminAuth) {
        throw new Error('admin.js wymaga js/auth.js załadowanego wcześniej');
    }
    if (!window.AdminObjects) {
        throw new Error('admin.js wymaga js/objects.js załadowanego wcześniej');
    }
    if (!window.AdminOwners) {
        throw new Error('admin.js wymaga js/owners.js załadowanego wcześniej');
    }
    if (!window.AdminDemography) {
        throw new Error('admin.js wymaga js/demography.js załadowanego wcześniej');
    }
    if (!window.AdminDashboard) {
        throw new Error('admin.js wymaga js/dashboard.js załadowanego wcześniej');
    }
    if (!window.AdminOwnerModal) {
        throw new Error('admin.js wymaga js/owner-modal.js załadowanego wcześniej');
    }
    if (!window.AdminGenealogyMiniTree) {
        throw new Error('admin.js wymaga js/genealogy-mini-tree.js załadowanego wcześniej');
    }
    if (!window.AdminGenealogyTree) {
        throw new Error('admin.js wymaga js/genealogy-tree.js załadowanego wcześniej');
    }
    if (!window.AdminGenealogyDetails) {
        throw new Error('admin.js wymaga js/genealogy-details.js załadowanego wcześniej');
    }
    if (!window.AdminGenealogyModal) {
        throw new Error('admin.js wymaga js/genealogy-modal.js załadowanego wcześniej');
    }
    if (!window.AdminGenealogyList) {
        throw new Error('admin.js wymaga js/genealogy-list.js załadowanego wcześniej');
    }
    const API = window.AdminAPI;
    const AUTH = window.AdminAuth;
    const OBJ = window.AdminObjects;
    const OWNERS = window.AdminOwners;
    const DEMO = window.AdminDemography;
    const DASH = window.AdminDashboard;
    const OWNER_MODAL = window.AdminOwnerModal;
    const GEN_MINI = window.AdminGenealogyMiniTree;
    const GEN_TREE = window.AdminGenealogyTree;
    const GEN_DETAILS = window.AdminGenealogyDetails;
    const GEN_MODAL = window.AdminGenealogyModal;
    const GEN_LIST = window.AdminGenealogyList;
    const { showToast } = window.AdminNotifications;

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
        AUTH.init({
            elements: {
                loginForm: elements.loginForm,
                loginError: elements.loginError,
                logoutBtn: elements.logoutBtn
            },
            callbacks: {
                showLoginScreen,
                showAdminPanel
            }
        });
        setupEventListeners();
        DASH.startClock();
        AUTH.checkAuth();
    };

    // canonicalSurname dostarczany przez js/utils.js (window.AdminUtils.canonicalSurname)

    const showLoginScreen = () => {
        elements.loginScreen.classList.remove('hidden');
        elements.adminPanel.classList.add('hidden');
    };

    const showAdminPanel = () => {
        elements.loginScreen.classList.add('hidden');
        elements.adminPanel.classList.remove('hidden');
        DASH.load();
    };

    const setupEventListeners = () => {
        elements.loginForm.addEventListener('submit', AUTH.login);
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
                    DASH.downloadBackup();
                } else if (item.id === 'logoutBtn') {
                    AUTH.logout();
                }
            });
        });

        elements.themeToggle.addEventListener('click', toggleTheme);

        elements.modalClose.addEventListener('click', closeModal);
        elements.modalCancel.addEventListener('click', closeModal);
        elements.modalOverlay.addEventListener('click', (e) => {
            if (e.target === elements.modalOverlay) closeModal();
        });

        document.getElementById('addOwnerBtn')?.addEventListener('click', () => OWNER_MODAL.open());
        document.getElementById('searchOwners')?.addEventListener('input', (e) => OWNERS.filter(e.target.value));

        document.getElementById('searchObjects')?.addEventListener('input', (e) => OBJ.filter(e.target.value));

        document.getElementById('addDemographyBtn')?.addEventListener('click', () => DEMO.add());

        document.getElementById('refreshDiagnosticsBtn')?.addEventListener('click', () => {
            if (window.AdminDiagnostics && window.AdminDiagnostics.refresh) {
                window.AdminDiagnostics.refresh().catch((err) =>
                    console.error('Diagnostics refresh failed', err)
                );
            }
        });

        document.getElementById('addGenealogyBtn')?.addEventListener('click', () => GEN_MODAL.open(null, genealogyModalOptions()));
        document.getElementById('searchGenealogy')?.addEventListener('input', (e) => filterGenealogy());
        document.getElementById('filterHouse')?.addEventListener('input', (e) => filterGenealogy());
        document.getElementById('sortFilter')?.addEventListener('change', (e) => filterGenealogy());

        // Filtry płci w genealogii
        document.querySelectorAll('.genealogy-filters .filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.genealogy-filters .filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                filterGenealogy();
            });
        });

        document.querySelectorAll('.action-card').forEach(card => {
            card.addEventListener('click', () => {
                const action = card.dataset.action;
                DASH.handleQuickAction(action, { switchSection });
            });
        });
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
            genealogy: 'Genealogia',
            diagnostics: 'Diagnostyka'
        };
        return names[section] || section;
    };

    const loadSectionData = async (section) => {
        switch (section) {
            case 'dashboard':
                DASH.load();
                break;
            case 'owners':
                OWNERS.load();
                break;
            case 'objects':
                OBJ.load();
                break;
            case 'demography':
                DEMO.load();
                break;
            case 'genealogy':
                loadGenealogy();
                break;
            case 'diagnostics':
                if (window.AdminDiagnostics && window.AdminDiagnostics.refresh) {
                    window.AdminDiagnostics.refresh().catch((err) =>
                        console.error('Diagnostics refresh failed', err)
                    );
                } else {
                    console.warn('AdminDiagnostics nie załadowany');
                }
                break;
        }
    };

    // Sekcja właścicieli wydzielona do js/owners.js (P2.5 Etap 3):
    // loadOwners, renderOwners, filterOwners, editOwner, deleteOwner
    // są dostępne przez window.AdminOwners.{load, filter, edit, remove}.
    // (Zapis właściciela nadal tu - openOwnerModal wymaga dostępu do `elements`.)

    // Sekcja demografii wydzielona do js/demography.js (P2.5 Etap 3):
    // loadDemography, renderDemography, openDemographyModal, saveDemographyEntry,
    // saveDemography (inline), deleteDemography są dostępne przez
    // window.AdminDemography.{load, add, save, remove}.

    // Sekcja obiektów wydzielona do js/objects.js (P2.5 Etap 2):
    // loadObjects, renderObjects, renderObjectStatus, renderOwnerLink, filterObjects
    // są dostępne przez window.AdminObjects.{load, filter}.

    const genealogyListOptions = () => ({
        allGenealogy,
        onDataLoaded: ({ genealogy, protocols }) => {
            allGenealogy = genealogy;
            allProtocols = protocols;
        },
        onSelect: (person, allGenealogy) => GEN_DETAILS.show(person, allGenealogy, {
            onEdit: editGenealogy,
            onDelete: deleteGenealogy,
            onShowTree: (person, allGenealogy) => GEN_MINI.show(person, allGenealogy),
            onShowFullTree: (person, allGenealogy) => GEN_TREE.showFromData(person, allGenealogy)
        })
    });

    const loadGenealogy = async () => {
        showPersonDetails = await GEN_LIST.load(genealogyListOptions());
    };

    const renderGenealogy = (data) => {
        showPersonDetails = GEN_LIST.render(data, genealogyListOptions());
    };

    const filterGenealogy = () => {
        showPersonDetails = GEN_LIST.filter(genealogyListOptions());
    };

    // Modal właściciela wydzielony do js/owner-modal.js (P2.5 Etap 6).
    // Dostępny przez window.AdminOwnerModal.{open, save, populate}.

    // Sekcja modala demografii (openDemographyModal, saveDemographyEntry)
    // wydzielona do js/demography.js (P2.5 Etap 3). Dostępne przez
    // window.AdminDemography.add() i wywoływane wewnętrznie przy zapisie.

    // Funkcja globalna do filtrowania selectów
    window.filterSelect = (input, selectId) => {
        const filter = input.value.toLowerCase();
        const select = document.getElementById(selectId);
        if (!select) return;

        const options = select.options;
        for (let i = 0; i < options.length; i++) {
            const txt = options[i].text.toLowerCase();
            // Pokaż opcję jeśli pasuje lub jeśli to opcja "Brak"/"Wybierz..." (pusta wartość)
            // Ale chcemy móc ukryć "Brak" jeśli szukamy konkretnego imienia
            if (options[i].value === "") {
                options[i].style.display = "";
            } else {
                options[i].style.display = txt.includes(filter) ? "" : "none";
            }
        }
    };

    const genealogyModalOptions = () => ({
        allGenealogy,
        allProtocols,
        onSaved: async (savedData) => {
            await loadGenealogy();

            const savedId = savedData?.id_osoby;
            if (savedId) {
                const person = allGenealogy.find(p => String(p.id_osoby) === String(savedId));
                if (person && showPersonDetails) {
                    showPersonDetails(person);
                } else {
                    console.warn('Nie znaleziono nowo dodanej osoby na liście:', savedId);
                }
            }
        }
    });

    const closeModal = () => {
        elements.modalOverlay.classList.add('hidden');
        elements.modalBody.innerHTML = '';
    };

    // showToast / showNotification dostarczane przez js/notifications.js
    // (window.AdminNotifications.{showToast,showNotification})

    const toggleTheme = () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        elements.themeToggle.innerHTML = `<i class="fas fa-${isDark ? 'sun' : 'moon'}"></i>`;
    };

    // Sekcja pulpitu/systemu wydzielona do js/dashboard.js (P2.5 Etap 5):
    // loadDashboardData, updateDateTime, downloadBackup, handleQuickAction,
    // showSystemInfo są dostępne przez window.AdminDashboard.

    // Sekcja CRUD właścicieli (editOwner, deleteOwner) wydzielona do js/owners.js
    // (P2.5 Etap 3). Dostępne przez window.AdminOwners.{edit, remove}.
    // openOwnerModal nadal tu - wymaga dostępu do `elements` (modal*).

    // Sekcja CRUD obiektów (editObject, saveObject, deleteObject) oraz kategorie
    // (areaCategories, pointCategories, objectCategories) wydzielone do js/objects.js
    // (P2.5 Etap 2). Dostępne przez window.AdminObjects.{edit, save, remove}.

    // Sekcja CRUD demografii (saveDemography inline, deleteDemography) wydzielona
    // do js/demography.js (P2.5 Etap 3). Dostępne przez
    // window.AdminDemography.{save, remove}.

    const editGenealogy = (id) => {
        const person = allGenealogy.find(p => p.db_id === id);
        if (person) GEN_MODAL.open(person, genealogyModalOptions());
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

    // Sprawdzenie theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        elements.themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    }

    // INICJALIZACJA
    init();
}); // <-- Tutaj kończy się DOMContentLoaded

