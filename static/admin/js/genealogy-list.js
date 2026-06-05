(function () {
    'use strict';

    const API = window.AdminAPI;
    const { showNotification } = window.AdminNotifications;

    function formatLifespan(person) {
        if (!person) return '? - ?';
        if (!person.rok_urodzenia && !person.rok_smierci) return '? - ?';
        const birth = person.rok_urodzenia || '?';
        const death = person.rok_smierci || '?';
        return `${birth} - ${death}`;
    }

    async function loadGenealogy(options = {}) {
        try {
            const [genealogyResponse, protocolsResponse] = await Promise.all([
                fetch(`${API.genealogy}?t=${Date.now()}`),
                fetch(API.protocols)
            ]);

            if (!genealogyResponse.ok) throw new Error('Błąd pobierania danych genealogicznych');

            const genealogy = await genealogyResponse.json();
            let protocols = [];

            if (protocolsResponse.ok) {
                protocols = await protocolsResponse.json();
            } else {
                console.warn('Nie udało się pobrać protokołów');
            }

            if (typeof options.onDataLoaded === 'function') {
                options.onDataLoaded({ genealogy, protocols });
            }

            return filterGenealogy({ ...options, allGenealogy: genealogy });
        } catch (error) {
            console.error('Błąd:', error);
            showNotification('Nie udało się pobrać danych genealogicznych', 'error');
            return null;
        }
    }

    function renderGenealogy(data, options = {}) {
        const listContainer = document.getElementById('personsListContainer');
        const countEl = document.getElementById('genPersonCount');
        const sortedData = Array.isArray(data) ? data : [];
        const allGenealogy = Array.isArray(options.allGenealogy) ? options.allGenealogy : sortedData;
        const onSelect = options.onSelect || function () { };

        if (!listContainer || !countEl) return null;

        listContainer.innerHTML = '';
        countEl.textContent = sortedData.length;

        const showPersonDetails = (person) => onSelect(person, allGenealogy);

        if (sortedData.length === 0) {
            listContainer.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: #64748b;">
                <i class="fas fa-search" style="font-size: 2rem; margin-bottom: 1rem; display: block;"></i>
                Nie znaleziono osób
            </div>
        `;
            return showPersonDetails;
        }

        sortedData.forEach(person => {
            const genderClass = person.plec === 'M' ? 'male' : (person.plec === 'F' ? 'female' : '');
            const genderIcon = person.plec === 'M' ? 'fa-mars' : (person.plec === 'F' ? 'fa-venus' : 'fa-genderless');

            const item = document.createElement('div');
            item.className = `person-list-item ${genderClass}`;
            item.dataset.personId = person.id_osoby;
            item.innerHTML = `
            <div class="person-list-icon">
                <i class="fas ${genderIcon}"></i>
            </div>
            <div class="person-list-info">
                <div class="person-list-name">${person.imie} ${person.nazwisko || ''}</div>
                <div class="person-list-dates">
                    <i class="fas fa-calendar"></i> ${formatLifespan(person)}
                </div>
            </div>
            <div class="person-list-arrow">
                <i class="fas fa-chevron-right"></i>
            </div>
        `;

            item.addEventListener('click', () => showPersonDetails(person));
            listContainer.appendChild(item);
        });

        if (sortedData.length > 0) {
            showPersonDetails(sortedData[0]);
        }

        return showPersonDetails;
    }

    function filterGenealogy(options = {}) {
        const allGenealogy = Array.isArray(options.allGenealogy) ? options.allGenealogy : [];
        const searchTerm = document.getElementById('searchGenealogy')?.value || '';
        const houseFilter = document.getElementById('filterHouse')?.value || '';
        const sortOrder = document.getElementById('sortFilter')?.value || 'az';
        const genderFilter = document.querySelector('.genealogy-filters .filter-btn.active')?.dataset.filter || 'all';

        let filtered = allGenealogy;

        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            filtered = filtered.filter(person => {
                const fullName = `${person.imie} ${person.nazwisko}`.toLowerCase();
                const yearStr = String(person.rok_urodzenia || '');
                return fullName.includes(term) || yearStr.includes(term);
            });
        }

        if (houseFilter) {
            const term = houseFilter.toLowerCase();
            filtered = filtered.filter(person => {
                const houseStr = String(person.numer_domu || '');
                return houseStr.toLowerCase().includes(term);
            });
        }

        if (genderFilter !== 'all') {
            const genderKey = genderFilter === 'male' ? 'M' : 'F';
            filtered = filtered.filter(person => person.plec === genderKey);
        }

        filtered.sort((a, b) => {
            if (sortOrder === 'id_asc') {
                const idA = parseInt(a.id_osoby) || 0;
                const idB = parseInt(b.id_osoby) || 0;
                return idA - idB;
            }
            if (sortOrder === 'id_desc') {
                const idA = parseInt(a.id_osoby) || 0;
                const idB = parseInt(b.id_osoby) || 0;
                return idB - idA;
            }

            const getSurnameStatus = (person) => {
                if (person.nazwisko && person.nazwisko.trim()) return true;
                if (person.imie && person.imie.includes('(')) return true;
                return false;
            };

            const hasSurnameA = getSurnameStatus(a);
            const hasSurnameB = getSurnameStatus(b);

            if (hasSurnameA && !hasSurnameB) return -1;
            if (!hasSurnameA && hasSurnameB) return 1;

            const firstNameA = (a.imie || '').toLowerCase();
            const firstNameB = (b.imie || '').toLowerCase();
            const surnameA = (a.nazwisko || '').toLowerCase();
            const surnameB = (b.nazwisko || '').toLowerCase();

            if (sortOrder === 'za') {
                const firstNameCompare = firstNameB.localeCompare(firstNameA, 'pl');
                if (firstNameCompare !== 0) return firstNameCompare;
                return surnameB.localeCompare(surnameA, 'pl');
            }

            const firstNameCompare = firstNameA.localeCompare(firstNameB, 'pl');
            if (firstNameCompare !== 0) return firstNameCompare;
            return surnameA.localeCompare(surnameB, 'pl');
        });

        return renderGenealogy(filtered, options);
    }

    window.AdminGenealogyList = Object.freeze({
        load: loadGenealogy,
        render: renderGenealogy,
        filter: filterGenealogy
    });
})();
