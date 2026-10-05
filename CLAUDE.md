# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Latest delivered: M6, classifier v4 and the Berlin Bezirk deep-dive (`docs/superpowers/specs/2026-10-04-velometer-m6-design.md`, rulings in `docs/superpowers/rulings-m6.md`). Next: none planned (HANDOVER §9 ends at M6).

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest`
- Network tests are `@pytest.mark.slow` and deselected by default.
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
