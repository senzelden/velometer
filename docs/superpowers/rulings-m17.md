# M17 rulings

M17 makes velometer findable, citable and published from GitHub.
- Spec: `docs/superpowers/specs/2026-10-31-velometer-m17-design.md`.
- Plan: `docs/superpowers/plans/2026-10-31-velometer-m17.md`.
- SDD ledger, briefs, reports and reviews: `.superpowers/sdd/2026-10-31-velometer-m17/`
  (git-ignored scratch).

Each execution ruling reads: Ruling — why — cost if wrong.

## Execution rulings

- **R1.** (Extends M16 R58.) The public site values, `url` included, are committed in
  `config/site.public.yaml`; `load_site(config_dir, public=True)` merges it over `site.yaml` key by
  key, and only `export --public` asks for it. The config guard therefore exempts no file: the
  scratch copy of `config/` is retired, and a config directory must equal HEAD's `config/`
  — cost: the overlay holds public values only (tested), so a private value must never go in it.
