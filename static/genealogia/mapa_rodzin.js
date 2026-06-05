// Mapa Rodzin - skrypt aplikacji (wydzielony z mapa_rodzin.html)

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('mapTheme') || 'light';
    applyTheme(savedTheme);
    window.addEventListener('storage', (e) => {
        if (e.key === 'mapTheme') applyTheme(e.newValue);
    });
}

function applyTheme(theme) {
    const isDark = theme === 'dark';
    document.body.classList.toggle('dark-mode', isDark);
    const icon = document.querySelector('#themeToggle i');
    if (icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
}

document.getElementById('themeToggle').addEventListener('click', () => {
    const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('mapTheme', newTheme);
    applyTheme(newTheme);
});

initTheme();

// Data
let allPersons = [];
let personMap = new Map();
let childrenMap = new Map();
let families = [];

async function loadData() {
    try {
        const response = await fetch('/api/genealogia/list');
        const data = await response.json();
        allPersons = Array.isArray(data) ? data : (data.persons || []);

        allPersons.forEach(p => {
            personMap.set(p.id, p);
            if (p.parentIds) {
                p.parentIds.forEach(parentId => {
                    if (!childrenMap.has(parentId)) childrenMap.set(parentId, []);
                    childrenMap.get(parentId).push(p.id);
                });
            }
        });

        families = findFamilyLineages();

        document.getElementById('familiesCount').textContent = families.length;
        document.getElementById('personsCount').textContent = allPersons.length;

        renderFamilies(families);
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('familiesGrid').style.display = 'grid';
    } catch (error) {
        console.error('Blad ladowania danych:', error);
        document.getElementById('loadingState').innerHTML = '<p style="color: var(--danger);">Blad ladowania danych</p>';
    }
}

function findFamilyLineages() {
    const surnameGroups = new Map();

    allPersons.forEach(p => {
        const surname = extractSurname(p.name);
        if (!surnameGroups.has(surname)) surnameGroups.set(surname, []);
        surnameGroups.get(surname).push(p);
    });

    const lineages = [];

    surnameGroups.forEach((people, surname) => {
        if (people.length === 0) return;

        const visited = new Set();
        const peopleIds = new Set(people.map(p => p.id));

        people.forEach(startPerson => {
            if (visited.has(startPerson.id)) return;

            const lineageMembers = [];
            const queue = [startPerson.id];
            visited.add(startPerson.id);

            while (queue.length > 0) {
                const currentId = queue.shift();
                const person = personMap.get(currentId);
                if (person) lineageMembers.push(person);

                const parents = [...(person.parentIds || [])];
                if (person.fatherId) parents.push(person.fatherId);
                if (person.motherId) parents.push(person.motherId);

                parents.forEach(pid => {
                    if (peopleIds.has(pid) && !visited.has(pid)) {
                        visited.add(pid);
                        queue.push(pid);
                    }
                });

                const kids = childrenMap.get(currentId) || [];
                kids.forEach(cid => {
                    if (peopleIds.has(cid) && !visited.has(cid)) {
                        visited.add(cid);
                        queue.push(cid);
                    }
                });
            }

            lineageMembers.sort((a, b) => {
                const yearA = a.birthDate?.year || 9999;
                const yearB = b.birthDate?.year || 9999;
                return yearA - yearB;
            });

            const progenitor = lineageMembers[0];
            const progenitorName = progenitor.name.split(' ')[0];
            const progenitorYear = progenitor.birthDate?.year;

            let lineageName = 'Rodzina ' + surname;
            if (lineageMembers.length > 1 || surnameGroups.get(surname).length > lineageMembers.length) {
                lineageName += ' (linia: ' + progenitorName + (progenitorYear ? ' ur. ' + progenitorYear : '') + ')';
            }

            lineages.push({
                surname: surname,
                displayName: lineageName,
                members: lineageMembers,
                progenitor: progenitor
            });
        });
    });

    return lineages.sort((a, b) => b.members.length - a.members.length);
}

function extractSurname(name) {
    if (!name) return 'Nieznane';
    let cleanName = name.replace(/\([^)]*\)/g, '').trim();
    const parts = cleanName.split(/\s+/).filter(p => p.length > 0);
    if (parts.length === 0) return 'Nieznane';
    const zIndex = parts.indexOf('z');
    if (zIndex !== -1 && zIndex < parts.length - 1) return parts[parts.length - 1];
    return parts[parts.length - 1];
}

function renderFamilies(familiesToRender) {
    const grid = document.getElementById('familiesGrid');
    grid.innerHTML = '';

    familiesToRender.forEach((family) => {
        const card = document.createElement('div');
        card.className = 'family-card';
        card.onclick = () => showFamilyTree(family);

        const previewMembers = family.members.slice(0, 5);
        const moreCount = family.members.length - 5;

        card.innerHTML = `
            <div class="family-name">
                <i class="fas fa-users" style="color: var(--primary);"></i>
                ${family.displayName || 'Rodzina ' + family.surname}
            </div>
            <div class="family-count">${family.members.length} ${getPersonsWord(family.members.length)}</div>
            <div class="family-members-preview">
                ${previewMembers.map(m => '<span class="member-chip">' + m.name.split(' ')[0] + '</span>').join('')}
                ${moreCount > 0 ? '<span class="member-chip">+' + moreCount + '</span>' : ''}
            </div>
        `;
        grid.appendChild(card);
    });
}

function getPersonsWord(count) {
    if (count === 1) return 'osoba';
    if (count >= 2 && count <= 4) return 'osoby';
    return 'osob';
}

// Family Search
document.getElementById('familySearchInput').addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    if (!query) { renderFamilies(families); return; }
    const filtered = families.filter(f => {
        return f.surname.toLowerCase().includes(query) || (f.displayName || '').toLowerCase().includes(query);
    });
    renderFamilies(filtered);
});

// Person Search
document.getElementById('personSearchInput').addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();
    const resultsContainer = document.getElementById('personSearchResults');
    const resultsList = document.getElementById('personResultsList');

    if (!query || query.length < 2) { resultsContainer.style.display = 'none'; return; }

    const matches = allPersons.filter(p => p.name && p.name.toLowerCase().includes(query)).slice(0, 20);

    if (matches.length === 0) { resultsContainer.style.display = 'none'; return; }

    resultsContainer.style.display = 'block';
    resultsList.innerHTML = matches.map(p => {
        const bgColor = p.gender === 'M' ? '#e3f2fd' : '#fce4ec';
        const borderColor = p.gender === 'M' ? '#1976d2' : '#c2185b';
        const years = (p.birthDate?.year || '?') + ' - ' + (p.deathDate?.year || '?');
        return `
            <div onclick="showPersonTree(${p.id})" style="
                background: ${bgColor}; border: 2px solid ${borderColor};
                border-radius: 12px; padding: 0.5rem 1rem; cursor: pointer;
                transition: all 0.2s; color: #1e293b;
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <div style="font-weight: 700; font-size: 0.9rem; color: #1e293b;">${p.name}</div>
                <div style="font-size: 0.75rem; color: #475569;">${years}</div>
            </div>
        `;
    }).join('');
});

// Modal
function closeModal() {
    document.getElementById('treeModal').classList.remove('active');
}

document.getElementById('treeModal').addEventListener('click', (e) => {
    if (e.target.id === 'treeModal') closeModal();
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

function showFamilyTree(family) {
    document.getElementById('modalTitle').textContent = '🌳 ' + (family.displayName || 'Drzewo rodziny ' + family.surname);
    document.getElementById('treeModal').classList.add('active');
    const rootPerson = family.progenitor || family.members[0];
    renderFamilyTree(rootPerson, family.members);
}

function renderFamilyTree(rootPerson, familyMembers) {
    const container = document.getElementById('treeContainer');

    const getParentRole = (p) => p?.gender === 'M' ? 'Ojciec' : (p?.gender === 'F' ? 'Matka' : 'Rodzic');
    const getGrandparentRole = (p) => p?.gender === 'M' ? 'Dziadek' : (p?.gender === 'F' ? 'Babcia' : 'Dziadek/Babcia');
    const formatYears = (p) => {
        if (!p) return '';
        return (p.birthDate?.year || '?') + ' - ' + (p.deathDate?.year || '?');
    };

    const getFatherId = (p) => {
        if (p.fatherId) return p.fatherId;
        const parents = (p.parentIds || []).map(id => personMap.get(id)).filter(x => x);
        const father = parents.find(x => x.gender === 'M');
        return father?.id;
    };

    const getMotherId = (p) => {
        if (p.motherId) return p.motherId;
        const parents = (p.parentIds || []).map(id => personMap.get(id)).filter(x => x);
        const mother = parents.find(x => x.gender === 'F');
        return mother?.id;
    };

    const father = personMap.get(getFatherId(rootPerson));
    const mother = personMap.get(getMotherId(rootPerson));

    const parents = [];
    if (father) parents.push({ role: getParentRole(father), ...father });
    if (mother) parents.push({ role: getParentRole(mother), ...mother });

    const grandparentsFather = [];
    const grandparentsMother = [];

    if (father) {
        const gf = personMap.get(getFatherId(father));
        const gm = personMap.get(getMotherId(father));
        if (gf) grandparentsFather.push({ role: getGrandparentRole(gf), ...gf });
        if (gm) grandparentsFather.push({ role: getGrandparentRole(gm), ...gm });
    }
    if (mother) {
        const gf = personMap.get(getFatherId(mother));
        const gm = personMap.get(getMotherId(mother));
        if (gf) grandparentsMother.push({ role: getGrandparentRole(gf), ...gf });
        if (gm) grandparentsMother.push({ role: getGrandparentRole(gm), ...gm });
    }

    const spouses = (rootPerson.spouseIds || [])
        .map(sid => personMap.get(sid)).filter(s => s)
        .map(s => ({ role: 'Malzonek', ...s }));

    const children = (childrenMap.get(rootPerson.id) || [])
        .map(cid => personMap.get(cid)).filter(c => c)
        .map(c => ({ role: 'Dziecko', ...c }));

    const siblingIds = new Set();
    const fatherId = getFatherId(rootPerson);
    const motherId = getMotherId(rootPerson);
    if (fatherId) (childrenMap.get(fatherId) || []).forEach(id => { if (id !== rootPerson.id) siblingIds.add(id); });
    if (motherId) (childrenMap.get(motherId) || []).forEach(id => { if (id !== rootPerson.id) siblingIds.add(id); });
    const siblings = Array.from(siblingIds)
        .map(sid => personMap.get(sid)).filter(s => s)
        .map(s => ({ role: 'Rodzenstwo', ...s }));

    const renderTreeNode = (person, isRoot, showRole) => {
        if (!person) return '';
        const bgColor = isRoot ? '#fff3cd' : (person.gender === 'M' ? '#e3f2fd' : '#fce4ec');
        const borderColor = isRoot ? '#f57f17' : (person.gender === 'M' ? '#1976d2' : '#c2185b');
        return `
            <div class="tree-node" style="background: ${bgColor}; border: 2px solid ${borderColor}; cursor: pointer;"
                 onclick="showPersonTree(${person.id})" title="Kliknij aby zobaczyc drzewo tej osoby">
                ${showRole && person.role ? '<div style="font-size: 0.6rem; text-transform: uppercase; color: #888; margin-bottom: 0.2rem;">' + person.role + '</div>' : ''}
                <div style="font-weight: 700; font-size: 0.85rem; color: #333;">${person.name}</div>
                <div style="font-size: 0.7rem; color: #666; margin-top: 0.2rem;">${formatYears(person)}</div>
            </div>
        `;
    };

    let html = '<div class="tree-scroll-wrapper"><div class="tree-container">';

    if (grandparentsFather.length > 0 || grandparentsMother.length > 0) {
        html += '<div class="generation-label">Dziadkowie</div>';
        html += '<div class="tree-level" style="gap: 4rem;">';

        if (grandparentsFather.length > 0) {
            html += '<div class="tree-branch"><div style="font-size: 0.6rem; color: #888; margin-bottom: 0.25rem;">od ojca</div><div class="tree-pair">';
            grandparentsFather.forEach((gp, i) => {
                if (i > 0) html += '<div class="tree-pair-connector"></div>';
                html += renderTreeNode(gp, false, false);
            });
            html += '</div></div>';
        }

        if (grandparentsMother.length > 0) {
            html += '<div class="tree-branch"><div style="font-size: 0.6rem; color: #888; margin-bottom: 0.25rem;">od matki</div><div class="tree-pair">';
            grandparentsMother.forEach((gp, i) => {
                if (i > 0) html += '<div class="tree-pair-connector"></div>';
                html += renderTreeNode(gp, false, false);
            });
            html += '</div></div>';
        }

        html += '</div><div class="tree-connector-down"></div>';
    }

    if (parents.length > 0) {
        html += '<div class="generation-label">Rodzice</div>';
        html += '<div class="tree-level"><div class="tree-pair">';
        parents.forEach((p, i) => {
            if (i > 0) html += '<div class="tree-pair-connector"></div>';
            html += renderTreeNode(p);
        });
        html += '</div></div><div class="tree-connector-down"></div>';
    }

    html += '<div class="tree-with-siblings">';

    if (siblings.length > 0) {
        html += '<div class="tree-siblings-section"><div class="section-label">Rodzenstwo</div><div class="tree-siblings-grid">';
        siblings.forEach(s => { html += renderTreeNode(s); });
        html += '</div></div>';
    }

    html += '<div class="tree-main-column">';
    html += '<div class="generation-label">Glowna osoba</div>';
    html += '<div class="tree-pair">';
    html += renderTreeNode(rootPerson, true);
    if (spouses.length > 0) {
        html += '<div class="tree-pair-connector"></div>';
        html += renderTreeNode(spouses[0]);
    }
    html += '</div>';

    if (children.length > 0) {
        html += '<div class="tree-connector-down"></div>';
        html += '<div class="generation-label">Dzieci</div>';
        html += '<div class="tree-children">';
        if (children.length > 1) {
            const childWidth = 160;
            const connectorWidth = (children.length - 1) * childWidth;
            html += '<div class="tree-children-connector" style="width: ' + connectorWidth + 'px; left: calc(50% - ' + (connectorWidth / 2) + 'px);"></div>';
        }
        children.forEach(child => {
            html += '<div class="tree-child-branch">' + renderTreeNode(child) + '</div>';
        });
        html += '</div>';
    }

    html += '</div></div>';

    html += `
        <div style="margin-top: 2rem; padding: 1rem; background: #f8f9fa; border-radius: 8px; font-size: 0.75rem; color: #666; text-align: center; width: 100%;">
            <strong>Legenda:</strong> 💙 Mezczyzna | 💗 Kobieta | 💛 Glowna osoba | 💕 Malzenstwo<br>
            <em>Kliknij na osobe, aby zobaczyc jej drzewo</em>
        </div>
    `;

    html += '</div></div>';
    container.innerHTML = html;
}

function showPersonTree(personId) {
    const person = personMap.get(personId);
    if (!person) return;
    document.getElementById('modalTitle').textContent = '🌳 Drzewo: ' + person.name;
    document.getElementById('treeModal').classList.add('active');
    renderFamilyTree(person, []);
}

loadData();
