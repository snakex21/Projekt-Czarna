/**
 * ================================================================================
 * Moduł: project-loader.js
 * Opis: Dynamiczne ładowanie informacji o aktywnym projekcie
 *       Zastępuje zhardkodowane referencje do "Czarna" w całym systemie
 * ================================================================================
 */

// Cache dla informacji o projekcie
window.PROJECT_INFO = null;

/**
 * Pobiera informacje o aktywnym projekcie z API
 * @returns {Promise<Object>} Obiekt z danymi projektu
 */
async function loadProjectInfo() {
    try {
        const response = await fetch('/api/project-info');
        const data = await response.json();
        
        if (data.status === 'success' && data.project) {
            window.PROJECT_INFO = data.project;
            console.log('✅ Załadowano informacje o projekcie:', data.project.nazwa);
            return data.project;
        } else {
            console.error('❌ Błąd podczas ładowania informacji o projekcie');
            return getDefaultProjectInfo();
        }
    } catch (error) {
        console.error('❌ Błąd połączenia z API projektu:', error);
        return getDefaultProjectInfo();
    }
}

/**
 * Zwraca domyślne informacje o projekcie (fallback)
 * @returns {Object} Domyślny obiekt projektu
 */
function getDefaultProjectInfo() {
    return {
        short_code: 'czarna',
        nazwa: 'Czarna',
        pelna_nazwa: 'Gmina Czarna',
        opis: 'System mapy katastralnej',
        kontekst_czasowy: 'XIX wiek',
        rok_zrodlowy: 1880,
        okres_danych: '1850-1900',
        region: 'Powiat Mielecki',
        wojewodztwo: 'Podkarpackie'
    };
}

/**
 * Aktualizuje tytuł strony na podstawie informacji o projekcie
 * @param {string} pageTitle - Tytuł specyficzny dla strony (np. "Mapa Katastralna")
 */
function updatePageTitle(pageTitle) {
    const project = window.PROJECT_INFO || getDefaultProjectInfo();
    document.title = `${pageTitle} - ${project.nazwa}`;
}

/**
 * Aktualizuje elementy DOM z informacjami o projekcie
 * Automatycznie szuka elementów z atrybutami data-project-*
 */
function updateProjectElements() {
    const project = window.PROJECT_INFO || getDefaultProjectInfo();
    
    // Aktualizacja elementów z atrybutami data-project-*
    const elements = document.querySelectorAll('[data-project-field]');
    elements.forEach(element => {
        const field = element.getAttribute('data-project-field');
        const value = project[field];
        
        if (value !== undefined && value !== null) {
            // Jeśli element ma atrybut data-project-template, użyj go jako szablonu
            const template = element.getAttribute('data-project-template');
            if (template) {
                element.textContent = template.replace('{value}', value);
            } else {
                element.textContent = value;
            }
        }
    });
    
    // Specjalne obsłużenie dla typowych przypadków
    updateCommonElements(project);
}

/**
 * Aktualizuje często używane elementy
 */
function updateCommonElements(project) {
    // Nagłówki strony
    const titleElements = document.querySelectorAll('.app-title, .page-title, h1[data-project]');
    titleElements.forEach(el => {
        if (el.textContent.includes('Czarna')) {
            el.textContent = el.textContent.replace(/Czarna/g, project.nazwa);
        }
        // Zamień "XIX w." na kontekst czasowy projektu
        if (el.textContent.includes('XIX w.')) {
            el.textContent = el.textContent.replace(/XIX w\./g, project.kontekst_czasowy || 'XIX w.');
        }
    });
    
    // Meta description
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc && metaDesc.content.includes('Czarna')) {
        metaDesc.content = metaDesc.content.replace(/Czarna/g, project.nazwa);
    }
    
    // Meta keywords
    const metaKeywords = document.querySelector('meta[name="keywords"]');
    if (metaKeywords && metaKeywords.content.includes('Czarna')) {
        metaKeywords.content = metaKeywords.content.replace(/Czarna/g, project.nazwa);
    }
}

/**
 * Zwraca sformatowany tekst z informacjami o projekcie
 * @param {string} template - Szablon z placeholderami {field_name}
 * @returns {string} Wypełniony szablon
 */
function formatProjectText(template) {
    const project = window.PROJECT_INFO || getDefaultProjectInfo();
    let result = template;
    
    // Zamień wszystkie {field_name} na wartości z projektu
    const regex = /\{(\w+)\}/g;
    result = result.replace(regex, (match, field) => {
        return project[field] !== undefined ? project[field] : match;
    });
    
    return result;
}

/**
 * Tworzy element wskaźnika aktywnego projektu
 * @param {string} containerId - ID kontenera, do którego dodać wskaźnik
 */
function createProjectIndicator(containerId) {
    const project = window.PROJECT_INFO || getDefaultProjectInfo();
    const container = document.getElementById(containerId);
    
    if (!container) {
        console.warn(`Kontener ${containerId} nie został znaleziony`);
        return;
    }
    
    const indicator = document.createElement('div');
    indicator.className = 'project-indicator';
    indicator.innerHTML = `
        <i class="fas fa-folder-open"></i>
        <span>Projekt: <strong>${project.nazwa}</strong></span>
    `;
    
    // Dodaj style jeśli nie istnieją
    if (!document.getElementById('project-indicator-styles')) {
        const style = document.createElement('style');
        style.id = 'project-indicator-styles';
        style.textContent = `
            .project-indicator {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 6px 12px;
                background: rgba(13, 110, 253, 0.1);
                border: 1px solid rgba(13, 110, 253, 0.3);
                border-radius: 6px;
                font-size: 14px;
                color: #0d6efd;
            }
            .project-indicator i {
                font-size: 16px;
            }
            .project-indicator strong {
                font-weight: 600;
            }
        `;
        document.head.appendChild(style);
    }
    
    container.appendChild(indicator);
}

/**
 * Inicjalizacja - automatycznie ładuje projekt przy załadowaniu strony
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🔄 Ładowanie informacji o projekcie...');
    await loadProjectInfo();
    updateProjectElements();
    
    // Emit custom event informujący, że projekt został załadowany
    const event = new CustomEvent('projectLoaded', { 
        detail: window.PROJECT_INFO 
    });
    document.dispatchEvent(event);
    
    console.log('✅ Projekt załadowany:', window.PROJECT_INFO?.nazwa);
});

// Eksport funkcji dla innych modułów
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        loadProjectInfo,
        updatePageTitle,
        updateProjectElements,
        formatProjectText,
        createProjectIndicator
    };
}
