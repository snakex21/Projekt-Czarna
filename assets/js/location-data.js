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

    // Mapa placeholderów na wartości
    const placeholders = {
        '{{MIEJSCOWOSC}}': config.name,
        '{{MIEJSCOWOSC_PELNA}}': config.fullName,
        '{{POWIAT}}': config.powiat,
        '{{REGION}}': config.region,
        '{{YEAR}}': config.year,
        '{{WIEK}}': config.century
    };

    /**
     * Zamienia wszystkie placeholdery w dokumencie na dane z konfiguracji
     */
    function replacePlaceholders(rootElement) {
        const root = rootElement || document.body;

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

        // Przetworz drzewo DOM
        processNode(root);

        // Zaktualizuj również tytuł strony (tylko jeśli przetwarzamy cały dokument)
        if (root === document.body && document.title) {
            let title = document.title;
            for (const [placeholder, value] of Object.entries(placeholders)) {
                title = title.replace(new RegExp(placeholder.replace(/[{}]/g, '\\$&'), 'g'), value);
            }
            document.title = title;
        }
    }

    // Eksportuj funkcję globalnie, żeby można było wywołać ręcznie
    window.applyLocationData = function() {
        replacePlaceholders();
        console.log('✓ Dane miejscowości zostały wstawione:', config);
    };

    // Uruchom gdy DOM jest gotowy
    function initialize() {
        replacePlaceholders();
        console.log('✓ Dane miejscowości zostały wstawione (inicjalizacja):', config);

        // Obserwuj zmiany DOM i automatycznie przetwarzaj nową zawartość
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                // Jeśli dodano nowe węzły
                if (mutation.addedNodes && mutation.addedNodes.length > 0) {
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            replacePlaceholders(node);
                        }
                    });
                }
            });
        });

        // Zacznij obserwować zmiany w document.body
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });

        console.log('✓ MutationObserver aktywny - automatyczne przetwarzanie nowej zawartości');
    }

    // Uruchom
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        // DOM już załadowany
        initialize();
    }

    // Dodatkowe wywołanie po pełnym załadowaniu strony (dla pewności)
    window.addEventListener('load', function() {
        setTimeout(function() {
            replacePlaceholders();
            console.log('✓ Dane miejscowości ponownie wstawione (po window.load)');
        }, 100);
    });
})();
