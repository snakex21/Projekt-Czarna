/**
 * Moduł pulpitu admina (P2.5 Etap 5 - wydzielenie z admin.js).
 *
 * Odpowiada za:
 *   - statystyki pulpitu,
 *   - zegar/data w nagłówku,
 *   - pobieranie backupu,
 *   - szybkie akcje z kart pulpitu,
 *   - modal informacji o systemie.
 *
 * Publiczne API: `window.AdminDashboard = {load, tick, startClock, downloadBackup, handleQuickAction}`.
 */
(function () {
    'use strict';

    const API = window.AdminAPI;
    const { showToast } = window.AdminNotifications;

    async function loadDashboardData() {
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
    }

    function updateDateTime() {
        const now = new Date();
        const currentDate = document.getElementById('currentDate');
        const currentTime = document.getElementById('currentTime');
        if (!currentDate || !currentTime) return;

        const options = {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        };
        currentDate.textContent = now.toLocaleDateString('pl-PL', options);

        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        currentTime.textContent = `${hours}:${minutes}:${seconds}`;
    }

    function startClock() {
        updateDateTime();
        setInterval(updateDateTime, 1000);
    }

    function downloadBackup() {
        window.location.href = API.backup;
        showToast('info', 'Rozpoczęto pobieranie backupu');
    }

    function showSystemInfo() {
        const modalTitle = document.getElementById('modalTitle');
        const modalBody = document.getElementById('modalBody');
        const modalSave = document.getElementById('modalSave');
        const modalOverlay = document.getElementById('modalOverlay');
        if (!modalTitle || !modalBody || !modalSave || !modalOverlay) return;

        modalTitle.textContent = 'Informacje o Systemie';
        modalBody.innerHTML = `
            <div style="padding: 1rem;">
                <h3>System Zarządzania Mapą Katastralną</h3>
                <p><strong>Wersja:</strong> 2.0</p>
                <p><strong>Autor:</strong> Maksymilian Augustyn</p>
                <p><strong>Technologie:</strong> HTML5, CSS3, JavaScript, FastAPI</p>
                <p><strong>Status:</strong> Aktywny</p>
            </div>
        `;
        modalSave.style.display = 'none';
        modalOverlay.classList.remove('hidden');
    }

    function handleQuickAction(action, callbacks = {}) {
        switch (action) {
            case 'add-owner':
                if (callbacks.switchSection) callbacks.switchSection('owners');
                if (window.AdminOwnerModal && typeof window.AdminOwnerModal.open === 'function') {
                    window.AdminOwnerModal.open();
                }
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
    }

    window.AdminDashboard = Object.freeze({
        load: loadDashboardData,
        tick: updateDateTime,
        startClock: startClock,
        downloadBackup: downloadBackup,
        handleQuickAction: handleQuickAction,
    });
})();
