/* ==========================================================================
   Plik: compare.js
   Opis: Skrypt obsługujący porównywanie dwóch protokołów katastralnych.
         Umożliwia równoległe wyświetlanie danych, generowanie PDF,
         przeglądanie skanów oraz wizualizację drzew genealogicznych.
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  if (!window.OwnersAPI) {
    throw new Error('compare.js wymaga js/api.js załadowanego wcześniej');
  }
  if (!window.OwnersUtils) {
    throw new Error('compare.js wymaga js/utils.js załadowanego wcześniej');
  }
  if (!window.ProtocolImages) {
    throw new Error('compare.js wymaga js/protocol-images.js załadowanego wcześniej');
  }
  if (!window.ProtocolGenealogyTree) {
    throw new Error('compare.js wymaga js/protocol-genealogy-tree.js załadowanego wcześniej');
  }
  if (!window.CompareRenderer) {
    throw new Error('compare.js wymaga js/compare-renderer.js załadowanego wcześniej');
  }
  if (!window.CompareInteractions) {
    throw new Error('compare.js wymaga js/compare-interactions.js załadowanego wcześniej');
  }
  const API = window.OwnersAPI;
  const UTILS = window.OwnersUtils;
  const IMAGES = window.ProtocolImages;
  const TREE = window.ProtocolGenealogyTree;
  const RENDERER = window.CompareRenderer;
  const INTERACTIONS = window.CompareInteractions;

  /* ==========================================================================
     INICJALIZACJA KOMPONENTÓW UI
     ========================================================================== */

  /**
   * Zarządzanie motywem kolorystycznym
   */
  const setupThemeLogic = () => {
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    if (!themeToggleBtn) return;

    const icon = themeToggleBtn.querySelector('i');

    // Aplikacja motywu
    const applyTheme = (theme) => {
      document.body.classList.toggle('dark-mode', theme === 'dark');
      if (icon) {
        icon.className = theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
      }
    };

    // Odczyt zapisanego motywu
    const savedTheme = localStorage.getItem('mapTheme') || 'light';
    applyTheme(savedTheme);

    // Obsługa zmiany motywu
    themeToggleBtn.addEventListener('click', () => {
      const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('mapTheme', newTheme);
      applyTheme(newTheme);
    });
  };

  /**
   * Zarządzanie trybem pełnoekranowym
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

  // Inicjalizacja komponentów
  setupThemeLogic();
  setupFullscreen();

  /* ==========================================================================
     WALIDACJA PARAMETRÓW I INICJALIZACJA
     ========================================================================== */

  const urlParams = new URLSearchParams(window.location.search);
  const ownerKeys = urlParams.get("owners")?.split(",");

  // Ustawienie aktualnej daty
  const currentDateEl = document.getElementById('currentDate');
  if (currentDateEl) {
    currentDateEl.textContent = new Date().toLocaleDateString('pl-PL');
  }

  // Walidacja - wymagane dokładnie 2 klucze właścicieli
  if (!ownerKeys || ownerKeys.length !== 2) {
    showError("Proszę wybrać dwóch właścicieli do porównania.");
    return;
  }

  /**
   * Wyświetla komunikat błędu
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
   * Wyświetla spinner ładowania
   */
  function showLoadingSpinner() {
    document.querySelector('.compare-container').innerHTML = `
      <div class="loading-spinner" style="width: 100%;">
        <i class="fas fa-spinner fa-spin"></i>
        <span style="margin-left: 1rem;">Ładowanie protokołów...</span>
      </div>
    `;
  }

  /* ==========================================================================
     KONFIGURACJA LINKÓW DO MAPY
     ========================================================================== */

  const mapLinkReal = document.getElementById("mapLinkReal");
  const mapLinkProtocol = document.getElementById("mapLinkProtocol");
  const mapLinkBoth = document.getElementById("mapLinkBoth");
  INTERACTIONS.setupHeaderMapLinks(ownerKeys, { mapLinkReal, mapLinkProtocol, mapLinkBoth });

  const imageModal = document.getElementById("imageModal");
  const modalImg = document.getElementById("modalImageSrc");
  const closeModalBtn = document.querySelector(".modal-close-btn");
  const prevBtn = document.getElementById("prevImageBtn");
  const nextBtn = document.getElementById("nextImageBtn");
  const counterLbl = document.getElementById("pageCounter");

  let storedColumnData = [null, null];

  const treeDialog = document.getElementById("treeDialog");
  const closeTreeBtn = document.getElementById("closeTreeBtn");
  const treeContainer = document.getElementById("treeContainer");

  // Re-align przy resize (debounce 100ms) — bez tego karty rozjeżdżają się
  // po zmianie orientacji okna lub otwarciu devtools
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(RENDERER.alignCardHeights, 100);
  });

  /**
   * Buduje kolumnę protokołu z danymi
   */
  const buildColumn = (data, columnIndex) => {
    const colEl = document.getElementById(`protocol-${columnIndex + 1}`);
    if (!colEl) {
      console.error(`Nie znaleziono elementu protocol-${columnIndex + 1}`);
      return;
    }

    colEl.innerHTML = RENDERER.columnTemplate(data);

    // Zapis danych do globalnego odświeżania
    storedColumnData[columnIndex] = data;

    INTERACTIONS.bindColumnMapLinks(data, colEl);

    // Wypełnienie sekcji działek — używamy gotowych tablic z API zamiast filtrowania
    // po typ_posiadania (porównanie stringów jest niestabilne po migracji kodowania).
    const rzeczywistePlots = data.dzialki_rzeczywiste || [];
    const protokolPlots = data.dzialki_protokol || [];

    RENDERER.fillPlotSection(`view-rzeczywiste-${data.unikalny_klucz}`, rzeczywistePlots, data.unikalny_klucz);
    RENDERER.fillPlotSection(`view-protokol-${data.unikalny_klucz}`, protokolPlots, data.unikalny_klucz);

    // Przełącznik widoków
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

        // Po przełączeniu widoku wysokości kart się zmieniają — wyrównaj ponownie
        RENDERER.alignCardHeights();
      });
    });

    // Przyciski rozwijania szczegółów
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

    // Przycisk PDF
    const pdfBtn = colEl.querySelector(`#downloadPdfBtn-${data.unikalny_klucz}`);
    if (pdfBtn) {
      pdfBtn.addEventListener("click", () => INTERACTIONS.createPDF(colEl, data.nazwa_wlasciciela, data));
    }

    // Przycisk "Pokaż oryginał" — skany obsługuje wspólny moduł ProtocolImages.
    const origBtn = colEl.querySelector(`#showOriginalBtn-${data.unikalny_klucz}`);
    if (origBtn) {
      const imageSession = IMAGES.init({
        ownerKey: data.unikalny_klucz,
        elements: {
          showOriginalBtn: origBtn,
          imageModal,
          modalImage: modalImg,
          closeModalBtn,
          prevBtn,
          nextBtn,
          pageCounter: counterLbl
        }
      });
      IMAGES.find(imageSession);
    }

    // Przycisk drzewa genealogicznego
    const treeBtn = colEl.querySelector(`#showTreeBtn-${data.unikalny_klucz}`);
    if (treeBtn) {
      TREE.init({
        ownerKey: data.unikalny_klucz,
        elements: {
          showTreeBtn: treeBtn,
          treeDialog,
          closeTreeBtn,
          treeContainer
        }
      });
    }
  };

  /* ==========================================================================
     GŁÓWNA LOGIKA - POBIERANIE I WYŚWIETLANIE DANYCH
     ========================================================================== */

  // Wyświetlenie spinnera ładowania
  showLoadingSpinner();

  // Przygotowanie zapytań API
  const fetchPromises = ownerKeys.map((key) =>
    fetch(API.owner(key))
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

  // Pobieranie danych i budowanie interfejsu
  Promise.all(fetchPromises)
    .then(([data1, data2]) => {
      // Przywrócenie kontenera
      document.querySelector('.compare-container').innerHTML = `
        <div class="protocol-column" id="protocol-1"></div>
        <div class="protocol-column" id="protocol-2"></div>
      `;

      // Budowanie kolumn
      buildColumn(data1, 0);
      buildColumn(data2, 1);

      // Wyrównaj wysokości kart w obu kolumnach (dwa requestAnimationFrame —
      // pierwszy czeka aż DOM się zmaterializuje, drugi aż przeglądarka
      // zmierzy offsetHeight po wstawieniu treści)
      requestAnimationFrame(() =>
        requestAnimationFrame(() => RENDERER.alignCardHeights())
      );

      // Sprawdzenie dostępności działek (bez filtrowania po stringu)
      const maDzialkiRzeczywiste =
        (data1.dzialki_rzeczywiste?.length || 0) > 0 ||
        (data2.dzialki_rzeczywiste?.length || 0) > 0;

      const maDzialkiProtokol =
        (data1.dzialki_protokol?.length || 0) > 0 ||
        (data2.dzialki_protokol?.length || 0) > 0;

      // Pokazanie odpowiednich przycisków nawigacji do mapy
      if (maDzialkiRzeczywiste && mapLinkReal)
        mapLinkReal.classList.remove("hidden");

      if (maDzialkiProtokol && mapLinkProtocol)
        mapLinkProtocol.classList.remove("hidden");

      if (maDzialkiRzeczywiste && maDzialkiProtokol && mapLinkBoth)
        mapLinkBoth.classList.remove("hidden");
    })
    .catch((error) => {
      console.error("Błąd podczas pobierania danych:", error);
      showError(`Nie udało się pobrać danych właścicieli. ${error.message}`);
    });
});
