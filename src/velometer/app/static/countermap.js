// velometer counter-site map (Counts tab): one marker per counter site with coordinates, over
// OSM raster tiles. Every URL comes from the #countermap-config blob the server renders, so this
// file names no host. Site names are portal data: tooltips are built with textContent.
(function () {
  "use strict";
  var configEl = document.getElementById("countermap-config");
  var mapEl = document.getElementById("countermap");
  if (!configEl || !mapEl || typeof L === "undefined") return;
  var cfg = JSON.parse(configEl.textContent);

  var map = L.map(mapEl, { preferCanvas: true });
  var renderer = L.canvas({ tolerance: 4 });
  L.tileLayer(cfg.tiles, {
    maxZoom: 19,
    className: cfg.tile_class,
    attribution: '© <a href="' + cfg.links.copyright + '">OpenStreetMap contributors</a>',
  }).addTo(map);

  var points = [];
  cfg.sites.forEach(function (s) {
    var name = document.createElement("span");
    name.textContent = s.name;
    L.circleMarker([s.lat, s.lon], {
      renderer: renderer,
      radius: 6,
      color: "#ffffff",
      weight: 1.5,
      fillColor: "#2a78d6",
      fillOpacity: 0.9,
    })
      .bindTooltip(name)
      .addTo(map);
    points.push([s.lat, s.lon]);
  });
  if (points.length === 1) map.setView(points[0], 15);
  else if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: 15 });
})();
