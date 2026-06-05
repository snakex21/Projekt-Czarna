/**
 * Modal właściciela (P2.5 Etap 6 - wydzielenie z admin.js).
 *
 * Odpowiada za formularz dodawania/edycji właściciela oraz edytor działek.
 * Lista/karty właścicieli zostają w `owners.js`.
 *
 * Publiczne API: `window.AdminOwnerModal = {open, save, populate}`.
 */
(function () {
    'use strict';

    const API = window.AdminAPI;
    const { showToast } = window.AdminNotifications;

    function _elements() {
        return {
            modalTitle: document.getElementById('modalTitle'),
            modalBody: document.getElementById('modalBody'),
            modalSave: document.getElementById('modalSave'),
            modalOverlay: document.getElementById('modalOverlay'),
        };
    }

    function _closeModal() {
        const { modalOverlay, modalBody } = _elements();
        if (modalOverlay) modalOverlay.classList.add('hidden');
        if (modalBody) modalBody.innerHTML = '';
    }

    function _formatDateForInput(dateString) {
        if (!dateString) return '';
        try {
            return new Date(dateString).toISOString().split('T')[0];
        } catch (e) {
            return '';
        }
    }

    function _formatTextForTextarea(text) {
        return text ? String(text).replace(/\\n/g, "\n") : "";
    }

    function openOwnerModal(owner = null) {
        const { modalTitle, modalBody, modalSave, modalOverlay } = _elements();
        if (!modalTitle || !modalBody || !modalSave || !modalOverlay) return;

        modalTitle.textContent = owner ? 'Edytuj Właściciela' : 'Dodaj Właściciela';

        modalBody.innerHTML = `
            <form id="ownerForm">
                <div class="form-grid">
                    <div class="form-group"><label>Unikalny klucz</label><input type="text" name="unikalny_klucz" value="${owner?.unikalny_klucz || ''}" required></div>
                    <div class="form-group"><label>Nazwisko i imię</label><input type="text" name="nazwa_wlasciciela" value="${owner?.nazwa_wlasciciela || ''}" required></div>
                    <div class="form-group"><label>Numer protokołu</label><input type="text" name="numer_protokolu" value="${owner?.numer_protokolu || ''}"></div>
                    <div class="form-group"><label>Numer domu</label><input type="text" name="numer_domu" value="${owner?.numer_domu || ''}"></div>
                    <div class="form-group">
                        <label>Data protokołu</label>
                        <input type="date" name="data_protokolu" value="${_formatDateForInput(owner?.data_protokolu)}">
                    </div>
                    <div class="form-group"><label>Miejsce protokołu</label><input type="text" name="miejsce_protokolu" value="${owner?.miejsce_protokolu || ''}"></div>
                </div>

                <div class="parcel-editor" id="parcelEditorContainer">
                    <!-- Treść edytora działek zostanie wstawiona dynamicznie -->
                </div>

                <div class="form-group"><label>Genealogia</label><textarea name="genealogia">${_formatTextForTextarea(owner?.genealogia)}</textarea></div>
                <div class="form-group"><label>Historia własności</label><textarea name="historia_wlasnosci">${_formatTextForTextarea(owner?.historia_wlasnosci)}</textarea></div>
                <div class="form-group"><label>Ciąg dalszy / Uwagi</label><textarea name="uwagi">${_formatTextForTextarea(owner?.uwagi)}</textarea></div>
                <div class="form-group"><label>Współwłasność / Służebność</label><textarea name="wspolwlasnosc">${_formatTextForTextarea(owner?.wspolwlasnosc)}</textarea></div>
                <div class="form-group"><label>Powiązania i transakcje</label><textarea name="powiazania_i_transakcje">${_formatTextForTextarea(owner?.powiazania_i_transakcje)}</textarea></div>
                <div class="form-group"><label>Interpretacja i wnioski</label><textarea name="interpretacja_i_wnioski">${_formatTextForTextarea(owner?.interpretacja_i_wnioski)}</textarea></div>
            </form>
        `;

        populateAndSetupParcelEditor(owner);

        modalSave.style.display = '';
        modalSave.onclick = () => saveOwner(owner?.id);
        modalOverlay.classList.remove('hidden');
    }

    async function populateAndSetupParcelEditor(owner) {
        const container = document.getElementById('parcelEditorContainer');
        if (!container) return;

        const allObjectsResponse = await fetch(API.allObjects);
        const allParcels = await allObjectsResponse.json();

        const ownerParcels = owner?.dzialki_wszystkie || [];
        const realPlotIds = new Set(ownerParcels.filter(p => p.typ_posiadania === 'własność rzeczywista').map(p => p.id));
        const protocolPlotIds = new Set(ownerParcels.filter(p => p.typ_posiadania !== 'własność rzeczywista').map(p => p.id));

        function createOptions(assignedIds) {
            let assignedHTML = '';
            let availableHTML = '';
            const excludedCategories = ['budynek', 'kapliczka', 'obiekt_specjalny'];

            allParcels.forEach(p => {
                if (excludedCategories.includes(p.kategoria)) return;
                const option = `<option value="${p.id}">${p.nazwa_lub_numer} (${p.kategoria})</option>`;
                if (assignedIds.has(p.id)) {
                    assignedHTML += option;
                } else {
                    availableHTML += option;
                }
            });
            return { assignedHTML, availableHTML };
        }

        const realOptions = createOptions(realPlotIds);
        const protocolOptions = createOptions(protocolPlotIds);

        container.innerHTML = `
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

        container.querySelectorAll('.parcel-buttons button').forEach(btn => {
            btn.addEventListener('click', () => {
                const type = btn.dataset.type;
                const action = btn.dataset.action;
                const source = document.getElementById(action === 'add' ? `available-${type}` : `assigned-${type}`);
                const dest = document.getElementById(action === 'add' ? `assigned-${type}` : `available-${type}`);

                Array.from(source.selectedOptions).forEach(opt => dest.appendChild(opt));
            });
        });
    }

    async function saveOwner(id) {
        const form = document.getElementById('ownerForm');
        const formData = new FormData(form);
        const data = Object.fromEntries(formData);

        data.dzialki_rzeczywiste_ids = Array.from(document.getElementById('assigned-real').options).map(o => o.value);
        data.dzialki_protokol_ids = Array.from(document.getElementById('assigned-protocol').options).map(o => o.value);

        try {
            const url = id ? `${API.owners}/${id}` : API.owners;
            const method = id ? 'PUT' : 'POST';

            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (response.ok) {
                showToast('success', 'Właściciel został zapisany');
                _closeModal();
                window.AdminOwners.load();
                window.AdminDashboard.load();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Błąd zapisu');
            }
        } catch (error) {
            showToast('error', `Nie udało się zapisać właściciela: ${error.message}`);
        }
    }

    window.AdminOwnerModal = Object.freeze({
        open: openOwnerModal,
        save: saveOwner,
        populate: populateAndSetupParcelEditor,
    });
})();
