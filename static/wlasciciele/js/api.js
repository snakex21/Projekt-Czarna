/**
 * Publiczna mapa URL-i dla stron właścicieli/protokołów (P2.7 Etap 1).
 *
 * Kolejność ładowania:
 *   1. js/api.js       ← ten plik
 *   2. protokol.js / compare.js / stats-script.js
 *
 * Dostęp przez `window.OwnersAPI`.
 */
(function () {
    'use strict';

    function encodeOwnerKey(ownerKey) {
        return encodeURIComponent(ownerKey);
    }

    function owner(ownerKey) {
        return `/api/wlasciciel/${encodeOwnerKey(ownerKey)}`;
    }

    function genealogy(ownerKey) {
        return `/api/genealogia/${encodeOwnerKey(ownerKey)}`;
    }

    function stats() {
        return '/api/stats';
    }

    function protocolScan(ownerKey, page) {
        return `/protokoly/${encodeOwnerKey(ownerKey)}/${page}.jpg`;
    }

    function protocolScanSingle(ownerKey) {
        return `/protokoly/${encodeOwnerKey(ownerKey)}.jpg`;
    }

    function mapPage() {
        return '../mapa/mapa.html';
    }

    window.OwnersAPI = Object.freeze({
        owner: owner,
        genealogy: genealogy,
        stats: stats,
        protocolScan: protocolScan,
        protocolScanSingle: protocolScanSingle,
        mapPage: mapPage,
    });
})();
