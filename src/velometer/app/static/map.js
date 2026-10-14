// velometer tier map: the run's tiered sides (GeoJSON from `velometer report maps`) over OSM
// raster tiles, with a LAU/FUA switch and tier checkboxes. Every URL comes from the
// #tiermap-config blob the server renders, so this file names no host; every colour is a
// stylesheet token (--tier-a … --tier-e, --outline) read when it draws, and the layers are
// restyled in place when the OS theme changes (zoom and position stay). OSM tag values are user
// data: popups are built with textContent, never innerHTML.
import { TIERMAP, read, readerMoves, write } from "./js/permalink.js";
import { onThemeChange, tierColours, token } from "./js/theme.js";
import { number } from "./js/fmt.js";
import { mapStatus } from "./js/data.js";
import { leafletPrefix, t } from "./js/strings.js";

(function () {
  "use strict";
  var configEl = document.getElementById("tiermap-config");
  var mapEl = document.getElementById("tiermap");
  if (!configEl || !mapEl || typeof L === "undefined") return;
  var cfg = JSON.parse(configEl.textContent);
  var status = document.getElementById("tiermap-status");
  var TIERS = Object.keys(cfg.labels); // A..E
  var cache = {}; // kind -> FeatureCollection
  var current = null; // {tiers: {A: layer, ...}, boundary: layer}
  var selected = null; // the kind the reader picked last
  // permalink state (?kind=&tiers=&at=lat,lon,z): bad values are the defaults, see permalink.js
  var want = read(location.search, TIERMAP, cfg.kinds.map(function (k) { return k.kind; }));
  var view = want.at; // the reader's own pan/zoom, or null while the app's fit is showing
  var fitting = false; // true while the app moves the map itself: that is not the reader's view

  var map = L.map(mapEl, { preferCanvas: true });
  map.attributionControl.setPrefix(leafletPrefix(map.attributionControl.options.prefix));
  var renderer = L.canvas({ tolerance: 6 }); // thin lines: a forgiving click target
  L.tileLayer(cfg.tiles, {
    maxZoom: 19,
    className: cfg.tile_class, // muted in app.css; the vector canvas is not
    attribution:
      '© <a href="' + cfg.links.copyright + '">' + t("js.map.osm_contributors") + "</a>",
  }).addTo(map);

  function say(text) {
    if (status) status.textContent = text;
  }

  function tierStyle(colours, t) {
    return { color: colours[t], weight: cfg.weight, opacity: 0.9 };
  }

  function boundaryStyle() {
    return { color: token("--outline"), weight: 1.5, fill: false };
  }

  // the key beside the tier checkboxes: one swatch per tier, the colour its lines are drawn in
  function paintKey(colours) {
    document.querySelectorAll(".tiermap-controls svg.swatch[data-key] rect").forEach(function (r) {
      r.setAttribute("fill", colours[r.parentNode.getAttribute("data-key")]);
    });
  }

  function restyle() {
    var colours = tierColours();
    paintKey(colours);
    if (!current) return;
    TIERS.forEach(function (t) { current.tiers[t].setStyle(tierStyle(colours, t)); });
    if (current.boundary) current.boundary.setStyle(boundaryStyle());
  }

  function el(tag, text, attrs) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    for (var k in attrs || {}) node.setAttribute(k, attrs[k]);
    return node;
  }

  function popup(p) {
    var box = el("div", null, { class: "tiermap-popup" });
    // the tier opens the popup, by name ("A separated track"): the line's colour is not the only
    // thing that says which tier a side is
    box.appendChild(el("p", cfg.labels[p.tier] || p.tier, { class: "tiermap-popup-tier" }));
    var dl = el("dl");
    function row(label, value) {
      dl.appendChild(el("dt", label));
      var dd = el("dd");
      if (value instanceof Node) dd.appendChild(value);
      else dd.textContent = value === null || value === undefined ? "–" : String(value);
      dl.appendChild(dd);
    }
    var link = el("a", t("js.map.way", { id: p.way_id }), {
      href: cfg.links.way + encodeURIComponent(p.way_id),
      target: "_blank",
      rel: "noopener noreferrer",
    });
    row("OSM", link);
    row(t("js.map.side"), p.side);
    row(t("js.map.tier"), cfg.labels[p.tier] || p.tier);
    row(t("js.map.subtype"), p.subtype);
    row(t("js.map.rule"), p.rule_id);
    row("km", typeof p.km === "number" ? number(p.km, 3) : p.km);
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

  // write the state into the address (replaceState: the Back button is not flooded)
  function sync() {
    var radio = document.querySelector('input[name="kind"]:checked');
    var tiers = TIERS.filter(checked);
    try {
      history.replaceState(history.state, "", write({
        kind: radio && radio.value !== cfg.kinds[0].kind ? radio.value : null,
        tiers: tiers,
        at: view,
      }, TIERMAP));
    } catch (e) { /* a sandboxed frame may refuse; the page works without */ }
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
          style: boundaryStyle(),
        }).addTo(map)
      : null;
    var tiers = {};
    var colours = tierColours();
    // E first, A last: A draws on top where sides overlap (as in the PNG)
    TIERS.slice().reverse().forEach(function (t) {
      tiers[t] = L.geoJSON(data, {
        renderer: renderer,
        filter: function (f) { return f.properties.tier === t; },
        style: tierStyle(colours, t),
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
    fitting = true;
    if (view) map.setView([view[0], view[1]], view[2], { animate: false });
    else if (bounds.isValid()) map.fitBounds(bounds, { animate: false });
    fitting = false;
    var p = data.properties || {};
    say(mapStatus(kind, data.features.length, p));
  }

  function load(kind) {
    var entry = cfg.kinds.filter(function (k) { return k.kind === kind; })[0];
    if (!entry) return;
    selected = kind;
    if (cache[kind]) return show(kind, cache[kind]);
    say(t("js.map.loading", { kind: entry.label }));
    fetch(entry.url)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status + " " + r.statusText);
        return r.json();
      })
      .then(function (data) {
        cache[kind] = data;
        if (selected === kind) show(kind, data); // else a late answer for a kind left
      })
      .catch(function (e) {
        if (selected === kind) say(t("js.map.failed", { kind: entry.label, reason: e.message }));
      });
  }

  document.querySelectorAll('input[name="tier"]').forEach(function (box) {
    box.addEventListener("change", function () {
      sync();
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
    radio.addEventListener("change", function () {
      if (!radio.checked) return;
      view = null; // another boundary is fitted by the app; the old view is no longer the reader's
      load(radio.value);
      sync();
    });
  });
  var moves = readerMoves();
  map.on("resize", moves.resize);
  map.on("moveend", function () {
    if (!moves.moveend(fitting)) return;
    var c = map.getCenter();
    view = [c.lat, c.lng, map.getZoom()];
    sync();
  });
  paintKey(tierColours());
  onThemeChange(restyle);
  // apply the permalink state to the controls before the first draw
  var kind = want.kind || cfg.kinds[0].kind;
  document.querySelectorAll('input[name="kind"]').forEach(function (radio) {
    radio.checked = radio.value === kind;
  });
  document.querySelectorAll('input[name="tier"]').forEach(function (box) {
    box.checked = want.tiers.indexOf(box.value) !== -1;
  });
  load(kind);
})();
