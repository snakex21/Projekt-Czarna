/**
 * Oś czasu protokołów centrum analitycznego (P2.8 Etap 14).
 *
 * Dostęp przez `window.StatsTimeline`.
 */
(function () {
  'use strict';

  function render(protocolsPerDay) {
    if (!protocolsPerDay) return;

    const container = document.getElementById('timeline-content');
    if (!container) return;

    container.innerHTML = protocolsPerDay.map(item => {
      const date = new Date(item.protocol_date);
      const formatted = date.toLocaleDateString('pl-PL', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
      const ownersList = _renderOwners(item.owners || []);

      return `
        <div class="timeline-item">
          <div class="timeline-marker"></div>
          <div class="timeline-content">
            <div class="timeline-date">${formatted}</div>
            <details>
              <summary class="timeline-title">${item.protocol_count} protokołów (kliknij, aby rozwinąć)</summary>
              <ul class="timeline-owners-list">${ownersList}</ul>
            </details>
          </div>
        </div>`;
    }).join('');
  }

  function _renderOwners(owners) {
    return owners.map(owner => `
      <li>
        <a href="../wlasciciele/protokol.html?ownerId=${owner.unikalny_klucz}">
          ${owner.nazwa_wlasciciela}
        </a>
      </li>`).join('');
  }

  window.StatsTimeline = Object.freeze({
    render: render,
  });
})();
