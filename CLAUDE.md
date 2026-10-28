# velometer

Read `HANDOVER.md` (project brief) and `docs/adr/` (locked decisions) before changing behaviour.
Latest delivered: M16, Hetzner deployment behind the lock, own tiles, statistics, legal review (`docs/superpowers/specs/2026-10-21-velometer-m16-design.md`, rulings in `docs/superpowers/rulings-m16.md`, evidence `docs/review/m16-deploy.md` and `docs/review/m16-legal.md`; deploy guide `docs/deploy.md`).
Next: Task 12 go-live (user's go).

- Gate: `uv run ruff format --check . && uv run ruff check . && uv run pytest && node --test "src/velometer/app/static/js/tests/*.test.mjs"`
- Network tests are `@pytest.mark.slow` and deselected by default.
- A `ResourceWarning` fails the run at session end; `VELOMETER_GC_EACH_TEST=1 uv run pytest` names the leaking test (slower).
- Classifier rules are data in `config/classifier/vN.yaml`; a rule change is a new version.
- Lengths only in the city's projected EPSG. OSM km are "mapped km" (ADR 0006).
- Never type OSM ids from memory; query them.
