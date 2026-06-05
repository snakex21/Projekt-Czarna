/**
 * Moduł obiektów geograficznych (P2.5 Etap 2 - wydzielenie z admin.js).
 *
 * Odpowiada za sekcję "Obiekty" w panelu admina:
 *   - ładowanie listy obiektów z API,
 *   - renderowanie tabeli obiektów ze statusem przypisania do właścicieli,
 *   - filtrowanie po nazwie/kategorii/właścicielu,
 *   - edycja nazwy i kategorii w miejscu (in-place),
 *   - zapis zmian przez PUT,
 *   - usuwanie przez DELETE.
 *
 * Kolejność ładowania (admin.html):
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/notifications.js
 *   4. js/diagnostics.js
 *   5. js/objects.js       ← ten plik
 *   6. kolejne moduły admina
 *   7. admin.js
 *
 * Zależności:
 *   - window.AdminAPI.objects                       — URL endpointu GET/POST/PUT/DELETE
 *   - window.AdminUtils.escapeHtml                  — sanityzacja danych
 *   - window.AdminNotifications.showToast           — komunikaty błędów/sukcesu
 *
 * Publiczne API: `window.AdminObjects = {load, filter, edit, save, remove}`.
 */
(function () {
    'use strict';

    // ---------------------------------------------------------------------
    // Aliasy zależności (pobrane raz przy starcie modułu)
    // ---------------------------------------------------------------------
    const API = window.AdminAPI;
    const { escapeHtml } = window.AdminUtils;
    const { showToast } = window.AdminNotifications;

    // ---------------------------------------------------------------------
    // Stan modułu (prywatny - niedostępny z zewnątrz)
    // ---------------------------------------------------------------------
    let allObjects = [];

    // ---------------------------------------------------------------------
    // Kategorie (prywatne - używane tylko w editObject do rozróżniania
    // edytowalnych opcji: obiekty punktowe ↔ obiekty powierzchniowe)
    // ---------------------------------------------------------------------
    const areaCategories = ['rolna', 'budowlana', 'las', 'pastwisko', 'droga', 'rzeka'];
    const pointCategories = ['budynek', 'kapliczka', 'obiekt_specjalny'];

    // ---------------------------------------------------------------------
    // Renderowanie - pomocnicze
    // ---------------------------------------------------------------------

    /**
     * Renderuje link do protokołu właściciela przypisanego do obiektu.
     * Helper wyciągnięty z renderObjectStatus dla czytelności.
     */
    function renderOwnerLink(owner) {
        const protocol = owner.protocol_number || owner.numer_protokolu || owner.owner_id || owner.unikalny_klucz || owner.id;
        const name = owner.name || owner.nazwa_wlasciciela || owner.owner_id || owner.unikalny_klucz || 'Właściciel';
        const label = `Protokół ${protocol} — ${name}`;
        const url = owner.protocol_url || (owner.owner_id || owner.unikalny_klucz
            ? `../wlasciciele/protokol.html?ownerId=${encodeURIComponent(owner.owner_id || owner.unikalny_klucz)}`
            : '');
        if (!url) {
            return `<span style="color: var(--success-color);">${escapeHtml(label)}</span>`;
        }
        return `<a href="${escapeHtml(url)}" style="color: var(--success-color); text-decoration: underline;" title="Otwórz protokół">${escapeHtml(label)}</a>`;
    }

    /**
     * Renderuje status przypisania obiektu (lista protokołów właścicieli).
     */
    function renderObjectStatus(obj) {
        const assigned = Array.isArray(obj.assigned_owners) ? obj.assigned_owners : [];
        if (!assigned.length) {
            return '<span style="color: var(--text-secondary);">Nieprzypisany</span>';
        }

        if (assigned.length === 1) {
            return renderOwnerLink(assigned[0]);
        }

        return `
            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                <span style="color: var(--success-color); font-weight: 600;">${assigned.length} protokoły</span>
                ${assigned.slice(0, 3).map(renderOwnerLink).join('')}
                ${assigned.length > 3 ? `<span style="color: var(--text-secondary);">+${assigned.length - 3} więcej</span>` : ''}
            </div>
        `;
    }

    // ---------------------------------------------------------------------
    // Publiczne API
    // ---------------------------------------------------------------------

    /**
     * Ładuje listę obiektów z API i renderuje tabelę.
     * Używane przez: switch case 'objects', po edycji, po usunięciu, po anulowaniu.
     */
    async function loadObjects() {
        try {
            const response = await fetch(API.objects);
            allObjects = await response.json();
            renderObjects(allObjects);
        } catch (error) {
            console.error('Błąd ładowania obiektów:', error);
            showToast('error', 'Nie udało się załadować obiektów');
        }
    }

    /**
     * Renderuje tabelę obiektów w tbody#objectsTableBody.
     * Podpina delegację zdarzeń dla przycisków edycji/usuwania.
     */
    function renderObjects(objects) {
        const tbody = document.getElementById('objectsTableBody');
        tbody.innerHTML = '';

        objects.forEach(obj => {
            const row = document.createElement('tr');
            row.dataset.id = obj.id; // Przechowujemy ID obiektu w atrybucie data

            row.innerHTML = `
                <td data-field="nazwa_lub_numer">${escapeHtml(obj.nazwa_lub_numer)}</td>
                <td data-field="kategoria">${escapeHtml(obj.kategoria)}</td>
                <td>${renderObjectStatus(obj)}</td>
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
    }

    /**
     * Filtruje listę obiektów po nazwie, kategorii lub właścicielu.
     * Wywoływane przez input#searchObjects.
     */
    function filterObjects(searchTerm) {
        const term = searchTerm.toLowerCase();
        const filtered = allObjects.filter(obj =>
            String(obj.nazwa_lub_numer || '').toLowerCase().includes(term) ||
            String(obj.kategoria || '').toLowerCase().includes(term) ||
            (Array.isArray(obj.assigned_owners) && obj.assigned_owners.some(owner =>
                String(owner.name || owner.nazwa_wlasciciela || '').toLowerCase().includes(term) ||
                String(owner.protocol_number || owner.numer_protokolu || '').toLowerCase().includes(term)
            ))
        );
        renderObjects(filtered);
    }

    /**
     * Tryb edycji wiersza - zamienia komórki z nazwą i kategorią na input/select.
     * Rozróżnia obiekty punktowe (pointCategories) od powierzchniowych (areaCategories).
     */
    function editObject(row) {
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

        // Zmień przyciski
        const actionsCell = row.querySelector('.actions');
        actionsCell.innerHTML = `
            <button class="btn-success save-btn"><i class="fas fa-save"></i> Zapisz</button>
            <button class="btn-cancel"><i class="fas fa-times"></i> Anuluj</button>
        `;

        actionsCell.querySelector('.save-btn').addEventListener('click', () => saveObject(row));
        actionsCell.querySelector('.btn-cancel').addEventListener('click', () => loadObjects());
    }

    /**
     * Wysyła PUT z nową nazwą i kategorią do API.
     * Po sukcesie lub błędzie - odświeża widok (loadObjects).
     */
    async function saveObject(row) {
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
    }

    /**
     * Usuwa obiekt przez DELETE. Wymaga potwierdzenia użytkownika.
     */
    async function deleteObject(row) {
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
    }

    // ---------------------------------------------------------------------
    // Eksport publicznego API
    // ---------------------------------------------------------------------
    window.AdminObjects = Object.freeze({
        load: loadObjects,
        filter: filterObjects,
        edit: editObject,
        save: saveObject,
        remove: deleteObject,
    });
})();
