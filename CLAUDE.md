# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Latest delivered: M4 (`docs/superpowers/specs/2026-10-02-velometer-m4-design.md`, rulings in `docs/superpowers/rulings-m4.md`). Next: M5 (HANDOVER §9), not yet designed.

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest`
- Network tests are `@pytest.mark.slow` and deselected by default.
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
