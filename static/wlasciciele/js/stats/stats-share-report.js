/**
 * Udost?pnianie raportu centrum analitycznego (P2.8 Etap 21).
 *
 * Dost?p przez `window.StatsShareReport`.
 */
(function () {
  'use strict';

  let showToast = () => {};

  function init(callbacks) {
    callbacks = callbacks || {};
    showToast = callbacks.showToast || showToast;
  }

/** Otwiera modal z linkiem i kodem QR do udostępniania */
function shareReport() {
  const modal = document.getElementById('share-modal');
  const linkInput = document.getElementById('share-link-input');
  const qrcodeContainer = document.getElementById('qrcode');
  const copyBtn = document.getElementById('copy-link-btn');

  // Ustaw link w polu tekstowym
  linkInput.value = window.location.href;

  // Wyczyść poprzedni kod QR jeśli istnieje
  qrcodeContainer.innerHTML = '';

  // Generuj nowy kod QR
  new QRCode(qrcodeContainer, {
    text: window.location.href,
    width: 256,
    height: 256,
    colorDark: '#000000',
    colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.H
  });

  // Pokaż modal
  modal.classList.add('active');

  // Obsługa kopiowania linku
  copyBtn.onclick = () => {
    linkInput.select();
    navigator.clipboard.writeText(window.location.href);
    showToast('success', 'Sukces', 'Link skopiowany do schowka');
  };

  // Obsługa zamykania modalu
  const closeBtn = modal.querySelector('.modal-close');
  closeBtn.onclick = () => modal.classList.remove('active');
  modal.onclick = (e) => {
    if (e.target === modal) modal.classList.remove('active');
  };
}

  window.StatsShareReport = Object.freeze({
    init: init,
    shareReport: shareReport,
  });
})();
