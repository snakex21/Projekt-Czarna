/** Helpery geometrii GeoJSON dla mapy. */
(function () {
    'use strict';

    function featureBBox(f) {
        if (!f?.geometry) return null;
        const g = f.geometry;
        let min = [Infinity, Infinity], max = [-Infinity, -Infinity];
        const eat = ([x, y]) => {
            if (x < min[0]) min[0] = x;
            if (y < min[1]) min[1] = y;
            if (x > max[0]) max[0] = x;
            if (y > max[1]) max[1] = y;
        };
        if (g.type === 'Point') return [g.coordinates[0], g.coordinates[1], g.coordinates[0], g.coordinates[1]];
        if (g.type === 'LineString') g.coordinates.forEach(eat);
        else if (g.type === 'MultiLineString') g.coordinates.forEach(line => line.forEach(eat));
        else if (g.type === 'Polygon') g.coordinates.forEach(ring => ring.forEach(eat));
        else if (g.type === 'MultiPolygon') g.coordinates.forEach(poly => poly.forEach(ring => ring.forEach(eat)));
        else return null;
        if (!Number.isFinite(min[0])) return null;
        return [min[0], min[1], max[0], max[1]];
    }

    function featureCenter(f) {
        const bb = featureBBox(f);
        if (!bb) return null;
        return [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2];
    }

    window.MapGeometry = Object.freeze({
        featureBBox,
        featureCenter,
    });
})();
