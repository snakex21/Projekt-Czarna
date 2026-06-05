(function () {
    'use strict';

    function getPersonById(id, allGenealogy) {
        if (!id) return null;
        return allGenealogy.find(p => p.id_osoby == id || p.db_id == id) || null;
    }

    function formatYears(person) {
        if (!person) return '';
        const birth = person.rok_urodzenia || '?';
        const death = person.rok_smierci || '?';
        return `${birth} - ${death}`;
    }

    function getNodeClass(person, isRoot = false) {
        if (isRoot) return 'tree-node tree-node-root';
        if (person?.plec === 'M') return 'tree-node tree-node-male';
        if (person?.plec === 'F') return 'tree-node tree-node-female';
        return 'tree-node';
    }

    function renderTreeNode(person, isRoot = false, showRole = true) {
        if (!person) return '';
        return `
            <div class="${getNodeClass(person, isRoot)}"
                 onclick="window.showMiniTreeForPerson && window.showMiniTreeForPerson('${person.id_osoby}')"
                 title="Kliknij aby zobaczyć drzewo tej osoby">
                ${showRole && person.role ? `<div style="font-size: 0.6rem; text-transform: uppercase; color: var(--text-tertiary); margin-bottom: 0.2rem;">${person.role}</div>` : ''}
                <div style="font-weight: 700; font-size: 0.85rem;">
                    ${person.imie} ${person.nazwisko || ''}
                </div>
                <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 0.2rem;">
                    ${formatYears(person)}
                </div>
            </div>
        `;
    }

    function showMiniTree(rootPerson, allGenealogy) {
        const genealogy = Array.isArray(allGenealogy) ? allGenealogy : [];
        const modal = document.getElementById('treeModal');
        const modalTitle = document.getElementById('treeModalTitle');
        const treeContainer = document.getElementById('treeContainer');
        const closeBtn = document.getElementById('treeModalClose');

        if (!modal || !modalTitle || !treeContainer) {
            console.error('Nie znaleziono elementów modala drzewa');
            return;
        }

        const findPerson = (id) => getPersonById(id, genealogy);
        const father = findPerson(rootPerson.id_ojca);
        const mother = findPerson(rootPerson.id_matki);

        const grandparentsFather = [];
        const grandparentsMother = [];

        if (father) {
            const gf = findPerson(father.id_ojca);
            const gm = findPerson(father.id_matki);
            if (gf) grandparentsFather.push({ role: 'Dziadek', ...gf });
            if (gm) grandparentsFather.push({ role: 'Babcia', ...gm });
        }
        if (mother) {
            const gf = findPerson(mother.id_ojca);
            const gm = findPerson(mother.id_matki);
            if (gf) grandparentsMother.push({ role: 'Dziadek', ...gf });
            if (gm) grandparentsMother.push({ role: 'Babcia', ...gm });
        }

        const parents = [];
        if (father) parents.push({ role: 'Ojciec', ...father });
        if (mother) parents.push({ role: 'Matka', ...mother });

        const spouses = [];
        if (rootPerson.marriages && rootPerson.marriages.length > 0) {
            rootPerson.marriages.forEach(m => {
                const spouse = findPerson(m.spouseId);
                if (spouse) spouses.push({ role: 'Małżonek', ...spouse });
            });
        } else if (rootPerson.id_malzonka) {
            const spouse = findPerson(rootPerson.id_malzonka);
            if (spouse) spouses.push({ role: 'Małżonek', ...spouse });
        }

        const siblingIds = new Set();
        if (rootPerson.id_ojca) {
            genealogy.filter(p => p.id_ojca === rootPerson.id_ojca && p.id_osoby !== rootPerson.id_osoby)
                .forEach(p => siblingIds.add(p.id_osoby));
        }
        if (rootPerson.id_matki) {
            genealogy.filter(p => p.id_matki === rootPerson.id_matki && p.id_osoby !== rootPerson.id_osoby)
                .forEach(p => siblingIds.add(p.id_osoby));
        }
        const siblings = Array.from(siblingIds).map(id => {
            const person = findPerson(id);
            return person ? { role: 'Rodzeństwo', ...person } : null;
        }).filter(Boolean);

        const children = genealogy.filter(p =>
            p.id_ojca === rootPerson.id_osoby || p.id_matki === rootPerson.id_osoby
        ).map(p => ({ role: 'Dziecko', ...p }));

        let html = '<div class="tree-scroll-wrapper"><div class="tree-container">';

        if (grandparentsFather.length > 0 || grandparentsMother.length > 0) {
            html += '<div class="generation-label">Dziadkowie</div>';
            html += '<div class="tree-level" style="gap: 4rem;">';

            if (grandparentsFather.length > 0) {
                html += '<div class="tree-branch"><div style="font-size: 0.6rem; color: var(--text-tertiary); margin-bottom: 0.25rem;">od ojca</div><div class="tree-pair">';
                grandparentsFather.forEach((gp, i) => {
                    if (i > 0) html += '<div class="tree-pair-connector"></div>';
                    html += renderTreeNode(gp, false, false);
                });
                html += '</div></div>';
            }

            if (grandparentsMother.length > 0) {
                html += '<div class="tree-branch"><div style="font-size: 0.6rem; color: var(--text-tertiary); margin-bottom: 0.25rem;">od matki</div><div class="tree-pair">';
                grandparentsMother.forEach((gp, i) => {
                    if (i > 0) html += '<div class="tree-pair-connector"></div>';
                    html += renderTreeNode(gp, false, false);
                });
                html += '</div></div>';
            }

            html += '</div>';
            html += '<div class="tree-connector-down"></div>';
        }

        if (parents.length > 0) {
            html += '<div class="generation-label">Rodzice</div>';
            html += '<div class="tree-level"><div class="tree-pair">';
            parents.forEach((person, i) => {
                if (i > 0) html += '<div class="tree-pair-connector"></div>';
                html += renderTreeNode(person);
            });
            html += '</div></div>';
            html += '<div class="tree-connector-down"></div>';
        }

        html += '<div class="tree-with-siblings">';

        if (siblings.length > 0) {
            html += '<div class="tree-siblings-section">';
            html += '<div class="section-label">Rodzeństwo</div>';
            html += '<div class="tree-siblings-grid">';
            siblings.forEach(sibling => {
                html += renderTreeNode(sibling, false, false);
            });
            html += '</div></div>';
        }

        html += '<div class="tree-main-column">';
        html += '<div class="generation-label">Główna osoba</div>';

        html += '<div class="tree-pair">';
        html += renderTreeNode({ ...rootPerson, role: null }, true, false);
        if (spouses.length > 0) {
            html += '<div class="tree-pair-connector"></div>';
            html += renderTreeNode(spouses[0], false, false);
        }
        html += '</div>';

        if (children.length > 0) {
            html += '<div class="tree-connector-down"></div>';
            html += '<div class="generation-label">Dzieci</div>';
            html += '<div class="tree-children">';

            if (children.length > 1) {
                const childWidth = 160;
                const connectorWidth = (children.length - 1) * childWidth;
                html += `<div class="tree-children-connector" style="width: ${connectorWidth}px; left: calc(50% - ${connectorWidth / 2}px);"></div>`;
            }

            children.forEach(child => {
                html += '<div class="tree-child-branch">';
                html += renderTreeNode(child, false, false);
                html += '</div>';
            });
            html += '</div>';
        }

        html += '</div>';
        html += '</div>';

        html += '</div></div>';
        treeContainer.innerHTML = html;

        modalTitle.innerHTML = `🌳 Drzewo: ${rootPerson.imie} ${rootPerson.nazwisko || ''} <span style="margin-left: 2rem; font-size: 0.7rem; font-weight: 400; color: var(--text-secondary);">💙 Mężczyzna | 💗 Kobieta | 💛 Główna osoba | 💕 Małżeństwo | Kliknij węzeł by nawigować</span>`;
        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');

        window.showMiniTreeForPerson = (personId) => {
            const person = findPerson(personId);
            if (person) showMiniTree(person, genealogy);
        };

        const closeModal = () => {
            modal.classList.add('hidden');
            document.body.classList.remove('modal-open');
        };

        if (closeBtn) closeBtn.onclick = closeModal;
        modal.onclick = (event) => { if (event.target === modal) closeModal(); };

        const escHandler = (event) => {
            if (event.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    window.AdminGenealogyMiniTree = Object.freeze({
        show: showMiniTree
    });
})();
