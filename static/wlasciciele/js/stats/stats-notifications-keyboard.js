/**
 * Powiadomienia toast i skróty klawiaturowe centrum analitycznego (P2.8 Etap 19).
 *
 * Dostęp przez window.StatsNotificationsKeyboard.
 */
(function () {
  'use strict';

/* ==========================================================================
   POWIADOMIENIA (Toast)
   ========================================================================== */

/**
 * Prosty system toastów (kontener #toast-container w HTML).
 * @param {'success' | 'error' | 'info'} type
            * @param {string} title
            * @param {string} message
            */
function showToast(type, title, message) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
            <div class="toast-icon">
                <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}"></i>
            </div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-message">${message}</div>
            </div>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toastOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

/* ==========================================================================
   SKRÓTY KLAWISZOWE
   ========================================================================== */

/**
 * Podstawowe skróty: Ctrl+F (search), D (dark), Esc (zamknij).
 */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Ctrl+F – szybkie wyszukiwanie
    if (e.ctrlKey && (e.key === 'f' || e.key === 'F')) {
      e.preventDefault();
      document.getElementById('search-toggle')?.click();
    }
    // D – przełącz tryb ciemny (jeśli fokus nie w input/textarea)
    if ((e.key === 'd' || e.key === 'D') && !e.target.matches('input, textarea')) {
      document.getElementById('theme-toggle')?.click();
    }
    // Esc – zamknij modal / wyszukiwarkę
    if (e.key === 'Escape') {
      document.querySelector('.modal.active')?.classList.remove('active');
      document.getElementById('search-bar')?.classList.remove('active');
    }
  });
}



  window.StatsNotificationsKeyboard = Object.freeze({
    showToast: showToast,
    initKeyboardShortcuts: initKeyboardShortcuts,
  });
})();
