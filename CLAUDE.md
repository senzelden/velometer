# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Latest delivered: M7, the reader app and narratives (`docs/superpowers/specs/2026-10-06-velometer-m7-design.md`, rulings in `docs/superpowers/rulings-m7.md`). Next: none planned.

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`
- Network tests are `@pytest.mark.slow` and deselected by default.
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
