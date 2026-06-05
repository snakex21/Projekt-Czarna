/**
 * Drzewo genealogiczne protokołu właściciela (P2.7 Etap 4).
 * Moduł pobiera dane genealogii, renderuje drzewo HTML i obsługuje dialog.
 */
(function () {
    'use strict';

    const API = window.OwnersAPI;

    let ownerKey = null;
    let elements = {
        showTreeBtn: null,
        treeDialog: null,
        closeTreeBtn: null,
        treeContainer: null,
    };

    function init(options) {
        const config = options || {};
        ownerKey = config.ownerKey || ownerKey;
        elements = Object.assign({}, elements, config.elements || {});
        bindEvents(ownerKey, elements);
    }

    function bindEvents(boundOwnerKey, boundElements) {
        if (boundElements.showTreeBtn && !boundElements.showTreeBtn.dataset.protocolGenealogyTreeBound) {
            boundElements.showTreeBtn.addEventListener('click', () => load(boundOwnerKey, boundElements));
            boundElements.showTreeBtn.dataset.protocolGenealogyTreeBound = 'true';
        }
        if (boundElements.closeTreeBtn && !boundElements.closeTreeBtn.dataset.protocolGenealogyTreeBound) {
            boundElements.closeTreeBtn.addEventListener('click', () => close(boundElements));
            boundElements.closeTreeBtn.dataset.protocolGenealogyTreeBound = 'true';
        }
    }

    async function load(selectedOwnerKey, selectedElements) {
        ownerKey = selectedOwnerKey || ownerKey;
        const activeElements = selectedElements || elements;
        setLoading(true, activeElements);
        try {
            const response = await fetch(API.genealogy(ownerKey));
            const treeData = await response.json();
            render(treeData, activeElements);
        } catch (error) {
            console.error('Błąd ładowania drzewa:', error);
            alert('Nie udało się załadować drzewa genealogicznego');
        } finally {
            setLoading(false, activeElements);
        }
    }

    function setLoading(isLoading, selectedElements) {
        const activeElements = selectedElements || elements;
        if (!activeElements.showTreeBtn) return;
        activeElements.showTreeBtn.disabled = isLoading;
        activeElements.showTreeBtn.innerHTML = isLoading
            ? '<i class="fas fa-spinner fa-spin"></i> Ładowanie...'
            : '<i class="fas fa-project-diagram"></i> Pokaż drzewo genealogiczne';
    }

    function render(treeData, selectedElements) {
        const activeElements = selectedElements || elements;
        if (!treeData.persons || treeData.persons.length === 0) {
            alert('Brak danych genealogicznych do wyświetlenia');
            return;
        }

        const maps = buildMaps(treeData.persons);
        const rootPerson = maps.personMap.get(treeData.rootId);
        if (!rootPerson) {
            alert('Nie znaleziono osoby głównej');
            return;
        }

        const family = collectFamily(rootPerson, maps);
        activeElements.treeContainer.innerHTML = buildTreeHtml(rootPerson, family);
        bindScrollControls(activeElements);
        open(activeElements);
    }

    function buildMaps(persons) {
        const personMap = new Map();
        const childrenMap = new Map();
        persons.forEach(person => {
            personMap.set(person.id, person);
            addChild(childrenMap, person.fatherId, person.id);
            addChild(childrenMap, person.motherId, person.id);
        });
        return { personMap, childrenMap };
    }

    function addChild(childrenMap, parentId, childId) {
        if (!parentId) return;
        if (!childrenMap.has(parentId)) childrenMap.set(parentId, []);
        childrenMap.get(parentId).push(childId);
    }

    function collectFamily(rootPerson, maps) {
        const father = maps.personMap.get(rootPerson.fatherId);
        const mother = maps.personMap.get(rootPerson.motherId);
        const parents = [withRole(father, getParentRole), withRole(mother, getParentRole)].filter(Boolean);
        const grandparentsFather = father ? [
            withRole(maps.personMap.get(father.fatherId), getGrandparentRole),
            withRole(maps.personMap.get(father.motherId), getGrandparentRole),
        ].filter(Boolean) : [];
        const grandparentsMother = mother ? [
            withRole(maps.personMap.get(mother.fatherId), getGrandparentRole),
            withRole(maps.personMap.get(mother.motherId), getGrandparentRole),
        ].filter(Boolean) : [];
        const spouses = (rootPerson.spouseIds || [])
            .map(id => maps.personMap.get(id)).filter(Boolean).map(person => ({ role: 'Małżonek', ...person }));
        const children = idsToPeople(maps.childrenMap.get(rootPerson.id), maps.personMap)
            .map(person => ({ role: 'Dziecko', ...person }));
        const siblingIds = new Set();
        [rootPerson.fatherId, rootPerson.motherId].filter(Boolean).forEach(parentId => {
            (maps.childrenMap.get(parentId) || []).forEach(id => {
                if (id !== rootPerson.id) siblingIds.add(id);
            });
        });
        const siblings = idsToPeople(Array.from(siblingIds), maps.personMap)
            .map(person => ({ role: 'Rodzeństwo', ...person }));
        return { parents, grandparentsFather, grandparentsMother, spouses, children, siblings };
    }

    function withRole(person, roleFactory) {
        return person ? { role: roleFactory(person), ...person } : null;
    }

    function idsToPeople(ids, personMap) {
        return (ids || []).map(id => personMap.get(id)).filter(Boolean);
    }

    function getParentRole(person) {
        return person?.gender === 'M' ? 'Ojciec' : (person?.gender === 'F' ? 'Matka' : 'Rodzic');
    }

    function getGrandparentRole(person) {
        return person?.gender === 'M' ? 'Dziadek' : (person?.gender === 'F' ? 'Babcia' : 'Dziadek/Babcia');
    }

    function buildTreeHtml(rootPerson, family) {
        let html = treeStyles() + '<div class="tree-scroll-wrapper"><div class="tree-content">';
        html += renderGrandparents(family.grandparentsFather, family.grandparentsMother);
        html += renderParents(family.parents);
        html += '<div class="tree-with-siblings">';
        html += renderSiblings(family.siblings);
        html += renderMainColumn(rootPerson, family.spouses, family.children);
        html += '</div></div></div>';
        html += renderScrollControl();
        return html;
    }

    function renderGrandparents(grandparentsFather, grandparentsMother) {
        if (grandparentsFather.length === 0 && grandparentsMother.length === 0) return '';
        let html = '<div class="generation-label">Dziadkowie</div><div class="tree-level" style="gap: 4rem;">';
        html += renderGrandparentBranch('od ojca', grandparentsFather);
        html += renderGrandparentBranch('od matki', grandparentsMother);
        return `${html}</div><div class="tree-connector-down"></div>`;
    }

    function renderGrandparentBranch(label, people) {
        if (people.length === 0) return '';
        return `<div class="tree-branch"><div style="font-size: 0.6rem; color: #888; margin-bottom: 0.25rem;">${label}</div><div class="tree-pair">${renderNodePair(people, false)}</div></div>`;
    }

    function renderParents(parents) {
        if (parents.length === 0) return '';
        return `<div class="generation-label">Rodzice</div><div class="tree-level"><div class="tree-pair">${renderNodePair(parents, true)}</div></div><div class="tree-connector-down"></div>`;
    }

    function renderSiblings(siblings) {
        if (siblings.length === 0) return '';
        return `<div class="tree-siblings-section"><div class="section-label">Rodzeństwo</div><div class="tree-siblings-grid">${siblings.map(person => renderTreeNode(person)).join('')}</div></div>`;
    }

    function renderMainColumn(rootPerson, spouses, children) {
        let html = '<div class="tree-main-column"><div class="generation-label">Główna osoba</div><div class="tree-pair">';
        html += renderTreeNode(rootPerson, true);
        if (spouses.length > 0) html += `<div class="tree-pair-connector"></div>${renderTreeNode(spouses[0])}`;
        html += '</div>';
        if (children.length > 0) html += `<div class="tree-connector-down"></div><div class="generation-label">Dzieci</div>${renderChildren(children)}`;
        return `${html}</div>`;
    }

    function renderChildren(children) {
        const connector = children.length > 1
            ? `<div class="tree-children-connector" style="width: ${(children.length - 1) * 160}px; left: calc(50% - ${((children.length - 1) * 160) / 2}px);"></div>`
            : '';
        return `<div class="tree-children">${connector}${children.map(child => `<div class="tree-child-branch">${renderTreeNode(child)}</div>`).join('')}</div>`;
    }

    function renderNodePair(people, showRole) {
        return people.map((person, index) => `${index > 0 ? '<div class="tree-pair-connector"></div>' : ''}${renderTreeNode(person, false, showRole)}`).join('');
    }

    function renderTreeNode(person, isRoot = false, showRole = true) {
        const bgColor = isRoot ? '#fff3cd' : (person.gender === 'M' ? '#e3f2fd' : '#fce4ec');
        const borderColor = isRoot ? '#f57f17' : (person.gender === 'M' ? '#1976d2' : '#c2185b');
        const cursor = person.protocolKey ? 'pointer' : 'default';
        const click = person.protocolKey ? `window.open('../wlasciciele/protokol.html?ownerId=${person.protocolKey}', '_blank')` : '';
        const role = showRole && person.role ? `<div style="font-size: 0.6rem; text-transform: uppercase; color: #888; margin-bottom: 0.2rem;">${person.role}</div>` : '';
        const protocolIcon = person.protocolKey ? '<div style="font-size: 0.65rem; color: #007bff; margin-top: 0.2rem;">📜</div>' : '';
        return `<div class="tree-node" style="background: ${bgColor}; border: 2px solid ${borderColor}; border-radius: 10px; padding: 0.75rem 1rem; min-width: 140px; max-width: 180px; text-align: center; cursor: ${cursor}; transition: all 0.2s; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" onclick="${click}" title="${person.protocolKey ? 'Kliknij aby otworzyć protokół' : person.name}">${role}<div style="font-weight: 700; font-size: 0.85rem; color: #333;">${person.name}</div><div style="font-size: 0.7rem; color: #666; margin-top: 0.2rem;">${formatYears(person)}</div>${protocolIcon}</div>`;
    }

    function formatYears(person) {
        return `${person.birthDate?.year || '?'} - ${person.deathDate?.year || '?'}`;
    }

    function treeStyles() {
        return `<style>
            .tree-content{display:flex;flex-direction:column;align-items:center;gap:0;padding:1.5rem;min-width:max-content;width:max-content}.tree-scroll-wrapper{min-width:max-content;display:inline-block;padding:1rem;box-sizing:border-box}.tree-level{display:flex;justify-content:center;gap:2rem;position:relative;min-width:max-content}.tree-connector-down{width:2px;height:30px;background:#ccc;margin:0 auto}.tree-pair{display:flex;align-items:center;gap:.5rem;min-width:max-content}.tree-pair-connector{width:30px;height:2px;background:#e74c3c;position:relative;flex-shrink:0}.tree-pair-connector::after{content:'💕';position:absolute;top:-10px;left:50%;transform:translateX(-50%);font-size:14px}.tree-branch,.tree-main-column,.tree-siblings-section,.tree-child-branch{display:flex;flex-direction:column;align-items:center}.tree-with-siblings{display:flex;align-items:flex-start;gap:2rem;min-width:max-content}.tree-siblings-section{opacity:.8;padding-top:1.5rem}.tree-siblings-grid{display:flex;gap:.5rem;justify-content:center;min-width:max-content}.tree-children{display:flex;justify-content:center;gap:1rem;position:relative;padding-top:30px;min-width:max-content}.tree-children::before{content:'';position:absolute;top:0;left:50%;width:2px;height:15px;background:#ccc}.tree-children-connector{position:absolute;top:15px;height:2px;background:#ccc}.tree-child-branch{flex-shrink:0}.tree-child-branch::before{content:'';width:2px;height:15px;background:#ccc}.generation-label{font-size:.7rem;text-transform:uppercase;letter-spacing:1px;color:#888;margin:1rem 0 .5rem;font-weight:700}.section-label{font-size:.6rem;text-transform:uppercase;letter-spacing:1px;color:#999;margin-bottom:.5rem;font-weight:600}
        </style>`;
    }

    function renderScrollControl() {
        return `<div class="tree-horizontal-scroll-control"><button class="scroll-arrow scroll-left" title="Przewiń w lewo"><i class="fas fa-chevron-left"></i></button><input type="range" class="horizontal-scroll-slider" min="0" max="100" value="50" title="Przesuń drzewo w lewo/prawo"><button class="scroll-arrow scroll-right" title="Przewiń w prawo"><i class="fas fa-chevron-right"></i></button></div>`;
    }

    function bindScrollControls(selectedElements) {
        const activeElements = selectedElements || elements;
        const treeContainer = activeElements.treeContainer;
        const scrollWrapper = treeContainer.querySelector('.tree-scroll-wrapper');
        const slider = treeContainer.querySelector('.horizontal-scroll-slider');
        if (!scrollWrapper || !slider) return;

        const updateSlider = () => {
            const maxScroll = treeContainer.scrollWidth - treeContainer.clientWidth;
            slider.parentElement.style.display = maxScroll > 0 ? 'flex' : 'none';
            if (maxScroll > 0) slider.value = (treeContainer.scrollLeft / maxScroll) * 100;
        };
        slider.addEventListener('input', () => {
            const maxScroll = treeContainer.scrollWidth - treeContainer.clientWidth;
            treeContainer.scrollLeft = (slider.value / 100) * maxScroll;
        });
        treeContainer.querySelector('.scroll-left').addEventListener('click', () => treeContainer.scrollBy({ left: -200, behavior: 'smooth' }));
        treeContainer.querySelector('.scroll-right').addEventListener('click', () => treeContainer.scrollBy({ left: 200, behavior: 'smooth' }));
        treeContainer.addEventListener('scroll', updateSlider);
        setTimeout(updateSlider, 100);
    }

    function open(selectedElements) {
        const activeElements = selectedElements || elements;
        const dialogTitle = activeElements.treeDialog.querySelector('.dialog-header h3');
        if (dialogTitle) {
            dialogTitle.innerHTML = `<i class="fas fa-sitemap"></i> Drzewo Genealogiczne <span style="font-size: 0.7rem; font-weight: normal; margin-left: 15px; color: #e0e0e0;">(Legenda: 💙 Mężczyzna | 💗 Kobieta | 💛 Właściciel | 💕 Małżeństwo)</span>`;
        }
        activeElements.treeDialog.showModal();
    }

    function close(selectedElements) {
        const activeElements = selectedElements || elements;
        if (!activeElements.treeDialog) return;
        activeElements.treeDialog.close();
        if (activeElements.treeContainer) activeElements.treeContainer.innerHTML = '';
    }

    window.ProtocolGenealogyTree = Object.freeze({
        init: init,
        load: load,
        render: render,
        open: open,
        close: close,
    });
})();
