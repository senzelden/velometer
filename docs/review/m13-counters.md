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
differs is Paris site 100047545 on 2025-09-08, complete both times, count 3814 before and 3825
after; it moves the Paris 2025 index from 205.156570 to 205.156543 (74 sites, unchanged). Berlin
is untouched.
