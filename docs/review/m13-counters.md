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

### Stored counter index v1 (base 2019, `series` counts): index (sites), before and after

**paris**

| year | before | after |
|---|---|---|
| 2016 | 75.878718 (7) | 75.878718 (7) |
| 2017 | 76.940360 (6) | 76.940360 (6) |
| 2018 | 66.938820 (8) | 66.938820 (8) |
| 2019 | 100.000000 (31) | 100.000000 (31) |
| 2020 | 130.210615 (26) | 130.210615 (26) |
| 2021 | 141.330406 (49) | 141.330406 (49) |
| 2022 | 165.172519 (49) | 165.172519 (49) |
| 2023 | 186.493199 (48) | 186.493199 (48) |
| 2024 | 191.538824 (60) | 191.538824 (60) |
| 2025 | 205.156574 (74) | 205.156543 (74) |
| 2026 | none (0) | none (0) |

**helsinki**

| year | before | after |
|---|---|---|
| 2014 | 87.594307 (5) | 87.594307 (5) |
| 2015 | 91.058002 (8) | 91.058002 (8) |
| 2016 | 92.212885 (13) | 92.212885 (13) |
| 2017 | 90.754434 (12) | 90.754434 (12) |
| 2018 | 104.435715 (13) | 104.435715 (13) |
| 2019 | 100.000000 (13) | 100.000000 (13) |
| 2020 | 106.196739 (13) | 106.196739 (13) |
| 2021 | 85.589400 (13) | 85.589400 (13) |
| 2022 | 78.953821 (9) | 78.953821 (9) |
| 2023 | 85.642590 (10) | 85.642590 (10) |
| 2024 | 85.938157 (8) | 85.938157 (8) |
| 2025 | 84.157555 (9) | 84.157555 (9) |
| 2026 | none (0) | none (0) |

### Reading

The hour rule changes almost nothing in the stored data. Complete site-days are identical in every
city and year. The only `counter_daily` row of Paris or Helsinki (308,116 rows each side) that
differs is Paris site 100047545 on 2025-09-08, complete both times, count 3825 before and 3814
after (an earlier draft of this log had the two reversed); it moves the Paris 2025 index from
205.156570 to 205.156543 (74 sites, unchanged). Berlin is untouched.

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

