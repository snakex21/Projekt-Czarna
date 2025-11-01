#!/usr/bin/env python3
"""
Skrypt do aplikacji zmian w plikach projektu.
Dodaje obsługę statystyk powierzchni działek.
"""

import re

# ============================================================================
# Patch dla backend/app.py
# ============================================================================

def patch_app_py():
    """Modyfikuje backend/app.py aby dodać obliczenia powierzchni."""
    
    file_path = '/home/engine/project/backend/app.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Patch dla zapytania SQL w get_top_by_category
    old_query = '''            query = f"""
                SELECT w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu,
                       COUNT(dw.obiekt_id) as plot_count
                FROM wlasciciele w
                JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
                JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
                WHERE {condition} {category_condition}
                GROUP BY w.id, w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu
                HAVING COUNT(dw.obiekt_id) > 0
                ORDER BY plot_count DESC;
            """'''
    
    new_query = '''            query = f"""
                SELECT w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu,
                       COUNT(dw.obiekt_id) as plot_count,
                       COALESCE(SUM(ST_Area(o.geometria::geography)), 0) as total_area_m2,
                       json_agg(o.nazwa_lub_numer ORDER BY o.nazwa_lub_numer) as plot_numbers
                FROM wlasciciele w
                JOIN dzialki_wlasciciele dw ON w.id = dw.wlasciciel_id
                JOIN obiekty_geograficzne o ON dw.obiekt_id = o.id
                WHERE {condition} {category_condition}
                GROUP BY w.id, w.nazwa_wlasciciela, w.unikalny_klucz, w.numer_protokolu
                HAVING COUNT(dw.obiekt_id) > 0
                ORDER BY plot_count DESC;
            """'''
    
    content = content.replace(old_query, new_query)
    
    # 2. Patch dla dodania statystyk powierzchni po category_counts
    insertion_point = '    category_counts = {item[\'kategoria\']: item[\'count\'] for item in category_counts_list}\n\n    # ——— Genealogia:'
    
    area_stats_code = '''    category_counts = {item['kategoria']: item['count'] for item in category_counts_list}

    # ——— Statystyki powierzchni
    cur.execute("""
        SELECT 
            COUNT(*) as total_plots_with_geometry,
            COALESCE(SUM(ST_Area(geometria::geography)), 0) as total_area_m2,
            COALESCE(AVG(ST_Area(geometria::geography)), 0) as avg_area_m2,
            COALESCE(MIN(ST_Area(geometria::geography)), 0) as min_area_m2,
            COALESCE(MAX(ST_Area(geometria::geography)), 0) as max_area_m2
        FROM obiekty_geograficzne
        WHERE geometria IS NOT NULL;
    """)
    area_stats_raw = cur.fetchone()
    area_stats = {
        'total_plots_with_geometry': area_stats_raw['total_plots_with_geometry'],
        'total_area_m2': float(area_stats_raw['total_area_m2']),
        'total_area_ha': float(area_stats_raw['total_area_m2']) / 10000,
        'total_area_ares': float(area_stats_raw['total_area_m2']) / 100,
        'avg_area_m2': float(area_stats_raw['avg_area_m2']),
        'avg_area_ha': float(area_stats_raw['avg_area_m2']) / 10000,
        'avg_area_ares': float(area_stats_raw['avg_area_m2']) / 100,
        'min_area_m2': float(area_stats_raw['min_area_m2']),
        'max_area_m2': float(area_stats_raw['max_area_m2'])
    }

    # ——— Genealogia:'''
    
    content = content.replace(insertion_point, area_stats_code)
    
    # 3. Patch dla zwracanego JSONa
    old_return = '''    return jsonify({
        'general_stats': {'total_owners': total_owners, 'total_plots': total_plots},
        'protocols_per_day': protocols_per_day,
        'rankings_real': rankings_real,
        'rankings_protocol': rankings_protocol,
        'demografia': demografia_data,
        'category_counts': category_counts,
        'genealogy_stats': genealogy_stats
    })'''
    
    new_return = '''    return jsonify({
        'general_stats': {'total_owners': total_owners, 'total_plots': total_plots},
        'area_stats': area_stats,
        'protocols_per_day': protocols_per_day,
        'rankings_real': rankings_real,
        'rankings_protocol': rankings_protocol,
        'demografia': demografia_data,
        'category_counts': category_counts,
        'genealogy_stats': genealogy_stats
    })'''
    
    content = content.replace(old_return, new_return)
    
    # Zapisz zmiany
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ backend/app.py zaktualizowany")

# ============================================================================
# Patch dla wlasciciele/stats-script.js  
# ============================================================================

def patch_stats_script_js():
    """Modyfikuje stats-script.js aby dodać obsługę powierzchni."""
    
    file_path = '/home/engine/project/wlasciciele/stats-script.js'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Patch dla loadStatistics
    old_load = '''    updateCounters(statsData.general_stats);
    createCharts(statsData);'''
    
    new_load = '''    updateCounters(statsData.general_stats);
    updateAreaStats(statsData.area_stats);
    createCharts(statsData);'''
    
    content = content.replace(old_load, new_load)
    
    # 2. Dodaj updateAreaStats i formatArea po updateCounters
    insert_after = '''function updateCounters(stats) {
  const ownersCounter = document.querySelector('#total-owners .counter');
  const plotsCounter  = document.querySelector('#total-plots .counter');

  if (ownersCounter) {
    ownersCounter.dataset.target = stats.total_owners;
    animateCounter(ownersCounter, stats.total_owners);
  }
  if (plotsCounter) {
    plotsCounter.dataset.target = stats.total_plots;
    animateCounter(plotsCounter, stats.total_plots);
  }
}

/* ==========================================================================
   WYKRESY (Chart.js)
   ========================================================================== */'''
    
    new_functions = '''function updateCounters(stats) {
  const ownersCounter = document.querySelector('#total-owners .counter');
  const plotsCounter  = document.querySelector('#total-plots .counter');

  if (ownersCounter) {
    ownersCounter.dataset.target = stats.total_owners;
    animateCounter(ownersCounter, stats.total_owners);
  }
  if (plotsCounter) {
    plotsCounter.dataset.target = stats.total_plots;
    animateCounter(plotsCounter, stats.total_plots);
  }
}

/**
 * Aktualizuje statystyki powierzchni działek.
 * @param {Object} areaStats
 */
function updateAreaStats(areaStats) {
  if (!areaStats) return;

  const totalHa = document.getElementById('stat-total-area-ha');
  const avgAres = document.getElementById('stat-avg-area-ares');
  const minM2 = document.getElementById('stat-min-area-m2');
  const maxHa = document.getElementById('stat-max-area-ha');

  if (totalHa) {
    totalHa.textContent = `${areaStats.total_area_ha.toFixed(2)} ha`;
  }
  if (avgAres) {
    avgAres.textContent = `${areaStats.avg_area_ares.toFixed(2)} arów`;
  }
  if (minM2) {
    minM2.textContent = `${Math.round(areaStats.min_area_m2)} m²`;
  }
  if (maxHa) {
    const maxHaValue = areaStats.max_area_m2 / 10000;
    if (maxHaValue < 1) {
      maxHa.textContent = `${Math.round(areaStats.max_area_m2)} m²`;
    } else {
      maxHa.textContent = `${maxHaValue.toFixed(2)} ha`;
    }
  }
}

/* ==========================================================================
   WYKRESY (Chart.js)
   ========================================================================== */'''
    
    content = content.replace(insert_after, new_functions)
    
    # 3. Dodaj funkcję formatArea przed displayRanking
    insert_before_display = '''/**
 * Buduje HTML listy rankingowej (pierwsze 50 pozycji).
 * @param {Array} rankingData
 * @param {HTMLElement} container
 */
function displayRanking(rankingData, container) {'''
    
    format_area_func = '''/**
 * Formatuje powierzchnię dla wyświetlenia.
 * @param {number} areaM2 - Powierzchnia w m²
 * @returns {string}
 */
function formatArea(areaM2) {
  if (!areaM2 || areaM2 === 0) return '0 m²';
  
  const ha = areaM2 / 10000;
  const ares = areaM2 / 100;
  
  if (ha >= 1) {
    return `${ha.toFixed(2)} ha`;
  } else if (ares >= 1) {
    return `${ares.toFixed(2)} arów`;
  } else {
    return `${Math.round(areaM2)} m²`;
  }
}

/**
 * Buduje HTML listy rankingowej (pierwsze 50 pozycji).
 * @param {Array} rankingData
 * @param {HTMLElement} container
 */
function displayRanking(rankingData, container) {'''
    
    content = content.replace(insert_before_display, format_area_func)
    
    # 4. Zamień loadRankings
    old_loadRankings = '''  // Filtry
  document.querySelectorAll('input[name="ownership"]').forEach(r => {
    r.addEventListener('change', filterRankings);
  });
  document.getElementById('category-filter')?.addEventListener('change', filterRankings);
}'''
    
    new_loadRankings = '''  // Filtry
  document.querySelectorAll('input[name="ownership"]').forEach(r => {
    r.addEventListener('change', filterRankings);
  });
  document.querySelectorAll('input[name="sort-by"]').forEach(r => {
    r.addEventListener('change', filterRankings);
  });
  document.getElementById('category-filter')?.addEventListener('change', filterRankings);
}'''
    
    content = content.replace(old_loadRankings, new_loadRankings)
    
    # 5. Zamień całą displayRanking
    old_displayRanking = '''function displayRanking(rankingData, container) {
  container.innerHTML = (rankingData || []).slice(0, 50).map((owner, i) => {
    const pos = i + 1;
    const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
    const prot = owner.numer_protokolu ?? 'Brak';
    return `
      <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}" class="ranking-item">
        <div class="ranking-position ${cls}">${pos}</div>
        <div class="ranking-info">
          <div class="ranking-name">${owner.nazwa_wlasciciela}</div>
          <div class="ranking-meta">Protokół nr ${prot}</div>
        </div>
        <div class="ranking-value">${owner.plot_count}</div>
      </a>`;
  }).join('');
}'''
    
    new_displayRanking = '''function displayRanking(rankingData, container) {
  const sortBy = document.querySelector('input[name="sort-by"]:checked')?.value || 'count';
  
  container.innerHTML = (rankingData || []).slice(0, 50).map((owner, i) => {
    const pos = i + 1;
    const cls = pos === 1 ? 'gold' : pos === 2 ? 'silver' : pos === 3 ? 'bronze' : '';
    const prot = owner.numer_protokolu ?? 'Brak';
    const areaM2 = owner.total_area_m2 || 0;
    const plotNumbers = owner.plot_numbers || [];
    
    const plotNumbersDisplay = plotNumbers.length > 0 
      ? plotNumbers.slice(0, 5).join(', ') + (plotNumbers.length > 5 ? '...' : '')
      : 'Brak';
    
    const valueDisplay = sortBy === 'area' 
      ? `<div style="text-align: right;"><strong>${formatArea(areaM2)}</strong><br><small>${owner.plot_count} działek</small></div>`
      : `<div style="text-align: right;"><strong>${owner.plot_count}</strong> działek<br><small>${formatArea(areaM2)}</small></div>`;
    
    return `
      <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}" class="ranking-item">
        <div class="ranking-position ${cls}">${pos}</div>
        <div class="ranking-info">
          <div class="ranking-name">${owner.nazwa_wlasciciela}</div>
          <div class="ranking-meta">
            Protokół nr ${prot} | Działki: ${plotNumbersDisplay}
          </div>
        </div>
        <div class="ranking-value">${valueDisplay}</div>
      </a>`;
  }).join('');
}'''
    
    content = content.replace(old_displayRanking, new_displayRanking)
    
    # 6. Zamień filterRankings
    old_filterRankings = '''function filterRankings() {
  if (!statsData) return;
  const ownership = document.querySelector('input[name="ownership"]:checked')?.value || 'real';
  const category = document.getElementById('category-filter')?.value || 'all';
  const container = document.getElementById('ranking-list');

  const dataSet = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  let rankingData = category === 'all' ? dataSet.all_plots : dataSet[category];
  if (!rankingData) rankingData = [];

  displayRanking(rankingData, container);

  // Zachowaj aktywne filtrowanie tekstowe
  const searchQuery = document.getElementById('global-search')?.value || '';
  performGlobalSearch(searchQuery);
}'''
    
    new_filterRankings = '''function filterRankings() {
  if (!statsData) return;
  const ownership = document.querySelector('input[name="ownership"]:checked')?.value || 'real';
  const category = document.getElementById('category-filter')?.value || 'all';
  const sortBy = document.querySelector('input[name="sort-by"]:checked')?.value || 'count';
  const container = document.getElementById('ranking-list');

  const dataSet = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  let rankingData = category === 'all' ? dataSet.all_plots : dataSet[category];
  if (!rankingData) rankingData = [];

  rankingData = [...rankingData].sort((a, b) => {
    if (sortBy === 'area') {
      return (b.total_area_m2 || 0) - (a.total_area_m2 || 0);
    } else {
      return (b.plot_count || 0) - (a.plot_count || 0);
    }
  });

  displayRanking(rankingData, container);

  // Zachowaj aktywne filtrowanie tekstowe
  const searchQuery = document.getElementById('global-search')?.value || '';
  performGlobalSearch(searchQuery);
}'''
    
    content = content.replace(old_filterRankings, new_filterRankings)
    
    # 7. Zamień getTop10Owners
    old_getTop10 = '''function getTop10Owners(ownership, category) {
  const data = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  const rankingData = category === 'all' ? data.all_plots : data[category];
  return rankingData?.slice(0, 10) || [];
}'''
    
    new_getTop10 = '''function getTop10Owners(ownership, category) {
  const data = ownership === 'real' ? statsData.rankings_real : statsData.rankings_protocol;
  let rankingData = category === 'all' ? data.all_plots : data[category];
  const sortBy = document.querySelector('input[name="sort-by"]:checked')?.value || 'count';
  
  if (rankingData) {
    rankingData = [...rankingData].sort((a, b) => {
      if (sortBy === 'area') {
        return (b.total_area_m2 || 0) - (a.total_area_m2 || 0);
      } else {
        return (b.plot_count || 0) - (a.plot_count || 0);
      }
    });
  }
  
  return rankingData?.slice(0, 10) || [];
}'''
    
    content = content.replace(old_getTop10, new_getTop10)
    
    # Zapisz zmiany
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ wlasciciele/stats-script.js zaktualizowany")

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("Aplikowanie zmian do plików...")
    patch_app_py()
    patch_stats_script_js()
    print("\n✅ Wszystkie zmiany zostały zastosowane!")
