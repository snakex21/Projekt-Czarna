/**
 * Moduł właścicieli (P2.5 Etap 3 - wydzielenie z admin.js).
 *
 * Odpowiada za sekcję "Właściciele" w panelu admina:
 *   - ładowanie listy właścicieli z API,
 *   - renderowanie kart właścicieli (nazwa, numer protokołu, dom, klucz),
 *   - filtrowanie po nazwie właściciela lub unikalnym kluczu,
 *   - edycja: pobiera pełne dane właściciela i otwiera modal
 *     przez window.AdminOwnerModal.open,
 *   - usuwanie z potwierdzeniem przez DELETE.
 *
 * Kolejność ładowania (admin.html):
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/notifications.js
 *   4. js/diagnostics.js
 *   5. js/objects.js
 *   6. js/owners.js        ← ten plik
 *   7. kolejne moduły admina
 *   8. admin.js
 *
 * Zależności:
 *   - window.AdminAPI.owners                          — URL endpointu GET/PUT/DELETE
 *   - window.AdminUtils.escapeHtml                    — sanityzacja nazw
 *   - window.AdminNotifications.showToast             — komunikaty błędów/sukcesu
 *
 * Publiczne API: `window.AdminOwners = {load, filter, edit, remove}`.
 *
 * Uwaga: brak metody `save` — zapis właściciela odbywa się przez
 * `window.AdminOwnerModal` (Etap 6).
 */
(function () {
    'use strict';

    // ---------------------------------------------------------------------
    // Aliasy zależności (pobrane raz przy starcie modułu).
    // Wzorzec z obiektów: ciche pobranie, brak throw (test izolacji
    // wykrywa importy innych modułów w AKTYWNYM kodzie, nie w error msg).
    // Wymuszenie kolejności ładowania jest egzekwowane przez admin.js
    // (który rzuca błąd jeśli window.AdminOwners nie istnieje).
    // ---------------------------------------------------------------------
    const API = window.AdminAPI;
    const { escapeHtml } = window.AdminUtils;
    const { showToast } = window.AdminNotifications;

    // ---------------------------------------------------------------------
    // Stan modułu (prywatny - niedostępny z zewnątrz)
    // ---------------------------------------------------------------------
    let allOwners = [];

    // ---------------------------------------------------------------------
    // Renderowanie - pomocnicze (prywatne)
    // ---------------------------------------------------------------------

    /**
     * Renderuje karty właścicieli w kontenerze #ownersList.
     * Każda karta zawiera: nagłówek (nazwa + numer protokołu), dane (dom, klucz),
     * akcje (edytuj, usuń).
     */
    function renderOwners(owners) {
        const container = document.getElementById('ownersList');
        if (!container) {
            console.error('Brak elementu #ownersList w DOM');
            return;
        }
        container.innerHTML = '';

        owners.forEach(owner => {
            const card = document.createElement('div');
            card.className = 'owner-card';
            card.dataset.id = owner.id; // Przechowujemy ID właściciela w atrybucie data
            card.innerHTML = `
                <div class="owner-card-header">
                    <div class="owner-name">${escapeHtml(owner.nazwa_wlasciciela)}</div>
                    <div class="owner-protocol">Lp. ${escapeHtml(String(owner.numer_protokolu || 'N/A'))}</div>
                </div>
                <div class="owner-details">
                    <div>Dom: ${escapeHtml(String(owner.numer_domu || '-'))}</div>
                    <div>Klucz: ${escapeHtml(owner.unikalny_klucz)}</div>
                </div>
                <div class="owner-actions">
                    <button class="edit-btn"><i class="fas fa-edit"></i> Edytuj</button>
                    <button class="delete-btn"><i class="fas fa-trash"></i> Usuń</button>
                </div>
            `;
            // Delegacja zdarzeń (zamiast inline onclick - czystsze i bezpieczniejsze)
            card.querySelector('.edit-btn').addEventListener('click', () => editOwner(owner.id));
            card.querySelector('.delete-btn').addEventListener('click', () => deleteOwner(owner.id));
            container.appendChild(card);
        });
    }

    // ---------------------------------------------------------------------
    // Publiczne API
    // ---------------------------------------------------------------------

    /**
     * Ładuje listę właścicieli z API i renderuje karty.
     * Używane przez: switch case 'owners', po edycji, po usunięciu.
     */
    async function loadOwners() {
        try {
            const response = await fetch(API.owners);
            allOwners = await response.json();
            renderOwners(allOwners);
        } catch (error) {
            console.error('Błąd ładowania właścicieli:', error);
            showToast('error', 'Nie udało się załadować właścicieli');
        }
    }

    /**
     * Filtruje listę właścicieli po nazwie lub unikalnym kluczu.
     * Wywoływane przez input#searchOwners.
     */
    function filterOwners(searchTerm) {
        const term = String(searchTerm || '').toLowerCase();
        const filtered = allOwners.filter(owner =>
            String(owner.nazwa_wlasciciela || '').toLowerCase().includes(term) ||
            String(owner.unikalny_klucz || '').toLowerCase().includes(term)
        );
        renderOwners(filtered);
    }

    /**
     * Pobiera pełne dane właściciela z API i otwiera modal edycji
     * (openOwnerModal pozostaje w admin.js - wymaga dostępu do `elements`
     * i innych modułów specyficznych dla modala).
     */
    async function editOwner(id) {
        try {
            const owner = allOwners.find(o => o.id === id);
            if (!owner) {
                throw new Error(`Nie znaleziono właściciela o ID ${id}`);
            }
            const response = await fetch(`${API.owners}/${id}`);
            const fullData = await response.json();
            // Wywołujemy moduł modala właściciela (P2.5 Etap 6)
            if (window.AdminOwnerModal && typeof window.AdminOwnerModal.open === 'function') {
                window.AdminOwnerModal.open(fullData);
            } else {
                throw new Error('Brak modułu AdminOwnerModal.open');
            }
        } catch (error) {
            console.error('Błąd edycji właściciela:', error);
            showToast('error', 'Nie udało się otworzyć edycji właściciela');
        }
    }

    /**
     * Usuwa właściciela przez DELETE. Wymaga potwierdzenia użytkownika.
     */
    async function deleteOwner(id) {
        if (!confirm('Czy na pewno chcesz usunąć tego właściciela?')) {
            return;
        }
        try {
            const response = await fetch(`${API.owners}/${id}`, { method: 'DELETE' });
            if (response.ok) {
                showToast('success', 'Właściciel został usunięty');
                loadOwners(); // Odśwież widok
            } else {
                throw new Error('Błąd usuwania na serwerze');
            }
        } catch (error) {
            console.error('Błąd usuwania właściciela:', error);
            showToast('error', 'Nie udało się usunąć właściciela');
        }
    }

    // ---------------------------------------------------------------------
    // Eksport publicznego API
    // ---------------------------------------------------------------------
    window.AdminOwners = Object.freeze({
        load: loadOwners,
        filter: filterOwners,
        edit: editOwner,
        remove: deleteOwner,
    });
})();
