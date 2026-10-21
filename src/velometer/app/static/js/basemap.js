// The maps' background: a Protomaps vector extract (one PMTiles file served beside the site at
// the config's `tiles` URL, ADR 0008) drawn by the vendored protomaps-leaflet (the `protomapsL`
// global of static/vendor/protomaps-leaflet.js) in a muted flavour of our own. Its colours are the
// stylesheet's --map-* tokens (app.css, light and dark): near-grey, so no road or area reads as a
// tier or change colour; read again and swapped in place when the OS theme changes (no CSS
// filter). Labels use the generic sans-serif the browser already has: no glyph, sprite or font
// host. The `landcover` layer (ESA WorldCover) is never drawn: the flavour has no `landcover` key,
// which is how protomaps-leaflet's rules leave it out. A missing or unreachable tile file leaves
// the map without a background, quietly: the lines and markers draw on the container's own ground
// and the console stays empty.
import { onThemeChange, token } from "./theme.js";
import { t } from "./strings.js";

// the maps' own limit (their L.map maxZoom); past the extract's maxzoom the layer overzooms
export const MAX_ZOOM = 19;
// the colour roles, each the token --map-<role>
export const ROLES = [
  "earth", "water", "green", "area", "hard", "building", "road", "rail", "boundary", "label",
  "place", "faint", "halo",
];

/**
 * The flavour of the current theme, in the shape protomaps-leaflet's paintRules/labelRules read
 * (the keys of @protomaps/basemaps' Flavor its rules use; js/tests/basemap.test.mjs reads them
 * from the vendored bundle), without `landcover`. Every road is drawn in `major`. `read` is
 * injectable for node tests (theme.js).
 */
export function flavour(read) {
  const c = Object.fromEntries(ROLES.map((r) => [r, token(`--map-${r}`, read)]));
  return {
    background: c.water, // the sea: Protomaps draws land (`earth`) over it
    earth: c.earth,
    water: c.water,
    park_a: c.green,
    park_b: c.green,
    wood_a: c.green,
    wood_b: c.green,
    scrub_a: c.green,
    scrub_b: c.green,
    hospital: c.area,
    industrial: c.area,
    school: c.area,
    pedestrian: c.area,
    glacier: c.area,
    sand: c.area,
    beach: c.area,
    aerodrome: c.area,
    zoo: c.area,
    runway: c.hard,
    pier: c.hard,
    buildings: c.building, // drawn at half opacity
    major: c.road,
    railway: c.rail,
    boundaries: c.boundary,
    roads_label_minor: c.label,
    roads_label_minor_halo: c.halo,
    roads_label_major: c.label,
    roads_label_major_halo: c.halo,
    ocean_label: c.label,
    city_label: c.place,
    city_label_halo: c.halo,
    state_label: c.faint,
    state_label_halo: c.halo,
    country_label: c.label,
  };
}

/**
 * The map credits (docs/review/m16-legal.md 1.1a, 1.7): `data`, the OSM credit linked to the
 * copyright page, which every map shows (its lines are OSM data too); `basemap`, the layer's.
 */
export function credits(cfg) {
  return {
    data: '© <a href="' + cfg.links.copyright + '">' + t("js.map.osm_contributors") + "</a>",
    basemap: t("js.map.basemap_credit"), // landcover is credited although never drawn (R11)
  };
}

/**
 * Put the basemap under `map`'s lines: a HEAD request for `cfg.tiles` first; anything but 200/206,
 * a failed request, an unreadable PMTiles header or a library call that throws resolves `null`
 * (no layer, nothing logged); it never rejects, so the maps call it without awaiting it.
 * `theme` is the matchMedia whose colour-scheme changes repaint it; `deps` replace the page's
 * globals in tests (`read`: the token reader).
 */
export async function addBasemap(map, cfg, theme = globalThis.matchMedia, deps = {}) {
  const fetchFn = deps.fetch ?? globalThis.fetch;
  const pm = deps.pm ?? globalThis.protomapsL;
  const lang = deps.lang ?? (globalThis.document?.documentElement.lang || "en");
  const credit = credits(cfg);
  map.attributionControl.addAttribution(credit.data);
  if (!cfg.tiles || !pm || !fetchFn) return null;
  try {
    const r = await fetchFn(cfg.tiles, { method: "HEAD" });
    if (r.status !== 200 && r.status !== 206) return null;
    const source = new pm.PmtilesSource(cfg.tiles, true).p;
    const header = await source.getHeader();
    const f = flavour(deps.read);
    const layer = pm.leafletLayer({
      url: source,
      paintRules: pm.paintRules(f),
      labelRules: pm.labelRules(f, lang),
      backgroundColor: f.background,
      maxDataZoom: header.maxZoom,
      maxZoom: MAX_ZOOM,
      lang: lang,
      attribution: credit.basemap,
    });
    layer.addTo(map);
    onThemeChange(function () {
      const next = flavour(deps.read);
      layer.paintRules = pm.paintRules(next);
      layer.labelRules = pm.labelRules(next, lang);
      layer.backgroundColor = next.background;
      layer.clearLayout();
      layer.rerenderTiles();
    }, theme);
    return layer;
  } catch (e) {
    // unreachable, a server without byte ranges, or a vendored library that no longer fits these
    // calls (the render pass's map steps catch that one: no tile is drawn): no background
    return null;
  }
}
