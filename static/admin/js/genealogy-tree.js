/**
 * Pełne drzewo genealogiczne w panelu admina (P2.5 Etap 13).
 *
 * Moduł zastępuje legacy renderer i używa danych już załadowanych przez panel
 * admina. Nie wykonuje własnych fetchy i korzysta z istniejącego modala
 * `treeModal` / `treeContainer` z admin.html.
 */
(function () {
    'use strict';

    let treeContainerId = 'treeContainer';

    function setTreeContainer(containerId) {
        if (document.getElementById(containerId)) {
            treeContainerId = containerId;
        }
    }

    function getPersonId(person) {
        if (!person) return null;
        return person.id_osoby || person.id || person.db_id || null;
    }

    function normalizePerson(person) {
        const id = getPersonId(person);
        return {
            id: id,
            dbId: person.db_id || null,
            name: `${person.imie || ''} ${person.nazwisko || ''}`.trim() || person.name || `ID ${id}`,
            gender: person.plec || person.gender || '',
            birth: person.rok_urodzenia || person.birth || null,
            death: person.rok_smierci || person.death || null,
            fatherId: person.id_ojca || person.ojciec_id || null,
            motherId: person.id_matki || person.matka_id || null,
            spouseId: person.id_malzonka || person.malzonek_id || null,
            protocolKey: person.protokol_klucz || person.unikalny_klucz || null,
            raw: person,
        };
    }

    function buildContext(allGenealogy) {
        const people = (Array.isArray(allGenealogy) ? allGenealogy : []).map(normalizePerson);
        const byId = new Map();
        const byDbId = new Map();
        people.forEach(person => {
            if (person.id !== null && person.id !== undefined) byId.set(String(person.id), person);
            if (person.dbId !== null && person.dbId !== undefined) byDbId.set(String(person.dbId), person);
        });

        function getPersonById(id) {
            if (!id && id !== 0) return null;
            const idStr = String(id);
            return byId.get(idStr) || byDbId.get(idStr) || null;
        }

        const childrenMap = new Map();
        people.forEach(person => {
            [person.fatherId, person.motherId].forEach(parentId => {
                const parent = getPersonById(parentId);
                if (!parent) return;
                const key = String(parent.id);
                if (!childrenMap.has(key)) childrenMap.set(key, []);
                childrenMap.get(key).push(person);
            });
        });

        return { people, byId, getPersonById, childrenMap };
    }

    function formatYears(person) {
        if (!person) return '';
        if (!person.birth && !person.death) return '';
        const birth = person.birth || '?';
        const death = person.death || '?';
        return `${birth}–${death}`;
    }

    function nodeClass(person, isRoot) {
        if (isRoot) return 'tree-node tree-node-root';
        if (person.gender === 'M') return 'tree-node tree-node-male';
        if (person.gender === 'F') return 'tree-node tree-node-female';
        return 'tree-node';
    }

    function collectAncestors(root, context, depth) {
        const levels = [];
        let current = [root];
        for (let level = 0; level < depth; level++) {
            const parents = [];
            current.forEach(person => {
                const father = context.getPersonById(person.fatherId);
                const mother = context.getPersonById(person.motherId);
                if (father) parents.push(father);
                if (mother) parents.push(mother);
            });
            if (!parents.length) break;
            levels.unshift(uniquePeople(parents));
            current = parents;
        }
        return levels;
    }

    function collectDescendantLevels(root, context, maxDepth) {
        const levels = [];
        let current = [root];
        for (let depth = 0; depth < maxDepth; depth++) {
            const children = [];
            current.forEach(person => {
                const personChildren = context.childrenMap.get(String(person.id)) || [];
                children.push(...personChildren);
            });
            const uniqueChildren = uniquePeople(children);
            if (!uniqueChildren.length) break;
            levels.push(uniqueChildren);
            current = uniqueChildren;
        }
        return levels;
    }

    function uniquePeople(people) {
        const seen = new Set();
        return people.filter(person => {
            const key = String(person.id);
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }

    function renderNode(person, rootId) {
        const isRoot = String(person.id) === String(rootId);
        const protocol = person.protocolKey
            ? `<a href="../wlasciciele/protokol.html?ownerId=${person.protocolKey}" class="tree-protocol-link">📜 Protokół</a>`
            : '';
        return `
            <div class="${nodeClass(person, isRoot)}" data-full-tree-person-id="${person.id}" title="Kliknij osobę, aby ustawić ją w centrum">
                <div style="font-weight: 700; font-size: 0.9rem;">${person.name}</div>
                <div style="font-size: 0.72rem; color: var(--text-secondary); margin-top: 0.25rem;">${formatYears(person)}</div>
                ${protocol}
            </div>
        `;
    }

    function renderLevel(label, people, rootId) {
        if (!people.length) return '';
        return `
            <div class="generation-label">${label}</div>
            <div class="tree-level full-tree-level">
                ${people.map(person => renderNode(person, rootId)).join('')}
            </div>
            <div class="tree-connector-down"></div>
        `;
    }

    function drawTree(containerId, rootPerson, allGenealogy) {
        const container = document.getElementById(containerId || treeContainerId);
        if (!container) return;

        const context = buildContext(allGenealogy);
        const normalizedRoot = normalizePerson(rootPerson || {});
        const root = context.getPersonById(normalizedRoot.id) || normalizedRoot;

        if (!root || !root.id) {
            container.innerHTML = '<div class="no-data"><h3>Brak danych genealogicznych do wyświetlenia</h3></div>';
            return;
        }

        const ancestorLevels = collectAncestors(root, context, 4);
        const descendantLevels = collectDescendantLevels(root, context, 4);
        const spouse = context.getPersonById(root.spouseId);

        let html = '<div class="tree-scroll-wrapper"><div class="tree-container full-tree-container">';
        ancestorLevels.forEach((level, index) => {
            const distance = ancestorLevels.length - index;
            const label = distance === 1 ? 'Rodzice' : `${distance}. pokolenie przodków`;
            html += renderLevel(label, level, root.id);
        });

        html += '<div class="generation-label">Główna osoba</div>';
        html += '<div class="tree-level full-tree-level">';
        html += renderNode(root, root.id);
        if (spouse) html += renderNode(spouse, root.id);
        html += '</div>';

        descendantLevels.forEach((level, index) => {
            html += '<div class="tree-connector-down"></div>';
            html += renderLevel(index === 0 ? 'Dzieci' : `${index + 1}. pokolenie potomków`, level, root.id);
        });

        html += '</div></div>';
        container.innerHTML = html;

        container.querySelectorAll('[data-full-tree-person-id]').forEach(node => {
            node.addEventListener('click', () => {
                const nextRoot = context.getPersonById(node.dataset.fullTreePersonId);
                if (nextRoot) showFromData(nextRoot.raw || nextRoot, allGenealogy);
            });
        });
    }

    function showFromData(rootPerson, allGenealogy) {
        const modal = document.getElementById('treeModal');
        const modalTitle = document.getElementById('treeModalTitle');
        const container = document.getElementById(treeContainerId);
        const closeBtn = document.getElementById('treeModalClose');

        if (!modal || !modalTitle || !container) {
            console.error('Nie znaleziono elementów modala pełnego drzewa');
            return;
        }

        const titleName = `${rootPerson?.imie || ''} ${rootPerson?.nazwisko || ''}`.trim() || rootPerson?.name || 'Rodzina';
        modalTitle.innerHTML = `🌳 Pełne drzewo: ${titleName} <span style="margin-left: 2rem; font-size: 0.7rem; font-weight: 400; color: var(--text-secondary);">Kliknij osobę, aby ustawić ją w centrum</span>`;
        drawTree(treeContainerId, rootPerson, allGenealogy);

        modal.classList.remove('hidden');
        document.body.classList.add('modal-open');

        const closeModal = () => {
            modal.classList.add('hidden');
            document.body.classList.remove('modal-open');
        };

        if (closeBtn) closeBtn.onclick = closeModal;
        modal.onclick = (event) => { if (event.target === modal) closeModal(); };
    }

    function showGenealogyTree(rootPerson, allGenealogy) {
        showFromData(rootPerson, allGenealogy);
    }

    window.AdminGenealogyTree = Object.freeze({
        show: showGenealogyTree,
        showFromData: showFromData,
        render: drawTree,
        setContainer: setTreeContainer,
    });
})();
