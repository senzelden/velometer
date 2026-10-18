# M15 rulings

M15 serves the static export locally with the server software of both hosting routes and audits it
over HTTP. Nothing was deployed.
- Spec: `docs/superpowers/specs/2026-10-18-velometer-m15-design.md`.
- Plan: `docs/superpowers/plans/2026-10-18-velometer-m15.md`.
- SDD ledger, briefs, reports and reviews: `.superpowers/sdd/2026-10-18-velometer-m15/` (git-ignored
  scratch).

The committed evidence:
- `docs/review/m15-dryrun.md`, the versions, commands, reports and fixes;
- `docs/deploy.md`, with the local dry run (§0a).

Each execution ruling reads: Ruling — why — cost if wrong.

## User decisions, 2026-10-18 (spec §2)

- **Tier maps:** not shrunk. They are 226 MB raw and 29 MB gzipped; the largest, Helsinki FUA, is
  20.9 MB raw and 2.8 MB gzipped. A 1 m simplification was measured and not chosen (Helsinki FUA
  compressed geometry 2.07 to 1.17 MB).
- **Dry run:** both routes locally, Caddy in Docker and `wrangler pages dev` through `npx`.
- **Site values:** `site.yaml` gets placeholders in a scratch config only.
- **Host and tiles:** the host stays neutral; tiles stay a follow-up.

## Execution rulings

1. Work on branch `m15` in the main checkout, without a worktree — earlier milestones did the same,
   and `.worktrees/` is not git-ignored — cost: none.
2. Task 2 review: the clean failure on a missing `docker` or `npx`, and SIGKILL to the wrangler
   process group, entered the fix loop although the reviewer had rated them Minor. They break the
   plan's Review Focus #1 and #2 — cost: one extra fix round.
3. Pin `caddy:2.11.4-alpine` instead of the plan's `caddy:2.10.2-alpine` — 2.10.2 answers
   precompressed files with 206; the spec only asks for an exact version at least two weeks old —
   cost: a version string.
4. The 404 probe accepts any Cache-Control and keeps CSP, nosniff and Referrer-Policy strict.
   Cloudflare's `_headers` documentation (developers.cloudflare.com/pages/configuration/headers/,
   read 2026-10-18) says the rules apply to "static asset responses" and says nothing about 404s,
   and `wrangler pages dev` sends `no-store` on its 404. An uncached not-found answer is harmless —
   cost: a host could cache 404s differently from `_headers`, with no security effect.
5. The subagent commits carry the trailer `Assisted-by: Claude:claude-opus-5-5`, the session's model
   and the project convention — cost: the trailer names the controller model, not the
   implementer's.
6. The plan's SDD workspace is not deleted with `rm -rf` (user rule). It is git-ignored and left in
   place — cost: a few KB.
