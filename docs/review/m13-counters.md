# M13 counters

## In service by hour

`days.sum_counters` now treats a counter as in service from its first to its last reported *hour* in a file (was: day). Paris and Helsinki (bridge sides) both use it. Raw files unchanged; no download. `velometer.sqlite` is gitignored, so the reloaded database is not part of the commit.

Commands:

```
cp velometer.sqlite $TMPDIR/m13-before.sqlite
uv run velometer counters load paris helsinki   # reads data/counters/<city>/retrieved.json, about 57 s
```

### Complete site-days (complete / all), before and after

**paris**

| year | before | after |
|---|---|---|
| 2016 | 2831 / 16470 | 2831 / 16470 |
| 2017 | 3273 / 17520 | 3273 / 17520 |
| 2018 | 4836 / 4971 | 4836 / 4971 |
| 2019 | 13478 / 14063 | 13478 / 14063 |
| 2020 | 22942 / 23679 | 22942 / 23679 |
| 2021 | 23984 / 27375 | 23984 / 27375 |
| 2022 | 23067 / 27375 | 23067 / 27375 |
| 2023 | 25070 / 25488 | 25070 / 25488 |
| 2024 | 30232 / 31504 | 30232 / 31504 |
| 2025 | 30929 / 32076 | 30929 / 32076 |
| 2026 | 21621 / 22182 | 21621 / 22182 |

**helsinki**

| year | before | after |
|---|---|---|
| 2014 | 2412 / 2424 | 2412 / 2424 |
| 2015 | 4169 / 4192 | 4169 / 4192 |
| 2016 | 4745 / 4758 | 4745 / 4758 |
| 2017 | 4996 / 5016 | 4996 / 5016 |
| 2018 | 6095 / 6114 | 6095 / 6114 |
| 2019 | 5629 / 5743 | 5629 / 5743 |
| 2020 | 6027 / 6048 | 6027 / 6048 |
| 2021 | 5964 / 6029 | 5964 / 6029 |
| 2022 | 5684 / 5703 | 5684 / 5703 |
| 2023 | 5570 / 5608 | 5570 / 5608 |
| 2024 | 4778 / 5173 | 4778 / 5173 |
| 2025 | 5745 / 5802 | 5745 / 5802 |
| 2026 | 2748 / 2803 | 2748 / 2803 |

### Stored counter index v1 (base 2019, `series` counts): index (sites), before, after and final

"After" is the hour rule alone (commit 4466d9d); "final" is after the overlap rule below
(commit 76149c2), the state Task 2's v1 rows were migrated from and recomputed to.

**paris**

| year | before | after (hour rule only) | final (with overlap rule) |
|---|---|---|---|
| 2016 | 75.878718 (7) | 75.878718 (7) | 75.878718 (7) |
| 2017 | 76.940360 (6) | 76.940360 (6) | 76.940360 (6) |
| 2018 | 66.938820 (8) | 66.938820 (8) | 66.938820 (8) |
| 2019 | 100.000000 (31) | 100.000000 (31) | 100.000000 (31) |
| 2020 | 130.210615 (26) | 130.210615 (26) | 130.210615 (26) |
| 2021 | 141.330406 (49) | 141.330406 (49) | 141.330406 (49) |
| 2022 | 165.172519 (49) | 165.172519 (49) | 165.172519 (49) |
| 2023 | 186.493199 (48) | 186.493199 (48) | 186.493199 (48) |
| 2024 | 191.538824 (60) | 191.538824 (60) | 191.538824 (60) |
| 2025 | 205.156574 (74) | 205.156543 (74) | 205.244892 (74) |
| 2026 | none (0) | none (0) | none (0) |

**helsinki**

| year | before | after (hour rule only) | final (with overlap rule) |
|---|---|---|---|
| 2014 | 87.594307 (5) | 87.594307 (5) | 87.594307 (5) |
| 2015 | 91.058002 (8) | 91.058002 (8) | 91.058002 (8) |
| 2016 | 92.212885 (13) | 92.212885 (13) | 92.212885 (13) |
| 2017 | 90.754434 (12) | 90.754434 (12) | 90.754434 (12) |
| 2018 | 104.435715 (13) | 104.435715 (13) | 104.435715 (13) |
| 2019 | 100.000000 (13) | 100.000000 (13) | 100.000000 (13) |
| 2020 | 106.196739 (13) | 106.196739 (13) | 106.196739 (13) |
| 2021 | 85.589400 (13) | 85.589400 (13) | 85.589400 (13) |
| 2022 | 78.953821 (9) | 78.953821 (9) | 78.953821 (9) |
| 2023 | 85.642590 (10) | 85.642590 (10) | 85.642590 (10) |
| 2024 | 85.938157 (8) | 85.938157 (8) | 85.938157 (8) |
| 2025 | 84.157555 (9) | 84.157555 (9) | 84.157555 (9) |
| 2026 | none (0) | none (0) | none (0) |

### Reading

State after the hour rule alone, superseded by the overlap rule below (the final values are
there and in the last column above). The hour rule changes almost nothing in the stored data.
Complete site-days are identical in every city and year. The only `counter_daily` row of Paris
or Helsinki (308,116 rows each side) that differs is Paris site 100047545 on 2025-09-08, complete
both times, count 3825 before and 3814 after the hour rule (an earlier draft of this log had the
two reversed; the overlap rule restores 3825); the hour rule alone moved the Paris 2025 index
from 205.156574 to 205.156543 (74 sites, unchanged). Berlin is untouched.

### Why that one value moved, and why nothing else did

Method: each Paris member file and the Helsinki workbook were parsed, and the per-counter hours
given to the old (day) and the new (hour) `sum_counters` side by side (scratch scripts in
`$TMPDIR/m13scratch`, not committed). Across all 11 Paris members and the Helsinki workbook the
two rules differ in exactly one site-hour: Paris site 100047545, 2025-09-08 00:00, in the rolling
export (the last file, so it wins over the 2025 archive for the days both hold).

- 2025 archive: four counters (101, 102, 103, 104) all report the whole of 2025. 00:00 on
  2025-09-08 is 10 + 8 + 1 + 34 = 53.
- Rolling export (13-month window, starts 2025-09-06): only counters 103 and 104 appear. 104
  reports from 00:00 (42 at 00:00), 103's first row in the file is 02:00 that day (no rows at 00:00
  and 01:00; 01:00 is reported by neither). Under the day rule 103 was in service all of 09-08, so
  00:00 (reported by 104 only) was left out and the archive's 53 stood. Under the hour rule 103 is
  not yet in service at 00:00, so the hour is kept with 42 and, last file winning, replaces 53.
  Day total 3825 - 53 + 42 = 3814. The day was complete before and after.
- So the changed value is the rule working as written, on a counter whose first row in the
  rolling export is at 02:00. It is probably not a commissioning but an edge of the export (the
  archive shows 103 reporting all year, and 101 and 102 are absent from the rolling export): the
  export's partial sum overwrites the archive's fuller one for one hour. The same overwrite
  already holds for every other hour of that day (the archive's four-counter sums are replaced by
  the rolling two-counter sums), under both rules. Not a defect of the hour rule; a limit of
  "last file wins" across overlapping exports, left as is (impact: 11 trips on one site-day).

Why no complete-day count moved: the day rule and the hour rule differ only where a counter starts
or ends inside a day while another counter of the same site reports hours outside its span. Counter
starts and ends that are not at the first or last hour of the file ("interior"), counted per
member file (a start/end is counted when its first/last reported hour is not 00:00/23:00; the
"edge" ones are the file's own first/last hour):

| member | mid-day starts (all / interior) | mid-day ends (all / interior) | hours the hour rule keeps that the day rule dropped |
|---|---|---|---|
| 2016, 2017, 2021, 2022 | 0 / 0 | 0 / 0 | 0 |
| 2018 | 31 / 31 | 45 / 0 | 0 |
| 2019 | 36 / 36 | 81 / 0 | 0 |
| 2020 | 16 / 16 | 0 / 0 | 0 |
| 2023 | 101 / 16 | 0 / 0 | 0 |
| 2024 | 16 / 16 | 1 / 1 | 0 |
| 2025 archive | 2 / 2 | 0 / 0 | 0 |
| rolling export | 112 / 111 | 1 / 1 | 1 (the hour above) |
| Paris total interior | 228 | 2 | 1 |
| Helsinki workbook | 2 / 2 (both sides of Kulosaaren silta, 2015-05-07 01:00, together) | 0 / 0 | 0 |

(The 45 and 81 ends in 2018 and 2019 are the archives stopping at 2018-12-31 00:00 and
2019-12-31 00:00, the file edge.) Mid-day starts exist in the real files, 228 interior ones in
Paris, but nearly all are a whole site's counters starting together (a new site, or a site's
first row is a few hours into a day), so before the start no counter of the site reports and
nothing is dropped under either rule; the two Helsinki bridge sides start together as well. The
M8 defect needs a counter to start or end mid-day while a sibling counter of its site is in
service and reporting; in the real Paris and Helsinki data that happens once (above) and not at
a complete-day boundary that mattered. The M8 defect therefore did not exist in the real data in a
form that changed any stored complete-day figure; the hour rule is a correctness fix for the
rule, not for the numbers.


### Overlapping files: the fuller reading wins (controller ruling)

Ruling: when two files hold the same site-hour, `to_days` keeps the reading summed from more
counters; on a tie the later file, as before. `HourCount` gained `counters: int = 1` (set by
`sum_counters` to the number of counters that reported the hour; other adapters keep 1, so their
behaviour is unchanged). Helsinki reads one workbook, so no cross-file merge happens there: its
numbers are unchanged. Paris was reloaded from the same raw files
(`uv run velometer counters load paris helsinki`).

Result against the pre-M13 database: Paris site 100047545 on 2025-09-08 is back to 3825 (the
archive's four-counter reading is kept for 00:00). The ruling reaches further than that one hour:
119 Paris site-days from 2025-09-06 to 2025-12-31 (8 sites) now hold a higher count than before
(together +31,520), because wherever the rolling export lists fewer counters of a site than the
2025 archive for the same hours, the archive's fuller sum now stands. None of the 119 changes its
completeness. Helsinki: no change. Complete site-days are still identical in every city and year.
Stored Paris index v1: 2025 = 205.244892 (74 sites), was 205.156574; every other Paris year and
all Helsinki years are unchanged. (An earlier version of this paragraph said a printed 205.2 in
content/counters.yaml still matched; no content file prints a Paris index value, so nothing
needed to match. Corrected in Task 2.)

### Complete site-days with hours from readings of different counter counts (Task 2)

Question from the Task 1 review: does any complete Paris site-day mix hours from readings summed
from different numbers of counters (for example an archive outage hour filled by a rolling-export
reading from fewer counters)? Method: each of the 11 Paris files parsed on its own, the overlap
resolution of `to_days` replayed with the file of each kept site-hour recorded, the day totals
checked equal to `to_days` + `zero_days_invalid`, then the distinct `counters` values of each
day's kept hours counted (scratch script, not committed).

| year | complete site-days | with mixed `counters` | of which across files |
|---|---|---|---|
| 2016 | 2831 | 0 | 0 |
| 2017 | 3273 | 0 | 0 |
| 2018 | 4836 | 0 | 0 |
| 2019 | 13478 | 0 | 0 |
| 2020 | 22942 | 0 | 0 |
| 2021 | 23984 | 0 | 0 |
| 2022 | 23067 | 0 | 0 |
| 2023 | 25070 | 0 | 0 |
| 2024 | 30232 | 0 | 0 |
| 2025 | 30929 | 0 | 0 |
| 2026 | 21621 | 0 | 0 |

None. Over all Paris site-days, complete or not, one mixes counter counts: site 100057329 on
2025-09-29, 13 of 24 hours (11 from the 2025 archive with 4 counters, 2 from the rolling export
with 2), incomplete, so outside the index. Count effect: none (marking the mixed complete days
incomplete leaves v1 and v2 unchanged, as there are none). The rule is unchanged.

## Counter index v2 (Task 2)

The link ratio is now the pooled mean per complete day, `(Σ count_t / Σ completedays_t) /
(Σ count_{t−1} / Σ completedays_{t−1})` over the sites that qualify in both years (spec §4.2);
qualification, `MIN_SITES`, `MIN_VALID`, chaining and breaks are unchanged. `counter_index` has a
`method` column (schema v10); the migration tagged the 90 stored rows `v1`, and the recompute
writes v1 and v2 rows for every city (90 each). Readers use `INDEX_METHOD` = v2.

Commands:

```
cp velometer.sqlite data/velometer-pre-m13-v10.sqlite   # git-ignored backup
uv run velometer migrate                                # schema v10, rows -> v1
uv run velometer counters load berlin paris vienna helsinki madrid oslo barcelona   # 81 s
uv run velometer counters --check                       # counters ok: 7 cities
uv run velometer content --check                        # ok, after the Berlin edit below
uv run velometer report methodology
```

The recomputed v1 rows equal the migrated ones exactly (0 of 90 differ), so v1 is the Task 1
state. Barcelona's v1 and v2 rows are identical (one monthly chain stored for both).

### v1 → v2, per link (ratio change = v2 link / v1 link − 1)

Links with a value in consecutive years under both methods. 49 daily-count links; 37 move by less
than 0.5 %.

| city | link | v1 | v2 | change |
|---|---|---|---|---|
| paris | 2019–2020 | +30.21 % | +27.49 % | −2.09 % |
| helsinki | 2024–2025 | −2.07 % | −0.05 % | +2.06 % |
| helsinki | 2022–2023 | +8.47 % | +10.51 % | +1.88 % |
| paris | 2023–2024 | +2.71 % | +1.04 % | −1.63 % |
| oslo | 2018–2019 | −7.98 % | −6.76 % | +1.32 % |
| helsinki | 2023–2024 | +0.35 % | −0.62 % | −0.96 % |
| paris | 2020–2021 | +8.54 % | +9.46 % | +0.85 % |
| oslo | 2019–2020 | +28.29 % | +27.35 % | −0.73 % |
| oslo | 2017–2018 | +17.55 % | +16.70 % | −0.72 % |
| berlin | 2024–2025 | −1.33 % | −0.63 % | +0.71 % |
| paris | 2018–2019 | +49.39 % | +48.62 % | −0.52 % |
| berlin | 2016–2017 | −4.52 % | −4.03 % | +0.51 % |
| helsinki | 2020–2021 | −19.40 % | −19.06 % | +0.43 % |
| berlin | 2022–2023 | −3.47 % | −3.85 % | −0.39 % |
| berlin | 2021–2022 | −0.12 % | +0.20 % | +0.32 % |
| helsinki | 2016–2017 | −1.58 % | −1.27 % | +0.32 % |
| oslo | 2022–2023 | +3.15 % | +2.84 % | −0.30 % |
| paris | 2022–2023 | +12.91 % | +13.22 % | +0.28 % |
| berlin | 2018–2019 | −1.29 % | −1.02 % | +0.28 % |
| paris | 2017–2018 | −13.00 % | −12.76 % | +0.28 % |
| helsinki | 2018–2019 | −4.25 % | −3.98 % | +0.28 % |
| berlin | 2019–2020 | +14.55 % | +14.24 % | −0.28 % |
| helsinki | 2015–2016 | +1.27 % | +0.99 % | −0.27 % |
| vienna | 2020–2021 | +1.20 % | +1.48 % | +0.27 % |
| vienna | 2016–2017 | −0.93 % | −0.66 % | +0.27 % |
| vienna | 2024–2025 | −0.71 % | −0.43 % | +0.27 % |
| vienna | 2019–2020 | +11.98 % | +11.67 % | −0.27 % |
| vienna | 2023–2024 | +4.76 % | +4.47 % | −0.27 % |
| vienna | 2015–2016 | +7.30 % | +7.01 % | −0.27 % |
| oslo | 2020–2021 | −19.33 % | −19.53 % | −0.24 % |
| oslo | 2023–2024 | +6.41 % | +6.16 % | −0.24 % |
| paris | 2021–2022 | +16.87 % | +17.04 % | +0.15 % |
| oslo | 2021–2022 | +9.79 % | +9.94 % | +0.14 % |
| helsinki | 2019–2020 | +6.20 % | +6.06 % | −0.13 % |
| berlin | 2020–2021 | −10.82 % | −10.75 % | +0.08 % |
| oslo | 2024–2025 | +12.73 % | +12.65 % | −0.07 % |
| paris | 2024–2025 | +7.16 % | +7.09 % | −0.06 % |
| berlin | 2023–2024 | +3.20 % | +3.14 % | −0.06 % |
| helsinki | 2017–2018 | +15.08 % | +15.02 % | −0.05 % |
| paris | 2016–2017 | +1.40 % | +1.36 % | −0.04 % |
| helsinki | 2021–2022 | −7.75 % | −7.72 % | +0.03 % |
| vienna | 2013–2014 | +22.89 % | +22.85 % | −0.03 % |
| berlin | 2017–2018 | +13.11 % | +13.13 % | +0.01 % |
| vienna | 2014–2015 | −0.61 % | −0.61 % | −0.00 % |
| helsinki | 2014–2015 | +3.95 % | +3.95 % | 0.00 % |
| vienna | 2017–2018 | +6.56 % | +6.56 % | 0.00 % |
| vienna | 2018–2019 | +0.85 % | +0.85 % | 0.00 % |
| vienna | 2021–2022 | +0.41 % | +0.41 % | 0.00 % |
| vienna | 2022–2023 | +2.76 % | +2.76 % | 0.00 % |

Barcelona's eight links: change 0.00 % each.

The ±0.27 % Vienna links are exactly the leap-year links (2015–2016, 2016–2017, 2019–2020,
2020–2021, 2023–2024, 2024–2025): 366/365 = 1.0027, the extra day v1 summed and v2 divides out.
The other Vienna links move by 0.03 % or less.

**Against the M8 measurement.** It matches. M8 found 37 of 49 links moving by less than 0.5 %;
so does this run. M8 reported the summed (v1) link relative to the pooled one (v1/v2 − 1), so its
signs are the opposite of the change column here; the magnitudes agree to 0.05 points: Paris
2019→2020 +2.1 % (here v1/v2 − 1 = +2.13 %), Helsinki 2024→2025 −2.0 % (−2.02 %), Helsinki
2022→2023 −1.8 % (−1.84 %), Paris 2023→2024 +1.6 % (+1.65 %), Oslo 2018→2019 −1.3 % (−1.30 %).
Task 1 changed Paris inputs only in 2025 (119 site-days of 8 sites, none changing completeness),
which moved the Paris 2024→2025 v1 link by +0.04 %; that link's v1→v2 change is −0.06 %, below
the threshold, so Task 1 explains no difference in the listed links.

**A residual coverage effect.** The pooled mean weights each site by its complete days. A site
that counts more than the pool's mean and loses complete days in one year of a link lowers that
year's pooled mean, so a coverage difference still moves a v2 link, through the site's weight
rather than through its missing days counted as zero. The methodology says so; the test
`test_a_coverage_difference_at_a_busier_site_still_moves_v2_by_its_weight_in_the_pool` pins it.

### Index values, v1 → v2 (base 2019 = 100; Madrid base 2020, only 2020 = 100 in both)

| year | berlin | paris | vienna | helsinki | oslo |
|---|---|---|---|---|---|
| 2013 | – | – | 71.7 → 71.7 | – | – |
| 2014 | – | – | 88.1 → 88.1 | 87.6 → 87.4 | – |
| 2015 | – | – | 87.5 → 87.5 | 91.1 → 90.8 | – |
| 2016 | 93.8 → 93.1 | 75.9 → 76.1 | 93.9 → 93.7 | 92.2 → 91.7 | – |
| 2017 | 89.6 → 89.3 | 76.9 → 77.1 | 93.0 → 93.0 | 90.8 → 90.5 | 92.4 → 91.9 |
| 2018 | 101.3 → 101.0 | 66.9 → 67.3 | 99.2 → 99.2 | 104.4 → 104.1 | 108.7 → 107.2 |
| 2019 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| 2020 | 114.6 → 114.2 | 130.2 → 127.5 | 112.0 → 111.7 | 106.2 → 106.1 | 128.3 → 127.4 |
| 2021 | 102.2 → 102.0 | 141.3 → 139.6 | 113.3 → 113.3 | 85.6 → 85.8 | 103.5 → 102.5 |
| 2022 | 102.0 → 102.2 | 165.2 → 163.3 | 113.8 → 113.8 | 79.0 → 79.2 | 113.6 → 112.7 |
| 2023 | 98.5 → 98.2 | 186.5 → 184.9 | 116.9 → 116.9 | 85.6 → 87.5 | 117.2 → 115.9 |
| 2024 | 101.6 → 101.3 | 191.5 → 186.8 | 122.5 → 122.2 | 85.9 → 87.0 | 124.7 → 123.0 |
| 2025 | 100.3 → 100.7 | 205.2 → 200.1 | 121.6 → 121.6 | 84.2 → 86.9 | 140.6 → 138.6 |

Barcelona: identical (2017 89.2 … 2025 140.3). Year cells "–": no value under either method.

### Prose changed by the recompute

- `content/counters.yaml#sections[covid].paragraphs[0]` (fact `berlin-2020`, `counter.berlin.2020`
  = 114.236212): "Berlin's index stood at 114.6." → "Berlin's index stood at 114.2."
- `content/de/counters.yaml#sections[2].paragraphs[0]`: "Berlins Index lag bei 114,6." →
  "Berlins Index lag bei 114,2." (re-stamped).
- `docs/methodology.md` / `docs/methodology.de.md`, `## Counter index` / `## Zählstellenindex`:
  the index rule sentence states v2; the "known property" paragraph and its hand-typed figures are
  replaced by the generated "Method change (M13)" / "Methodenwechsel (M13)" paragraph and the
  table of the 12 links that moved by 0.5 % or more.
