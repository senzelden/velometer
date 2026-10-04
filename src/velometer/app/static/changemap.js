// velometer change map: the mapped gained / lost / retiered / redrawn way-sides between two runs
// (GeoJSON from `velometer report change`) over OSM raster tiles. Every URL and colour comes from
// the #changemap-config blob the server renders, so this file names no host and duplicates no
// palette. Figures are mapped km (ADR 0006). OSM tag values are user data: popups are built with
// textContent, never innerHTML.
(function () {
  "use strict";
  var configEl = document.getElementById("changemap-config");
  var mapEl = document.getElementById("changemap");
  if (!configEl || !mapEl || typeof L === "undefined") return;
  var cfg = JSON.parse(configEl.textContent);
  var status = document.getElementById("changemap-status");

  var map = L.map(mapEl, { preferCanvas: true });
  var renderer = L.canvas({ tolerance: 6 });
  L.tileLayer(cfg.tiles, {
    maxZoom: 19,
    className: cfg.tile_class,
    attribution: '© <a href="' + cfg.links.copyright + '">OpenStreetMap contributors</a>',
  }).addTo(map);

  function say(text) {
    if (status) status.textContent = text;
  }

  function el(tag, text) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function wayLink(id) {
    var a = el("a", "way " + id);
    a.setAttribute("href", cfg.links.way + encodeURIComponent(id));
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
    return a;
  }

  function popup(p) {
    var box = el("div");
    box.className = "tiermap-popup";
    var dl = el("dl");
    function row(label, value) {
      dl.appendChild(el("dt", label));
      var dd = el("dd");
      if (value instanceof Node) dd.appendChild(value);
      else dd.textContent = value === null || value === undefined ? "–" : String(value);
      dl.appendChild(dd);
    }
    row("change", cfg.labels[p.category] || p.category);
    if (p.way_id_from) row("way (from)", wayLink(p.way_id_from));
    if (p.way_id_to) row("way (to)", wayLink(p.way_id_to));
    row("side", p.side);
    row("tier", p.tier_from === p.tier_to ? p.tier_to : (p.tier_from || "–") + " → " + (p.tier_to || "–"));
    row("mapped km", typeof p.km === "number" ? p.km.toFixed(3) : p.km);
    box.appendChild(dl);
    return box;
  }

  say("Loading the change map …");
  fetch(cfg.url)
    .then(function (r) {
      if (!r.ok) throw new Error(r.status + " " + r.statusText);
      return r.json();
    })
    .then(function (data) {
      // geometry changes are listed in the table, not drawn (no colour for them)
      var layer = L.geoJSON(data, {
        renderer: renderer,
        filter: function (f) { return !!cfg.colours[f.properties.category]; },
        style: function (f) {
          return { color: cfg.colours[f.properties.category], weight: cfg.weight, opacity: 0.9 };
        },
        onEachFeature: function (f, l) {
          l.bindPopup(function () { return popup(f.properties); }, { maxWidth: 360 });
        },
      }).addTo(map);
      var bounds = layer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds);
      var counts = {};
      data.features.forEach(function (f) {
        var c = f.properties.category;
        if (cfg.colours[c]) counts[c] = (counts[c] || 0) + 1;
      });
      say(
        Object.keys(cfg.colours)
          .map(function (c) { return (counts[c] || 0) + " " + cfg.labels[c]; })
          .join(" · ") + ". Click a way-side for its way and mapped km."
      );
    })
    .catch(function (e) {
      say("Could not load the change map: " + e.message);
    });
})();
