// velometer tier map: the run's tiered sides (GeoJSON from `velometer report maps`) over OSM
// raster tiles, with a LAU/FUA switch and tier checkboxes. Every URL and colour comes from the
// #tiermap-config blob the server renders (charts.TIER_COLOURS, the tile and link URLs), so this
// file names no host and duplicates no palette. OSM tag values are user data: popups are built
// with textContent, never innerHTML.
(function () {
  "use strict";
  var configEl = document.getElementById("tiermap-config");
  var mapEl = document.getElementById("tiermap");
  if (!configEl || !mapEl || typeof L === "undefined") return;
  var cfg = JSON.parse(configEl.textContent);
  var status = document.getElementById("tiermap-status");
  var TIERS = Object.keys(cfg.colours); // A..E
  var cache = {}; // kind -> FeatureCollection
  var current = null; // {tiers: {A: layer, ...}, boundary: layer}

  var map = L.map(mapEl, { preferCanvas: true });
  var renderer = L.canvas({ tolerance: 6 }); // thin lines: a forgiving click target
  L.tileLayer(cfg.tiles, {
    maxZoom: 19,
    attribution:
      '© <a href="' + cfg.links.copyright + '">OpenStreetMap contributors</a>',
  }).addTo(map);

  function say(text) {
    if (status) status.textContent = text;
  }

  function el(tag, text, attrs) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    for (var k in attrs || {}) node.setAttribute(k, attrs[k]);
    return node;
  }

  function popup(p) {
    var box = el("div", null, { class: "tiermap-popup" });
    var dl = el("dl");
    function row(label, value) {
      dl.appendChild(el("dt", label));
      var dd = el("dd");
      if (value instanceof Node) dd.appendChild(value);
      else dd.textContent = value === null || value === undefined ? "–" : String(value);
      dl.appendChild(dd);
    }
    var link = el("a", "way " + p.way_id, {
      href: cfg.links.way + encodeURIComponent(p.way_id),
      target: "_blank",
      rel: "noopener noreferrer",
    });
    row("OSM", link);
    row("side", p.side);
    row("tier", cfg.labels[p.tier] || p.tier);
    row("subtype", p.subtype);
    row("rule", p.rule_id);
    row("km", typeof p.km === "number" ? p.km.toFixed(3) : p.km);
    box.appendChild(dl);
    var keys = Object.keys(p.tags || {}).sort();
    if (keys.length) {
      var table = el("table");
      keys.forEach(function (k) {
        var tr = el("tr");
        tr.appendChild(el("td", k));
        tr.appendChild(el("td", p.tags[k]));
        table.appendChild(tr);
      });
      box.appendChild(table);
    }
    return box;
  }

  function checked(tier) {
    var box = document.querySelector('input[name="tier"][value="' + tier + '"]');
    return !box || box.checked;
  }

  function show(kind, data) {
    if (current) {
      TIERS.forEach(function (t) { map.removeLayer(current.tiers[t]); });
      if (current.boundary) map.removeLayer(current.boundary);
    }
    var boundary = data.boundary
      ? L.geoJSON(data.boundary, {
          interactive: false,
          renderer: renderer,
          style: { color: cfg.outline, weight: 1.5, fill: false },
        }).addTo(map)
      : null;
    var tiers = {};
    // E first, A last: A draws on top where sides overlap (as in the PNG)
    TIERS.slice().reverse().forEach(function (t) {
      tiers[t] = L.geoJSON(data, {
        renderer: renderer,
        filter: function (f) { return f.properties.tier === t; },
        style: { color: cfg.colours[t], weight: 2.5, opacity: 0.9 },
        onEachFeature: function (f, layer) {
          layer.bindPopup(function () { return popup(f.properties); }, { maxWidth: 360 });
        },
      });
      if (checked(t)) tiers[t].addTo(map);
    });
    current = { tiers: tiers, boundary: boundary };
    var bounds = boundary ? boundary.getBounds() : L.featureGroup(TIERS.map(function (t) {
      return tiers[t];
    })).getBounds();
    if (bounds.isValid()) map.fitBounds(bounds);
    var p = data.properties || {};
    say(
      kind.toUpperCase() + " · " + data.features.length + " sides · OSM " + p.osm_timestamp +
        " · classifier " + p.classifier + " · run " + p.run_id +
        ". Click a side for its way, tier, rule and tags."
    );
  }

  function load(kind) {
    var entry = cfg.kinds.filter(function (k) { return k.kind === kind; })[0];
    if (!entry) return;
    if (cache[kind]) return show(kind, cache[kind]);
    say("Loading " + entry.label + " map …");
    fetch(entry.url)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status + " " + r.statusText);
        return r.json();
      })
      .then(function (data) {
        cache[kind] = data;
        show(kind, data);
      })
      .catch(function (e) { say("Could not load the " + entry.label + " map: " + e.message); });
  }

  document.querySelectorAll('input[name="tier"]').forEach(function (box) {
    box.addEventListener("change", function () {
      if (!current) return;
      var layer = current.tiers[box.value];
      if (box.checked) layer.addTo(map);
      else map.removeLayer(layer);
      // re-adding puts a tier on top: restore A-over-E order
      TIERS.slice().reverse().forEach(function (t) {
        if (map.hasLayer(current.tiers[t])) current.tiers[t].bringToFront();
      });
    });
  });
  document.querySelectorAll('input[name="kind"]').forEach(function (radio) {
    radio.addEventListener("change", function () { if (radio.checked) load(radio.value); });
  });
  var first = document.querySelector('input[name="kind"]:checked');
  load(first ? first.value : cfg.kinds[0].kind);
})();
