# M2 execution rulings

These are the decisions made while building M2. Each entry gives the ruling, why it was made, and what it costs if it turns out wrong. Where an ADR or the M2 spec differs from an entry here, the ADR or spec is authoritative.

- **Ruling R1:** test helpers that build fixture files (pyosmium writer, pyogrio write) may be adapted to the installed library API, but assertions may not. The plan already allows this for T3, and the same applies to T5 and T7. Cost: none.
- **Ruling R2:** the commit trailer carries the implementing agent's own model id, per the user instruction of 2026-10-01 (claude-setup-audit policy).
- **Ruling R3 (Task 4):**
  - Retry only transient errors: transport errors, 5xx, 408 and 429.
  - The `.part` file is removed on any BaseException.
  - `retries` must be at least 1.
  - A missing location header or an empty md5 raises a clear error.
  
  Why: the brief's code retried 4xx errors and leaked `.part` files. Cost: none.
- **Ruling R4 (Task 5):**
  - An empty or ≤0 Eurostat population raises ValueError, and `Population.value` must be > 0.
  - A NaN or ≤0 LAU population falls back to NUTS3.
  - A missing NUTS3 code still gives None.
  
  Why: a 0 or a silent None would publish an infinite or blank per-100k figure. Cost if wrong: that city's run fails until its config or data is fixed.
- **Ruling R5 (Task 6):** failures before the run starts (region, boundary or population) are not written to `runs`. They are reported through `RunOutcome` and exit code 1. Why: `osm_timestamp` and `boundary_sha256` are NOT NULL, so recording them would need sentinel values. Cost if wrong: pre-run failures leave no trace in the DB.
- **Ruling R6 (Task 6):** with `--force`, the old run is retired inside `complete_run`'s transaction (`supersedes=`). This overrules the brief, whose up-front retire lost the old results whenever the forced run failed. Cost: one extra keyword argument.
- **Ruling R7 (Task 7):** `retrieved_at` is the downloaded file's mtime as a UTC date. The QECIO file's md5 goes in the row note, and `--refresh-qecio` forces a re-download. Cost if wrong: provenance sits in free-text notes rather than columns.
- **Ruling R8 (Task 8):**
  - `reconcile --write` always renders every city that has a done run; `--city` only filters printing and checking.
  - `--check` fails for any city without a done run.
  
  Cost: `--check` cannot pass until every city has run.
- **Ruling R9 (Task 8):** a tag-only `scope_mismatch` tag is added to the spec's tag list.
- **Ruling R10 (final review I6):** `bnk_network_km` is compared against A+B+E, because BikeNetKit has no lanes (research §7), and the spec was amended. Cost if wrong: Berlin's BikeNetKit flag flips, since the gap is +20.7% with A–E.
- **Ruling R11 (I8):**
  - A dual-carriageway partner candidate must lie within `max_dist_m` before the union is built. This is equivalent for the halving decision, and road km were checked to be bit-identical.
  - Only real partners are persisted.
  - Cost: none.
- **Ruling R12 (I4), schema v3:**
  - `runs` records the population and `config_sha256` (classifier YAML plus `presets.yaml`), and the sha is part of the run key.
  - The migration is additive.
  - Cost: one rerun.
- **Ruling R13 (I3):**
  - The reconcile block carries a provenance line per city.
  - The explanations carry an `explained-against` marker; `--check` fails when it is stale and warns on headings that are no longer used.
- **Ruling R14:** deferred to M3:
  - an atomic v1→v2 migration;
  - an `--offline` mode for cached reruns.
- **Ruling R15 (Task 10, user request):**
  - Each parameterised preset is computed on both bases, and both rows are stored. This is schema v4: the `metrics` primary key gains `length_basis`.
  - `clean_cities_basis` in presets.yaml chooses which row is reported. Its default is `per_side`, as ADR 0003 records; the user confirmed it on 2026-10-01.
  - `--clean-cities-basis` overrides it for reporting only, and `reconcile --write` refuses the override.
  - Reconcile shows the other basis as informational `~basis` rows.
- **DB housekeeping (user approval, 2026-10-01):** superseded runs 1–10 were deleted and the DB vacuumed. `data/velometer-pre-v3.sqlite` holds the pre-v3 state.
