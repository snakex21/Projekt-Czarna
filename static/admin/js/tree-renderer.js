/**
 * Renderer drzewa genealogicznego (P2.5 Etap 4 - wydzielenie z admin.js).
 *
 * Odpowiada wyłącznie za rysowanie SVG/D3 dla przygotowanej listy osób.
 * Nie pobiera danych z backendu, nie zna endpointów API i nie obsługuje modali.
 *
 * Publiczne API: `window.AdminTreeRenderer = { render }`.
 */
(function () {
    'use strict';

    // Stałe konfiguracyjne dla rysowania drzewa
    const TREE_CONFIG = Object.freeze({
        NODE_HEIGHT: 80,
        NODE_MIN_W: 120,
        H_GAP: 80,
        V_GAP: 120,
        MARGIN: 80,
        FONT: '700 16px "Segoe UI", sans-serif',
        MARRIAGE_GAP: 20,
    });

    function render(container, persons, rootId = null) {
        container.innerHTML = '';

        if (!persons || persons.length === 0) {
            container.innerHTML = '<div style="padding: 2rem; text-align: center;">Brak danych do wyświetlenia</div>';
            return;
        }

        // Filtruj osoby - usuń wszystkie z undefined ID lub nazwą
        const validPersons = persons.filter(p =>
            p && p.id && p.name && !p.name.includes('undefined')
        );

        // Przygotowanie canvas do pomiaru tekstu
        const ctx = document.createElement("canvas").getContext("2d");
        ctx.font = TREE_CONFIG.FONT;
        const textWidth = (t) => ctx.measureText(t).width;

        // Mapa osób - tylko istniejące osoby
        const personMap = new Map();
        const existingIds = new Set(validPersons.map(p => String(p.id)));

        validPersons.forEach(p => {
            // Filtruj rodziców i małżonków - tylko jeśli istnieją w danych
            const validFatherId = p.fatherId && existingIds.has(String(p.fatherId)) ? String(p.fatherId) : null;
            const validMotherId = p.motherId && existingIds.has(String(p.motherId)) ? String(p.motherId) : null;
            const validSpouseIds = (p.spouseIds || []).filter(id => existingIds.has(String(id)));

            const rec = {
                nodeId: String(p.id),
                name: p.name,
                birth: p.birthDate?.year,
                death: p.deathDate?.year,
                gender: p.gender,
                ojciec_id: validFatherId,
                matka_id: validMotherId,
                malzonek_ids: validSpouseIds,
                key: p.protocolKey,
                isRoot: p.id === rootId,
                boxW: Math.max(TREE_CONFIG.NODE_MIN_W, Math.ceil(textWidth(p.name || '')) + 30),
                generation: 0,
                x: 0,
                y: 0,
            };
            personMap.set(String(p.id), rec);
        });

        // Pozycjonowanie węzłów
        const allNodes = positionTreeNodes(personMap);
        const { connections, marriages } = findTreeConnections(allNodes);

        if (allNodes.length === 0) {
            container.innerHTML = '<div style="padding: 2rem; text-align: center;">Brak danych do wyświetlenia</div>';
            return;
        }

        // Obliczenie wymiarów
        const xs = allNodes.map(n => [n.x, n.x + n.boxW]).flat();
        const ys = allNodes.map(n => n.y);
        const minX = Math.min(...xs) || 0;
        const maxX = Math.max(...xs) || 100;
        const minY = Math.min(...ys) || 0;
        const maxY = Math.max(...ys) || 100;
        const W = maxX - minX + 2 * TREE_CONFIG.MARGIN;
        const H = maxY - minY + TREE_CONFIG.NODE_HEIGHT + 2 * TREE_CONFIG.MARGIN;

        // Tworzenie SVG
        const svg = d3.create("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", `0 0 ${W} ${H}`)
            .call(
                d3.zoom()
                    .scaleExtent([0.2, 4])
                    .on("zoom", (e) => g.attr("transform", e.transform))
            );

        const g = svg.append("g")
            .attr("transform", `translate(${-minX + TREE_CONFIG.MARGIN}, ${-minY + TREE_CONFIG.MARGIN})`);

        // Rysowanie połączeń rodzic-dziecko
        g.append("g")
            .selectAll("path")
            .data(connections.filter(c => c.type === "parent-child"))
            .join("path")
            .attr("d", d => {
                const midY = (d.source.y + d.target.y) / 2;
                return `M${d.source.x},${d.source.y}V${midY}H${d.target.x}V${d.target.y}`;
            })
            .attr("stroke", "#999")
            .attr("stroke-width", 2)
            .attr("fill", "none");

        // Rysowanie linii małżeństw
        g.append("g")
            .selectAll("line")
            .data(marriages)
            .join("line")
            .attr("x1", ([left, right]) => left.x + left.boxW)
            .attr("y1", ([left, right]) => left.y + TREE_CONFIG.NODE_HEIGHT / 2)
            .attr("x2", ([left, right]) => right.x)
            .attr("y2", ([left, right]) => right.y + TREE_CONFIG.NODE_HEIGHT / 2)
            .attr("stroke", "#e74c3c")
            .attr("stroke-width", 3)
            .attr("stroke-dasharray", "5,5");

        // Kolory pokoleń
        const generationColors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"];
        const getColor = (generation) => generationColors[Math.abs(generation) % generationColors.length];

        // Rysowanie węzłów
        const ng = g.append("g")
            .selectAll("g")
            .data(allNodes)
            .join("g")
            .attr("transform", d => `translate(${d.x}, ${d.y})`)
            .style("cursor", "pointer")
            .on("click", (event, d) => {
                // Po kliknięciu pokaż info o osobie
                console.log('Kliknięto:', d.name);
            });

        // Prostokąty
        ng.append("rect")
            .attr("width", d => d.boxW)
            .attr("height", TREE_CONFIG.NODE_HEIGHT)
            .attr("rx", 8)
            .attr("fill", d => d.gender === 'F' ? "#FFE4E1" : "#E6F3FF")
            .attr("stroke", d => d.isRoot ? "#e74c3c" : getColor(d.generation))
            .attr("stroke-width", d => d.isRoot ? 3 : 2);

        // Ikona płci
        ng.append("text")
            .attr("x", 10)
            .attr("y", 25)
            .style("font-size", "18px")
            .text(d => d.gender === 'F' ? '♀' : '♂')
            .style("fill", d => d.gender === 'F' ? "#FF69B4" : "#4169E1");

        // Tekst - imię i nazwisko
        ng.append("text")
            .attr("x", d => d.boxW / 2)
            .attr("y", TREE_CONFIG.NODE_HEIGHT / 2 - 8)
            .attr("text-anchor", "middle")
            .style("font", "14px 'Segoe UI', sans-serif")
            .style("font-weight", "600")
            .text(d => d.name);

        // Daty
        ng.append("text")
            .attr("x", d => d.boxW / 2)
            .attr("y", TREE_CONFIG.NODE_HEIGHT / 2 + 12)
            .attr("text-anchor", "middle")
            .style("font-size", "12px")
            .style("fill", "#666")
            .text(d => {
                const b = d.birth, dd = d.death;
                return b && !dd ? `ur. ${b}` :
                    dd && !b ? `† ${dd}` :
                        b && dd ? `${b} – ${dd}` : "";
            });

        container.appendChild(svg.node());
    }

    function positionTreeNodes(personMap) {
        // Najpierw ustal generacje na podstawie relacji rodzic-dziecko
        const setGenerations = () => {
            // Resetuj generacje
            personMap.forEach(p => p.generation = null);

            // Znajdź osoby bez rodziców (najstarsze pokolenie)
            const roots = Array.from(personMap.values()).filter(
                p => !p.ojciec_id && !p.matka_id
            );

            if (roots.length === 0) {
                // Jeśli nie ma korzeni, zacznij od najstarszej osoby
                const oldest = Array.from(personMap.values()).sort((a, b) =>
                    (a.birth || 0) - (b.birth || 0)
                )[0];
                if (oldest) {
                    oldest.generation = 0;
                    roots.push(oldest);
                }
            } else {
                roots.forEach(r => r.generation = 0);
            }

            // BFS do ustalenia generacji
            const queue = [...roots];
            const visited = new Set(roots.map(r => r.nodeId));

            while (queue.length > 0) {
                const current = queue.shift();

                // Znajdź dzieci
                personMap.forEach(person => {
                    if (!visited.has(person.nodeId)) {
                        if (person.ojciec_id === current.nodeId ||
                            person.matka_id === current.nodeId) {
                            person.generation = current.generation + 1;
                            queue.push(person);
                            visited.add(person.nodeId);
                        }
                    }
                });

                // Ustaw małżonka na tym samym poziomie
                if (current.malzonek_ids && current.malzonek_ids.length > 0) {
                    current.malzonek_ids.forEach(spouseId => {
                        const spouse = personMap.get(spouseId);
                        if (spouse && spouse.generation === null) {
                            spouse.generation = current.generation;
                            if (!visited.has(spouse.nodeId)) {
                                queue.push(spouse);
                                visited.add(spouse.nodeId);
                            }
                        }
                    });
                }
            }

            // Dla osób które nie zostały przypisane
            personMap.forEach(p => {
                if (p.generation === null) {
                    // Spróbuj ustalić na podstawie małżonka
                    if (p.malzonek_ids && p.malzonek_ids.length > 0) {
                        for (const spouseId of p.malzonek_ids) {
                            const spouse = personMap.get(spouseId);
                            if (spouse && spouse.generation !== null) {
                                p.generation = spouse.generation;
                                break;
                            }
                        }
                    }
                    // Jeśli nadal null, ustaw na 0
                    if (p.generation === null) {
                        p.generation = 0;
                    }
                }
            });
        };

        setGenerations();

        // Grupuj osoby po generacjach
        const generations = new Map();
        personMap.forEach(p => {
            const gen = p.generation;
            if (!generations.has(gen)) {
                generations.set(gen, []);
            }
            generations.get(gen).push(p);
        });

        // Sortuj generacje
        const sortedGenerations = Array.from(generations.keys()).sort((a, b) => a - b);

        // Pozycjonuj węzły
        const positioned = [];
        let currentY = 0;

        sortedGenerations.forEach(genLevel => {
            const genMembers = generations.get(genLevel);

            // Grupuj małżeństwa razem
            const couples = [];
            const singles = [];
            const processed = new Set();

            genMembers.forEach(person => {
                if (processed.has(person.nodeId)) return;

                if (person.malzonek_ids && person.malzonek_ids.length > 0) {
                    // Znajdź małżonka na tym samym poziomie
                    const spouseId = person.malzonek_ids[0];
                    const spouse = genMembers.find(m => m.nodeId === spouseId);

                    if (spouse && !processed.has(spouse.nodeId)) {
                        couples.push([person, spouse]);
                        processed.add(person.nodeId);
                        processed.add(spouse.nodeId);
                    } else if (!spouse) {
                        // Małżonek nie jest na tym poziomie
                        singles.push(person);
                        processed.add(person.nodeId);
                    }
                } else {
                    singles.push(person);
                    processed.add(person.nodeId);
                }
            });

            // Pozycjonuj pary i single
            let currentX = TREE_CONFIG.MARGIN;

            // Najpierw pary małżeńskie
            couples.forEach(([person1, person2]) => {
                // Ustaw pierwszą osobę z pary
                person1.x = currentX;
                person1.y = currentY;
                positioned.push(person1);
                currentX += person1.boxW + TREE_CONFIG.MARRIAGE_GAP;

                // Ustaw drugą osobę z pary
                person2.x = currentX;
                person2.y = currentY;
                positioned.push(person2);
                currentX += person2.boxW + TREE_CONFIG.H_GAP;
            });

            // Potem osoby single
            singles.forEach(person => {
                person.x = currentX;
                person.y = currentY;
                positioned.push(person);
                currentX += person.boxW + TREE_CONFIG.H_GAP;
            });

            currentY += TREE_CONFIG.NODE_HEIGHT + TREE_CONFIG.V_GAP;
        });

        return positioned;
    }

    function findTreeConnections(allNodes) {
        const connections = [];
        const marriages = [];
        const nodeById = new Map(allNodes.map(n => [n.nodeId, n]));

        // Znajdź małżeństwa - tylko między osobami na tym samym poziomie
        const processed = new Set();
        allNodes.forEach(person => {
            if (person.malzonek_ids && person.malzonek_ids.length > 0) {
                person.malzonek_ids.forEach(spouseId => {
                    const spouse = nodeById.get(String(spouseId));
                    if (spouse &&
                        person.generation === spouse.generation &&
                        !processed.has(`${person.nodeId}-${spouseId}`) &&
                        !processed.has(`${spouseId}-${person.nodeId}`)) {

                        // Ustaw od lewej do prawej
                        const left = person.x < spouse.x ? person : spouse;
                        const right = person.x < spouse.x ? spouse : person;
                        marriages.push([left, right]);
                        processed.add(`${person.nodeId}-${spouseId}`);
                    }
                });
            }
        });

        // Znajdź połączenia rodzic-dziecko
        allNodes.forEach(child => {
            const father = child.ojciec_id ? nodeById.get(child.ojciec_id) : null;
            const mother = child.matka_id ? nodeById.get(child.matka_id) : null;

            if (!father && !mother) return;

            let sourceX, sourceY;

            if (father && mother) {
                // Oboje rodzice istnieją
                // Sprawdź czy są małżeństwem na tym samym poziomie
                if (father.generation === mother.generation &&
                    Math.abs(father.x - mother.x) < (TREE_CONFIG.H_GAP * 2)) {
                    // Rodzice są obok siebie - linia schodzi z środka między nimi
                    const leftParent = father.x < mother.x ? father : mother;
                    const rightParent = father.x < mother.x ? mother : father;
                    sourceX = (leftParent.x + leftParent.boxW + rightParent.x) / 2;
                    sourceY = leftParent.y + TREE_CONFIG.NODE_HEIGHT;
                } else {
                    // Rodzice nie są obok siebie - użyj środka między nimi
                    sourceX = (father.x + father.boxW / 2 + mother.x + mother.boxW / 2) / 2;
                    sourceY = Math.max(father.y, mother.y) + TREE_CONFIG.NODE_HEIGHT;
                }
            } else {
                // Tylko jeden rodzic
                const parent = father || mother;
                sourceX = parent.x + parent.boxW / 2;
                sourceY = parent.y + TREE_CONFIG.NODE_HEIGHT;
            }

            connections.push({
                type: "parent-child",
                source: { x: sourceX, y: sourceY },
                target: { x: child.x + child.boxW / 2, y: child.y },
                child: child,
            });
        });

        return { connections, marriages };
    }

    window.AdminTreeRenderer = Object.freeze({
        render: render,
    });
})();
