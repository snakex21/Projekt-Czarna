/**
 * Moduł demografii (P2.5 Etap 3 - wydzielenie z admin.js).
 *
 * Odpowiada za sekcję "Demografia" w panelu admina:
 *   - ładowanie wpisów demograficznych z API (rok, populacja, katolicy, żydzi, inni, opis),
 *   - renderowanie tabeli z edycją inline (inputy w każdej komórce),
 *   - dodawanie nowego wpisu przez modal,
 *   - zapis nowego wpisu (POST) oraz edycji istniejącego (PUT inline),
 *   - usuwanie wpisu (DELETE z potwierdzeniem).
 *
 * Kolejność ładowania (admin.html):
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/notifications.js
 *   4. js/diagnostics.js
 *   5. js/objects.js
 *   6. js/owners.js
 *   7. js/demography.js     ← ten plik
 *   8. kolejne moduły admina
 *   9. admin.js
 *
 * Zależności:
 *   - window.AdminAPI.demography                       — URL endpointu GET/POST/PUT/DELETE
 *   - window.AdminUtils.escapeHtml                     — sanityzacja opisów
 *   - window.AdminNotifications.showToast              — komunikaty błędów/sukcesu
 *
 * Publiczne API: `window.AdminDemography = {load, add, save, remove}`.
 */
(function () {
    'use strict';

    // ---------------------------------------------------------------------
    // Aliasy zależności (pobrane raz przy starcie modułu).
    // Wzorzec z obiektów: ciche pobranie, brak throw (test izolacji wykrywa
    // importy w AKTYWNYM kodzie, nie w error msg). Wymuszenie kolejności
    // ładowania jest egzekwowane przez admin.js.
    // ---------------------------------------------------------------------
    const API = window.AdminAPI;
    const { escapeHtml } = window.AdminUtils;
    const { showToast } = window.AdminNotifications;

    // ---------------------------------------------------------------------
    // Elementy DOM (pobrane z dokumentu; moduł samodzielny)
    // ---------------------------------------------------------------------
    function _getModalElements() {
        return {
            overlay: document.getElementById('modalOverlay'),
            title: document.getElementById('modalTitle'),
            body: document.getElementById('modalBody'),
            save: document.getElementById('modalSave'),
        };
    }

    // ---------------------------------------------------------------------
    // Stan modułu (prywatny - niedostępny z zewnątrz)
    // ---------------------------------------------------------------------
    let allDemography = [];

    // ---------------------------------------------------------------------
    // Renderowanie - pomocnicze (prywatne)
    // ---------------------------------------------------------------------

    /**
     * Renderuje tabelę wpisów demograficznych w tbody#demographyTableBody.
     * Każdy wiersz to formularz inline: inputy dla pól numerycznych
     * (rok, populacja, katolicy, żydzi, inni) i textarea dla opisu.
     * Delegacja zdarzeń dla przycisków Zapisz/Usuń.
     */
    function renderDemography(data) {
        const tbody = document.getElementById('demographyTableBody');
        if (!tbody) {
            console.error('Brak elementu #demographyTableBody w DOM');
            return;
        }
        tbody.innerHTML = '';

        data.forEach(entry => {
            const row = document.createElement('tr');
            row.dataset.id = entry.id;
            row.innerHTML = `
                <td><input type="number" value="${escapeHtml(String(entry.rok))}" data-field="rok"></td>
                <td><input type="number" value="${entry.populacja_ogolem ?? ''}" data-field="populacja_ogolem"></td>
                <td><input type="number" value="${entry.katolicy ?? ''}" data-field="katolicy"></td>
                <td><input type="number" value="${entry.zydzi ?? ''}" data-field="zydzi"></td>
                <td><input type="number" value="${entry.inni ?? ''}" data-field="inni"></td>
                <td><textarea data-field="opis">${escapeHtml(String(entry.opis || ''))}</textarea></td>
                <td class="actions">
                    <button class="btn-success save-btn">Zapisz</button>
                    <button class="delete-btn">Usuń</button>
                </td>
            `;
            // Delegacja zdarzeń (zamiast inline onclick - czystsze)
            row.querySelector('.save-btn').addEventListener('click', (e) => saveDemography(entry.id, e));
            row.querySelector('.delete-btn').addEventListener('click', () => deleteDemography(entry.id));
            tbody.appendChild(row);
        });
    }

    // ---------------------------------------------------------------------
    // Publiczne API
    // ---------------------------------------------------------------------

    /**
     * Ładuje wpisy demograficzne z API i renderuje tabelę.
     * Używane przez: switch case 'demography', po dodaniu, po usunięciu.
     */
    async function loadDemography() {
        try {
            const response = await fetch(API.demography);
            allDemography = await response.json();
            renderDemography(allDemography);
        } catch (error) {
            console.error('Błąd ładowania demografii:', error);
            showToast('error', 'Nie udało się załadować danych demograficznych');
        }
    }

    /**
     * Otwiera modal z formularzem nowego wpisu demograficznego.
     * Po kliknięciu "Zapisz" w modalu - wywołuje saveDemographyEntry.
     */
    function openDemographyModal() {
        const elements = _getModalElements();
        if (!elements.overlay || !elements.title || !elements.body || !elements.save) {
            console.error('Brak elementów modala w DOM');
            return;
        }
        elements.title.textContent = 'Dodaj Wpis Demograficzny';

        elements.body.innerHTML = `
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

        elements.save.onclick = saveDemographyEntry;
        elements.overlay.classList.remove('hidden');
    }

    /**
     * Zapisuje nowy wpis demograficzny (POST) z formularza w modalu.
     * Po sukcesie - zamyka modal i odświeża listę.
     */
    async function saveDemographyEntry() {
        const form = document.getElementById('demographyForm');
        if (!form) {
            showToast('error', 'Brak formularza demografii w modalu');
            return;
        }
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        try {
            const response = await fetch(API.demography, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (response.ok) {
                showToast('success', 'Wpis demograficzny został dodany');
                const elements = _getModalElements();
                if (elements.overlay) elements.overlay.classList.add('hidden');
                loadDemography();
            } else {
                throw new Error('Błąd zapisu');
            }
        } catch (error) {
            console.error('Błąd zapisu wpisu demograficznego:', error);
            showToast('error', 'Nie udało się dodać wpisu');
        }
    }

    /**
     * Zapisuje edycję inline istniejącego wpisu (PUT).
     * Wywoływane przez przycisk "Zapisz" w wierszu tabeli.
     */
    async function saveDemography(id, event) {
        const row = event.target.closest('tr');
        if (!row) return;
        const inputs = row.querySelectorAll('input, textarea');
        const data = {};

        inputs.forEach(input => {
            data[input.dataset.field] = input.value || null;
        });

        try {
            const response = await fetch(`${API.demography}/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (response.ok) {
                showToast('success', 'Wpis został zapisany');
            } else {
                throw new Error('Błąd zapisu na serwerze');
            }
        } catch (error) {
            console.error('Błąd zapisu wpisu demograficznego:', error);
            showToast('error', 'Nie udało się zapisać wpisu');
        }
    }

    /**
     * Usuwa wpis demograficzny przez DELETE. Wymaga potwierdzenia użytkownika.
     */
    async function deleteDemography(id) {
        if (!confirm('Czy na pewno chcesz usunąć ten wpis?')) {
            return;
        }
        try {
            const response = await fetch(`${API.demography}/${id}`, { method: 'DELETE' });
            if (response.ok) {
                showToast('success', 'Wpis został usunięty');
                loadDemography();
            } else {
                throw new Error('Błąd usuwania na serwerze');
            }
        } catch (error) {
            console.error('Błąd usuwania wpisu demograficznego:', error);
            showToast('error', 'Nie udało się usunąć wpisu');
        }
    }

    // ---------------------------------------------------------------------
    // Eksport publicznego API
    // ---------------------------------------------------------------------
    window.AdminDemography = Object.freeze({
        load: loadDemography,
        add: openDemographyModal,
        save: saveDemography,
        remove: deleteDemography,
    });
})();
