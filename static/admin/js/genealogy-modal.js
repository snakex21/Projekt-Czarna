(function () {
    'use strict';

    const API = window.AdminAPI;
    const { showToast } = window.AdminNotifications;

    function _elements() {
        return {
            modalTitle: document.getElementById('modalTitle'),
            modalBody: document.getElementById('modalBody'),
            modalSave: document.getElementById('modalSave'),
            modalOverlay: document.getElementById('modalOverlay')
        };
    }

    function _closeModal() {
        const elements = _elements();
        elements.modalOverlay.classList.add('hidden');
        elements.modalBody.innerHTML = '';
    }

    function _findPersonByAnyId(people, id) {
        return people.find(person => person.id_osoby == id || person.db_id == id);
    }

    function _setupProtocolAutocomplete(person, allProtocols) {
        const protocolInput = document.getElementById('protocolAutocomplete');
        const protocolIdInput = document.getElementById('protocolIdInput');
        const suggestionsBox = document.getElementById('protocolSuggestions');

        document.addEventListener('click', (event) => {
            if (!protocolInput.contains(event.target) && !suggestionsBox.contains(event.target)) {
                suggestionsBox.classList.add('hidden');
            }
        });

        protocolInput.addEventListener('input', () => {
            const query = protocolInput.value.toLowerCase();
            suggestionsBox.innerHTML = '';

            if (query.length < 1) {
                suggestionsBox.classList.add('hidden');
                if (query === '') protocolIdInput.value = '';
                return;
            }

            const matches = allProtocols.filter(protocol => {
                const nameMatch = protocol.name && protocol.name.toLowerCase().includes(query);
                const numMatch = String(protocol.ordernumber || protocol.orderNumber || '').includes(query);
                return nameMatch || numMatch;
            });

            matches.sort((a, b) => {
                const aNum = String(a.ordernumber || a.orderNumber || '');
                const bNum = String(b.ordernumber || b.orderNumber || '');
                const aName = (a.name || '').toLowerCase();
                const bName = (b.name || '').toLowerCase();

                const getScore = (num, name) => {
                    if (num === query) return 0;
                    if (num.startsWith(query)) return 1;
                    if (name === query) return 2;
                    if (name.startsWith(query)) return 3;
                    return 4;
                };

                const scoreA = getScore(aNum, aName);
                const scoreB = getScore(bNum, bName);

                if (scoreA !== scoreB) return scoreA - scoreB;
                return parseInt(aNum || 0) - parseInt(bNum || 0);
            });

            if (matches.length > 0) {
                matches.forEach(protocol => {
                    const div = document.createElement('div');
                    div.className = 'autocomplete-suggestion';
                    const displayNum = protocol.ordernumber || protocol.orderNumber || '?';
                    div.innerHTML = `<strong>${protocol.name}</strong> (Lp. ${displayNum})`;
                    div.onclick = () => {
                        protocolInput.value = `${protocol.name} (Lp. ${displayNum})`;
                        protocolIdInput.value = protocol.key;
                        suggestionsBox.classList.add('hidden');
                    };
                    suggestionsBox.appendChild(div);
                });
                suggestionsBox.classList.remove('hidden');
            } else {
                suggestionsBox.classList.add('hidden');
            }
        });

        if (person && person.protokol_klucz) {
            const existing = allProtocols.find(protocol => protocol.key == person.protokol_klucz);
            if (existing) {
                const displayNum = existing.ordernumber || existing.orderNumber || '?';
                protocolInput.value = `${existing.name} (Lp. ${displayNum})`;
                protocolIdInput.value = existing.key;
            } else {
                protocolIdInput.value = person.protokol_klucz;
                protocolInput.value = `Protokół nr ${person.protokol_klucz}`;
            }
        }
    }

    function setupPersonAutocomplete(input, idInput, suggestions, allGenealogy, genderFilter = null) {
        document.addEventListener('click', (event) => {
            if (!input.contains(event.target) && !suggestions.contains(event.target)) {
                suggestions.classList.add('hidden');
            }
        });

        input.addEventListener('input', () => {
            const query = input.value.toLowerCase().trim();
            suggestions.innerHTML = '';

            if (query.length < 1) {
                suggestions.classList.add('hidden');
                if (query === '') idInput.value = '';
                return;
            }

            let matches = allGenealogy.filter(person => {
                const fullName = `${person.imie || ''} ${person.nazwisko || ''}`.toLowerCase();
                const idMatch = String(person.id_osoby).includes(query);
                return fullName.includes(query) || idMatch;
            });

            if (genderFilter) {
                matches = matches.filter(person => person.plec === genderFilter);
            }

            matches.sort((a, b) => {
                const aName = `${a.imie || ''} ${a.nazwisko || ''}`.toLowerCase();
                const bName = `${b.imie || ''} ${b.nazwisko || ''}`.toLowerCase();

                const getScore = (name) => {
                    if (name === query) return 0;
                    if (name.startsWith(query)) return 1;
                    return 2;
                };

                return getScore(aName) - getScore(bName) || aName.localeCompare(bName);
            });

            matches = matches.slice(0, 15);

            if (matches.length > 0) {
                matches.forEach(person => {
                    const div = document.createElement('div');
                    div.className = 'autocomplete-suggestion';
                    const lifespan = person.rok_urodzenia ? `${person.rok_urodzenia}-${person.rok_smierci || '?'}` : '';
                    div.innerHTML = `<strong>${person.imie} ${person.nazwisko || ''}</strong> <span style="color: #64748b;">(ID: ${person.id_osoby}${lifespan ? `, ${lifespan}` : ''})</span>`;
                    div.onclick = () => {
                        input.value = `${person.imie} ${person.nazwisko || ''} (ID: ${person.id_osoby})`;
                        idInput.value = person.id_osoby;
                        suggestions.classList.add('hidden');
                    };
                    suggestions.appendChild(div);
                });
                suggestions.classList.remove('hidden');
            } else {
                suggestions.classList.add('hidden');
            }
        });

        input.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                suggestions.classList.add('hidden');
            } else if (event.key === 'Backspace' && input.value === '') {
                idInput.value = '';
            }
        });
    }

    function addSpouseRow(spousesContainer, allGenealogy, spouseId = '', year = '') {
        const uniqueId = 'spouse_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
        const row = document.createElement('div');
        row.className = 'spouse-row';
        row.style.display = 'flex';
        row.style.gap = '10px';
        row.style.alignItems = 'flex-start';
        row.style.marginBottom = '10px';

        row.innerHTML = `
            <div style="flex: 2; position: relative;">
                <input type="hidden" class="spouse-id" id="${uniqueId}_id">
                <input type="text" class="spouse-autocomplete" id="${uniqueId}_input" placeholder="Szukaj małżonka (imię lub ID)..." autocomplete="off" style="width: 100%;">
                <div class="autocomplete-suggestions hidden" id="${uniqueId}_suggestions"></div>
            </div>
            <input type="number" class="spouse-year" placeholder="Rok" value="${year}" style="flex: 1;">
            <button type="button" class="btn-remove" onclick="this.closest('.spouse-row').remove()">×</button>
        `;

        spousesContainer.appendChild(row);

        const spouseInput = document.getElementById(`${uniqueId}_input`);
        const spouseIdField = document.getElementById(`${uniqueId}_id`);
        const spouseSuggestions = document.getElementById(`${uniqueId}_suggestions`);

        setupPersonAutocomplete(spouseInput, spouseIdField, spouseSuggestions, allGenealogy, null);

        if (spouseId) {
            const spouse = _findPersonByAnyId(allGenealogy, spouseId);
            if (spouse) {
                spouseInput.value = `${spouse.imie} ${spouse.nazwisko || ''} (ID: ${spouse.id_osoby})`;
                spouseIdField.value = spouse.id_osoby;
            }
        }
    }

    function openGenealogyModal(person = null, options = {}) {
        const allGenealogy = Array.isArray(options.allGenealogy) ? options.allGenealogy : [];
        const allProtocols = Array.isArray(options.allProtocols) ? options.allProtocols : [];
        const elements = _elements();

        elements.modalTitle.textContent = person ? 'Edytuj Osobę' : 'Dodaj Osobę';
        elements.modalSave.style.display = '';

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
                        <div style="position: relative;">
                            <input type="hidden" name="id_ojca" id="fatherIdInput">
                            <input type="text" id="fatherAutocomplete" placeholder="Szukaj ojca (imię lub ID)..." autocomplete="off" style="width: 100%;">
                            <div id="fatherSuggestions" class="autocomplete-suggestions hidden"></div>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Matka</label>
                        <div style="position: relative;">
                            <input type="hidden" name="id_matki" id="motherIdInput">
                            <input type="text" id="motherAutocomplete" placeholder="Szukaj matki (imię lub ID)..." autocomplete="off" style="width: 100%;">
                            <div id="motherSuggestions" class="autocomplete-suggestions hidden"></div>
                        </div>
                    </div>
                    <div class="form-group" style="grid-column: 1 / -1;">
                        <label>Małżeństwa (Małżonek + Rok)</label>
                        <div id="spousesContainer"></div>
                        <button type="button" class="btn-add-spouse" id="addSpouseBtn">+ Dodaj małżonka</button>
                    </div>
                    <div class="form-group">
                        <label>Protokół</label>
                        <div style="position: relative;">
                            <input type="hidden" name="protokol_klucz" id="protocolIdInput">
                            <input type="text" id="protocolAutocomplete" placeholder="Wybierz protokół (nazwa lub Lp.)..." autocomplete="off" style="width: 100%;">
                            <div id="protocolSuggestions" class="autocomplete-suggestions hidden"></div>
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <label>Uwagi</label>
                    <textarea name="uwagi">${person?.uwagi || ''}</textarea>
                </div>
            </form>
        `;

        _setupProtocolAutocomplete(person, allProtocols);

        const fatherInput = document.getElementById('fatherAutocomplete');
        const fatherIdInput = document.getElementById('fatherIdInput');
        const fatherSuggestions = document.getElementById('fatherSuggestions');
        setupPersonAutocomplete(fatherInput, fatherIdInput, fatherSuggestions, allGenealogy, 'M');

        const motherInput = document.getElementById('motherAutocomplete');
        const motherIdInput = document.getElementById('motherIdInput');
        const motherSuggestions = document.getElementById('motherSuggestions');
        setupPersonAutocomplete(motherInput, motherIdInput, motherSuggestions, allGenealogy, 'F');

        if (person && person.id_ojca) {
            const father = _findPersonByAnyId(allGenealogy, person.id_ojca);
            if (father) {
                fatherInput.value = `${father.imie} ${father.nazwisko || ''} (ID: ${father.id_osoby})`;
                fatherIdInput.value = father.id_osoby;
            }
        }
        if (person && person.id_matki) {
            const mother = _findPersonByAnyId(allGenealogy, person.id_matki);
            if (mother) {
                motherInput.value = `${mother.imie} ${mother.nazwisko || ''} (ID: ${mother.id_osoby})`;
                motherIdInput.value = mother.id_osoby;
            }
        }

        const spousesContainer = document.getElementById('spousesContainer');
        document.getElementById('addSpouseBtn').onclick = () => addSpouseRow(spousesContainer, allGenealogy);

        if (person) {
            if (person.marriages && person.marriages.length > 0) {
                person.marriages.forEach(marriage => addSpouseRow(spousesContainer, allGenealogy, marriage.spouseId, marriage.date));
            } else if (person.id_malzonka) {
                const spouse = allGenealogy.find(candidate => candidate.db_id === person.id_malzonka) ||
                    allGenealogy.find(candidate => candidate.id_osoby == person.id_malzonka);
                if (spouse) addSpouseRow(spousesContainer, allGenealogy, spouse.id_osoby, '');
            }
        }

        elements.modalSave.onclick = () => saveGenealogy(person?.db_id, options);
        elements.modalOverlay.classList.remove('hidden');
    }

    async function saveGenealogy(id = null, options = {}) {
        const onSaved = options.onSaved || function () { };
        const form = document.getElementById('genealogyForm');

        if (!form.reportValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        const marriageRows = document.querySelectorAll('.spouse-row');
        const marriages = [];
        let hasError = false;

        marriageRows.forEach(row => {
            const autocomplete = row.querySelector('.spouse-autocomplete');
            if (autocomplete) autocomplete.style.borderColor = '';
        });

        for (const row of marriageRows) {
            const hiddenInput = row.querySelector('.spouse-id');
            const autocomplete = row.querySelector('.spouse-autocomplete');
            const sid = hiddenInput ? hiddenInput.value : '';
            const year = row.querySelector('.spouse-year').value;

            if (!sid) {
                if (autocomplete) autocomplete.style.borderColor = 'red';
                hasError = true;
            } else {
                marriages.push({
                    spouse_json_id: sid,
                    year: year ? parseInt(year, 10) : null
                });
            }
        }

        if (hasError) {
            showToast('error', 'Wybierz małżonka w dodanym wierszu lub usuń pusty wiersz.');
            return;
        }

        data.marriages = marriages;

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
                const responseData = await response.json();
                showToast('success', 'Osoba została zapisana');
                _closeModal();

                try {
                    await onSaved(responseData);
                } catch (viewError) {
                    console.error('Błąd podczas odświeżania widoku po zapisie:', viewError);
                    showToast('warning', 'Osoba zapisana, ale wystąpił błąd odświeżania widoku.');
                }
            } else {
                try {
                    const errData = await response.json();
                    throw new Error(errData.message || 'Błąd zapisu');
                } catch (error) {
                    throw new Error('Błąd zapisu (nieznana odpowiedź serwera)');
                }
            }
        } catch (error) {
            console.error('Błąd zapisu:', error);
            showToast('error', error.message || 'Nie udało się zapisać osoby');
        }
    }

    window.AdminGenealogyModal = Object.freeze({
        open: openGenealogyModal,
        save: saveGenealogy
    });
})();
