/**
 * Plik: genealogia-script.js
 * Opis: Wizualizacja interaktywnego drzewa genealogicznego z hierarchicznym układem.
 *       Wykorzystuje D3.js do renderowania i obsługi interakcji.
 */

document.addEventListener("DOMContentLoaded", () => {
  /* ==========================================================================
     KONFIGURACJA WIZUALIZACJI
     ========================================================================== */
  const NODE_WIDTH = 180;
  const NODE_HEIGHT = 100;
  const HORIZONTAL_SPACING = 60;
  const VERTICAL_SPACING = 150;
  const MARRIAGE_LINE_OFFSET = 20;
  const FAMILY_GROUP_SPACING = 200;
  const MARGIN = 50;

  /* ==========================================================================
     REFERENCJE DO ELEMENTÓW DOM
     ========================================================================== */
  const container = document.getElementById("genealogy-network");
  const searchInput = document.getElementById("search-input");
  const searchResults = document.getElementById("search-results");
  const familySelect = document.getElementById("family-select");
  const showAllBtn = document.getElementById("show-all");
  const centerViewBtn = document.getElementById("center-view");
  const resetViewBtn = document.getElementById("reset-view");

  /* ==========================================================================
     ZMIENNE STANU APLIKACJI
     ========================================================================== */
  let svg = null;
  let g = null;
  let zoom = null;
  let allPersons = [];
  let families = new Map();
  let familyGroups = [];

  /* ==========================================================================
     ŁADOWANIE ZASOBÓW ZEWNĘTRZNYCH
     ========================================================================== */
  
  /**
   * Asynchroniczne ładowanie biblioteki D3.js
   */
  const loadD3 = () => {
    return new Promise((resolve, reject) => {
      if (window.d3) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://d3js.org/d3.v7.min.js';
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  };

  /* ==========================================================================
     POBIERANIE I PRZETWARZANIE DANYCH
     ========================================================================== */
  
  /**
   * Pobiera dane genealogiczne z API lub pliku lokalnego
   */
  const fetchAllGenealogyData = async () => {
    try {
      // Próba pobrania z API
      const response = await fetch('/api/genealogia/full-graph');
      if (!response.ok) throw new Error('Błąd pobierania danych');
      const data = await response.json();
      
      console.log('Otrzymane dane z API:', data);
      
      // Rozpoznanie formatu danych
      if (data.nodes && data.edges) {
        return processVisJsData(data);
      } else if (data.persons) {
        return processGenealogyData(data);
      }
      
      return false;
    } catch (error) {
      console.error('Błąd pobierania danych:', error);
      
      // Fallback - lokalny plik JSON
      try {
        const localResponse = await fetch('/genealogia/genealogia.json');
        if (localResponse.ok) {
          const localData = await localResponse.json();
          console.log('Załadowano lokalne dane:', localData);
          return processGenealogyData(localData);
        }
      } catch (localError) {
        console.error('Błąd ładowania lokalnych danych:', localError);
      }
      
      throw error;
    }
  };

  /**
   * Przetwarza dane w formacie genealogia.json
   */
  const processGenealogyData = (data) => {
    if (!data.persons || !Array.isArray(data.persons)) {
      console.error('Nieprawidłowy format danych genealogicznych');
      return false;
    }

    const personMap = new Map();
    
    // Mapowanie osób
    allPersons = data.persons.map(person => {
      const p = {
        id: person.id,
        name: person.name,
        gender: person.gender,
        birthYear: person.birthDate?.year,
        deathYear: person.deathDate?.year,
        houseNumber: person.houseNumber,
        protocolKey: person.protocolKey,
        level: null,
        x: 0,
        y: 0,
        children: [],
        parents: [],
        spouses: person.spouseIds || [],
        fatherId: person.fatherId,
        motherId: person.motherId,
        notes: person.notes
      };
      personMap.set(person.id, p);
      return p;
    });

    // Budowanie relacji rodzinnych
    allPersons.forEach(person => {
      if (person.fatherId) {
        person.parents.push(person.fatherId);
        const father = personMap.get(person.fatherId);
        if (father && !father.children.includes(person.id)) {
          father.children.push(person.id);
        }
      }
      if (person.motherId) {
        person.parents.push(person.motherId);
        const mother = personMap.get(person.motherId);
        if (mother && !mother.children.includes(person.id)) {
          mother.children.push(person.id);
        }
      }
    });

    console.log('Przetworzone osoby z genealogia.json:', allPersons);
    return true;
  };

  /**
   * Przetwarza dane w formacie vis.js
   */
  const processVisJsData = (data) => {
    const personMap = new Map();
    
    // Konwersja węzłów
    allPersons = data.nodes.map(node => {
      const person = {
        id: node.id,
        name: node.label,
        gender: (node.shape === 'box' || node.shape === 'square') ? 'M' : 'F',
        protocolKey: node.protocolKey,
        level: null,
        x: 0,
        y: 0,
        children: [],
        parents: [],
        spouses: []
      };
      personMap.set(node.id, person);
      return person;
    });

    // Przetwarzanie relacji
    data.edges.forEach(edge => {
      const fromPerson = personMap.get(edge.from);
      const toPerson = personMap.get(edge.to);
      
      if (!fromPerson || !toPerson) return;
      
      if (edge.dashes || edge.color === '#9b59b6') {
        // Relacja małżeńska
        if (!fromPerson.spouses.includes(edge.to)) {
          fromPerson.spouses.push(edge.to);
        }
        if (!toPerson.spouses.includes(edge.from)) {
          toPerson.spouses.push(edge.from);
        }
      } else {
        // Relacja rodzic-dziecko
        if (!fromPerson.children.includes(edge.to)) {
          fromPerson.children.push(edge.to);
        }
        if (!toPerson.parents.includes(edge.from)) {
          toPerson.parents.push(edge.from);
        }
      }
    });

    console.log('Przetworzone osoby z vis.js:', allPersons);
    return true;
  };

  /* ==========================================================================
     ANALIZA STRUKTURY RODZINNEJ
     ========================================================================== */
  
  /**
   * Identyfikuje niezależne grupy rodzinne (connected components)
   */
  const identifyFamilyGroups = () => {
    const visited = new Set();
    familyGroups = [];
    
    const dfs = (personId, group) => {
      if (visited.has(personId)) return;
      visited.add(personId);
      group.add(personId);
      
      const person = allPersons.find(p => p.id === personId);
      if (!person) return;
      
      // Rekurencyjne odwiedzanie połączonych osób
      [...person.parents, ...person.children, ...person.spouses].forEach(relatedId => {
        dfs(relatedId, group);
      });
    };
    
    // Znajdowanie wszystkich grup
    allPersons.forEach(person => {
      if (!visited.has(person.id)) {
        const group = new Set();
        dfs(person.id, group);
        familyGroups.push(group);
      }
    });
    
    // Sortowanie według wielkości
    familyGroups.sort((a, b) => b.size - a.size);
    
    console.log(`Znaleziono ${familyGroups.length} niezależnych grup rodzinnych:`, 
      familyGroups.map(g => `Grupa z ${g.size} osobami`));
    
    return familyGroups;
  };

  /**
   * Oblicza poziomy generacji dla każdej osoby
   */
  const calculateGenerations = () => {
    // Reset poziomów
    allPersons.forEach(p => p.level = null);
    
    // Przetwarzanie każdej grupy rodzinnej
    familyGroups.forEach(group => {
      const groupPersons = allPersons.filter(p => group.has(p.id));
      
      // Znajdowanie korzeni drzewa
      const roots = groupPersons.filter(p => 
        p.parents.length === 0 || 
        p.parents.every(parentId => !group.has(parentId))
      );
      
      if (roots.length === 0) {
        // Heurystyka dla cyklicznych struktur
        let maxDescendants = 0;
        let bestRoot = null;
        
        groupPersons.forEach(person => {
          const descendants = countDescendantsInGroup(person.id, group);
          if (descendants > maxDescendants) {
            maxDescendants = descendants;
            bestRoot = person;
          }
        });
        
        if (bestRoot) {
          roots.push(bestRoot);
        } else {
          roots.push(groupPersons[0]);
        }
      }
      
      console.log(`Grupa ${Array.from(group).join(',')}: korzenie:`, roots.map(r => r.name));
      
      // BFS dla przypisania poziomów
      const queue = [];
      const visited = new Set();
      
      roots.forEach(root => {
        root.level = 0;
        queue.push(root);
        visited.add(root.id);
      });
      
      while (queue.length > 0) {
        const current = queue.shift();
        
        // Małżonkowie na tym samym poziomie
        current.spouses.forEach(spouseId => {
          if (!group.has(spouseId)) return;
          const spouse = allPersons.find(p => p.id === spouseId);
          if (spouse) {
            if (spouse.level === null || spouse.level !== current.level) {
              spouse.level = current.level;
              if (!visited.has(spouseId)) {
                visited.add(spouseId);
                queue.push(spouse);
              }
            }
          }
        });
        
        // Dzieci - poziom niżej
        current.children.forEach(childId => {
          if (!group.has(childId)) return;
          const child = allPersons.find(p => p.id === childId);
          if (child) {
            const childLevel = current.level + 1;
            if (child.level === null || child.level < childLevel) {
              child.level = childLevel;
              if (!visited.has(childId)) {
                visited.add(childId);
                queue.push(child);
              }
            }
          }
        });
        
        // Rodzice - poziom wyżej
        current.parents.forEach(parentId => {
          if (!group.has(parentId)) return;
          const parent = allPersons.find(p => p.id === parentId);
          if (parent) {
            const parentLevel = Math.max(0, current.level - 1);
            if (parent.level === null || parent.level > parentLevel) {
              parent.level = parentLevel;
              if (!visited.has(parentId)) {
                visited.add(parentId);
                queue.push(parent);
              }
            }
          }
        });
      }
    });
    
    // Normalizacja poziomów
    const minLevel = Math.min(...allPersons.filter(p => p.level !== null).map(p => p.level));
    if (minLevel < 0) {
      allPersons.forEach(p => {
        if (p.level !== null) p.level -= minLevel;
      });
    }
    
    // Grupowanie według poziomów
    const generations = new Map();
    allPersons.forEach(person => {
      if (person.level === null) {
        console.warn('Osoba bez poziomu:', person.name);
        person.level = 0;
      }
      if (!generations.has(person.level)) {
        generations.set(person.level, []);
      }
      generations.get(person.level).push(person);
    });
    
    console.log('Poziomy generacji:');
    Array.from(generations.entries()).sort((a, b) => a[0] - b[0]).forEach(([level, persons]) => {
      console.log(`  Poziom ${level}: ${persons.map(p => p.name).join(', ')}`);
    });
    
    return generations;
  };

  /**
   * Rekurencyjne liczenie potomków w grupie
   */
  const countDescendantsInGroup = (personId, group, visited = new Set()) => {
    if (visited.has(personId)) return 0;
    visited.add(personId);
    
    let count = 0;
    const person = allPersons.find(p => p.id === personId);
    
    if (person && person.children) {
      person.children.forEach(childId => {
        if (group.has(childId)) {
          count++;
          count += countDescendantsInGroup(childId, group, visited);
        }
      });
    }
    
    return count;
  };

  /* ==========================================================================
     POZYCJONOWANIE I UKŁAD GRAFICZNY
     ========================================================================== */
  
  /**
   * Oblicza pozycje węzłów w układzie hierarchicznym
   */
  const positionNodes = (generations) => {
    let maxWidth = 0;
    let currentY = MARGIN;
    
    const sortedLevels = Array.from(generations.keys()).sort((a, b) => a - b);
    
    sortedLevels.forEach(level => {
      const persons = generations.get(level);
      let currentX = MARGIN;
      
      // Grupowanie według rodzin
      familyGroups.forEach((group, groupIndex) => {
        const groupPersons = persons.filter(p => group.has(p.id));
        if (groupPersons.length === 0) return;
        
        // Sortowanie osób w grupie
        groupPersons.sort((a, b) => {
          const aSpouseInGroup = groupPersons.find(p => a.spouses.includes(p.id));
          const bSpouseInGroup = groupPersons.find(p => b.spouses.includes(p.id));
          
          if (aSpouseInGroup && !bSpouseInGroup) return -1;
          if (!aSpouseInGroup && bSpouseInGroup) return 1;
          
          if (aSpouseInGroup && bSpouseInGroup) {
            const aSpouseId = Math.min(a.id, aSpouseInGroup.id);
            const bSpouseId = Math.min(b.id, bSpouseInGroup.id);
            return aSpouseId - bSpouseId;
          }
          
          return a.name.localeCompare(b.name);
        });
        
        // Pozycjonowanie osób
        const processed = new Set();
        
        groupPersons.forEach(person => {
          if (processed.has(person.id)) return;
          
          const spouse = person.spouses
            .map(id => groupPersons.find(p => p.id === id))
            .filter(Boolean)[0];
          
          if (spouse && !processed.has(spouse.id)) {
            // Pozycjonowanie pary małżeńskiej
            person.x = currentX;
            person.y = currentY;
            spouse.x = currentX + NODE_WIDTH + MARRIAGE_LINE_OFFSET;
            spouse.y = currentY;
            processed.add(person.id);
            processed.add(spouse.id);
            currentX += NODE_WIDTH * 2 + MARRIAGE_LINE_OFFSET + HORIZONTAL_SPACING;
          } else if (!processed.has(person.id)) {
            // Pozycjonowanie pojedynczej osoby
            person.x = currentX;
            person.y = currentY;
            processed.add(person.id);
            currentX += NODE_WIDTH + HORIZONTAL_SPACING;
          }
        });
        
        // Odstęp między grupami rodzinnymi
        if (groupIndex < familyGroups.length - 1 && groupPersons.length > 0) {
          currentX += FAMILY_GROUP_SPACING;
        }
      });
      
      maxWidth = Math.max(maxWidth, currentX);
      currentY += NODE_HEIGHT + VERTICAL_SPACING;
    });
    
    return { width: maxWidth + MARGIN, height: currentY + MARGIN };
  };

  /**
   * Generuje połączenia między węzłami
   */
  const createConnections = () => {
    const connections = [];
    const marriages = [];

    // Połączenia rodzic-dziecko
    allPersons.forEach(parent => {
      if (parent.children && parent.children.length > 0) {
        parent.children.forEach(childId => {
          const child = allPersons.find(p => p.id === childId);
          if (!child || child.level === null || parent.level === null) return;
          if (child.level <= parent.level) return;
          
          const parentX = parent.x + NODE_WIDTH / 2;
          const parentY = parent.y + NODE_HEIGHT;
          const childX = child.x + NODE_WIDTH / 2;
          const childY = child.y;
          
          // Centrowanie linii dla par małżeńskich
          const spouse = parent.spouses
            .map(id => allPersons.find(p => p.id === id))
            .find(s => s && s.level === parent.level && Math.abs(s.x - parent.x) < NODE_WIDTH * 3);
          
          let startX = parentX;
          if (spouse) {
            startX = (parentX + spouse.x + NODE_WIDTH / 2) / 2;
          }
          
          const midY = parentY + (childY - parentY) / 2;
          
          connections.push({
            path: `M${startX},${parentY} L${startX},${midY} L${childX},${midY} L${childX},${childY}`,
            type: 'parent-child',
            parent: parent,
            child: child
          });
        });
      }
    });

    // Połączenia małżeńskie
    const processedMarriages = new Set();
    
    allPersons.forEach(person => {
      person.spouses.forEach(spouseId => {
        const spouse = allPersons.find(p => p.id === spouseId);
        if (!spouse || person.level !== spouse.level) return;
        
        const marriageKey = [person.id, spouse.id].sort().join('-');
        if (!processedMarriages.has(marriageKey)) {
          processedMarriages.add(marriageKey);
          
          if (Math.abs(person.x - spouse.x) < NODE_WIDTH * 3) {
            marriages.push([person, spouse]);
          }
        }
      });
    });

    return { connections, marriages };
  };

  /**
   * Analizuje i grupuje osoby według nazwisk
   */
  const analyzeFamilies = () => {
    families.clear();
    
    allPersons.forEach(person => {
      const nameParts = person.name.split(' ');
      const surname = nameParts[nameParts.length - 1] || 'Nieznane';
      
      if (!families.has(surname)) {
        families.set(surname, new Set());
      }
      families.get(surname).add(person.id);
    });
    
    return families;
  };

  /* ==========================================================================
     RENDEROWANIE WIZUALIZACJI
     ========================================================================== */
  
  /**
   * Główna funkcja rysująca drzewo genealogiczne
   */
  const drawTree = () => {
    container.innerHTML = '';

    // Analiza struktury
    identifyFamilyGroups();
    const generations = calculateGenerations();
    const { width, height } = positionNodes(generations);
    const { connections, marriages } = createConnections();

    // Inicjalizacja SVG
    svg = d3.create('svg')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('background', 'linear-gradient(135deg, #f5f3f0 0%, #e8e4de 100%)');

    // Konfiguracja zoom
    zoom = d3.zoom()
      .scaleExtent([0.1, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);
    g = svg.append('g');

    // Renderowanie połączeń rodzic-dziecko
    g.selectAll('.parent-child-line')
      .data(connections)
      .enter()
      .append('path')
      .attr('class', 'parent-child-line')
      .attr('d', d => d.path)
      .attr('stroke', '#666')
      .attr('stroke-width', 2)
      .attr('fill', 'none')
      .attr('stroke-dasharray', '5,5')
      .attr('opacity', 0.6);

    // Renderowanie linii małżeństw
    g.selectAll('.marriage-line')
      .data(marriages)
      .enter()
      .append('line')
      .attr('class', 'marriage-line')
      .attr('x1', d => Math.min(d[0].x + NODE_WIDTH, d[1].x + NODE_WIDTH))
      .attr('y1', d => d[0].y + NODE_HEIGHT/2)
      .attr('x2', d => Math.max(d[0].x, d[1].x))
      .attr('y2', d => d[1].y + NODE_HEIGHT/2)
      .attr('stroke', '#e74c3c')
      .attr('stroke-width', 3);

    // Symbol małżeństwa
    g.selectAll('.marriage-symbol')
      .data(marriages)
      .enter()
      .append('text')
      .attr('class', 'marriage-symbol')
      .attr('x', d => (d[0].x + NODE_WIDTH + d[1].x) / 2)
      .attr('y', d => d[0].y + NODE_HEIGHT/2 - 5)
      .attr('text-anchor', 'middle')
      .attr('font-size', '20px')
      .text('💕');

    // Renderowanie węzłów osób
    const nodeGroups = g.selectAll('.person-node')
      .data(allPersons)
      .enter()
      .append('g')
      .attr('class', 'person-node')
      .attr('transform', d => `translate(${d.x}, ${d.y})`)
      .style('cursor', 'pointer')
      .on('dblclick', (event, d) => {
        if (d.protocolKey) {
          window.open(`../wlasciciele/protokol.html?ownerId=${d.protocolKey}`, '_blank');
        }
      })
      .on('click', (event, d) => {
        d3.selectAll('.person-node rect').attr('stroke-width', 2);
        d3.select(event.currentTarget).select('rect').attr('stroke-width', 4);
        
        // Logowanie informacji debugowych
        console.log('=== Informacje o osobie ===');
        console.log('Imię i nazwisko:', d.name);
        console.log('ID:', d.id);
        console.log('Poziom:', d.level);
        
        const groupIndex = familyGroups.findIndex(g => g.has(d.id));
        console.log('Grupa rodzinna:', groupIndex + 1);
        
        const parents = d.parents.map(id => allPersons.find(p => p.id === id));
        const children = d.children.map(id => allPersons.find(p => p.id === id));
        const spouses = d.spouses.map(id => allPersons.find(p => p.id === id));
        
        console.log('Rodzice:', parents.map(p => p ? `${p.name} (poziom ${p.level})` : 'nieznany').join(', ') || 'brak');
        console.log('Dzieci:', children.map(p => p ? `${p.name} (poziom ${p.level})` : 'nieznany').join(', ') || 'brak');
        console.log('Małżonkowie:', spouses.map(p => p ? `${p.name} (poziom ${p.level})` : 'nieznany').join(', ') || 'brak');
      });

    // Tło węzła
    nodeGroups.append('rect')
      .attr('width', NODE_WIDTH)
      .attr('height', NODE_HEIGHT)
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('fill', d => d.gender === 'M' ? '#e3f2fd' : '#fce4ec')
      .attr('stroke', d => d.gender === 'M' ? '#1976d2' : '#c2185b')
      .attr('stroke-width', 2)
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.15))');

    // Imię i nazwisko
    nodeGroups.append('text')
      .attr('x', NODE_WIDTH / 2)
      .attr('y', 30)
      .attr('text-anchor', 'middle')
      .attr('font-size', '13px')
      .attr('font-weight', 'bold')
      .attr('fill', '#333')
      .text(d => d.name.length > 22 ? d.name.substring(0, 20) + '...' : d.name);

    // Lata życia
    nodeGroups.append('text')
      .attr('x', NODE_WIDTH / 2)
      .attr('y', 50)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', '#666')
      .text(d => {
        if (d.birthYear && d.deathYear) return `${d.birthYear} - ${d.deathYear}`;
        if (d.birthYear) return `ur. ${d.birthYear}`;
        if (d.deathYear) return `zm. ${d.deathYear}`;
        return '';
      });

    // Poziom generacji
    nodeGroups.append('text')
      .attr('x', NODE_WIDTH / 2)
      .attr('y', 70)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('fill', '#999')
      .text(d => `Generacja ${d.level + 1}`);

    // Numer domu
    nodeGroups.filter(d => d.houseNumber)
      .append('text')
      .attr('x', NODE_WIDTH / 2)
      .attr('y', 85)
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('fill', '#666')
      .text(d => `Dom: ${d.houseNumber}`);

    // Symbol płci
    nodeGroups.append('text')
      .attr('x', NODE_WIDTH - 15)
      .attr('y', 25)
      .attr('text-anchor', 'middle')
      .attr('font-size', '18px')
      .text(d => d.gender === 'M' ? '♂' : '♀')
      .attr('fill', d => d.gender === 'M' ? '#1976d2' : '#c2185b');

    container.appendChild(svg.node());
    
    // Auto-centrowanie widoku
    setTimeout(() => {
      const bounds = g.node().getBBox();
      const fullWidth = container.clientWidth;
      const fullHeight = container.clientHeight;
      const widthScale = fullWidth / bounds.width;
      const heightScale = fullHeight / bounds.height;
      const scale = Math.min(widthScale, heightScale, 1) * 0.9;
      
      const translate = [
        fullWidth / 2 - scale * (bounds.x + bounds.width / 2),
        fullHeight / 2 - scale * (bounds.y + bounds.height / 2)
      ];
      
      svg.call(
        zoom.transform,
        d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
      );
    }, 100);
  };

  /* ==========================================================================
     FILTRY I INTERAKCJE
     ========================================================================== */
  
  /**
   * Filtruje widok według wybranej rodziny
   */
  const filterByFamily = (familyName) => {
    if (!familyName || familyName === 'all') {
      // Pokaż wszystko
      d3.selectAll('.person-node').style('opacity', 1);
      d3.selectAll('.parent-child-line').style('opacity', 0.6);
      d3.selectAll('.marriage-line').style('opacity', 1);
      d3.selectAll('.marriage-symbol').style('opacity', 1);
    } else {
      const familyMembers = families.get(familyName) || new Set();
      
      // Rozszerzenie o małżonków
      const extendedFamily = new Set(familyMembers);
      familyMembers.forEach(memberId => {
        const member = allPersons.find(p => p.id === memberId);
        if (member) {
          member.spouses.forEach(spouseId => extendedFamily.add(spouseId));
        }
      });
      
      // Zastosowanie filtru
      d3.selectAll('.person-node')
        .style('opacity', d => extendedFamily.has(d.id) ? 1 : 0.2);
      
      d3.selectAll('.parent-child-line')
        .style('opacity', d => {
          return (extendedFamily.has(d.parent.id) && extendedFamily.has(d.child.id)) ? 0.6 : 0.1;
        });
      
      d3.selectAll('.marriage-line')
        .style('opacity', d => 
          (extendedFamily.has(d[0].id) && extendedFamily.has(d[1].id)) ? 1 : 0.1
        );
      
      d3.selectAll('.marriage-symbol')
        .style('opacity', d => 
          (extendedFamily.has(d[0].id) && extendedFamily.has(d[1].id)) ? 1 : 0.1
        );
    }
  };

  /**
   * Inicjalizuje kontrolki interfejsu
   */
  const setupControls = () => {
    // Wypełnienie listy rodzin
    const sortedFamilies = Array.from(families.keys()).sort((a, b) => {
      const sizeA = families.get(a).size;
      const sizeB = families.get(b).size;
      if (sizeA !== sizeB) return sizeB - sizeA;
      return a.localeCompare(b);
    });
    
    familySelect.innerHTML = '<option value="all">Wszystkie rodziny</option>';
    sortedFamilies.forEach(family => {
      const option = document.createElement('option');
      option.value = family;
      const count = families.get(family).size;
      option.textContent = `${family} (${count} ${count === 1 ? 'osoba' : count < 5 ? 'osoby' : 'osób'})`;
      familySelect.appendChild(option);
    });

    // Obsługa zdarzeń
    familySelect.addEventListener('change', (e) => {
      filterByFamily(e.target.value);
    });

    showAllBtn.addEventListener('click', () => {
      familySelect.value = 'all';
      filterByFamily('all');
    });

    centerViewBtn.addEventListener('click', () => {
      svg.transition()
        .duration(750)
        .call(zoom.transform, d3.zoomIdentity);
    });

    if (resetViewBtn) {
      resetViewBtn.addEventListener('click', () => {
        drawTree();
        familySelect.value = 'all';
      });
    }

    // Wyszukiwarka osób
    searchInput.addEventListener('input', (e) => {
      const term = e.target.value.toLowerCase().trim();
      searchResults.innerHTML = '';
      
      if (term.length < 2) return;

      const filtered = allPersons.filter(p => 
        p.name.toLowerCase().includes(term)
      ).slice(0, 10);

      filtered.forEach(person => {
        const li = document.createElement('li');
        li.textContent = `${person.name} (Generacja ${person.level + 1})`;
        li.onclick = () => {
          // Fokus na wybranej osobie
          const node = d3.selectAll('.person-node')
            .filter(d => d.id === person.id);
          
          if (!node.empty()) {
            const transform = d3.zoomIdentity
              .translate(-person.x + container.clientWidth/2 - NODE_WIDTH/2, 
                        -person.y + container.clientHeight/2 - NODE_HEIGHT/2)
              .scale(1.5);
            
            svg.transition()
              .duration(750)
              .call(zoom.transform, transform);
            
            // Podświetlenie
            d3.selectAll('.person-node rect').attr('stroke-width', 2);
            node.select('rect').attr('stroke-width', 4);
          }
          
          searchInput.value = '';
          searchResults.innerHTML = '';
        };
        searchResults.appendChild(li);
      });
    });
  };

  /* ==========================================================================
     INICJALIZACJA APLIKACJI
     ========================================================================== */
  
  /**
   * Główna funkcja inicjalizująca
   */
  const initialize = async () => {
    // Ekran ładowania
    container.innerHTML = `
      <div class="loading-center">
        <div class="spinner"></div>
        <div>Ładowanie drzewa genealogicznego...</div>
      </div>`;

    try {
      // Ładowanie zależności i danych
      await loadD3();
      const hasData = await fetchAllGenealogyData();
      
      if (!hasData || allPersons.length === 0) {
        container.innerHTML = `
          <div class="loading-center">
            <div class="loading-error">
              <h3>Brak danych genealogicznych</h3>
              <p>Nie znaleziono żadnych osób w bazie danych.</p>
            </div>
          </div>`;
        return;
      }

      console.log(`Załadowano ${allPersons.length} osób`);
      
      // Budowanie wizualizacji
      analyzeFamilies();
      drawTree();
      setupControls();

    } catch (error) {
      console.error('Błąd inicjalizacji:', error);
      container.innerHTML = `
        <div class="loading-center">
          <div class="loading-error">
            <h3>Błąd ładowania danych</h3>
            <p>${error.message}</p>
          </div>
        </div>`;
    }
  };

  // Uruchomienie aplikacji
  initialize();
});