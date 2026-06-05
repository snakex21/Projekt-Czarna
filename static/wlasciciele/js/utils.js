/**
 * Helpery formatowania dla publicznych stron właścicieli/protokołów (P2.7 Etap 2).
 *
 * Kolejność ładowania:
 *   1. js/api.js
 *   2. js/utils.js      ← ten plik
 *   3. protokol.js / compare.js / stats-script.js
 *
 * Dostęp przez `window.OwnersUtils`.
 */
(function () {
    'use strict';

    function normalizeText(text) {
        return String(text ?? '').replace(/\\n/g, '\n');
    }

    function escapeHtml(text) {
        return String(text ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function generateFractionHTML(text) {
        if (!text) return '';

        return normalizeText(text)
            .replace(/\n/g, '<br>')
            .replace(/(\d+)\/(\d+)/g,
                `<span class="fraction">
                    <span class="numerator">$1</span>
                    <span class="denominator">$2</span>
                </span>`)
            .replace(/(?<!\/)\b(\d+)\b(?![\/<])/g,
                `<span class="whole-number">$1</span>`);
    }

    function formatArea(areaM2) {
        if (!areaM2 || areaM2 === 0) return '—';

        if (areaM2 >= 10000) {
            return `${(areaM2 / 10000).toFixed(2)} ha`;
        }
        if (areaM2 >= 100) {
            return `${(areaM2 / 100).toFixed(2)} a`;
        }
        return `${areaM2.toFixed(2)} m²`;
    }

    function formatLength(lengthM) {
        if (!lengthM || lengthM === 0) return '—';

        if (lengthM >= 1000) {
            return `${(lengthM / 1000).toFixed(2)} km`;
        }
        return `${lengthM.toFixed(2)} m`;
    }

    function formatDate(dateString) {
        if (!dateString) return '—';
        const date = new Date(dateString);
        return date.toLocaleDateString('pl-PL');
    }

    window.OwnersUtils = Object.freeze({
        escapeHtml: escapeHtml,
        normalizeText: normalizeText,
        generateFractionHTML: generateFractionHTML,
        formatArea: formatArea,
        formatLength: formatLength,
        formatDate: formatDate,
    });
})();
