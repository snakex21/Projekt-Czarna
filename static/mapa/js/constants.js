/** Stałe kontraktowe rdzenia mapy: kolory kategorii i paleta highlightów. */
(function () {
    'use strict';

    const PARCEL_COLORS = {
        budowlana: '#e67e22',
        rolna: '#27ae60',
        las: '#1abc9c',
        droga: '#8B4513',
        rzeka: '#3498db',
        pastwisko: '#f1c40f',
        obrys_miejscowosci: '#ff0000',
        obiekt_specjalny: '#2c3e50',
        default: '#3388ff',
    };

    const PARCEL_FILL_OPACITY = {
        las: 0.5,
        pastwisko: 0.4,
        default: 0.0,
    };

    const HIGHLIGHT_PALETTE = [
        '#E6194B', '#F58231', '#FFE119', '#BFDF45', '#3CB44B',
        '#42D4F4', '#4363D8', '#911EB4', '#F032E6', '#A9A9A9'
    ];

    window.MapConstants = Object.freeze({
        PARCEL_COLORS,
        PARCEL_FILL_OPACITY,
        HIGHLIGHT_PALETTE,
    });
})();
