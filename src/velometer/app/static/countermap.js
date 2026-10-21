// velometer counter-site map (Counts tab): one marker per counter site with coordinates, over
// the vector basemap (js/basemap.js). Every URL comes from the #countermap-config blob the server
// renders, so this file names no host; the markers are drawn in the stylesheet's --marker-fill /
// --marker-stroke tokens and restyled in place when the OS theme changes (zoom and position stay).
// Site names are portal data: tooltips are built with textContent.
import { onThemeChange, token } from "./js/theme.js";
import { leafletPrefix } from "./js/strings.js";
import { addBasemap } from "./js/basemap.js";

(function () {
  "use strict";
  var configEl = document.getElementById("countermap-config");
  var mapEl = document.getElementById("countermap");
  if (!configEl || !mapEl || typeof L === "undefined") return;
  var cfg = JSON.parse(configEl.textContent);

  var map = L.map(mapEl, { preferCanvas: true, maxZoom: 19 });
  map.attributionControl.setPrefix(leafletPrefix(map.attributionControl.options.prefix));
  var renderer = L.canvas({ tolerance: 4 });
  addBasemap(map, cfg);

  function markerStyle() {
    return { color: token("--marker-stroke"), fillColor: token("--marker-fill") };
  }

  var points = [];
  var markers = [];
  var look = markerStyle();
  cfg.sites.forEach(function (s) {
    var name = document.createElement("span");
    name.textContent = s.name;
    var marker = L.circleMarker([s.lat, s.lon], {
      renderer: renderer,
      radius: 6,
      color: look.color,
      weight: 1.5,
      fillColor: look.fillColor,
      fillOpacity: 0.9,
    })
      .bindTooltip(name)
      .addTo(map);
    markers.push(marker);
    points.push([s.lat, s.lon]);
  });
  onThemeChange(function () {
    var next = markerStyle();
    markers.forEach(function (m) { m.setStyle(next); });
  });
  if (points.length === 1) map.setView(points[0], 15);
  else if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 15 });
})();
