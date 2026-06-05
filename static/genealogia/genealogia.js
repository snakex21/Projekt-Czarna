// Genealogia - skrypt aplikacji (wydzielony z genealogia.html)
// --- Theme Management (Synchronized) ---
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

// --- App Logic ---
let allPersons = [];
let filteredPersons = [];
let personMap = new Map();
let childrenMap = new Map();
let currentFilter = 'all';
let itemsLimit = 100;
let existingHouses = new Set();

const DATA_URL = '/api/genealogia/persons-format';

document.addEventListener('DOMContentLoaded', async () => {
    const loading = document.getElementById('loadingIndicator');
    loading.style.display = 'inline';

    try {
        const response = await fetch(DATA_URL);
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
            if (p.parents) {
                p.parents.forEach(parentId => {
                    if (!childrenMap.has(parentId)) childrenMap.set(parentId, []);
                    childrenMap.get(parentId).push(p.id);
                });
            }
        });

        allPersons.sort((a, b) => a.name.localeCompare(b.name));
        filteredPersons = [...allPersons];

        renderList();
        updateCount();

        try {
            const mapResponse = await fetch('/api/dzialki');
            const mapData = await mapResponse.json();
            if (mapData && mapData.features) {
                mapData.features.forEach(f => {
                    const props = f.properties;
                    if (props && (props.kategoria === 'budynek' || props.kategoria === 'dom')) {
                        if (props.numer_obiektu) {
                            existingHouses.add(String(props.numer_obiektu).trim().toLowerCase());
                        }
                    }
                });
                console.log(`✅ Załadowano ${existingHouses.size} domów z mapy.`);
            }
        } catch (mapError) {
            console.error("Error loading map data (optional):", mapError);
        }
    } catch (error) {
        console.error("Error loading data:", error);
        document.getElementById('peopleList').innerHTML = '<div style="padding: 20px; color: #ef4444; text-align: center;">Błąd ładowania danych.<br>Upewnij się, że serwer działa.</div>';
    } finally {
        loading.style.display = 'none';
    }
});

const searchInput = document.getElementById('searchInput');
const houseInput = document.getElementById('houseInput');

const handleFilter = () => filterData(searchInput.value, houseInput.value);

searchInput.addEventListener('input', handleFilter);
houseInput.addEventListener('input', handleFilter);

document.querySelectorAll('.filter-tag').forEach(tag => {
    tag.addEventListener('click', () => {
        document.querySelectorAll('.filter-tag').forEach(t => t.classList.remove('active'));
        tag.classList.add('active');
        currentFilter = tag.dataset.filter;
        handleFilter();
    });
});

function filterData(query, houseQuery) {
    const lowerQuery = query.toLowerCase();
    const lowerHouse = houseQuery ? houseQuery.toLowerCase() : '';

    filteredPersons = allPersons.filter(p => {
        const matchesSearch = p.name.toLowerCase().includes(lowerQuery) ||
            (p.notes && p.notes.toLowerCase().includes(lowerQuery)) ||
            (p.birthDate && String(p.birthDate.year).includes(lowerQuery));

        let matchesHouse = true;
        if (lowerHouse) {
            const houseNum = p.houseNumber ? String(p.houseNumber) : (p.notes ? (p.notes.match(/dom nr (\d+)/) || [])[1] : null);
            matchesHouse = houseNum && houseNum.toLowerCase().includes(lowerHouse);
        }

        let matchesCategory = true;
        if (currentFilter === 'men') matchesCategory = p.gender === 'M';
        if (currentFilter === 'women') matchesCategory = p.gender === 'F';
        if (currentFilter === 'infants') {
            if (p.birthDate && p.deathDate && p.birthDate.year && p.deathDate.year) {
                matchesCategory = (p.deathDate.year - p.birthDate.year) <= 1;
            } else {
                matchesCategory = false;
            }
        }

        return matchesSearch && matchesCategory && matchesHouse;
    });

    itemsLimit = 100;
    renderList();
    updateCount();
}

function updateCount() {
    document.getElementById('countDisplay').textContent = filteredPersons.length;
}

function renderList() {
    const listContainer = document.getElementById('peopleList');
    listContainer.innerHTML = '';

    const limit = itemsLimit;
    const items = filteredPersons.slice(0, limit);

    items.forEach(p => {
        const el = document.createElement('div');
        el.className = 'person-item';
        el.dataset.id = p.id;
        el.onclick = () => showProfile(p.id);

        const houseNum = p.houseNumber || (p.notes ? (p.notes.match(/dom nr (\d+)/) || [])[1] : null);
        const birthYear = p.birthDate ? p.birthDate.year : '?';
        const deathYear = p.deathDate ? p.deathDate.year : '?';

        el.innerHTML = `
            <div class="person-info">
                <h3>${p.name}</h3>
                <div class="person-meta">
                    <span><i class="far fa-calendar-alt"></i> ${birthYear} - ${deathYear}</span>
                    ${houseNum ? `<span class="house-badge"><i class="fas fa-home"></i> ${houseNum}</span>` : ''}
                </div>
            </div>
            <i class="fas fa-chevron-right" style="font-size: 10px; color: var(--text-tertiary); opacity: 0.5;"></i>
        `;
        listContainer.appendChild(el);
    });

    if (filteredPersons.length > limit) {
        const moreBtn = document.createElement('button');
        moreBtn.className = 'btn btn-secondary';
        moreBtn.style.borderRadius = '12px';
        moreBtn.style.border = '1px solid var(--border)';
        moreBtn.style.background = 'var(--bg-secondary)';
        moreBtn.style.color = 'var(--text-primary)';
        moreBtn.style.cursor = 'pointer';
        moreBtn.style.transition = 'all 0.2s ease';
        moreBtn.innerHTML = `<i class="fas fa-plus-circle" style="margin-right: 8px;"></i> Pokaż więcej (${filteredPersons.length - limit})`;
        
        moreBtn.onmouseover = () => {
            moreBtn.style.background = 'var(--bg-hover)';
            moreBtn.style.transform = 'translateY(-2px)';
        };
        moreBtn.onmouseout = () => {
            moreBtn.style.background = 'var(--bg-secondary)';
            moreBtn.style.transform = 'translateY(0)';
        };
        moreBtn.onclick = () => {
            itemsLimit += 100;
            renderList();
            const newItems = listContainer.querySelectorAll('.person-item');
            if (newItems.length > limit) {
                newItems[limit].scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        };
        listContainer.appendChild(moreBtn);
    }
}

function showProfile(id) {
    const person = personMap.get(String(id)) || personMap.get(Number(id));
    if (!person) return;

    document.getElementById('emptyState').style.display = 'none';
    const container = document.getElementById('profileContainer');
    container.style.display = 'block';

    container.style.animation = 'none';
    container.offsetHeight;
    container.style.animation = 'slideUp 0.4s ease';

    document.querySelectorAll('.person-item').forEach(el => el.classList.remove('active'));
    const listItem = document.querySelector(`.person-item[data-id="${id}"]`);
    if (listItem) {
        listItem.classList.add('active');
        listItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    const birthDate = formatDate(person.birthDate);
    const deathDate = formatDate(person.deathDate);
    const houseMatch = person.notes ? person.notes.match(/dom nr (\d+)/) : null;
    const houseNum = houseMatch ? houseMatch[1] : null;

    const getParentRole = (p) => p.gender === 'M' ? 'Ojciec' : (p.gender === 'F' ? 'Matka' : 'Rodzic');
    const getGrandparentRole = (p) => p.gender === 'M' ? 'Dziadek' : (p.gender === 'F' ? 'Babcia' : 'Dziadek/Babcia');
    const getCousinRole = (p) => p.gender === 'M' ? 'Kuzyn' : (p.gender === 'F' ? 'Kuzynka' : 'Kuzynostwo');

    let fatherId = person.fatherId;
    let motherId = person.motherId;

    if (!fatherId || !motherId) {
        (person.parentIds || []).forEach(pid => {
            const p = personMap.get(pid);
            if (p) {
                if (p.gender === 'M' && !fatherId) fatherId = pid;
                else if (p.gender === 'F' && !motherId) motherId = pid;
            }
        });
    }

    const parentIds = person.parentIds || [];
    if (fatherId) parentIds.push(fatherId);
    if (motherId) parentIds.push(motherId);
    const uniqueParentIds = Array.from(new Set(parentIds));

    const parents = uniqueParentIds.map(pid => {
        const p = personMap.get(pid);
        return p ? { role: getParentRole(p), ...p } : null;
    }).filter(p => p);

    const spouses = (person.spouseIds || person.spouses || []).map(pid => ({ role: 'Małżonek', ...personMap.get(pid) })).filter(p => p.id);
    const children = (childrenMap.get(person.id) || []).map(cid => ({ role: 'Dziecko', ...personMap.get(cid) })).filter(p => p.id);

    const siblingsSet = new Set();
    uniqueParentIds.forEach(pid => {
        const kids = childrenMap.get(pid) || [];
        kids.forEach(kidId => {
            if (kidId !== person.id) siblingsSet.add(kidId);
        });
    });
    const siblings = Array.from(siblingsSet).map(sid => ({ role: 'Rodzeństwo', ...personMap.get(sid) })).filter(p => p.id);

    const grandparentsFather = [];
    const grandparentsMother = [];

    const father = personMap.get(fatherId);
    if (father) {
        const gIds = father.parentIds || [];
        if (father.fatherId) gIds.push(father.fatherId);
        if (father.motherId) gIds.push(father.motherId);
        Array.from(new Set(gIds)).forEach(gid => {
            const g = personMap.get(gid);
            if (g) grandparentsFather.push({ role: getGrandparentRole(g), ...g });
        });
    }

    const mother = personMap.get(motherId);
    if (mother) {
        const gIds = mother.parentIds || [];
        if (mother.fatherId) gIds.push(mother.fatherId);
        if (mother.motherId) gIds.push(mother.motherId);
        Array.from(new Set(gIds)).forEach(gid => {
            const g = personMap.get(gid);
            if (g) grandparentsMother.push({ role: getGrandparentRole(g), ...g });
        });
    }

    const cousinsSet = new Set();
    uniqueParentIds.forEach(pid => {
        const p = personMap.get(pid);
        if (p) {
            const gIds = p.parentIds || [];
            if (p.fatherId) gIds.push(p.fatherId);
            if (p.motherId) gIds.push(p.motherId);
            Array.from(new Set(gIds)).forEach(gid => {
                const siblingsOfParent = childrenMap.get(gid) || [];
                siblingsOfParent.forEach(sopId => {
                    if (sopId !== pid) {
                        const cousins = childrenMap.get(sopId) || [];
                        cousins.forEach(cId => cousinsSet.add(cId));
                    }
                });
            });
        }
    });
    const cousins = Array.from(cousinsSet).map(cid => ({ role: getCousinRole(personMap.get(cid)), ...personMap.get(cid) })).filter(p => p.id);

    const houseNumFromField = person.houseNumber || houseNum;

    container.innerHTML = `
        <div class="profile-header">
            <div class="profile-title">
                <h1>${person.name}</h1>
                <div class="profile-id">ID: ${person.id} • ${person.gender === 'M' ? 'Mężczyzna' : 'Kobieta'}</div>
            </div>
            <div class="profile-actions" style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.75rem;">
                ${houseNumFromField ? `<div style="font-weight: 800; color: var(--text-primary); font-size: 1.1rem; font-family: 'Space Grotesk', sans-serif;">Dom ${houseNumFromField}</div>` : ''}
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end;">
                    ${person.protocolKey ? `<a href="../wlasciciele/protokol.html?ownerId=${person.protocolKey}" class="btn btn-secondary" style="display: flex; align-items: center; gap: 0.5rem; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border);"><i class="fas fa-file-alt"></i> Zobacz protokół</a>` : ''}
                    ${houseNumFromField && existingHouses.has(String(houseNumFromField).toLowerCase()) ? `<a href="../mapa/mapa.html?findHouseNumber=${houseNumFromField}&ownerName=${encodeURIComponent(person.name)}&zoomToFit=true" class="btn btn-primary"><i class="fas fa-map-marker-alt"></i> Pokaż na mapie</a>` : (houseNumFromField ? `<div style="font-size: 0.8rem; color: var(--text-tertiary); font-style: italic; align-self: center;">(Brak na mapie)</div>` : '')}
                    <a href="/api/genealogia/pdf/${encodeURIComponent(person.dbId || person.id)}" class="btn" style="background: #e74c3c; color: white; display: flex; align-items: center; gap: 0.5rem; text-decoration: none;" target="_blank"><i class="fas fa-file-pdf"></i> Karta Rodziny</a>
                </div>
            </div>
        </div>
        
        <div class="profile-body">
            <div class="section-title"><i class="fas fa-history"></i> Oś czasu</div>
            <div class="timeline">
                ${birthDate ? `<div class="timeline-item"><div class="timeline-dot birth"></div><div class="timeline-content"><h4>Urodzenie</h4><div class="timeline-date">${birthDate}</div></div></div>` : ''}
                ${(person.marriages || []).map(m => {
                    const spouse = personMap.get(m.spouseId);
                    return `<div class="timeline-item"><div class="timeline-dot marriage"></div><div class="timeline-content"><h4>Ślub ${spouse ? 'z ' + spouse.name : ''}</h4><div class="timeline-date">${m.year ? m.year : (m.date || 'Data nieznana')}</div></div></div>`;
                }).join('')}
                ${deathDate ? `<div class="timeline-item"><div class="timeline-dot death"></div><div class="timeline-content"><h4>Śmierć</h4><div class="timeline-date">${deathDate} ${person.notes && person.notes.includes('wiek') ? '(' + extractAge(person.notes) + ')' : ''}</div></div></div>` : ''}
            </div>

            ${person.notes ? `<div class="section-title"><i class="fas fa-sticky-note"></i> Notatki</div><p style="margin-bottom: 3rem; color: var(--text-secondary); line-height: 1.8; font-size: 0.95rem;">${person.notes}</p>` : ''}

            <div class="section-title"><i class="fas fa-users"></i> Rodzina</div>
            ${grandparentsFather.length > 0 || grandparentsMother.length > 0 ? `
                <div class="relation-group">
                    <div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-tertiary); margin: 1.5rem 0 0.75rem 0; font-weight: 700;">Dziadkowie</div>
                    ${grandparentsFather.length > 0 ? `<div style="font-size: 0.65rem; color: var(--text-tertiary); margin-bottom: 0.5rem; font-style: italic;">od strony ojca:</div><div class="relations-grid" style="margin-bottom: 1rem;">${renderRelationCards(grandparentsFather)}</div>` : ''}
                    ${grandparentsMother.length > 0 ? `<div style="font-size: 0.65rem; color: var(--text-tertiary); margin-bottom: 0.5rem; font-style: italic;">od strony matki:</div><div class="relations-grid">${renderRelationCards(grandparentsMother)}</div>` : ''}
                </div>
            ` : ''}

            ${renderRelationSection('Rodzice', parents)}
            ${renderRelationSection('Małżonkowie', spouses)}
            ${renderRelationSection('Rodzeństwo', siblings)}
            ${renderRelationSection('Dzieci', children)}
            ${renderRelationSection('Kuzynostwo', cousins)}
        </div>
    `;
}

function renderRelationSection(title, relations) {
    if (!relations || relations.length === 0) return '';
    return `<div class="relation-group"><div style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; color: var(--text-tertiary); margin: 1.5rem 0 0.75rem 0; font-weight: 700;">${title}</div><div class="relations-grid">${renderRelationCards(relations)}</div></div>`;
}

function renderRelationCards(relations) {
    if (relations.length === 0) return '<p style="color: var(--text-tertiary); font-size: 0.9rem;">Brak danych o rodzinie.</p>';
    return relations.map(r => `
        <div class="relation-card" onclick="showProfile('${r.id}')">
            <div class="relation-role">${r.role}</div>
            <div class="relation-name">${r.name}</div>
            <div style="font-size: 0.75rem; color: var(--text-tertiary);">${r.birthDate ? r.birthDate.year : '?'} - ${r.deathDate ? r.deathDate.year : '?'}</div>
        </div>
    `).join('');
}

function formatDate(d) {
    if (!d) return null;
    if (d.day && d.month && d.year) return `${d.day}.${d.month}.${d.year}`;
    return d.year || null;
}

function extractAge(notes) {
    const match = notes.match(/wiek:? (\d+)/i);
    return match ? match[1] + ' lat' : '';
}
