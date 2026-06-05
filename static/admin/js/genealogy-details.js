(function () {
    'use strict';

    function buildContext(allGenealogy) {
        const genealogy = Array.isArray(allGenealogy) ? allGenealogy : [];
        const peopleMap = new Map(genealogy.map(p => [String(p.id_osoby), p]));
        const dbIdMap = new Map(genealogy.map(p => [p.db_id, p]));

        function getPersonById(id) {
            if (!id) return null;
            const idStr = String(id);
            if (peopleMap.has(idStr)) return peopleMap.get(idStr);
            return dbIdMap.get(id) || dbIdMap.get(parseInt(id));
        }

        const childrenMap = new Map();
        genealogy.forEach(person => {
            if (person.id_ojca) {
                const father = getPersonById(person.id_ojca);
                if (father) {
                    const fatherId = String(father.id_osoby);
                    if (!childrenMap.has(fatherId)) childrenMap.set(fatherId, []);
                    childrenMap.get(fatherId).push(String(person.id_osoby));
                }
            }
            if (person.id_matki) {
                const mother = getPersonById(person.id_matki);
                if (mother) {
                    const motherId = String(mother.id_osoby);
                    if (!childrenMap.has(motherId)) childrenMap.set(motherId, []);
                    childrenMap.get(motherId).push(String(person.id_osoby));
                }
            }
        });

        return { genealogy, peopleMap, childrenMap, getPersonById };
    }

    function formatLifespan(person) {
        if (!person) return '? - ?';
        if (!person.rok_urodzenia && !person.rok_smierci) return '? - ?';
        const birth = person.rok_urodzenia || '?';
        const death = person.rok_smierci || '?';
        return `${birth} - ${death}`;
    }

    function findGrandparents(person, side, context) {
        const parentId = side === 'father' ? person.id_ojca : person.id_matki;
        const parent = context.getPersonById(parentId);

        if (!parent) return [];

        const grandparents = [];
        if (parent.id_ojca) {
            const gf = context.getPersonById(parent.id_ojca);
            if (gf) grandparents.push({ ...gf, role: 'Dziadek' });
        }
        if (parent.id_matki) {
            const gm = context.getPersonById(parent.id_matki);
            if (gm) grandparents.push({ ...gm, role: 'Babcia' });
        }
        return grandparents;
    }

    function findParents(person, context) {
        const parents = [];
        if (person.id_ojca) {
            const father = context.getPersonById(person.id_ojca);
            if (father) parents.push({ ...father, role: 'Ojciec' });
        }
        if (person.id_matki) {
            const mother = context.getPersonById(person.id_matki);
            if (mother) parents.push({ ...mother, role: 'Matka' });
        }
        return parents;
    }

    function findSpouses(person, context) {
        const spousesIds = new Set();

        if (person.marriages && Array.isArray(person.marriages)) {
            person.marriages.forEach(marriage => {
                if (marriage.spouseId) spousesIds.add(String(marriage.spouseId));
                if (marriage.spouseDbId) {
                    const spouse = context.getPersonById(marriage.spouseDbId);
                    if (spouse) spousesIds.add(String(spouse.id_osoby));
                }
            });
        }

        if (person.id_malzonka) {
            const spouse = context.getPersonById(person.id_malzonka);
            if (spouse) spousesIds.add(String(spouse.id_osoby));
        }

        const personIdStr = String(person.id_osoby);
        const personDbId = person.db_id;

        context.genealogy.forEach(otherPerson => {
            let match = false;
            if (String(otherPerson.id_malzonka) === personIdStr) match = true;
            if (personDbId && otherPerson.id_malzonka == personDbId) match = true;

            if (otherPerson.marriages) {
                otherPerson.marriages.forEach(marriage => {
                    if (String(marriage.spouseId) === personIdStr) match = true;
                    if (personDbId && marriage.spouseDbId == personDbId) match = true;
                });
            }

            if (match) spousesIds.add(String(otherPerson.id_osoby));
        });

        return Array.from(spousesIds).map(id => {
            const spouse = context.peopleMap.get(id);
            return spouse ? { ...spouse, role: 'Małżonek' } : null;
        }).filter(Boolean);
    }

    function findSiblings(person, context) {
        const siblingsSet = new Set();
        const personIdStr = String(person.id_osoby);

        if (person.id_ojca) {
            const father = context.getPersonById(person.id_ojca);
            if (father) {
                const children = context.childrenMap.get(String(father.id_osoby)) || [];
                children.forEach(id => {
                    if (id !== personIdStr) siblingsSet.add(id);
                });
            }
        }

        if (person.id_matki) {
            const mother = context.getPersonById(person.id_matki);
            if (mother) {
                const children = context.childrenMap.get(String(mother.id_osoby)) || [];
                children.forEach(id => {
                    if (id !== personIdStr) siblingsSet.add(id);
                });
            }
        }

        return Array.from(siblingsSet).map(id => {
            const sibling = context.peopleMap.get(id);
            return sibling ? { ...sibling, role: 'Rodzeństwo' } : null;
        }).filter(Boolean);
    }

    function findChildren(personId, context) {
        const person = context.getPersonById(personId);
        if (!person) return [];

        const childrenIds = context.childrenMap.get(String(person.id_osoby)) || [];
        return childrenIds.map(id => {
            const child = context.peopleMap.get(id);
            return child ? { ...child, role: 'Dziecko' } : null;
        }).filter(Boolean)
            .sort((a, b) => (a.rok_urodzenia || 9999) - (b.rok_urodzenia || 9999));
    }

    function findCousins(person, context) {
        const cousinsSet = new Set();
        const parents = findParents(person, context);

        parents.forEach(parent => {
            const parentSiblings = findSiblings(parent, context);
            parentSiblings.forEach(uncleAunt => {
                const uncleAuntChildren = findChildren(uncleAunt.id_osoby, context);
                uncleAuntChildren.forEach(cousin => {
                    cousinsSet.add(String(cousin.id_osoby));
                });
            });
        });

        return Array.from(cousinsSet).map(id => {
            const cousin = context.getPersonById(id);
            if (cousin) {
                const role = cousin.plec === 'M' ? 'Kuzyn' : (cousin.plec === 'F' ? 'Kuzynka' : 'Kuzynostwo');
                return { ...cousin, role };
            }
            return null;
        }).filter(Boolean);
    }

    function createRelationCard(person, role) {
        if (!person || !person.id_osoby) {
            return `
                <div class="relation-card unknown">
                    <div class="relation-role">${role || '?'}</div>
                    <div class="relation-name">?</div>
                    <div class="relation-dates">? - ?</div>
                </div>
            `;
        }

        const genderClass = person.plec === 'M' ? 'male' : (person.plec === 'F' ? 'female' : '');

        return `
            <div class="relation-card ${genderClass}" data-person-id="${person.id_osoby}">
                <div class="relation-role">${role || person.role || ''}</div>
                <div class="relation-name">${person.imie} ${person.nazwisko || ''}</div>
                <div class="relation-dates">${formatLifespan(person)}</div>
            </div>
        `;
    }

    function renderRelationSection(title, relations) {
        if (!relations || relations.length === 0) return '';
        return `
            <div class="section-title"><i class="fas fa-users"></i> ${title}</div>
            <div class="relations-grid">
                ${relations.map(relation => createRelationCard(relation, relation.role)).join('')}
            </div>
        `;
    }

    function showPersonDetails(person, allGenealogy, callbacks = {}) {
        const detailsPanel = document.getElementById('personDetailsPanel');
        if (!person || !detailsPanel) return;

        const context = buildContext(allGenealogy);
        const onEdit = callbacks.onEdit || function () { };
        const onDelete = callbacks.onDelete || function () { };
        const onShowTree = callbacks.onShowTree || function () { };
        const onShowFullTree = callbacks.onShowFullTree || function () { };

        document.querySelectorAll('.person-list-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`.person-list-item[data-person-id="${person.id_osoby}"]`)?.classList.add('active');

        const grandparentsFather = findGrandparents(person, 'father', context);
        const grandparentsMother = findGrandparents(person, 'mother', context);
        const parents = findParents(person, context);
        const spouses = findSpouses(person, context);
        const siblings = findSiblings(person, context);
        const children = findChildren(person.id_osoby, context);
        const cousins = findCousins(person, context);

        const genderText = person.plec === 'M' ? 'Mężczyzna' : (person.plec === 'F' ? 'Kobieta' : '?');
        const houseDisplay = person.numer_domu ? `Dom ${person.numer_domu}` : 'Dom ?';

        let html = `
            <div class="profile-header">
                <div class="profile-title">
                    <h1>${person.imie} ${person.nazwisko || ''}</h1>
                    <div class="profile-id">ID: ${person.id_osoby} • ${genderText} • ${formatLifespan(person)}</div>
                </div>
                <div class="profile-actions">
                    <div style="font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem;">${houseDisplay}</div>
                    ${person.protokol_klucz ? `
                        <a href="../wlasciciele/protokol.html?ownerId=${person.protokol_klucz}" class="btn btn-secondary">
                            <i class="fas fa-file-alt"></i> Protokół
                        </a>
                    ` : ''}
                    <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                        <button class="btn btn-primary tree-btn" data-person-id="${person.id_osoby}">
                            <i class="fas fa-sitemap"></i> Drzewo mini
                        </button>
                        <button class="btn btn-secondary full-tree-btn" data-person-id="${person.id_osoby}">
                            <i class="fas fa-project-diagram"></i> Pełne drzewo
                        </button>
                        <button class="btn btn-secondary edit-btn" data-db-id="${person.db_id}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-danger delete-btn" data-db-id="${person.db_id}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

        if (person.uwagi) {
            html += `
                <div class="section-title"><i class="fas fa-sticky-note"></i> Notatki</div>
                <p style="margin-bottom: 1.5rem; color: var(--text-secondary); line-height: 1.8; font-size: 0.95rem; background: var(--bg-card); padding: 1rem; border-radius: 8px; border-left: 4px solid var(--primary-color);">${person.uwagi}</p>
            `;
        }

        html += '<div class="section-title" style="font-size: 1rem;"><i class="fas fa-users"></i> RODZINA</div>';

        if (grandparentsFather.length > 0 || grandparentsMother.length > 0) {
            html += '<div class="section-title">Dziadkowie</div>';

            if (grandparentsFather.length > 0) {
                html += `
                    <div class="section-subtitle">od strony ojca:</div>
                    <div class="relations-grid">
                        ${grandparentsFather.map(grandparent => createRelationCard(grandparent, grandparent.role)).join('')}
                    </div>
                `;
            }

            if (grandparentsMother.length > 0) {
                html += `
                    <div class="section-subtitle">od strony matki:</div>
                    <div class="relations-grid">
                        ${grandparentsMother.map(grandparent => createRelationCard(grandparent, grandparent.role)).join('')}
                    </div>
                `;
            }
        }

        html += renderRelationSection('Rodzice', parents);
        html += renderRelationSection('Małżonkowie', spouses);
        html += renderRelationSection('Rodzeństwo', siblings);
        html += renderRelationSection('Dzieci', children);
        html += renderRelationSection('Kuzynostwo', cousins);

        if (parents.length === 0 && spouses.length === 0 && siblings.length === 0 &&
            children.length === 0 && cousins.length === 0 &&
            grandparentsFather.length === 0 && grandparentsMother.length === 0) {
            html += `
                <p style="color: var(--text-light); font-style: italic; padding: 1rem;">
                    Brak powiązań rodzinnych w bazie danych.
                </p>
            `;
        }

        detailsPanel.innerHTML = html;

        detailsPanel.querySelectorAll('.relation-card[data-person-id]').forEach(card => {
            card.addEventListener('click', () => {
                const personId = card.dataset.personId;
                const targetPerson = context.peopleMap.get(String(personId));
                if (targetPerson) {
                    showPersonDetails(targetPerson, context.genealogy, callbacks);
                    const listItem = document.querySelector(`.person-list-item[data-person-id="${personId}"]`);
                    if (listItem) listItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            });
        });

        detailsPanel.querySelector('.edit-btn')?.addEventListener('click', () => onEdit(person.db_id));
        detailsPanel.querySelector('.delete-btn')?.addEventListener('click', () => onDelete(person.db_id));
        detailsPanel.querySelector('.tree-btn')?.addEventListener('click', () => onShowTree(person, context.genealogy));
        detailsPanel.querySelector('.full-tree-btn')?.addEventListener('click', () => onShowFullTree(person, context.genealogy));
    }

    window.AdminGenealogyDetails = Object.freeze({
        show: showPersonDetails
    });
})();
