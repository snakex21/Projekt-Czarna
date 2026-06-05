/**
 * Mapa endpointów backendu dla panelu admina.
 *
 * Wyekstrahowane z admin.js — to jest jedyne źródło prawdy o URL-ach API
 * używanych przez panel administracyjny. Dzięki temu:
 *  - endpointy są w jednym miejscu i łatwe do zmiany,
 *  - test kontraktowy może czytać tę mapę zamiast regexa po admin.js,
 *  - nowe moduły (auth.js, objects.js, diagnostics.js, historical-points.js, owner-modal.js,
 *    owners.js, demography.js, dashboard.js, genealogy-mini-tree.js,
 *    genealogy-tree.js, genealogy-details.js, genealogy-modal.js, genealogy-list.js) mogą korzystać z tej samej mapy bez
 *    duplikowania URL-i.
 *
 * Kolejność ładowania (admin.html):
 *   1. js/api.js            ← ten plik (najpierw!)
 *   2. js/utils.js
 *   3. js/notifications.js
 *   4. js/auth.js           (P2.5 Etap 12)
 *   5. js/diagnostics.js    (Priorytet 4)
 *   6. js/owner-modal.js    (P2.5 Etap 6)
 *   7. js/objects.js        (P2.5 Etap 2)
 *   8. js/owners.js         (P2.5 Etap 3)
 *   9. js/demography.js     (P2.5 Etap 3)
 *   10. js/dashboard.js      (P2.5 Etap 5)
 *   11. js/genealogy-mini-tree.js (P2.5 Etap 7)
 *   12. js/genealogy-tree.js (P2.5 Etap 13)
 *   13. js/genealogy-details.js (P2.5 Etap 8)
 *   14. js/genealogy-modal.js (P2.5 Etap 9)
 *   15. js/genealogy-list.js (P2.5 Etap 10)
 *   16. admin.js
 *
 * Zmienna globalna `window.AdminAPI` jest wypełniana przed załadowaniem
 * admin.js, więc `const API = window.AdminAPI;` w admin.js działa stabilnie.
 */
(function () {
    'use strict';

    window.AdminAPI = Object.freeze({
        login: '/api/admin/login',
        logout: '/api/admin/logout',
        stats: '/api/admin/dashboard-stats',
        owners: '/api/admin/wlasciciele',
        objects: '/api/admin/obiekty',
        allObjects: '/api/admin/wszystkie-obiekty',
        demography: '/api/admin/demografia',
        genealogy: '/api/admin/genealogia',
        protocols: '/api/admin/protocols',
        diagnostics: '/api/admin/diagnostics',
        backup: '/api/admin/export-backup',
        authStatus: '/api/admin/auth-status'
    });
})();
