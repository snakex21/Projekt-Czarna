/**
 * ==========================================================================
 * Plik: genealogia_d3_fixed.js
 * Opis: Moduł wizualizacji drzewa genealogicznego z użyciem D3.js.
 *       Renderuje interaktywne drzewo z automatycznym pozycjonowaniem.
 * ==========================================================================
 */

(function () {
  // ==========================================================================
  // KONFIGURACJA STAŁYCH
  // ==========================================================================
  
  const NODE_HEIGHT = 80;      // Wysokość węzła
  const NODE_MIN_W = 120;      // Minimalna szerokość węzła
  const H_GAP = 80;           // Odstęp poziomy
  const V_GAP = 120;          // Odstęp pionowy
  const MARGIN = 80;          // Margines drzewa
  const MARRIAGE_GAP = 20;    // Odstęp między małżonkami
  const FONT = '700 16px "Segoe UI", sans-serif';

  // ==========================================================================
  // ZMIENNE GLOBALNE
  // ==========================================================================
  
  let COLORS = [];
  let people = [];
  let rootId = null;

  // Elementy DOM
  const modal = document.getElementById("genealogyModal");
  const chart = document.getElementById("genealogy-chart");
  const showBtn = document.getElementById("showGenealogyTreeBtn");
  const closeBtn = document.getElementById("closeGenealogyModalBtn");

  // Czyszczenie starych nakładek
  (function cleanupOldOverlays() {
    const oldOverlays = document.querySelectorAll('.loading-overlay');
    oldOverlays.forEach(overlay => overlay.remove());
  })();

  // ==========================================================================
  // FUNKCJE POMOCNICZE
  // ==========================================================================

  /**
   * Dynamicznie ładuje skrypt JavaScript.
   */
  const loadScript = (src) =>
    new Promise((res, rej) => {
      if (document.querySelector(`script[src="${src}"]`)) return res();
      
      const s = document.createElement("script");
      s.src = src;
      s.onload = res;
      s.onerror = () => rej(new Error(`Nie można załadować ${src}`));
      document.head.appendChild(s);
    });

  /**
   * Zapewnia dostępność bibliotek D3.js i d3-flextree.
   */
  async function ensureLibs() {
    if (!window.d3) await loadScript("https://cdn.jsdelivr.net/npm/d3@7");
    if (!d3.flextree) await loadScript("https://cdn.jsdelivr.net/npm/d3-flextree@2");
    if (!COLORS.length) COLORS = d3.schemeTableau10;
  }

  /**
   * Pobiera dane genealogiczne z API.
   */
  async function fetchData(ownerKey) {
    const res = await fetch(`/api/genealogia/drzewo/${ownerKey}`);
    if (!res.ok) throw new Error("Błąd pobierania danych genealogicznych");
    
    const data = await res.json();
    people = data.people ?? [];
    rootId = data.start_node_id ?? null;
  }

  // ==========================================================================
  // GŁÓWNA FUNKCJA RYSOWANIA DRZEWA
  // ==========================================================================

  /**
   * Rysuje drzewo genealogiczne używając D3.js.
   */
  function drawTree() {
    if (!people.length) {
      chart.innerHTML = "<h2>Brak danych do wyświetlenia.</h2>";
      return;
    }

    // Dodanie stylów dla nakładki ładowania
    if (!document.getElementById('genealogy-loading-styles')) {
      const style = document.createElement('style');
      style.id = 'genealogy-loading-styles';
      style.textContent = `
        .loading-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          display: flex;
          justify-content: center;
          align-items: center;
          z-index: 10000;
        }
        .loading-content {
          background: white;
          padding: 30px;
          border-radius: 10px;
          text-align: center;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .loading-content h3 {
          margin: 0 0 20px 0;
          color: #333;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }

    // Przygotowanie danych
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = FONT;
    const textWidth = (t) => ctx.measureText(t).width;
    
    people = expandUnions(people);

    // Tworzenie mapy osób
    const personMap = new Map();
    people.forEach((p) => {
      const title = `${p.imie} ${p.nazwisko || ""}`.trim();
      
      const rec = {
        nodeId: String(p.id),
        name: title,
        birth: p.rok_urodzenia,
        death: p.rok_smierci,
        ojciec_id: p.ojciec_id ? String(p.ojciec_id) : null,
        matka_id: p.matka_id ? String(p.matka_id) : null,
        malzonek_id: p.malzonek_id ? String(p.malzonek_id) : null,
        key: p.unikalny_klucz,
        isRoot: p.id === rootId,
        boxW: Math.max(NODE_MIN_W, Math.ceil(textWidth(title)) + 30),
        generation: 0,
        positioned: false,
      };
      personMap.set(String(p.id), rec);
    });

    // Pozycjonowanie i połączenia
    const allNodes = positionNodes();
    const { connections, marriages } = findConnections(allNodes);

    // Obliczanie wymiarów
    const xs = allNodes.map((n) => [n.x, n.x + n.boxW]).flat();
    const ys = allNodes.map((n) => n.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const W = maxX - minX + 2 * MARGIN;
    const H = maxY - minY + NODE_HEIGHT + 2 * MARGIN;

    // Renderowanie SVG
    chart.innerHTML = "";
    
    const svg = d3
      .create("svg")
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .call(
        d3
          .zoom()
          .scaleExtent([0.2, 4])
          .on("zoom", (e) => g.attr("transform", e.transform)),
      );

    const g = svg
      .append("g")
      .attr("transform", `translate(${-minX + MARGIN}, ${-minY + MARGIN})`);

    // Rysowanie połączeń rodzic-dziecko
    g.append("g")
      .selectAll("path")
      .data(connections.filter((c) => c.type === "parent-child"))
      .join("path")
      .attr("d", (d) => {
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
      .attr("y1", ([left, right]) => left.y + NODE_HEIGHT / 2)
      .attr("x2", ([left, right]) => right.x)
      .attr("y2", ([left, right]) => right.y + NODE_HEIGHT / 2)
      .attr("stroke", "#e74c3c")
      .attr("stroke-width", 3);

    // Kolory pokoleń
    const generationColors = [
      "#3498db", "#e74c3c", "#2ecc71", 
      "#f39c12", "#9b59b6", "#1abc9c"
    ];
    
    const getColor = (generation) =>
      generationColors[generation % generationColors.length];

    // Rysowanie węzłów
    const ng = g
      .append("g")
      .selectAll("g")
      .data(allNodes)
      .join("g")
      .attr("transform", (d) => `translate(${d.x}, ${d.y})`)
      .on("dblclick", (_, d) => {
        rootId = parseInt(d.nodeId);
        drawTree();
      });

    // Prostokąty osób
    ng.append("rect")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", (d) => d.boxW)
      .attr("height", NODE_HEIGHT)
      .attr("rx", 8)
      .attr("ry", 8)
      .attr("fill", "#fff")
      .attr("stroke", (d) => (d.isRoot ? "#e74c3c" : getColor(d.generation)))
      .attr("stroke-width", (d) => (d.isRoot ? 4 : 2));

    // Imiona i nazwiska
    ng.append("text")
      .attr("x", (d) => d.boxW / 2)
      .attr("y", NODE_HEIGHT / 2 - 8)
      .attr("text-anchor", "middle")
      .style("font", FONT)
      .text((d) => d.name);

    // Daty życia
    ng.append("text")
      .attr("x", (d) => d.boxW / 2)
      .attr("y", NODE_HEIGHT / 2 + 8)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .style("fill", "#666")
      .text((d) => {
        const b = d.birth, dd = d.death;
        return b && !dd
          ? `ur. ${b}`
          : dd && !b
            ? `† ${dd}`
            : b && dd
              ? `${b} – ${dd}`
              : "";
      });

    // Linki do protokołów
    ng.filter((d) => d.key && !d.isRoot)
      .append("text")
      .attr("x", (d) => d.boxW / 2)
      .attr("y", NODE_HEIGHT - 8)
      .attr("text-anchor", "middle")
      .style("font-size", "11px")
      .style("fill", "#007bff")
      .style("text-decoration", "underline")
      .style("cursor", "pointer")
      .text("📜 Protokół")
      .on("click", async function(event, d) {
        event.stopPropagation();

        const currentPort = window.location.port;
        const isInGenealogyEditor = currentPort === '5001';
        const isInMainApp = currentPort === '5000' || !currentPort;

        if (isInMainApp) {
          window.location.href = `/wlasciciele/protokol.html?ownerId=${d.key}`;
          return;
        }

        if (isInGenealogyEditor) {
          let loadingOverlay = null;
          try {
            loadingOverlay = document.createElement("div");
            loadingOverlay.className = "loading-overlay";
            loadingOverlay.innerHTML = `
              <div class="loading-content">
                <h3>Sprawdzanie backendu…</h3>
                <div class="spinner"></div>
              </div>
            `;
            document.body.appendChild(loadingOverlay);

            const checkResponse = await fetch("/api/editor/check-main");
            const checkData = await checkResponse.json();

            if (checkData.available && checkData.url) {
              const backendURL = new URL(checkData.url);
              const sameHost = backendURL.hostname === window.location.hostname;
              const samePort = backendURL.port === '5000' || backendURL.port === window.location.port;

              if (!sameHost || !samePort) {
                alert(
                  `Nie można przejść do protokołu.\n` +
                  `Backend działa pod innym adresem: ${backendURL.origin}\n\n` +
                  `Zmień FLASK_HOST/FLASK_PORT w .env backendu.`
                );
                return;
              }

              window.location.href = `${checkData.url}/wlasciciele/protokol.html?ownerId=${d.key}`;
              return;
            }

            alert(
              "Nie można przejść do protokołu.\n" +
              "Backend nie jest osiągalny pod domyślnym adresem (127.0.0.1:5000)."
            );
          } catch (err) {
            console.error(err);
            alert("Wystąpił błąd podczas sprawdzania backendu.");
          } finally {
            if (loadingOverlay && loadingOverlay.parentNode) loadingOverlay.remove();
          }
          return;
        }

        alert("Nie można przejść do protokołu: nieznany kontekst aplikacji.");
      });

    chart.appendChild(svg.node());

    // ==========================================================================
    // FUNKCJE WEWNĘTRZNE
    // ==========================================================================

    /**
     * Grupuje osoby według pokoleń.
     */
    function groupByGenerations() {
      // Reset pokoleń
      personMap.forEach((p) => (p.generation = null));
      
      // Znajdź korzenie
      const roots = Array.from(personMap.values()).filter(
        (p) => !p.ojciec_id && !p.matka_id,
      );
      
      // BFS
      const queue = roots.map((p) => ({ person: p, gen: 0 }));
      const visited = new Set(roots.map((p) => p.nodeId));

      while (queue.length > 0) {
        const { person, gen } = queue.shift();
        person.generation = gen;

        personMap.forEach((child) => {
          if (
            (child.ojciec_id === person.nodeId ||
              child.matka_id === person.nodeId) &&
            !visited.has(child.nodeId)
          ) {
            queue.push({ person: child, gen: gen + 1 });
            visited.add(child.nodeId);
          }
        });
      }
      
      // Osoby bez połączeń
      personMap.forEach((p) => {
        if (p.generation === null) p.generation = 0;
      });

      // Stabilizacja pokoleń
      let changedInLoop = true;
      
      while (changedInLoop) {
        changedInLoop = false;

        personMap.forEach((person) => {
          // Dziecko poniżej rodziców
          const father = person.ojciec_id ? personMap.get(person.ojciec_id) : null;
          const mother = person.matka_id ? personMap.get(person.matka_id) : null;

          if (father || mother) {
            const parentGens = [];
            if (father) parentGens.push(father.generation);
            if (mother) parentGens.push(mother.generation);

            const maxParentGen = Math.max(...parentGens);
            const expectedGen = maxParentGen + 1;

            if (person.generation < expectedGen) {
              person.generation = expectedGen;
              changedInLoop = true;
            }
          }

          // Małżonkowie w tym samym pokoleniu
          const spouse = person.malzonek_id ? personMap.get(person.malzonek_id) : null;
          
          if (spouse) {
            const maxGen = Math.max(person.generation, spouse.generation);
            
            if (person.generation !== maxGen) {
              person.generation = maxGen;
              changedInLoop = true;
            }
            if (spouse.generation !== maxGen) {
              spouse.generation = maxGen;
              changedInLoop = true;
            }
          }
        });
      }

      // Grupowanie
      const generations = new Map();
      personMap.forEach((p) => {
        const g = p.generation;
        if (!generations.has(g)) generations.set(g, []);
        generations.get(g).push(p);
      });

      return new Map([...generations.entries()].sort((a, b) => a[0] - b[0]));
    }

    /**
     * Rozszerza dane o węzły-unie dla małżeństw.
     */
    function expandUnions(rawPeople) {
      const nodes = [];
      const unions = [];
      
      rawPeople.forEach((p) => {
        if (Array.isArray(p.malzenstwa) && p.malzenstwa.length) {
          p.malzenstwa.forEach((m, idx) => {
            const uid = `u_${p.id}_${m.spouseId}_${idx}`;
            unions.push({
              id: uid,
              type: "union",
              parents: [p.id, m.spouseId],
              children: m.children,
            });
          });
        }
        nodes.push(p);
      });
      
      return nodes.concat(unions);
    }

    /**
     * Pozycjonuje węzły w układzie 2D.
     */
    function positionNodes() {
      const generations = groupByGenerations();
      const generationNodes = [];
      let currentY = MARGIN;
      
      const surname = (p) => (p.name.split(" ").pop() || "").toLowerCase();

      generations.forEach((persons, genLevel) => {
        persons.sort((a, b) => surname(a).localeCompare(surname(b)));
        
        const marriagesArr = [];
        const singles = [];
        const used = new Set();

        // Grupuj małżeństwa i single
        persons.forEach((person) => {
          if (used.has(person.nodeId)) return;

          if (person.malzonek_id && personMap.has(person.malzonek_id)) {
            const spouse = personMap.get(person.malzonek_id);
            
            if (spouse.generation === genLevel) {
              const left = surname(person) <= surname(spouse) ? person : spouse;
              const right = left === person ? spouse : person;
              
              marriagesArr.push([left, right]);
              used.add(left.nodeId);
              used.add(right.nodeId);
              return;
            }
          }

          singles.push(person);
          used.add(person.nodeId);
        });

        singles.sort((a, b) => surname(a).localeCompare(surname(b)));
        marriagesArr.sort((a, b) => surname(a[0]).localeCompare(surname(b[0])));

        let currentX = MARGIN;
        const genNodes = [];

        // Pozycjonowanie singli
        singles.forEach((person) => {
          person.x = currentX;
          person.y = currentY;
          genNodes.push(person);
          currentX += person.boxW + H_GAP;
        });

        // Pozycjonowanie małżeństw
        marriagesArr.forEach(([left, right]) => {
          left.x = currentX;
          left.y = currentY;
          right.x = currentX + left.boxW + MARRIAGE_GAP;
          right.y = currentY;
          genNodes.push(left, right);
          currentX += left.boxW + MARRIAGE_GAP + right.boxW + H_GAP;

          console.log(
            `Małżeństwo: ${left.name} (${left.nodeId}) <-> ${right.name} (${right.nodeId})`,
          );
          console.log(
            `Pozycje: left(${left.x}, ${left.y}), right(${right.x}, ${right.y})`,
          );
        });

        generationNodes.push(...genNodes);
        currentY += NODE_HEIGHT + V_GAP;
      });

      return generationNodes;
    }

    /**
     * Znajduje połączenia między węzłami.
     */
    function findConnections(allNodes) {
      const connections = [];
      const marriages = [];
      const nodeById = new Map(allNodes.map((n) => [n.nodeId, n]));

      // Linie małżeńskie
      allNodes.forEach((person) => {
        const spouseId = person.malzonek_id;
        if (!spouseId) return;
        
        const spouse = nodeById.get(spouseId);
        if (!spouse) return;

        console.log(
          `Sprawdzanie małżeństwa: ${person.name} (${person.nodeId}) -> ${spouse.name} (${spouse.nodeId})`,
        );
        console.log(
          `Wzajemność: ${spouse.malzonek_id === person.nodeId}, Pozycja: ${person.x < spouse.x}`,
        );

        if (spouse.malzonek_id === person.nodeId && person.x < spouse.x) {
          marriages.push([person, spouse]);
          console.log(`Dodano małżeństwo: ${person.name} <-> ${spouse.name}`);
        }
      });

      // Linie rodzic-dziecko
      allNodes.forEach((child) => {
        const father = child.ojciec_id ? nodeById.get(child.ojciec_id) : null;
        const mother = child.matka_id ? nodeById.get(child.matka_id) : null;
        
        if (!father && !mother) return;

        let sourceX, sourceY;
        
        if (father && mother) {
          const left = father.x < mother.x ? father : mother;
          const right = left === father ? mother : father;
          sourceX = (left.x + left.boxW + right.x) / 2;
          sourceY = left.y + NODE_HEIGHT / 2;
        } else {
          const solo = father || mother;
          sourceX = solo.x + solo.boxW / 2;
          sourceY = solo.y + NODE_HEIGHT;
        }

        connections.push({
          type: "parent-child",
          source: { x: sourceX, y: sourceY },
          target: { x: child.x + child.boxW / 2, y: child.y },
          child,
        });
      });

      console.log(
        `Znaleziono ${marriages.length} małżeństw i ${connections.length} połączeń rodzic-dziecko`,
      );
      
      return { connections, marriages };
    }
  }

  // ==========================================================================
  // OBSŁUGA ZDARZEŃ
  // ==========================================================================

  closeBtn.addEventListener("click", () => modal.classList.remove("visible"));
  
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("visible");
  });

  /**
   * Inicjalizacja po załadowaniu strony.
   */
  window.addEventListener("load", async () => {
    const ownerKey = new URLSearchParams(window.location.search).get("ownerId");
    if (!ownerKey) return;

    try {
      await fetchData(ownerKey);
      if (!people.length) return;

      showBtn.classList.remove("hidden");
      showBtn.addEventListener("click", async () => {
        modal.classList.add("visible");
        chart.innerHTML = "<h2>Ładowanie...</h2>";
        
        try {
          await ensureLibs();
          drawTree();
        } catch (e) {
          chart.innerHTML = `<h2>Błąd: ${e.message}</h2>`;
          console.error(e);
        }
      });
    } catch (e) {
      console.error("Błąd ładowania danych genealogicznych:", e);
    }
  });
  
  // ==========================================================================
  // EKSPORT API
  // ==========================================================================
  
  window.genealogiaD3 = {
    ensureLibs,
    fetchData,
    drawTree,
  };
})();