// --- INFORMACJE O PLIKU ---
// Plik: genealogia_d3_fixed.js
// Opis: Moduł wizualizacji drzewa genealogicznego wykorzystujący bibliotekę D3.js.
//       Renderuje interaktywne drzewo z automatycznym pozycjonowaniem węzłów,
//       grupowaniem po pokoleniach i wizualizacją relacji rodzinnych.

(function () {
  // --- KONFIGURACJA STAŁYCH WIZUALIZACJI ---
  
  // Wymiary i odstępy węzłów w drzewie
  const NODE_HEIGHT = 80;      // Wysokość pojedynczego węzła (osoby)
  const NODE_MIN_W = 120;      // Minimalna szerokość węzła
  const H_GAP = 80;           // Odstęp poziomy między węzłami
  const V_GAP = 120;          // Odstęp pionowy między pokoleniami
  const MARGIN = 80;          // Margines wokół całego drzewa
  const MARRIAGE_GAP = 20;    // Odstęp między małżonkami
  
  // Konfiguracja czcionki dla tekstów w drzewie
  const FONT = '700 16px "Segoe UI", sans-serif';

  // --- ZMIENNE GLOBALNE MODUŁU ---
  
  let COLORS = [];            // Paleta kolorów dla pokoleń (ładowana z D3)
  let people = [];            // Tablica wszystkich osób w drzewie
  let rootId = null;          // ID osoby będącej korzeniem drzewa

  // --- REFERENCJE DO ELEMENTÓW DOM ---
  
  const modal = document.getElementById("genealogyModal");
  const chart = document.getElementById("genealogy-chart");
  const showBtn = document.getElementById("showGenealogyTreeBtn");
  const closeBtn = document.getElementById("closeGenealogyModalBtn");

  // --- CZYSZCZENIE STARYCH NAKŁADEK ---

  // Funkcja czyszcząca stare nakładki ładowania przy powrocie do strony
  (function cleanupOldOverlays() {
    const oldOverlays = document.querySelectorAll('.loading-overlay');
    oldOverlays.forEach(overlay => overlay.remove());
  })();

  // --- FUNKCJE POMOCNICZE ---

  /**
   * Dynamicznie ładuje skrypt JavaScript.
   * 
   * Sprawdza czy skrypt już istnieje w DOM, jeśli nie - dodaje go.
   * Używane do ładowania bibliotek D3.js i d3-flextree na żądanie.
   * 
   * @param {string} src - URL skryptu do załadowania
   * @returns {Promise} - Promise rozwiązywana po załadowaniu skryptu
   */
  const loadScript = (src) =>
    new Promise((res, rej) => {
      // Sprawdź czy skrypt już jest załadowany
      if (document.querySelector(`script[src="${src}"]`)) return res();
      
      // Utwórz nowy element script
      const s = document.createElement("script");
      s.src = src;
      s.onload = res;
      s.onerror = () => rej(new Error(`Nie można załadować ${src}`));
      document.head.appendChild(s);
    });

  /**
   * Zapewnia dostępność wymaganych bibliotek.
   * 
   * Ładuje D3.js i d3-flextree jeśli nie są jeszcze dostępne.
   * Inicjalizuje też paletę kolorów dla pokoleń.
   */
  async function ensureLibs() {
    // Załaduj główną bibliotekę D3.js
    if (!window.d3) await loadScript("https://cdn.jsdelivr.net/npm/d3@7");
    
    // Załaduj rozszerzenie do elastycznego pozycjonowania drzew
    if (!d3.flextree)
      await loadScript("https://cdn.jsdelivr.net/npm/d3-flextree@2");
    
    // Zainicjalizuj paletę kolorów
    if (!COLORS.length) COLORS = d3.schemeTableau10;
  }

  /**
   * Pobiera dane genealogiczne z API.
   * 
   * @param {string} ownerKey - Klucz właściciela lub nazwisko rodziny
   * @returns {Promise} - Promise z danymi drzewa
   */
  async function fetchData(ownerKey) {
    const res = await fetch(`/api/genealogia/drzewo/${ownerKey}`);
    if (!res.ok) throw new Error("Błąd pobierania danych genealogicznych");
    
    const data = await res.json();
    people = data.people ?? [];
    rootId = data.start_node_id ?? null;
  }

  /**
   * Główna funkcja rysująca drzewo genealogiczne.
   * 
   * Wykonuje następujące kroki:
   * 1. Przygotowuje dane i oblicza szerokości węzłów
   * 2. Określa pokolenia dla każdej osoby
   * 3. Pozycjonuje węzły w układzie drzewa
   * 4. Znajduje połączenia (relacje rodzinne)
   * 5. Renderuje SVG z użyciem D3.js
   */
  function drawTree() {
    // Sprawdzenie czy są dane do wyświetlenia
    if (!people.length) {
      chart.innerHTML = "<h2>Brak danych do wyświetlenia.</h2>";
      return;
    }

    // Dodanie stylów dla nakładki ładowania jeśli nie istnieją
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

    // --- KROK 1: PRZYGOTOWANIE DANYCH ---
    
    // Utworzenie kontekstu canvas do pomiaru szerokości tekstu
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = FONT;
    const textWidth = (t) => ctx.measureText(t).width;
    
    // Rozszerzenie danych o węzły-unie (dla małżeństw z dziećmi)
    people = expandUnions(people);

    // Przygotowanie mapy osób z obliczonymi wymiarami
    const personMap = new Map();
    people.forEach((p) => {
      const title = `${p.imie} ${p.nazwisko || ""}`.trim();
      
      // Tworzenie rekordu osoby z wszystkimi potrzebnymi danymi
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
        boxW: Math.max(NODE_MIN_W, Math.ceil(textWidth(title)) + 30), // Dynamiczna szerokość
        generation: 0,      // Pokolenie (do obliczenia)
        positioned: false,   // Flaga pozycjonowania
      };
      personMap.set(String(p.id), rec);
    });

    // --- KROK 2: ALGORYTM OKREŚLANIA POKOLEŃ ---

    /**
     * Oblicza pokolenia dla wszystkich osób w drzewie.
     * 
     * Używa algorytmu przeszukiwania w głąb (DFS) startując
     * od osób bez rodziców (korzenie) i propagując w dół.
     */
    function calculateGenerations() {
      const visited = new Set();

      /**
       * Rekurencyjnie ustawia pokolenie dla osoby i jej potomków.
       */
      function setGeneration(personId, generation) {
        if (visited.has(personId)) return;
        visited.add(personId);

        const person = personMap.get(personId);
        if (!person) return;

        // Aktualizuj pokolenie tylko jeśli jest większe
        person.generation = Math.max(person.generation, generation);

        // Ustaw pokolenie dla dzieci (jedno niżej)
        personMap.forEach((child) => {
          if (child.ojciec_id === personId || child.matka_id === personId) {
            setGeneration(child.nodeId, generation + 1);
          }
        });
      }

      // Znajdź osoby-korzenie (bez rodziców)
      const rootPersons = Array.from(personMap.values()).filter(
        (p) => !p.ojciec_id && !p.matka_id,
      );

      // Jeśli nie ma osób bez rodziców, użyj najstarszych
      if (rootPersons.length === 0) {
        const oldestYear = Math.min(
          ...Array.from(personMap.values())
            .filter((p) => p.birth)
            .map((p) => p.birth),
        );
        rootPersons.push(
          ...Array.from(personMap.values()).filter(
            (p) => p.birth === oldestYear,
          ),
        );
      }

      // Ustaw pokolenia zaczynając od korzeni
      rootPersons.forEach((root) => setGeneration(root.nodeId, 0));

      // Dla nieprzypisanych osób, określ pokolenie na podstawie dzieci
      personMap.forEach((person) => {
        if (
          person.generation === 0 &&
          person.nodeId !== rootPersons[0]?.nodeId
        ) {
          const children = Array.from(personMap.values()).filter(
            (p) =>
              p.ojciec_id === person.nodeId || p.matka_id === person.nodeId,
          );
          if (children.length > 0) {
            const maxChildGen = Math.max(...children.map((c) => c.generation));
            person.generation = maxChildGen - 1;
          }
        }
      });
    }

    /**
     * Wyrównuje pokolenia małżonków.
     * 
     * Iteracyjnie sprawdza wszystkie pary małżeńskie
     * i ustawia im to samo (wyższe) pokolenie.
     */
    function unifySpouseGenerations() {
      let changed = true;
      
      // Powtarzaj dopóki zachodzą zmiany
      while (changed) {
        changed = false;
        
        personMap.forEach((p) => {
          if (!p.malzonek_id || !personMap.has(p.malzonek_id)) return;
          
          const s = personMap.get(p.malzonek_id);
          const lev = Math.max(p.generation, s.generation); // Wybierz wyższe pokolenie
          
          // Jeśli pokolenia się różnią, wyrównaj je
          if (p.generation !== lev || s.generation !== lev) {
            p.generation = s.generation = lev;
            changed = true;
          }
        });
      }
    }

    /**
     * Propaguje pokolenia w dół dla dzieci.
     * 
     * Zapewnia że dzieci są zawsze w pokoleniu
     * co najmniej o 1 niższym niż rodzice.
     */
    function propagateChildGenerations() {
      let bumped = true;
      
      while (bumped) {
        bumped = false;
        
        personMap.forEach((child) => {
          // Znajdź rodziców
          const parents = [];
          if (child.ojciec_id && personMap.has(child.ojciec_id))
            parents.push(personMap.get(child.ojciec_id));
          if (child.matka_id && personMap.has(child.matka_id))
            parents.push(personMap.get(child.matka_id));
          
          if (!parents.length) return;

          // Dziecko musi być co najmniej 1 pokolenie niżej niż najniższy rodzic
          const wanted = Math.min(...parents.map((p) => p.generation)) + 1;
          
          if (child.generation < wanted) {
            child.generation = wanted;
            bumped = true;
          }
        });
      }
    }

    /**
     * Grupuje osoby według pokoleń z pełną stabilizacją.
     * 
     * Wykonuje wieloetapowy algorytm:
     * 1. Wstępne przypisanie pokoleń (BFS)
     * 2. Stabilizacja z regułami rodzic-dziecko i małżonkowie
     * 3. Ostateczne grupowanie
     * 
     * @returns {Map} - Mapa pokoleń z listami osób
     */
    function groupByGenerations() {
      // --- ETAP 1: Wstępne przypisanie pokoleń (BFS) ---
      
      // Reset pokoleń
      personMap.forEach((p) => (p.generation = null));
      
      // Znajdź korzenie (osoby bez rodziców)
      const roots = Array.from(personMap.values()).filter(
        (p) => !p.ojciec_id && !p.matka_id,
      );
      
      // Kolejka BFS
      const queue = roots.map((p) => ({ person: p, gen: 0 }));
      const visited = new Set(roots.map((p) => p.nodeId));

      // Przeszukiwanie wszerz
      while (queue.length > 0) {
        const { person, gen } = queue.shift();
        person.generation = gen;

        // Znajdź dzieci tej osoby
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
      
      // Osoby "wiszące" dostają pokolenie 0
      personMap.forEach((p) => {
        if (p.generation === null) p.generation = 0;
      });

      // --- ETAP 2: Pętla stabilizująca ---
      
      let changedInLoop = true;
      
      while (changedInLoop) {
        changedInLoop = false;

        personMap.forEach((person) => {
          // REGUŁA 1: Dziecko musi być poniżej rodziców
          const father = person.ojciec_id
            ? personMap.get(person.ojciec_id)
            : null;
          const mother = person.matka_id
            ? personMap.get(person.matka_id)
            : null;

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

          // REGUŁA 2: Małżonkowie w tym samym pokoleniu
          const spouse = person.malzonek_id
            ? personMap.get(person.malzonek_id)
            : null;
          
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

      // --- ETAP 3: Ostateczne grupowanie ---
      
      const generations = new Map();
      personMap.forEach((p) => {
        const g = p.generation;
        if (!generations.has(g)) generations.set(g, []);
        generations.get(g).push(p);
      });

      // Sortowanie pokoleń rosnąco
      return new Map([...generations.entries()].sort((a, b) => a[0] - b[0]));
    }

    /**
     * Rozszerza dane o niewidoczne węzły-unie dla małżeństw.
     * 
     * Tworzy specjalne węzły reprezentujące związki małżeńskie
     * z dziećmi, co ułatwia rysowanie połączeń.
     * 
     * @param {Array} rawPeople - Surowe dane osób
     * @returns {Array} - Rozszerzona tablica z węzłami-uniami
     */
    function expandUnions(rawPeople) {
      const nodes = [];  // Osoby + unie
      const unions = []; // Same unie (do rysowania)
      
      rawPeople.forEach((p) => {
        // Jeśli osoba ma małżeństwa z dziećmi, utwórz węzły-unie
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
     * 
     * Układa osoby w poziomych warstwach według pokoleń,
     * grupując małżonków obok siebie i sortując alfabetycznie.
     * 
     * @returns {Array} - Tablica węzłów z obliczonymi pozycjami x,y
     */
    function positionNodes() {
      const generations = groupByGenerations();
      const generationNodes = [];
      let currentY = MARGIN;
      
      // Funkcja pomocnicza: wyciąga nazwisko z pełnego imienia
      const surname = (p) => (p.name.split(" ").pop() || "").toLowerCase();

      // Przetwarzaj każde pokolenie osobno
      generations.forEach((persons, genLevel) => {
        // Sortuj osoby w pokoleniu alfabetycznie po nazwisku
        persons.sort((a, b) => surname(a).localeCompare(surname(b)));
        
        // Tablice dla małżeństw i singli
        const marriagesArr = [];
        const singles = [];
        const used = new Set();

        // Grupuj osoby w pary małżeńskie lub jako single
        persons.forEach((person) => {
          if (used.has(person.nodeId)) return;

          // Sprawdź czy osoba ma małżonka w tym samym pokoleniu
          if (person.malzonek_id && personMap.has(person.malzonek_id)) {
            const spouse = personMap.get(person.malzonek_id);
            
            if (spouse.generation === genLevel) {
              // Ustaw lewą osobę (alfabetycznie wcześniejszą)
              const left = surname(person) <= surname(spouse) ? person : spouse;
              const right = left === person ? spouse : person;
              
              marriagesArr.push([left, right]);
              used.add(left.nodeId);
              used.add(right.nodeId);
              return;
            }
          }

          // Osoba bez małżonka lub małżonek w innym pokoleniu
          singles.push(person);
          used.add(person.nodeId);
        });

        // Sortowanie: single najpierw, potem małżeństwa
        singles.sort((a, b) => surname(a).localeCompare(surname(b)));
        marriagesArr.sort((a, b) => surname(a[0]).localeCompare(surname(b[0])));

        let currentX = MARGIN;
        const genNodes = [];

        // --- Pozycjonowanie singli ---
        singles.forEach((person) => {
          person.x = currentX;
          person.y = currentY;
          genNodes.push(person);
          currentX += person.boxW + H_GAP;
        });

        // --- Pozycjonowanie małżeństw ---
        marriagesArr.forEach(([left, right]) => {
          left.x = currentX;
          left.y = currentY;
          right.x = currentX + left.boxW + MARRIAGE_GAP;
          right.y = currentY;
          genNodes.push(left, right);
          currentX += left.boxW + MARRIAGE_GAP + right.boxW + H_GAP;

          // Logowanie diagnostyczne dla debugowania
          console.log(
            `Małżeństwo: ${left.name} (${left.nodeId}) <-> ${right.name} (${right.nodeId})`,
          );
          console.log(
            `Pozycje: left(${left.x}, ${left.y}), right(${right.x}, ${right.y})`,
          );
        });

        generationNodes.push(...genNodes);
        currentY += NODE_HEIGHT + V_GAP; // Przejdź do następnego pokolenia
      });

      return generationNodes;
    }

    /**
     * Znajduje wszystkie połączenia między węzłami.
     * 
     * Identyfikuje dwa typy połączeń:
     * 1. Linie małżeńskie (czerwone, poziome)
     * 2. Linie rodzic-dziecko (szare, łamane)
     * 
     * @param {Array} allNodes - Wszystkie węzły z pozycjami
     * @returns {Object} - Obiekt z tablicami connections i marriages
     */
    function findConnections(allNodes) {
      const connections = [];
      const marriages = [];
      const nodeById = new Map(allNodes.map((n) => [n.nodeId, n]));

      // --- ZNAJDOWANIE LINII MAŁŻEŃSKICH ---
      
      allNodes.forEach((person) => {
        const spouseId = person.malzonek_id;
        if (!spouseId) return;
        
        const spouse = nodeById.get(spouseId);
        if (!spouse) return;

        // Logowanie diagnostyczne
        console.log(
          `Sprawdzanie małżeństwa: ${person.name} (${person.nodeId}) -> ${spouse.name} (${spouse.nodeId})`,
        );
        console.log(
          `Wzajemność: ${spouse.malzonek_id === person.nodeId}, Pozycja: ${person.x < spouse.x}`,
        );

        // Małżeństwo rysujemy tylko raz (gdy jest wzajemne i osoba jest po lewej)
        if (spouse.malzonek_id === person.nodeId && person.x < spouse.x) {
          marriages.push([person, spouse]);
          console.log(`Dodano małżeństwo: ${person.name} <-> ${spouse.name}`);
        }
      });

      // --- ZNAJDOWANIE LINII RODZIC-DZIECKO ---
      
      allNodes.forEach((child) => {
        const father = child.ojciec_id ? nodeById.get(child.ojciec_id) : null;
        const mother = child.matka_id ? nodeById.get(child.matka_id) : null;
        
        // Pomiń jeśli brak rodziców
        if (!father && !mother) return;

        let sourceX, sourceY;
        
        if (father && mother) {
          // Oboje rodzice → start w połowie linii małżeńskiej
          const left = father.x < mother.x ? father : mother;
          const right = left === father ? mother : father;
          sourceX = (left.x + left.boxW + right.x) / 2;
          sourceY = left.y + NODE_HEIGHT / 2; // Wysokość linii małżeńskiej
        } else {
          // Tylko jeden rodzic → start z dolnej krawędzi rodzica
          const solo = father || mother;
          sourceX = solo.x + solo.boxW / 2;
          sourceY = solo.y + NODE_HEIGHT; // Dół pudełka rodzica
        }

        // Dodaj połączenie rodzic-dziecko
        connections.push({
          type: "parent-child",
          source: { x: sourceX, y: sourceY },
          target: { x: child.x + child.boxW / 2, y: child.y }, // Góra pudełka dziecka
          child,
        });
      });

      console.log(
        `Znaleziono ${marriages.length} małżeństw i ${connections.length} połączeń rodzic-dziecko`,
      );
      
      return { connections, marriages };
    }

    // --- WYKONANIE ALGORYTMU POZYCJONOWANIA ---
    
    const allNodes = positionNodes();
    const { connections, marriages } = findConnections(allNodes);

    // --- OBLICZANIE WYMIARÓW CANVAS ---
    
    // Znajdź skrajne pozycje węzłów
    const xs = allNodes.map((n) => [n.x, n.x + n.boxW]).flat();
    const ys = allNodes.map((n) => n.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    
    // Oblicz wymiary SVG z marginesami
    const W = maxX - minX + 2 * MARGIN;
    const H = maxY - minY + NODE_HEIGHT + 2 * MARGIN;

    // --- RENDEROWANIE SVG Z D3.JS ---
    
    // Wyczyść poprzednią zawartość
    chart.innerHTML = "";
    
    // Utwórz główny element SVG z obsługą zoom/pan
    const svg = d3
      .create("svg")
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("viewBox", `0 0 ${W} ${H}`)
      .call(
        d3
          .zoom()
          .scaleExtent([0.2, 4]) // Zakres powiększenia: 20% - 400%
          .on("zoom", (e) => g.attr("transform", e.transform)),
      );

    // Grupa główna z translacją do właściwych współrzędnych
    const g = svg
      .append("g")
      .attr("transform", `translate(${-minX + MARGIN}, ${-minY + MARGIN})`);

    // --- RYSOWANIE POŁĄCZEŃ RODZIC-DZIECKO ---
    
    g.append("g")
      .selectAll("path")
      .data(connections.filter((c) => c.type === "parent-child"))
      .join("path")
      .attr("d", (d) => {
        // Ścieżka łamana: pionowo do połowy, poziomo, pionowo do dziecka
        const midY = (d.source.y + d.target.y) / 2;
        return `M${d.source.x},${d.source.y}V${midY}H${d.target.x}V${d.target.y}`;
      })
      .attr("stroke", "#999")
      .attr("stroke-width", 2)
      .attr("fill", "none");

    // --- RYSOWANIE LINII MAŁŻEŃSTW ---
    
    g.append("g")
      .selectAll("line")
      .data(marriages)
      .join("line")
      .attr("x1", ([left, right]) => left.x + left.boxW)
      .attr("y1", ([left, right]) => left.y + NODE_HEIGHT / 2)
      .attr("x2", ([left, right]) => right.x)
      .attr("y2", ([left, right]) => right.y + NODE_HEIGHT / 2)
      .attr("stroke", "#e74c3c") // Czerwony kolor dla małżeństw
      .attr("stroke-width", 3);

    // --- DEFINICJA KOLORÓW DLA POKOLEŃ ---
    
    const generationColors = [
      "#3498db", // Niebieski
      "#e74c3c", // Czerwony
      "#2ecc71", // Zielony
      "#f39c12", // Pomarańczowy
      "#9b59b6", // Fioletowy
      "#1abc9c", // Turkusowy
    ];
    
    /**
     * Zwraca kolor dla danego pokolenia.
     * Kolory cyklicznie się powtarzają.
     */
    const getColor = (generation) =>
      generationColors[generation % generationColors.length];

    // --- RYSOWANIE WĘZŁÓW (OSÓB) ---
    
    // Grupa dla każdego węzła
    const ng = g
      .append("g")
      .selectAll("g")
      .data(allNodes)
      .join("g")
      .attr("transform", (d) => `translate(${d.x}, ${d.y})`)
      .on("dblclick", (_, d) => {
        // Podwójne kliknięcie zmienia korzeń drzewa
        rootId = parseInt(d.nodeId);
        drawTree();
      });

    // Prostokąty reprezentujące osoby
    ng.append("rect")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", (d) => d.boxW)
      .attr("height", NODE_HEIGHT)
      .attr("rx", 8)  // Zaokrąglone rogi
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

    // Daty życia (urodzenie - śmierć)
    ng.append("text")
      .attr("x", (d) => d.boxW / 2)
      .attr("y", NODE_HEIGHT / 2 + 8)
      .attr("text-anchor", "middle")
      .style("font-size", "12px")
      .style("fill", "#666")
      .text((d) => {
        const b = d.birth, dd = d.death;
        // Formatowanie: "ur. YYYY", "† YYYY", lub "YYYY – YYYY"
        return b && !dd
          ? `ur. ${b}`
          : dd && !b
            ? `† ${dd}`
            : b && dd
              ? `${b} – ${dd}`
              : "";
      });

    // Linki do protokołów (dla osób z kluczem protokołu)
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

        // Określenie kontekstu aplikacji na podstawie portu
        const currentPort = window.location.port;
        const isInGenealogyEditor = currentPort === '5001';
        const isInMainApp = currentPort === '5000' || !currentPort; // Port 5000 lub domyślny 80/443

        if (isInMainApp) {
          // Jesteśmy w głównej aplikacji – spróbuj przejść lokalnie
          window.location.href = `/wlasciciele/protokol.html?ownerId=${d.key}`;
          return;
        }

        if (isInGenealogyEditor) {
          // Edytor genealogii – sprawdź czy „główna” (backend) jest na znanym adresie
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

            // Pytamy lokalny pomocniczy endpoint – on sprawdza 127.0.0.1:5000
            const checkResponse = await fetch("/api/editor/check-main");
            const checkData = await checkResponse.json();

            if (checkData.available && checkData.url) {
              // Backend dostępny na wskazanym URL – ale jeżeli to INNY host/port niż bieżący,
              // pokaż komunikat i nie nawiguj automatycznie.
              const backendURL = new URL(checkData.url);
              const sameHost = backendURL.hostname === window.location.hostname;
              const samePort = backendURL.port === '5000' || backendURL.port === window.location.port;

              if (!sameHost || !samePort) {
                alert(
                  `Nie można przejść do protokołu.\n` +
                  `Backend działa pod innym adresem: ${backendURL.origin}\n\n` +
                  `Zmień FLASK_HOST/FLASK_PORT w .env backendu albo uruchom frontend z tego samego IP/portu.`
                );
                return;
              }

              // Jeżeli host/port są OK – przejdź
              window.location.href = `${checkData.url}/wlasciciele/protokol.html?ownerId=${d.key}`;
              return;
            }

            // Backend nie jest osiągalny pod standardem → komunikat
            alert(
              "Nie można przejść do protokołu.\n" +
              "Backend nie jest osiągalny pod domyślnym adresem (127.0.0.1:5000).\n\n" +
              "Wygląda na to, że działa na innym porcie/IP.\n" +
              "Zaktualizuj FLASK_HOST/FLASK_PORT w .env backendu lub uruchom go na 127.0.0.1:5000."
            );
          } catch (err) {
            console.error(err);
            alert("Wystąpił błąd podczas sprawdzania backendu.");
          } finally {
            if (loadingOverlay && loadingOverlay.parentNode) loadingOverlay.remove();
          }
          return;
        }

        // Nieznany kontekst – bezpiecznie przerwij
        alert("Nie można przejść do protokołu: nieznany kontekst aplikacji.");
      });

    // Dodaj gotowe SVG do kontenera
    chart.appendChild(svg.node());
  }

  // --- OBSŁUGA ZDARZEŃ INTERFEJSU ---

  // Zamykanie modala
  closeBtn.addEventListener("click", () => modal.classList.remove("visible"));
  
  // Zamykanie modala przez kliknięcie w tło
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("visible");
  });

  /**
   * Inicjalizacja po załadowaniu strony.
   * 
   * Sprawdza czy w URL jest parametr ownerId,
   * jeśli tak - ładuje dane i przygotowuje przycisk.
   */
  window.addEventListener("load", async () => {
    // Sprawdź parametr URL
    const ownerKey = new URLSearchParams(window.location.search).get("ownerId");
    if (!ownerKey) return;

    try {
      // Pobierz dane dla właściciela
      await fetchData(ownerKey);
      if (!people.length) return;

      // Pokaż przycisk i dodaj obsługę kliknięcia
      showBtn.classList.remove("hidden");
      showBtn.addEventListener("click", async () => {
        modal.classList.add("visible");
        chart.innerHTML = "<h2>Ładowanie...</h2>";
        
        try {
          // Załaduj biblioteki i narysuj drzewo
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
  
  // --- EKSPORT API DLA INNYCH MODUŁÓW ---
  
  /**
   * Eksportuje publiczne API modułu.
   * 
   * Umożliwia innym skryptom (np. editor_script.js)
   * korzystanie z funkcji wizualizacji drzewa.
   */
  window.genealogiaD3 = {
    ensureLibs,  // Ładowanie bibliotek
    fetchData,   // Pobieranie danych
    drawTree,    // Rysowanie drzewa
  };
})();