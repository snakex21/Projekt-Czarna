/** Czyste helpery danych i HTML dla mapy. */
(function () {
    'use strict';

    function parseMaybeJson(v) {
        if (typeof v !== 'string') return v;
        try { return JSON.parse(v); } catch { return v; }
    }

    function uniqueOwners(arr) {
        if (!Array.isArray(arr)) return [];
        const seen = new Set();
        const out = [];
        for (const w of arr) {
            const k = w?.unikalny_klucz || `id:${w?.id}`;
            if (!k || seen.has(k)) continue;
            seen.add(k);
            out.push(w);
        }
        return out;
    }

    function escapeHtml(s) {
        return String(s ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    window.MapUtils = Object.freeze({
        parseMaybeJson,
        uniqueOwners,
        escapeHtml,
    });
})();
