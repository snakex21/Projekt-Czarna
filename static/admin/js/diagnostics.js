/**
 * Moduł diagnostyki danych (Priorytet 4).
 *
 * Renderuje 9 metryk jakości danych z TODO.md:
 *   - parcels_without_owners
 *   - owners_without_parcels
 *   - protocols_without_genealogy
 *   - people_without_parents
 *   - people_without_birth_date
 *   - people_without_death_date
 *   - parcels_without_category
 *   - owners_without_house_number
 *   - parcel_owner_links (czysty licznik powiązań)
 *   - incomplete_records (agregat)
 *
 * Każda metryka ma count + sample (max 10). UI pokazuje liczbę w dużym
 * formacie i (jeśli count > 0) listę sample'ów. Zero "missing" → zielone
 * zero, większe liczby → pomarańczowe/czerwone.
 *
 * Kolejność ładowania (admin.html):
 *   1. js/api.js
 *   2. js/utils.js
 *   3. js/notifications.js
 *   4. js/diagnostics.js   ← ten plik
 *   5. admin.js
 *
 * Publiczne API: ``window.AdminDiagnostics = {load, render, refresh, formatCount}``.
 */
(function () {
    'use strict';

    // Etykiety polskie + progi kolorów.
    // Próg "alarmowy" - dla właścicieli/działek > 50 to czerwone.
    const LABELS = {
        parcels_without_owners: {
            title: 'Działki bez właściciela',
            hint: 'Obiekty geograficzne bez powiązania z żadnym protokołem',
            threshold: 50,
        },
        owners_without_parcels: {
            title: 'Właściciele bez działek',
            hint: 'Protokoły właścicieli bez żadnej przypisanej działki',
            threshold: 5,
        },
        protocols_without_genealogy: {
            title: 'Protokoły bez genealogii',
            hint: 'Właściciele bez osób w drzewie genealogicznym',
            threshold: 20,
        },
        people_without_parents: {
            title: 'Osoby bez rodziców',
            hint: 'Korzenie drzewa genealogicznego',
            threshold: 100,
        },
        people_without_birth_date: {
            title: 'Osoby bez daty urodzenia',
            hint: 'Brak roku urodzenia w rekordzie genealogicznym',
            threshold: 100,
        },
        people_without_death_date: {
            title: 'Osoby bez daty śmierci',
            hint: 'Brak roku śmierci w rekordzie genealogicznym',
            threshold: 200,
        },
        parcels_without_category: {
            title: 'Działki bez kategorii',
            hint: 'Kategoria NULL / pusta / "default"',
            threshold: 5,
        },
        owners_without_house_number: {
            title: 'Właściciele bez numeru domu',
            hint: 'Rekordy z pustym polem numer_domu',
            threshold: 10,
        },
        parcel_owner_links: {
            title: 'Powiązania działka–właściciel',
            hint: 'Łączna liczba wpisów w tabeli łączącej',
            threshold: null,
        },
        incomplete_records: {
            title: 'Niepełne rekordy (agregat)',
            hint: 'Właściciele/osoby/działki z przynajmniej jednym brakiem',
            threshold: 100,
        },
    };

    function _getApi() {
        if (!window.AdminAPI || !window.AdminAPI.diagnostics) {
            throw new Error('AdminAPI.diagnostics nie zdefiniowane - załaduj api.js');
        }
        return window.AdminAPI.diagnostics;
    }

    function _getUtils() {
        return window.AdminUtils || {};
    }

    function _getContainer() {
        return document.getElementById('diagnosticsContent');
    }

    function _escape(text) {
        const utils = _getUtils();
        if (utils.escapeHtml) {
            return utils.escapeHtml(text);
        }
        // Fallback gdy AdminUtils nie załadowany
        if (text == null) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function _colorClass(count, threshold) {
        if (count === 0) return 'metric-count metric-count--ok';
        if (threshold != null && count > threshold) return 'metric-count metric-count--bad';
        if (count > 0) return 'metric-count metric-count--warn';
        return 'metric-count';
    }

    /**
     * Formatuje liczbę z separatorem tysięcy (polski: spacja).
     */
    function formatCount(n) {
        if (n == null) return '—';
        return Number(n).toLocaleString('pl-PL');
    }

    /**
     * Pobiera metryki z backendu.
     * :returns: Promise<dict> - surowy payload z /api/admin/diagnostics
     */
    async function load() {
        const url = _getApi();
        const resp = await fetch(url, { credentials: 'same-origin' });
        if (!resp.ok) {
            throw new Error(
                `Błąd pobierania diagnostyki: HTTP ${resp.status} ${resp.statusText}`
            );
        }
        return await resp.json();
    }

    /**
     * Renderuje 9 metryk w kontenerze #diagnosticsContent.
     * :param data: dict z compute_diagnostics()
     */
    function render(data) {
        const container = _getContainer();
        if (!container) {
            console.warn('[diagnostics] Brak #diagnosticsContent - pomijam render');
            return;
        }

        const metrics = Object.keys(LABELS);
        const cards = metrics
            .map((key) => {
                const meta = LABELS[key];
                const value = data[key] || { count: 0, sample: [] };
                const count = value.count || 0;
                const colorCls = _colorClass(count, meta.threshold);
                const sample = value.sample || [];

                // Priorytet 4.1: kosmetyka - dla metryk typu counter/aggregate
                // (parcel_owner_links, incomplete_records) sample.length === 0.
                // Zamiast pustej przestrzeni wyświetl jednolinijkowy opis.
                let sampleHtml = '';
                if (sample.length) {
                    sampleHtml = `<ul class="metric-sample">
                            ${sample
                                .map(
                                    (s) =>
                                        `<li><span class="metric-sample-id">#${_escape(
                                            s.id
                                        )}</span> ${_escape(s.name)}</li>`
                                )
                                .join('')}
                       </ul>
                       ${
                           count > sample.length
                               ? `<p class="metric-sample-more">…i ${formatCount(
                                     count - sample.length
                                 )} więcej (pokazano ${sample.length} z ${formatCount(
                                     count
                                 )})</p>`
                               : ''
                       }`;
                } else if (count > 0) {
                    // Brak sampla ale są rekordy → łączna/agregat - placeholder
                    sampleHtml = `<p class="metric-empty">Łączna liczba rekordów (agregat)</p>`;
                } else {
                    // count === 0 i brak sampla → pozytywny komunikat
                    sampleHtml = `<p class="metric-empty metric-empty--ok">✓ Wszystkie rekordy kompletne</p>`;
                }

                return `
                    <div class="metric-card">
                        <h3 class="metric-title">${_escape(meta.title)}</h3>
                        <p class="metric-hint">${_escape(meta.hint)}</p>
                        <div class="${colorCls}" data-metric="${key}">
                            ${formatCount(count)}
                        </div>
                        ${sampleHtml}
                    </div>
                `;
            })
            .join('');

        container.innerHTML = `
            <div class="diagnostics-grid">${cards}</div>
            <p class="diagnostics-footer">
                Dane z <code>${_escape(_getApi())}</code>. Ostatnie odświeżenie: ${new Date().toLocaleString('pl-PL')}
            </p>
        `;
    }

    /**
     * Ładuje i renderuje (używane przez admin.js loadSectionData).
     * :returns: Promise<{count: int, sample: list}> - zawsze zwraca użyteczny obiekt
     */
    async function refresh() {
        try {
            const data = await load();
            render(data);
            // Zwracamy sumę countów - przydatne dla badge'a w sidebarze
            const total = Object.values(data).reduce(
                (acc, v) => acc + (v && typeof v.count === 'number' ? v.count : 0),
                0
            );
            return { count: total, sample: [] };
        } catch (err) {
            const container = _getContainer();
            if (container) {
                container.innerHTML = `
                    <div class="diagnostics-error">
                        <h3>❌ Błąd ładowania diagnostyki</h3>
                        <pre>${_escape(err.message)}</pre>
                    </div>
                `;
            }
            throw err;
        }
    }

    // Publiczne API modułu
    window.AdminDiagnostics = Object.freeze({
        load,
        render,
        refresh,
        formatCount,
        LABELS,
    });
})();
