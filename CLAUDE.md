# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Latest delivered: M13, open follow-ups batch (`docs/superpowers/specs/2026-10-14-velometer-m13-design.md`, rulings in `docs/superpowers/rulings-m13.md`).
Next: not yet decided.

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`
- Network tests are `@pytest.mark.slow` and deselected by default.
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
