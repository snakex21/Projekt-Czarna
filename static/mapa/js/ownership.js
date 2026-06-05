/** Helpery dopasowania właścicieli dla mapy. */
(function () {
    'use strict';

    function isRealOwnershipType(value) {
        return String(value || '')
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '') === 'wlasnosc rzeczywista';
    }

    function findMatchingOwner(parcelOwners, colorMap, ownershipType) {
        if (ownershipType === 'rzeczywista') {
            return parcelOwners.find(o => colorMap[o.unikalny_klucz] && isRealOwnershipType(o.typ_posiadania)) || null;
        }
        if (ownershipType === 'protokol') {
            return parcelOwners.find(o => colorMap[o.unikalny_klucz] && !isRealOwnershipType(o.typ_posiadania)) || null;
        }
        return parcelOwners.find(o => colorMap[o.unikalny_klucz]) || null;
    }

    window.MapOwnership = Object.freeze({
        isRealOwnershipType,
        findMatchingOwner,
    });
})();
