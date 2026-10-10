import * as L from "leaflet";
import { maplibreGL } from "https://unpkg.com/@maplibre/maplibre-gl-leaflet@0.1.4/dist/leaflet-maplibre-gl.mjs";

// DWD CDC station list and NOAA IGRA2 GMM00010113.
const station = [53.7123, 7.1519];
const styleUrl = "https://tiles.openfreemap.org/styles/fiord";
const attribution = '<a href="https://openfreemap.org/">OpenFreeMap</a> © <a href="https://openmaptiles.org/">OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

const mapElement = document.getElementById("launch-map");
if (mapElement) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const map = L.map(mapElement, {
        scrollWheelZoom: false,
        minZoom: 5,
        maxZoom: 12,
        maxBounds: [[-85, -180], [85, 180]],
        maxBoundsViscosity: 1,
        zoomAnimation: !reduceMotion,
        fadeAnimation: !reduceMotion
    }).setView(station, 8);

    const layer = maplibreGL({
        style: styleUrl,
        attributionControl: { customAttribution: attribution }
    }).addTo(map);

    const icon = L.divIcon({
        className: "launch-marker",
        iconSize: [14, 14],
        iconAnchor: [7, 7]
    });

    L.marker(station, {
        icon,
        title: "DWD-station 10113, Norderney",
        keyboard: true
    }).addTo(map);

    let frame = 0;
    const refreshSize = () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => map.invalidateSize());
    };

    map.whenReady(refreshSize);
    layer.getMaplibreMap().once("load", refreshSize);
    window.addEventListener("resize", refreshSize);
}
