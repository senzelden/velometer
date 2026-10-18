# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Latest delivered: M15, deploy dry run (`docs/superpowers/specs/2026-10-18-velometer-m15-design.md`, rulings in `docs/superpowers/rulings-m15.md`, evidence `docs/review/m15-dryrun.md`; deploy guide `docs/deploy.md`).
Next: not yet decided.

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`
- Network tests are `@pytest.mark.slow` and deselected by default.
- A `ResourceWarning` fails the run at session end; `VELOMETER_GC_EACH_TEST=1 uv run pytest` names the leaking test (slower).
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
