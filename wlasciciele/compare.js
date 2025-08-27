/**
 * Plik: compare.js
 * Opis: Skrypt obsługujący porównywanie dwóch protokołów właścicielskich.
 *       Umożliwia wyświetlanie danych, generowanie PDF, przeglądanie skanów
 *       oraz wizualizację drzew genealogicznych.
 */

document.addEventListener("DOMContentLoaded", () => {
    // === SEKCJA INICJALIZACJI DIALOGU DRZEWA ===
  const setupTreeDialog = () => {
    const closeTreeBtn = document.getElementById("closeTreeBtn");
    const treeDialog = document.getElementById("treeDialog");
    const treeContainer = document.getElementById("treeContainer");
    
    console.log("Inicjalizacja dialogu drzewa:", { closeTreeBtn, treeDialog, treeContainer });
    
    if (closeTreeBtn && !closeTreeBtn.hasAttribute('data-initialized')) {
      closeTreeBtn.addEventListener("click", () => {
        console.log("Zamykanie dialogu drzewa");
        if (treeDialog) {
          treeDialog.close();
          if (treeContainer) treeContainer.innerHTML = "";
        }
      });
      closeTreeBtn.setAttribute('data-initialized', 'true');
      
      // Obsługa ESC
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && treeDialog && treeDialog.open) {
          treeDialog.close();
          if (treeContainer) treeContainer.innerHTML = "";
        }
      });
      
      console.log("Dialog drzewa zainicjalizowany");
    }
  };
  
  setupTreeDialog();
  /**
   * Zarządza logiką zmiany i zapamiętywania motywu kolorystycznego.
   */
  const setupThemeLogic = () => {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (!themeToggleBtn) return;

    const icon = themeToggleBtn.querySelector('i');

    // Funkcja do zastosowania motywu i aktualizacji ikony
    const applyTheme = (theme) => {
      document.body.classList.toggle('dark-mode', theme === 'dark');
      if (icon) {
        icon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
      }
    };

    // Odczytanie zapisanego motywu i jego zastosowanie
    const savedTheme = localStorage.getItem('mapTheme') || 'light';
    applyTheme(savedTheme);

    // Listener do zmiany motywu przez użytkownika
    themeToggleBtn.addEventListener('click', () => {
      const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('mapTheme', newTheme);
      applyTheme(newTheme);
    });
  };
  
  /**
   * Zarządza trybem pełnoekranowym.
   */
  const setupFullscreen = () => {
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    if (!fullscreenBtn) return;
    const icon = fullscreenBtn.querySelector('i');

    fullscreenBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
        } else if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    });

    document.addEventListener('fullscreenchange', () => {
        if (icon) {
            icon.className = document.fullscreenElement ? 'fas fa-compress' : 'fas fa-expand';
        }
    });
  };

  // Inicjalizacja logiki motywu na starcie
  setupThemeLogic();
  // Inicjalizacja logiki pełnego ekranu
  setupFullscreen();
  
  /**
   * Sekcja 1: Inicjalizacja i walidacja parametrów URL
   */
  const urlParams = new URLSearchParams(window.location.search);
  const ownerKeys = urlParams.get("owners")?.split(",");

  // Ustawienie daty w stopce
  const currentDateEl = document.getElementById('currentDate');
  if (currentDateEl) {
    currentDateEl.textContent = new Date().toLocaleDateString('pl-PL');
  }

  // Walidacja - wymagane są dokładnie 2 klucze właścicieli
  if (!ownerKeys || ownerKeys.length !== 2) {
    showError("Proszę wybrać dwóch właścicieli do porównania.");
    return;
  }

  /**
   * Funkcja wyświetlająca błąd
   */
  function showError(message) {
    document.querySelector('.compare-container').innerHTML = `
      <div style="width: 100%; display: flex; justify-content: center; align-items: center; min-height: 400px;">
        <div style="text-align: center; padding: 2rem; background: white; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
          <i class="fas fa-exclamation-triangle" style="font-size: 3rem; color: #e53e3e; margin-bottom: 1rem;"></i>
          <h2 style="color: #2d3748; margin-bottom: 0.5rem;">Błąd</h2>
          <p style="color: #718096;">${message}</p>
        </div>
      </div>
    `;
  }

  /**
   * Funkcja wyświetlająca spinner ładowania
   */
  function showLoadingSpinner() {
    document.querySelector('.compare-container').innerHTML = `
      <div class="loading-spinner" style="width: 100%;">
        <i class="fas fa-spinner fa-spin"></i>
        <span style="margin-left: 1rem;">Ładowanie protokołów...</span>
      </div>
    `;
  }

  /**
   * Sekcja 2: Konfiguracja linków do mapy
   */
  const mapLinkReal = document.getElementById("mapLinkReal");
  const mapLinkProtocol = document.getElementById("mapLinkProtocol");
  const mapLinkBoth = document.getElementById("mapLinkBoth");
  const mapUrl = "../mapa/mapa.html";

  const ownersParam = ownerKeys.join(",");

  // Tworzenie parametryzowanych linków do mapy
  if (mapLinkReal)
    mapLinkReal.href = `${mapUrl}?${new URLSearchParams({ highlightTopOwners: ownersParam, ownership: "rzeczywista" })}`;
  if (mapLinkProtocol)
    mapLinkProtocol.href = `${mapUrl}?${new URLSearchParams({ highlightTopOwners: ownersParam, ownership: "protokol" })}`;
  if (mapLinkBoth)
    mapLinkBoth.href = `${mapUrl}?${new URLSearchParams({ highlightTopOwners: ownersParam, ownership: "wszystkie" })}`;

  /**
   * Sekcja 3: Obsługa modala do wyświetlania skanów protokołów
   */
  const imageModal = document.getElementById("imageModal");
  const modalImg = document.getElementById("modalImageSrc");
  const prevBtn = document.getElementById("prevImageBtn");
  const nextBtn = document.getElementById("nextImageBtn");
  const counterLbl = document.getElementById("pageCounter");
  let panzoomInst = null;
  let imgs = [];
  let idx = 0;

  const treeDialog = document.getElementById("treeDialog");
  const closeTreeBtn = document.getElementById("closeTreeBtn");
  const treeContainer = document.getElementById("treeContainer");

  const openModal = (arr) => {
    if (!arr || arr.length === 0) {
      alert("Brak skanów protokołu.");
      return;
    }
    imgs = arr;
    idx = 0;
    updateModal();
    imageModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
    panzoomInst = Panzoom(modalImg, { maxScale: 5, minScale: 0.5 });
    modalImg.parentElement.addEventListener("wheel", panzoomInst.zoomWithWheel);
  };

  const closeModal = () => {
    imageModal.classList.add("hidden");
    document.body.style.overflow = "auto";
    if (panzoomInst) {
      panzoomInst.destroy();
      panzoomInst = null;
    }
  };

  const updateModal = () => {
    modalImg.src = imgs[idx];
    counterLbl.textContent = `Strona ${idx + 1} / ${imgs.length}`;
    prevBtn.disabled = idx === 0;
    nextBtn.disabled = idx === imgs.length - 1;
    document.querySelector(".modal-nav-controls").style.display =
      imgs.length > 1 ? "flex" : "none";
  };

  prevBtn.addEventListener("click", () => {
    if (idx > 0) {
      idx--;
      updateModal();
      panzoomInst.reset();
    }
  });

  nextBtn.addEventListener("click", () => {
    if (idx < imgs.length - 1) {
      idx++;
      updateModal();
      panzoomInst.reset();
    }
  });

  document
    .querySelector(".modal-close-btn")
    .addEventListener("click", closeModal);

  imageModal.addEventListener("click", (e) => {
    if (e.target === imageModal) closeModal();
  });

/**
 * Sekcja 5: Funkcja rysująca drzewo genealogiczne
 */
function drawGenealogyTree(treeData) {
  console.log("=== ROZPOCZĘCIE RYSOWANIA DRZEWA ===");
  console.log("Otrzymane dane:", treeData);
  
  // Pobierz elementy DOM
  const treeDialog = document.getElementById("treeDialog");
  const treeContainer = document.getElementById("treeContainer");
  
  // Sprawdź czy elementy istnieją
  if (!treeDialog || !treeContainer) {
    console.error("BŁĄD: Nie znaleziono elementów dialogu", { treeDialog, treeContainer });
    alert("Błąd: Nie można otworzyć drzewa genealogicznego (brak elementów DOM)");
    return;
  }
  
  // Walidacja danych wejściowych - ale spróbuj pokazać cokolwiek
  if (!treeData) {
    console.error("BŁĄD: Brak danych drzewa");
    treeContainer.innerHTML = `
      <div style="padding: 2rem; text-align: center;">
        <p style="color: red;">Błąd: Nie otrzymano danych drzewa</p>
      </div>
    `;
    treeDialog.showModal();
    return;
  }
  
  if (!treeData.persons || treeData.persons.length === 0) {
    console.warn("Brak osób w drzewie, pokazuję komunikat");
    treeContainer.innerHTML = `
      <div style="padding: 2rem; text-align: center;">
        <p>Brak danych genealogicznych do wyświetlenia</p>
        <p style="font-size: 0.9em; color: #666;">Dane genealogiczne nie zostały jeszcze wprowadzone dla tego właściciela</p>
      </div>
    `;
    treeDialog.showModal();
    return;
  }

  console.log(`Liczba osób w drzewie: ${treeData.persons.length}`);
  
  // Wyczyść poprzednią zawartość
  treeContainer.innerHTML = "";

  try {
    // Konfiguracja wymiarów i odstępów dla wizualizacji
    const NODE_WIDTH = 200,
      NODE_HEIGHT = 120,
      HORIZONTAL_SPACING = 80,
      VERTICAL_SPACING = 180,
      MARRIAGE_LINE_OFFSET = 20,
      MARGIN = 50,
      LEGEND_HEIGHT = 120;

    // Tworzenie mapy osób z danymi genealogicznymi
    const persons = new Map();
    treeData.persons.forEach((p) => {
      const personData = {
        id: p.id,
        name: p.name || "Nieznana osoba",
        gender: p.gender || "?",
        birthYear: p.birthDate?.year,
        deathYear: p.deathDate?.year,
        fatherId: p.fatherId,
        motherId: p.motherId,
        spouseIds: p.spouseIds || [],
        protocolKey: p.protocolKey,
        notes: p.notes,
        houseNumber: p.houseNumber,
        isRoot: p.id === treeData.rootId,
      };
      persons.set(p.id, personData);
      console.log(`Dodano osobę: ${personData.name} (ID: ${personData.id})`);
    });

    /**
     * Funkcja obliczająca poziomy generacji dla każdej osoby
     */
    function calculateGenerations() {
      const generations = new Map();
      
      function assignGeneration(personId, level) {
        const current = generations.get(personId);
        if (current !== undefined && current >= level) return;
        
        generations.set(personId, level);
        const person = persons.get(personId);
        if (!person) return;
        
        // Przypisz ten sam poziom małżonkom
        (person.spouseIds || []).forEach((spId) =>
          assignGeneration(spId, level)
        );
        
        // Przypisz następny poziom dzieciom
        persons.forEach((child) => {
          if (child.fatherId === personId || child.motherId === personId) {
            assignGeneration(child.id, level + 1);
          }
        });
      }
      
      // Rozpocznij od osób bez rodziców (najstarsze pokolenie)
      persons.forEach((p, id) => {
        if (!p.fatherId && !p.motherId) {
          assignGeneration(id, 0);
        }
      });
      
      return generations;
    }

    /**
     * Funkcja tworząca grupy małżeńskie
     */
    function createMarriageGroups() {
      const marriages = new Map();
      const processed = new Set();
      
      persons.forEach((person, id) => {
        if (processed.has(id)) return;
        
        const spouses = person.spouseIds.filter((spouseId) =>
          persons.has(spouseId)
        );
        
        if (spouses.length > 0) {
          spouses.forEach((spouseId) => {
            if (!processed.has(spouseId)) {
              const marriageKey = [id, spouseId].sort().join("-");
              marriages.set(marriageKey, {
                person1: person,
                person2: persons.get(spouseId),
                id: `marriage-${marriageKey}`,
              });
              processed.add(id);
              processed.add(spouseId);
            }
          });
        }
      });
      
      return marriages;
    }

    // Obliczanie układu drzewa
    console.log("Obliczanie generacji...");
    const generations = calculateGenerations();
    const marriages = createMarriageGroups();
    const generationGroups = new Map();

    // Grupowanie osób według generacji
    persons.forEach((person, id) => {
      const gen = generations.get(id) || 0;
      if (!generationGroups.has(gen)) {
        generationGroups.set(gen, []);
      }
      generationGroups.get(gen).push({ ...person, generation: gen });
    });

    const sortedGenerations = Array.from(generationGroups.entries()).sort(
      (a, b) => a[0] - b[0]
    );
    
    console.log(`Liczba generacji: ${sortedGenerations.length}`);

    // Obliczanie pozycji węzłów na płótnie
    const nodePositions = new Map();
    let maxWidth = 0;

    sortedGenerations.forEach(([genLevel, personsInGen], genIndex) => {
      const arranged = [];
      const processed = new Set();

      // Najpierw układamy małżeństwa
      marriages.forEach((marriage) => {
        const p1Gen = generations.get(marriage.person1.id);
        const p2Gen = generations.get(marriage.person2.id);
        
        if (p1Gen === genLevel && p2Gen === genLevel) {
          arranged.push({
            type: "marriage",
            persons: [marriage.person1, marriage.person2],
            width: NODE_WIDTH * 2 + MARRIAGE_LINE_OFFSET,
          });
          processed.add(marriage.person1.id);
          processed.add(marriage.person2.id);
        }
      });

      // Następnie pojedyncze osoby
      personsInGen.forEach((person) => {
        if (!processed.has(person.id)) {
          arranged.push({
            type: "single",
            persons: [person],
            width: NODE_WIDTH,
          });
        }
      });

      // Obliczanie pozycji X i Y dla każdego węzła
      const totalWidth =
        arranged.reduce((sum, group) => sum + group.width + HORIZONTAL_SPACING, 0) - HORIZONTAL_SPACING;
      
      if (totalWidth > maxWidth) maxWidth = totalWidth;

      let currentX = MARGIN;
      const y = MARGIN + LEGEND_HEIGHT + genIndex * (NODE_HEIGHT + VERTICAL_SPACING);

      arranged.forEach((group) => {
        if (group.type === "marriage") {
          nodePositions.set(group.persons[0].id, {
            x: currentX,
            y: y,
            person: group.persons[0],
          });
          nodePositions.set(group.persons[1].id, {
            x: currentX + NODE_WIDTH + MARRIAGE_LINE_OFFSET,
            y: y,
            person: group.persons[1],
          });
        } else {
          nodePositions.set(group.persons[0].id, {
            x: currentX,
            y: y,
            person: group.persons[0],
          });
        }
        currentX += group.width + HORIZONTAL_SPACING;
      });
    });

    // Ustawienie wymiarów SVG
    const svgWidth = Math.max(maxWidth + 2 * MARGIN, 1000);
    const svgHeight = MARGIN + LEGEND_HEIGHT + sortedGenerations.length * (NODE_HEIGHT + VERTICAL_SPACING) + MARGIN;
    
    console.log(`Wymiary SVG: ${svgWidth}x${svgHeight}`);

    // Tworzenie SVG przy użyciu D3.js
    const svg = d3
      .create("svg")
      .attr("width", "100%")
      .attr("height", "100%")
      .attr("viewBox", `0 0 ${svgWidth} ${svgHeight}`)
      .style("background", "#fafafa")
      .call(
        d3.zoom()
          .scaleExtent([0.1, 3])
          .on("zoom", (event) => g.attr("transform", event.transform))
      );
    
    const g = svg.append("g");

    /**
     * Funkcja tworząca połączenia rodzic-dziecko
     */
    function createParentChildConnections() {
      const connections = [];
      
      nodePositions.forEach((childPos, childId) => {
        const child = childPos.person;
        const fatherPos = child.fatherId ? nodePositions.get(child.fatherId) : null;
        const motherPos = child.motherId ? nodePositions.get(child.motherId) : null;

        if (fatherPos || motherPos) {
          let parentCenterX, parentY;

          // Obliczanie punktu wyjścia linii od rodziców
          if (fatherPos && motherPos) {
            parentCenterX = (fatherPos.x + NODE_WIDTH / 2 + motherPos.x + NODE_WIDTH / 2) / 2;
            parentY = Math.max(fatherPos.y, motherPos.y) + NODE_HEIGHT;
          } else if (fatherPos) {
            parentCenterX = fatherPos.x + NODE_WIDTH / 2;
            parentY = fatherPos.y + NODE_HEIGHT;
          } else {
            parentCenterX = motherPos.x + NODE_WIDTH / 2;
            parentY = motherPos.y + NODE_HEIGHT;
          }

          // Tworzenie ścieżki połączenia
          const childCenterX = childPos.x + NODE_WIDTH / 2;
          const childY = childPos.y;
          const midY = parentY + (childY - parentY) / 2;

          connections.push({
            path: `M${parentCenterX},${parentY} L${parentCenterX},${midY} L${childCenterX},${midY} L${childCenterX},${childY}`,
            type: "parent-child",
          });
        }
      });
      
      return connections;
    }

    // Rysowanie połączeń rodzic-dziecko
    const parentChildConnections = createParentChildConnections();
    console.log(`Liczba połączeń rodzic-dziecko: ${parentChildConnections.length}`);
    
    g.selectAll(".parent-child-connection")
      .data(parentChildConnections)
      .enter()
      .append("path")
      .attr("class", "parent-child-connection")
      .attr("d", (d) => d.path)
      .attr("stroke", "#666")
      .attr("stroke-width", 2)
      .attr("fill", "none")
      .attr("stroke-dasharray", "5,5");

    // Rysowanie linii małżeńskich
    console.log(`Liczba małżeństw: ${marriages.size}`);
    
    marriages.forEach((marriage) => {
      const pos1 = nodePositions.get(marriage.person1.id);
      const pos2 = nodePositions.get(marriage.person2.id);
      
      if (pos1 && pos2 && Math.abs(pos1.y - pos2.y) < 10) {
        // Linia łącząca małżonków
        g.append("line")
          .attr("class", "marriage-line")
          .attr("x1", pos1.x + NODE_WIDTH)
          .attr("y1", pos1.y + NODE_HEIGHT / 2)
          .attr("x2", pos2.x)
          .attr("y2", pos2.y + NODE_HEIGHT / 2)
          .attr("stroke", "#e74c3c")
          .attr("stroke-width", 4);
        
        // Symbol serca nad linią
        g.append("text")
          .attr("x", (pos1.x + NODE_WIDTH + pos2.x) / 2)
          .attr("y", pos1.y + NODE_HEIGHT / 2 - 8)
          .attr("text-anchor", "middle")
          .attr("font-size", "20px")
          .attr("fill", "#e74c3c")
          .text("💕");
      }
    });

    // Tworzenie węzłów osób
    const nodeGroups = g
      .selectAll(".person-node")
      .data(Array.from(nodePositions.entries()))
      .enter()
      .append("g")
      .attr("class", "person-node")
      .attr("transform", (d) => `translate(${d[1].x}, ${d[1].y})`);

    // Prostokąt reprezentujący osobę
    nodeGroups
      .append("rect")
      .attr("width", NODE_WIDTH)
      .attr("height", NODE_HEIGHT)
      .attr("rx", 10)
      .attr("ry", 10)
      .attr("fill", (d) => {
        const person = d[1].person;
        if (person.isRoot) return "#ffeb3b";
        return person.gender === "M" ? "#e3f2fd" : "#fce4ec";
      })
      .attr("stroke", (d) => {
        const person = d[1].person;
        if (person.isRoot) return "#f57f17";
        return person.gender === "M" ? "#1976d2" : "#c2185b";
      })
      .attr("stroke-width", (d) => (d[1].person.isRoot ? 3 : 2))
      .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.1))");

    // Imię i nazwisko osoby
    nodeGroups
      .append("text")
      .attr("x", NODE_WIDTH / 2)
      .attr("y", 25)
      .attr("text-anchor", "middle")
      .attr("font-size", "14px")
      .attr("font-weight", "bold")
      .attr("fill", "#333")
      .text((d) => d[1].person.name);

    // Lata życia
    nodeGroups
      .append("text")
      .attr("x", NODE_WIDTH / 2)
      .attr("y", 50)
      .attr("text-anchor", "middle")
      .attr("font-size", "12px")
      .attr("fill", "#666")
      .text((d) => {
        const p = d[1].person;
        const b = p.birthYear;
        const dth = p.deathYear;
        if (b && dth) return `${b} - ${dth}`;
        if (b) return `ur. ${b}`;
        if (dth) return `zm. ${dth}`;
        return "";
      });

    // Numer domu
    nodeGroups
      .append("text")
      .attr("x", NODE_WIDTH / 2)
      .attr("y", 70)
      .attr("text-anchor", "middle")
      .attr("font-size", "11px")
      .attr("fill", "#888")
      .text((d) => d[1].person.houseNumber ? `Dom: ${d[1].person.houseNumber}` : "");

    // Link do protokołu (dla osób z kluczem protokołu)
    nodeGroups
      .filter((d) => d[1].person.protocolKey && !d[1].person.isRoot)
      .append("g")
      .attr("class", "protocol-link")
      .style("cursor", "pointer")
      .on("click", (event, d) => {
        window.open(`../wlasciciele/protokol.html?ownerId=${d[1].person.protocolKey}`, "_blank");
      })
      .append("text")
      .attr("x", NODE_WIDTH / 2)
      .attr("y", NODE_HEIGHT - 15)
      .attr("text-anchor", "middle")
      .attr("font-size", "10px")
      .attr("fill", "#007bff")
      .attr("text-decoration", "underline")
      .text("📜 Zobacz protokół");

    // Symbol płci
    nodeGroups
      .append("text")
      .attr("x", NODE_WIDTH - 20)
      .attr("y", 25)
      .attr("text-anchor", "middle")
      .attr("font-size", "18px")
      .text((d) => (d[1].person.gender === "M" ? "♂" : "♀"))
      .attr("fill", (d) => (d[1].person.gender === "M" ? "#1976d2" : "#c2185b"));

    // Tworzenie legendy
    const legend = g
      .append("g")
      .attr("class", "legend")
      .attr("transform", `translate(${MARGIN}, ${MARGIN})`);

    // Tło legendy
    legend
      .append("rect")
      .attr("width", 350)
      .attr("height", LEGEND_HEIGHT - 20)
      .attr("fill", "white")
      .attr("stroke", "#ccc")
      .attr("stroke-width", 2)
      .attr("rx", 8)
      .attr("ry", 8)
      .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.1))");

    // Tytuł legendy
    legend
      .append("text")
      .attr("x", 15)
      .attr("y", 20)
      .attr("font-size", "14px")
      .attr("font-weight", "bold")
      .attr("fill", "#333")
      .text("Legenda:");

    // Elementy legendy
    const legendItems = [
      { text: "💕 - Małżeństwo", y: 35 },
      { text: "📜 - Kliknij aby zobaczyć protokół", y: 50 },
      { text: "♂ - Mężczyzna, ♀ - Kobieta", y: 65 },
      { text: "Żółte tło - główna osoba protokołu", y: 80 },
    ];

    legendItems.forEach((item) => {
      legend
        .append("text")
        .attr("x", 15)
        .attr("y", item.y)
        .attr("font-size", "11px")
        .attr("fill", "#555")
        .text(item.text);
    });

    // Dodanie SVG do kontenera
    console.log("Dodawanie SVG do kontenera...");
    treeContainer.appendChild(svg.node());
    
    // Pokazanie dialogu
    console.log("Otwieranie dialogu...");
    try {
      treeDialog.showModal();
      console.log("Dialog otwarty pomyślnie");
    } catch (e) {
      console.error("Błąd przy otwieraniu dialogu:", e);
      // Fallback dla starszych przeglądarek
      treeDialog.style.display = "block";
    }
    
    console.log("=== DRZEWO NARYSOWANE POMYŚLNIE ===");
    
  } catch (error) {
    console.error("BŁĄD podczas rysowania drzewa:", error);
    console.error("Stack trace:", error.stack);
    
    // Pokaż błąd w kontenerze
    treeContainer.innerHTML = `
      <div style="padding: 2rem; text-align: center; color: red;">
        <h3>Wystąpił błąd podczas rysowania drzewa</h3>
        <p>${error.message}</p>
        <details style="margin-top: 1rem;">
          <summary>Szczegóły techniczne</summary>
          <pre style="text-align: left; background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow: auto;">
${error.stack}
          </pre>
        </details>
      </div>
    `;
    
    // Mimo błędu, spróbuj otworzyć dialog
    try {
      treeDialog.showModal();
    } catch (e) {
      treeDialog.style.display = "block";
    }
  }
}
  /**
   * Sekcja 6: Funkcje pomocnicze
   */
  const generateFractionHTML = (txt) => {
    if (!txt) return "";
    
    return String(txt)
      .replace(
        /(\d+)\/(\d+)/g,
        '<span class="fraction"><span class="numerator">$1</span><span class="denominator">$2</span></span>',
      )
      .replace(
        /(?<!\/)\b(\d+)\b(?![\/<])/g,
        '<span class="whole-number">$1</span>',
      );
  };

  let pdfLibPromise = null;
  const ensureHtml2Pdf = () => {
    if (typeof html2pdf !== "undefined") return Promise.resolve();
    if (pdfLibPromise) return pdfLibPromise;
    pdfLibPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src =
        "https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js";
      s.onload = () => resolve();
      s.onerror = () => reject();
      document.head.appendChild(s);
    });
    return pdfLibPromise;
  };

    const createPDF = async (columnEl, ownerName = "protokol", ownerData = null) => {
      // Załaduj bibliotekę jeśli trzeba
      try {
        await ensureHtml2Pdf();
      } catch {
        return alert("Nie udało się załadować modułu PDF.");
      }

      // 1) Tryb PDF – wyłącza animacje/przezroczystości (wymaga .pdf-export w CSS)
      document.body.classList.add('pdf-export');

      // 2) Ukryj elementy interaktywne w tej kolumnie (bez zostawiania pustych miejsc)
      const elementsToHide = columnEl.querySelectorAll(
        '.action-btn, .switch-btn, .details-toggle-btn, .view-switcher'
      );
      const originalDisplays = new Map();
      elementsToHide.forEach(el => originalDisplays.set(el, el.style.display));
      elementsToHide.forEach(el => el.style.display = 'none');

      // 3) Ustal, które widoki są aktualnie widoczne – NIE odsłaniamy na siłę ukrytych
      const allViews = Array.from(columnEl.querySelectorAll('.view-container'));
      const viewStates = allViews.map(el => ({
        el,
        hadHiddenClass: el.classList.contains('hidden'),
        prevDisplay: el.style.display
      }));

      const isVisible = (el) =>
        !el.classList.contains('hidden') && getComputedStyle(el).display !== 'none';

      let visibleViews = allViews.filter(isVisible);

      // 4) Jeśli przekażemy ownerData i działki R=Prot., to (dla bezpieczeństwa) ukryj widok protokołu w PDF
      //    nawet jeśli ktoś go ręcznie pokazał. Dzięki temu nie powstanie pusta karta.
      let forcedHideProtocol = false;
      if (ownerData) {
        const allPlots = ownerData.dzialki_wszystkie || [];
        const real = allPlots.filter(p => p.typ_posiadania === 'własność rzeczywista');
        const prot = allPlots.filter(p => p.typ_posiadania !== 'własność rzeczywista');

        const listsEqualById = (A, B) => {
          if (A.length !== B.length) return false;
          const idsA = new Set(A.map(p => p.id));
          for (const p of B) if (!idsA.has(p.id)) return false;
          return true;
        };

        const equal = listsEqualById(real, prot);
        if (equal) {
          const protocolView = columnEl.querySelector(`#view-protokol-${ownerData.unikalny_klucz}`);
          if (protocolView && isVisible(protocolView)) {
            protocolView.classList.add('hidden');
            forcedHideProtocol = true;
            // Odśwież listę widocznych widoków
            visibleViews = allViews.filter(isVisible);
          }
        }
      }

      // 5) Pokaż szczegóły działek tylko w aktualnie widocznych widokach
      const detailsOpened = [];
      visibleViews.forEach(v => {
        v.querySelectorAll('.plot-details-list.hidden').forEach(dl => {
          detailsOpened.push(dl);
          dl.classList.remove('hidden');
        });
      });

      // 6) Odczekaj klatkę + fonty, żeby zrzut był stabilny
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      if (document.fonts?.ready) { try { await document.fonts.ready; } catch(e) {} }
      await new Promise(r => setTimeout(r, 50));

      // 7) Parametry PDF: białe tło + skala
      const opt = {
        margin: 10,
        filename: `Protokol_${String(ownerName).replace(/[^\p{L}\p{N}_-]+/gu, '_')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: {
          scale: 2,
          useCORS: true,
          backgroundColor: '#ffffff',
          scrollY: 0
        },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak: {
          mode: ['css', 'avoid-all'],
          avoid: ['.plot-category-block', '.content-card']
        }
      };

      try {
        await html2pdf().from(columnEl).set(opt).save();
      } finally {
        // 8) Przywróć stan kolumny
        elementsToHide.forEach(el => el.style.display = originalDisplays.get(el) || '');
        detailsOpened.forEach(dl => dl.classList.add('hidden'));

        // Przywróć widoki dokładnie do wcześniejszego stanu
        viewStates.forEach(s => {
          s.el.style.display = s.prevDisplay;
          s.el.classList.toggle('hidden', s.hadHiddenClass);
        });

        // Jeśli wymusiliśmy ukrycie widoku protokołu, również go przywróć
        if (forcedHideProtocol && ownerData) {
          const protocolView = columnEl.querySelector(`#view-protokol-${ownerData.unikalny_klucz}`);
          if (protocolView) {
            // Nic – już odtworzyliśmy powyżej z viewStates
          }
        }

        document.body.classList.remove('pdf-export');
      }
    };

const findProtocolImages = (key) =>
    new Promise((resolve) => {
      const baseDir = `/assets/protokoly/${key}/`;
      let result = [],
        i = 1;

      const loadNext = () => {
        const img = new Image();
        img.src = `${baseDir}${i}.jpg`;
        img.onload = () => {
          result.push(img.src);
          i++;
          loadNext();
        };
        img.onerror = () => {
          if (i === 1 && result.length === 0) {
            const single = `/assets/protokoly/${key}.jpg`;
            const sImg = new Image();
            sImg.src = single;
            sImg.onload = () => {
              result.push(sImg.src);
              resolve(result);
            };
            sImg.onerror = () => resolve(result);
          } else resolve(result);
        };
      };
      loadNext();
    });



  /**
   * Sekcja 7: Szablony HTML i funkcje budujące interfejs
   */
  const columnTemplate = (d) => {
    const uid = d.unikalny_klucz;
    const genealogyButtonHTML = d.ma_drzewo_genealogiczne
      ? `<button id="showTreeBtn-${uid}" class="action-btn tree-btn">
          <i class="fas fa-project-diagram"></i> Drzewo genealogiczne
         </button>`
      : "";

    return `
      <!-- Nagłówek protokołu -->
      <div class="protocol-header-card">
        <div class="protocol-number-badge">L.p. ${d.numer_protokolu || "—"}</div>
        <h2 class="protocol-main-title">
          Protokół dochodzeń miejscowych
          <span class="protocol-location">w gminie katastralnej Czarna</span>
        </h2>
        <div class="protocol-actions">
          <button id="downloadPdfBtn-${uid}" class="action-btn">
            <i class="fas fa-file-pdf"></i> Pobierz PDF
          </button>
          ${genealogyButtonHTML}
          <button id="showOriginalBtn-${uid}" class="action-btn hidden">
            <i class="fas fa-images"></i> Oryginał
          </button>
        </div>
      </div>
      
      <!-- Dane właściciela -->
      <div class="content-card owner-card-section">
        <div class="card-header">
          <h3><i class="fas fa-user"></i> Dane Właściciela</h3>
        </div>
        <div class="card-body">
          <div class="owner-info">
            <div>
              <div class="owner-name-main">${d.nazwa_wlasciciela || ""}</div>
              ${d.numer_domu ? `
              <div class="owner-secondary-info">
                Dom: <span class="owner-details-value">${generateFractionHTML(d.numer_domu)}</span>
              </div>` : ''}
            </div>
          </div>
          <button id="showHouseOnMapBtn-${uid}" class="action-btn map-btn hidden">
            <i class="fas fa-home"></i> Pokaż dom na mapie
          </button>
        </div>
      </div>
      
      <!-- Genealogia -->
      ${d.genealogia ? `
      <div class="content-card genealogy-section">
        <div class="card-header">
          <h3><i class="fas fa-sitemap"></i> Genealogia</h3>
        </div>
        <div class="card-body">
          <div class="info-content">${d.genealogia}</div>
        </div>
      </div>` : ''}
      
      <!-- Przełącznik widoków -->
      <div class="view-switcher" data-target-id="${uid}">
        <button class="switch-btn active" data-view="rzeczywiste">
          <i class="fas fa-check-circle"></i> Stan Rzeczywisty
        </button>
        <button class="switch-btn" data-view="protokol">
          <i class="fas fa-file-alt"></i> Stan wg Protokołu
        </button>
      </div>
      
      <!-- Działki rzeczywiste -->
      <div id="view-rzeczywiste-${uid}" class="view-container">
        <div class="content-card plots-section">
          <div class="card-header">
            <h3><i class="fas fa-layer-group"></i> Działki Rzeczywiste</h3>
            <button class="details-toggle-btn" data-target="rzeczywiste-details-${uid}">
              <i class="fas fa-chevron-down"></i>
            </button>
          </div>
          <div class="card-body">
            <div class="plots-summary">
              <div class="plot-numbers"></div>
              <div class="plot-summary"></div>
            </div>
            <div class="plot-details-list hidden" id="rzeczywiste-details-${uid}"></div>
          </div>
        </div>
      </div>
      
      <!-- Działki wg protokołu -->
      <div id="view-protokol-${uid}" class="view-container hidden">
        <div class="content-card plots-section">
          <div class="card-header">
            <h3><i class="fas fa-layer-group"></i> Działki wg Protokołu</h3>
            <button class="details-toggle-btn" data-target="protokol-details-${uid}">
              <i class="fas fa-chevron-down"></i>
            </button>
          </div>
          <div class="card-body">
            <div class="plots-summary">
              <div class="plot-numbers"></div>
              <div class="plot-summary"></div>
            </div>
            <div class="plot-details-list hidden" id="protokol-details-${uid}"></div>
          </div>
        </div>
      </div>
      
      <!-- Treść protokołu -->
      <div class="content-card protocol-content-section">
        <div class="card-header">
          <h3><i class="fas fa-scroll"></i> Treść protokołu</h3>
        </div>
        <div class="card-body">
          <div class="info-content">${generateFractionHTML(d.pelna_historia || "")}</div>
        </div>
      </div>
      
      <!-- Współwłasność -->
      ${d.wspolwlasnosc ? `
      <div class="content-card" id="wspolwlasnoscSection-${uid}">
        <div class="card-header">
          <h3><i class="fas fa-users"></i> Współwłasność / Służebność</h3>
        </div>
        <div class="card-body">
          <div class="info-content">${generateFractionHTML(d.wspolwlasnosc)}</div>
        </div>
      </div>` : ''}
      
      <!-- Powiązania i transakcje -->
      ${d.powiazania_i_transakcje_html ? `
      <div class="content-card" id="powiazaniaTransakcjeSection-${uid}">
        <div class="card-header">
          <h3><i class="fas fa-exchange-alt"></i> Powiązania i transakcje</h3>
        </div>
        <div class="card-body">
          <div class="info-content">${generateFractionHTML(d.powiazania_i_transakcje_html)}</div>
        </div>
      </div>` : ''}
      
      <!-- Interpretacja -->
      ${d.interpretacja_i_wnioski ? `
      <div class="content-card" id="interpretacjaWnioskiSection-${uid}">
        <div class="card-header">
          <h3><i class="fas fa-lightbulb"></i> Interpretacja i wnioski</h3>
        </div>
        <div class="card-body">
          <div class="info-content">${generateFractionHTML(d.interpretacja_i_wnioski)}</div>
        </div>
      </div>` : ''}
    `;
  };

  /**
   * Funkcja wypełniająca sekcję działek
   */
  const fillPlotSection = (containerId, plots, uid) => {
    const container = document.querySelector(`#${containerId}`);
    if (!container) return;

    const plotsSection = container.querySelector('.plots-section');
    if (!plotsSection) return;

    if (!plots || plots.length === 0) {
      container.style.display = "none";
      return;
    }
    container.style.display = "block";

    const summaryEl = plotsSection.querySelector(".plots-summary");
    const numbersDiv = summaryEl.querySelector(".plot-numbers");
    const summaryDiv = summaryEl.querySelector(".plot-summary");
    const detailsList = plotsSection.querySelector(".plot-details-list");
    
    numbersDiv.innerHTML = plots
      .map((p) => generateFractionHTML(p.nazwa_lub_numer))
      .join(", ");

    const counts = plots.reduce((acc, p) => {
      const k = p.kategoria || "nieznana";
      acc[k] = (acc[k] || 0) + 1;
      return acc;
    }, {});
    summaryDiv.textContent = `(w tym: ${Object.entries(counts)
      .map(([k, c]) => `${c} ${k}`)
      .join(", ")})`;

    const byCat = plots.reduce((acc, p) => {
      const k = p.kategoria || "nieznana";
      (acc[k] = acc[k] || []).push(p);
      return acc;
    }, {});

    detailsList.innerHTML = Object.entries(byCat)
      .map(
        ([k, list]) => `
          <div class="plot-category-block">
            <h4>${k.charAt(0).toUpperCase() + k.slice(1)} (${list.length}):</h4>
            <div class="plot-numbers">
              ${list.map((p) => generateFractionHTML(p.nazwa_lub_numer)).join(", ")}
            </div>
          </div>
        `,
      )
      .join("");
  };

  /**
   * Funkcja budująca kolumnę protokołu
   */
  const buildColumn = (data, columnIndex) => {
    const colEl = document.getElementById(`protocol-${columnIndex + 1}`);
    if (!colEl) {
      console.error(`Nie znaleziono elementu protocol-${columnIndex + 1}`);
      return;
    }

    colEl.innerHTML = columnTemplate(data);

    // Obsługa przycisku "Pokaż dom na mapie"
    const showHouseBtn = colEl.querySelector(`#showHouseOnMapBtn-${data.unikalny_klucz}`);
    if (data.dom_obiekt_id && showHouseBtn) {
      showHouseBtn.classList.remove('hidden');
      showHouseBtn.addEventListener('click', () => {
        const mapUrl = '../mapa/mapa.html';
        const plotIds = (data.dzialki_wszystkie || []).map(p => p.id);
        const allIdsToHighlight = [data.dom_obiekt_id, ...plotIds];
        const uniqueIds = [...new Set(allIdsToHighlight)].join(',');
        const params = new URLSearchParams({
          highlightByIds: uniqueIds
        });
        window.location.href = `${mapUrl}?${params.toString()}`;
      });
    }

    // Wypełnij sekcje działek
    const allPlots = data.dzialki_wszystkie || [];
    const rzeczywistePlots = allPlots.filter((p) => p.typ_posiadania === "własność rzeczywista");
    const protokolPlots = allPlots.filter((p) => p.typ_posiadania !== "własność rzeczywista");

    fillPlotSection(`view-rzeczywiste-${data.unikalny_klucz}`, rzeczywistePlots, data.unikalny_klucz);
    fillPlotSection(`view-protokol-${data.unikalny_klucz}`, protokolPlots, data.unikalny_klucz);

    // Obsługa przełącznika widoków
    const switcher = colEl.querySelector(".view-switcher");
    const switchBtns = switcher.querySelectorAll(".switch-btn");
    
    switchBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const view = btn.dataset.view;
        const uid = switcher.dataset.targetId;
        
        colEl.querySelectorAll(".view-container").forEach((v) => v.classList.add("hidden"));
        const targetView = colEl.querySelector(`#view-${view}-${uid}`);
        if (targetView) targetView.classList.remove("hidden");
        
        switchBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });

    // Obsługa przycisków rozwijania szczegółów
    colEl.querySelectorAll('.details-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.dataset.target;
        const targetEl = document.getElementById(targetId);
        const icon = btn.querySelector('i');
        
        if (targetEl) {
          targetEl.classList.toggle('hidden');
          if (icon) {
            icon.className = targetEl.classList.contains('hidden') 
              ? 'fas fa-chevron-down' 
              : 'fas fa-chevron-up';
          }
        }
      });
    });

    // Obsługa przycisku PDF
    const pdfBtn = colEl.querySelector(`#downloadPdfBtn-${data.unikalny_klucz}`);
    if (pdfBtn) {
      pdfBtn.addEventListener("click", () => createPDF(colEl, data.nazwa_wlasciciela, data));
    }

    // Sprawdź dostępność skanów
    findProtocolImages(data.unikalny_klucz).then((imgArr) => {
      if (imgArr.length) {
        const origBtn = colEl.querySelector(`#showOriginalBtn-${data.unikalny_klucz}`);
        if (origBtn) {
          origBtn.classList.remove("hidden");
          origBtn.addEventListener("click", () => openModal(imgArr));
        }
      }
    });

    // Obsługa przycisku drzewa genealogicznego
  const treeBtn = colEl.querySelector(`#showTreeBtn-${data.unikalny_klucz}`);
  if (treeBtn) {
    console.log(`Znaleziono przycisk drzewa dla ${data.unikalny_klucz}`);
    
    treeBtn.addEventListener("click", () => {
      console.log(`Kliknięto przycisk drzewa dla ${data.unikalny_klucz}`);
      
      treeBtn.disabled = true;
      treeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Ładowanie...';
      
      fetch(`/api/genealogia/${data.unikalny_klucz}`)
        .then((r) => {
          console.log(`Odpowiedź API dla ${data.unikalny_klucz}:`, r.status);
          if (!r.ok) throw new Error(`HTTP error! status: ${r.status}`);
          return r.json();
        })
        .then((treeData) => {
          console.log(`Otrzymano dane drzewa dla ${data.unikalny_klucz}:`, treeData);
          drawGenealogyTree(treeData);
        })
        .catch((err) => {
          console.error(`Błąd ładowania drzewa dla ${data.unikalny_klucz}:`, err);
          
          // Pokaż błąd w dialogu zamiast alertu
          const treeDialog = document.getElementById("treeDialog");
          const treeContainer = document.getElementById("treeContainer");
          
          if (treeDialog && treeContainer) {
            treeContainer.innerHTML = `
              <div style="padding: 2rem; text-align: center;">
                <h3 style="color: red;">Błąd ładowania drzewa</h3>
                <p>${err.message}</p>
                <button onclick="document.getElementById('treeDialog').close()" 
                        style="margin-top: 1rem; padding: 0.5rem 1rem; 
                              background: #007bff; color: white; 
                              border: none; border-radius: 4px; cursor: pointer;">
                  Zamknij
                </button>
              </div>
            `;
            treeDialog.showModal();
          } else {
            alert("Błąd ładowania drzewa: " + err.message);
          }
        })
        .finally(() => {
          treeBtn.disabled = false;
          treeBtn.innerHTML = '<i class="fas fa-project-diagram"></i> Drzewo genealogiczne';
        });
    });
  }

    // Jednorazowe podpięcie zamykania dialogu drzewa
    if (!closeTreeBtn.handlerAttached) {
      closeTreeBtn.addEventListener("click", () => {
        treeDialog.close();
        treeContainer.innerHTML = "";
      });
      closeTreeBtn.handlerAttached = true;
    }
  };

  /**
   * Sekcja 8: Główna logika - pobieranie i wyświetlanie danych
   */
  
  // Pokaż spinner ładowania
  showLoadingSpinner();

  // Przygotuj zapytania do API dla obu właścicieli z lepszą obsługą błędów
  const fetchPromises = ownerKeys.map((key) =>
    fetch(`/api/wlasciciel/${key}`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Błąd pobierania danych dla ${key}: ${res.status} ${res.statusText}`);
        }
        return res.json();
      })
      .then((data) => {
        if (data.error) {
          throw new Error(data.error);
        }
        return data;
      })
      .catch((error) => {
        console.error(`Błąd dla klucza ${key}:`, error);
        throw error;
      })
  );

  // Pobierz dane i zbuduj interfejs
  Promise.all(fetchPromises)
    .then(([data1, data2]) => {
      // Przywróć oryginalny kontener
      document.querySelector('.compare-container').innerHTML = `
        <div class="protocol-column" id="protocol-1"></div>
        <div class="protocol-column" id="protocol-2"></div>
      `;

      // Zbuduj kolumny dla obu protokołów
      buildColumn(data1, 0);
      buildColumn(data2, 1);

      // Sprawdź dostępność różnych typów działek
      const maDzialkiRzeczywiste =
        data1.dzialki_wszystkie?.some((p) => p.typ_posiadania === "własność rzeczywista") ||
        data2.dzialki_wszystkie?.some((p) => p.typ_posiadania === "własność rzeczywista");
      
      const maDzialkiProtokol =
        data1.dzialki_wszystkie?.some((p) => p.typ_posiadania !== "własność rzeczywista") ||
        data2.dzialki_wszystkie?.some((p) => p.typ_posiadania !== "własność rzeczywista");

      // Pokaż odpowiednie przyciski nawigacji do mapy
      if (maDzialkiRzeczywiste && mapLinkReal) mapLinkReal.classList.remove("hidden");
      if (maDzialkiProtokol && mapLinkProtocol) mapLinkProtocol.classList.remove("hidden");
      if (maDzialkiRzeczywiste && maDzialkiProtokol && mapLinkBoth) 
        mapLinkBoth.classList.remove("hidden");
    })
    .catch((error) => {
      console.error("Błąd podczas pobierania danych:", error);
      showError(`Nie udało się pobrać danych właścicieli. ${error.message}`);
    });
});