/**
 * Powiadomienia (toast) w panelu admina — wyekstrahowane z admin.js.
 *
 * Preferowany wariant:
 *     showToast('success' | 'error' | 'info' | 'warning', 'komunikat');
 *
 * Alias kompatybilnościowy dla starszych fragmentów:
 *     showNotification('komunikat', 'success' | 'error' | 'info' | 'warning');
 *   (odwrócona kolejność argumentów!)
 *
 * Dostęp przez `window.AdminNotifications.{showToast,showNotification}`.
 */
(function () {
    'use strict';

    var ICONS = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle',
    };

    function getContainer() {
        return document.getElementById('toastContainer');
    }

    /**
     * Pokazuje toast w prawym dolnym rogu (kontener #toastContainer w admin.html).
     * Automatycznie znika po 3 sekundach z animacją slideOutRight.
     */
    function showToast(type, message) {
        var container = getContainer();
        if (!container) {
            // Brak kontenera to nie jest błąd krytyczny — nie wysypujemy UI,
            // tylko logujemy w konsoli, żeby łatwiej debugować.
            try {
                console.warn('AdminNotifications: brak #toastContainer w DOM, toast pominięty:', type, message);
            } catch (_) {
                /* ignore */
            }
            return;
        }
        var icon = ICONS[type] || 'info-circle';
        var toast = document.createElement('div');
        toast.className = 'toast ' + type;
        toast.innerHTML =
            '<i class="fas fa-' + icon + '"></i>' +
            '<span>' + message + '</span>';
        container.appendChild(toast);

        setTimeout(function () {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(function () { toast.remove(); }, 300);
        }, 3000);
    }

    /**
     * Alias kompatybilnościowy: (message, type) zamiast (type, message).
     * Zostawiony, bo starsze fragmenty panelu admina tak wywołują.
     */
    function showNotification(message, type) {
        showToast(type || 'info', message);
    }

    window.AdminNotifications = Object.freeze({
        showToast: showToast,
        showNotification: showNotification,
    });
})();
