// velometer change map: the mapped gained / lost / retiered / redrawn way-sides between two runs
// (GeoJSON from `velometer report change`) over OSM raster tiles. Every URL comes from the
// #changemap-config blob the server renders, so this file names no host; every colour is a
// stylesheet token (--change-<category>) read when it draws, and the layer and its key are
// restyled in place when the OS theme changes (zoom and position stay). Figures are mapped km
// (ADR 0006). OSM tag values are user data: popups are built with textContent, never innerHTML.
import { onThemeChange, token } from "./js/theme.js";
import { number } from "./js/fmt.js";
import { t } from "./js/strings.js";

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
    attribution: '© <a href="' + cfg.links.copyright + '">' + t("js.map.osm_contributors") + "</a>",
  }).addTo(map);

  function say(text) {
    if (status) status.textContent = text;
  }

  // the categories drawn (geometry changes are listed in the table, not drawn), in key order
  var CATEGORIES = Object.keys(cfg.labels);
  var drawn = function (c) { return CATEGORIES.indexOf(c) >= 0; };
  var colourOf = function (c) { return token("--change-" + c); };
  var layer = null;

  function style(f) {
    return { color: colourOf(f.properties.category), weight: cfg.weight, opacity: 0.9 };
  }

  // the key under the map: one swatch per category, the colour its way-sides are drawn in
  function paintKey() {
    document.querySelectorAll(".changemap-legend svg.swatch[data-key] rect").forEach(function (r) {
      r.setAttribute("fill", colourOf(r.parentNode.getAttribute("data-key")));
    });
  }

  paintKey();
  onThemeChange(function () {
    paintKey();
    if (layer) layer.setStyle(style);
  });

  function el(tag, text) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function wayLink(id) {
    var a = el("a", t("js.map.way", { id: id }));
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
    row(t("js.map.change"), cfg.labels[p.category] || p.category);
    if (p.way_id_from) row(t("js.map.way_from"), wayLink(p.way_id_from));
    if (p.way_id_to) row(t("js.map.way_to"), wayLink(p.way_id_to));
    row(t("js.map.side"), p.side);
    row(t("js.map.tier"), p.tier_from === p.tier_to ? p.tier_to : (p.tier_from || "–") + " → " + (p.tier_to || "–"));
    row(t("js.map.mapped_km"), typeof p.km === "number" ? number(p.km, 3) : p.km);
    box.appendChild(dl);
    return box;
  }

  say(t("js.map.change_loading"));
  fetch(cfg.url)
    .then(function (r) {
      if (!r.ok) throw new Error(r.status + " " + r.statusText);
      return r.json();
    })
    .then(function (data) {
      layer = L.geoJSON(data, {
        renderer: renderer,
        filter: function (f) { return drawn(f.properties.category); },
        style: style,
        onEachFeature: function (f, l) {
          l.bindPopup(function () { return popup(f.properties); }, { maxWidth: 360 });
        },
      }).addTo(map);
      var bounds = layer.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds);
      var counts = {};
      data.features.forEach(function (f) {
        var c = f.properties.category;
        if (drawn(c)) counts[c] = (counts[c] || 0) + 1;
      });
      say(t("js.map.change_status", {
        counts: CATEGORIES
          .map(function (c) { return number(counts[c] || 0, 0) + " " + cfg.labels[c]; })
          .join(" · "),
      }));
    })
    .catch(function (e) {
      say(t("js.map.change_failed", { reason: e.message }));
    });
})();
