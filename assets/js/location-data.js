/**
 * Skrypt automatycznie wstawia dane miejscowości do placeholderów w HTML
 * Działa dla wszystkich stron: mapa, statystyki, historia, strona główna
 */

(function() {
    'use strict';

    // Sprawdź czy konfiguracja została załadowana
    if (typeof window.LOCATION_CONFIG === 'undefined') {
        console.error('LOCATION_CONFIG nie został załadowany!');
        return;
    }

    const config = window.LOCATION_CONFIG;

    /**
     * Zamienia wszystkie placeholdery w dokumencie na dane z konfiguracji
     */
    function replacePlaceholders() {
        // Mapa placeholderów na wartości
        const placeholders = {
            '{{MIEJSCOWOSC}}': config.name,
            '{{MIEJSCOWOSC_PELNA}}': config.fullName,
            '{{POWIAT}}': config.powiat,
            '{{REGION}}': config.region,
            '{{YEAR}}': config.year,
            '{{WIEK}}': config.century
        };

        // Funkcja rekurencyjna do przeszukiwania wszystkich węzłów tekstowych
        function processNode(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                // To jest węzeł tekstowy - zamień placeholdery
                let text = node.textContent;
                let hasPlaceholder = false;

                for (const [placeholder, value] of Object.entries(placeholders)) {
                    if (text.includes(placeholder)) {
                        text = text.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), value);
                        hasPlaceholder = true;
                    }
                }

                if (hasPlaceholder) {
                    node.textContent = text;
                }
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                // To jest element - przeszukaj jego dzieci
                // Pomiń skrypty i style
                if (node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE') {
                    // Sprawdź również atrybuty (np. title, placeholder, data-*)
                    if (node.hasAttributes()) {
                        const attributes = node.attributes;
                        for (let i = 0; i < attributes.length; i++) {
                            const attr = attributes[i];
                            let attrValue = attr.value;

                            for (const [placeholder, value] of Object.entries(placeholders)) {
                                if (attrValue.includes(placeholder)) {
                                    attrValue = attrValue.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), value);
                                }
                            }

                            if (attrValue !== attr.value) {
                                attr.value = attrValue;
                            }
                        }
                    }

                    // Przeszukaj dzieci
                    for (let i = 0; i < node.childNodes.length; i++) {
                        processNode(node.childNodes[i]);
                    }
                }
            }
        }

        // Zacznij od całego dokumentu
        processNode(document.body);

        // Zaktualizuj również tytuł strony
        if (document.title) {
            let title = document.title;
            for (const [placeholder, value] of Object.entries(placeholders)) {
                title = title.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), value);
            }
            document.title = title;
        }

        console.log('✓ Dane miejscowości zostały wstawione:', config);
    }

    // Uruchom gdy DOM jest gotowy
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', replacePlaceholders);
    } else {
        // DOM już załadowany
        replacePlaceholders();
    }
})();
