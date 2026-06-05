/**
 * Helpery UI wyekstrahowane z admin.js.
 *
 * Moduł dostarcza czyste funkcje, które nie mają zależności od DOM
 * poza operacjami sanityzacji tekstu i normalizacji nazwisk polskich
 * (do grupowania w tabeli właścicieli).
 *
 * Dostęp przez `window.AdminUtils.{escapeHtml,canonicalSurname}`.
 */
(function () {
    'use strict';

    /**
     * Sanityzuje wartość do bezpiecznego wstawienia w innerHTML.
     * Używane przez wszystkie miejsca w admin.js, które renderują
     * dane z backendu w szablonach HTML (np. tabele, etykiety statusów).
     */
    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Normalizuje polskie nazwisko do postaci kanonicznej (do grupowania).
     * Nie zmienia oryginału, tylko jego ostatni człon (nazwisko rodowe):
     *   "Kowalska"   -> "Kowalski"
     *   "Nowicka"    -> "Nowicki"
     *   "X dzka"     -> "X dzki"  (Kowalska->Kowalski itp.)
     *   "X owa"      -> "X"        (np. "Królowa" -> "Król")
     *   "X a" (>=4)  -> "X"        (np. "Kowala"  -> "Kowal")
     * Puste/null zwraca pusty string.
     */
    function canonicalSurname(raw) {
        if (!raw) return "";
        let last = raw.trim().split(/\s+/).pop().toLowerCase();
        if (last.endsWith("ska")) last = last.slice(0, -3) + "ski";
        else if (last.endsWith("cka")) last = last.slice(0, -3) + "cki";
        else if (last.endsWith("dzka")) last = last.slice(0, -4) + "dzki";
        else if (last.endsWith("owa")) last = last.slice(0, -3);
        else if (last.endsWith("a") && last.length > 4) last = last.slice(0, -1);
        return last.charAt(0).toUpperCase() + last.slice(1);
    }

    window.AdminUtils = Object.freeze({
        escapeHtml: escapeHtml,
        canonicalSurname: canonicalSurname,
    });
})();
