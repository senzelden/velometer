# M5 rulings

## History run wall clock (ADR 0005 table)

Run on 2026-10-03 (16:57–19:33 UTC), classifier `v3` (`plain_cycleway_on_oneway: traffic_side`), one machine,
Geofabrik internal-server full-history files (published md5s of 2026-09-25 builds). 378 history runs,
21 cities × 2 boundary kinds × 9 years (2018–2026), runs 314–691, all `done`; none `-dirty`. (Run 313, a Berlin LAU
2018 row orphaned when its launcher was stopped and relaunched detached, is marked `failed`.)
Berlin and Paris LAU ran at commit 9a545a2; every other series at 0b4e0f2, which only changes how a
broken published md5 is handled (below), not what a run measures (`config_sha256` is the same).

- **Invocation wall:** one `velometer run --cities <c> --years 2018-2026 [--boundary fua]` per city and kind, run sequentially; includes the boundary, index, md5 checks and the per-city history extract, but not the downloads (prefetched with `osm fetch-history`), except Vienna FUA, which downloaded `austria` itself (about 4 min of its 594 s).
- **Run walls:** `finished_at − started_at` of the 9 run rows (snapshot, read, classify, persist).
- **Peak:** the largest `runs.peak_rss_kb` of the 9 years.
- LAU runs overlapped the downloads of later cities (network-bound); FUA runs ran alone.

| city | kind | runs | history set | invocation wall (s) | sum of run walls (s) | per year mean (min–max) | max peak RSS (GB) | commit |
|---|---|---|---|---:|---:|---|---:|---|
| berlin | lau | 314–322 (9, done) | `c3335f42` | 290 | 246 | 27 (16–51) | 2.43 | 9a545a2 |
| paris | lau | 323–331 (9, done) | `7db1f306` | 71 | 58 | 6 (4–11) | 0.97 | 9a545a2 |
| vienna | lau | 683–691 (9, done) | `1254c077` | 113 | 94 | 10 (8–13) | 0.98 | 0b4e0f2 |
| copenhagen | lau | 332–340 (9, done) | `be41de5b` | 33 | 27 | 3 (1–4) | 0.41 | 0b4e0f2 |
| wroclaw | lau | 341–349 (9, done) | `fda036ca` | 86 | 71 | 8 (6–10) | 0.75 | 0b4e0f2 |
| amsterdam | lau | 350–358 (9, done) | `2a652dc2` | 114 | 94 | 10 (8–15) | 0.68 | 0b4e0f2 |
| utrecht | lau | 359–367 (9, done) | `b0b39792` | 51 | 39 | 4 (3–5) | 0.45 | 0b4e0f2 |
| madrid | lau | 368–376 (9, done) | `323b467b` | 108 | 94 | 10 (8–14) | 0.92 | 0b4e0f2 |
| barcelona | lau | 377–385 (9, done) | `9a77f00a` | 59 | 46 | 5 (2–8) | 0.64 | 0b4e0f2 |
| stockholm | lau | 386–394 (9, done) | `149b5257` | 62 | 47 | 5 (4–7) | 0.56 | 0b4e0f2 |
| oslo | lau | 395–403 (9, done) | `47a4f74c` | 91 | 79 | 9 (6–12) | 0.74 | 0b4e0f2 |
| helsinki | lau | 404–412 (9, done) | `78321316` | 131 | 108 | 12 (10–14) | 0.97 | 0b4e0f2 |
| lyon | lau | 413–421 (9, done) | `1404a50e` | 39 | 25 | 3 (2–4) | 0.50 | 0b4e0f2 |
| strasbourg | lau | 422–430 (9, done) | `9c8283ec` | 29 | 19 | 2 (1–3) | 0.38 | 0b4e0f2 |
| bordeaux | lau | 431–439 (9, done) | `cb158134` | 24 | 17 | 2 (1–2) | 0.32 | 0b4e0f2 |
| warsaw | lau | 440–448 (9, done) | `e910fce2` | 182 | 150 | 17 (10–25) | 1.45 | 0b4e0f2 |
| krakow | lau | 449–457 (9, done) | `81a148c2` | 95 | 76 | 8 (6–12) | 0.80 | 0b4e0f2 |
| budapest | lau | 458–466 (9, done) | `0a58443e` | 100 | 79 | 9 (6–11) | 0.78 | 0b4e0f2 |
| prague | lau | 467–475 (9, done) | `6d158548` | 141 | 119 | 13 (10–18) | 1.03 | 0b4e0f2 |
| ljubljana | lau | 476–484 (9, done) | `81ef23ad` | 44 | 31 | 3 (2–5) | 0.52 | 0b4e0f2 |
| bratislava | lau | 485–493 (9, done) | `2e7369e0` | 64 | 50 | 6 (4–7) | 0.61 | 0b4e0f2 |
| berlin | fua | 494–502 (9, done) | `1308e2c9` | 535 | 463 | 51 (32–82) | 3.69 | 0b4e0f2 |
| paris | fua | 503–511 (9, done) | `df7be7ff` | 969 | 861 | 96 (67–130) | 4.86 | 0b4e0f2 |
| vienna | fua | 512–520 (9, done) | `1254c077` | 594 | 358 | 40 (30–48) | 2.46 | 0b4e0f2 |
| copenhagen | fua | 521–529 (9, done) | `be41de5b` | 286 | 246 | 27 (16–35) | 1.55 | 0b4e0f2 |
| wroclaw | fua | 530–538 (9, done) | `fda036ca` | 167 | 136 | 15 (12–19) | 1.09 | 0b4e0f2 |
| amsterdam | fua | 539–547 (9, done) | `3ba1483e` | 502 | 411 | 46 (33–59) | 1.99 | 0b4e0f2 |
| utrecht | fua | 548–556 (9, done) | `b37cd68d` | 178 | 135 | 15 (12–19) | 0.91 | 0b4e0f2 |
| madrid | fua | 557–565 (9, done) | `f0e3c8ec` | 362 | 317 | 35 (26–46) | 2.24 | 0b4e0f2 |
| barcelona | fua | 566–574 (9, done) | `9a77f00a` | 313 | 280 | 31 (18–46) | 2.17 | 0b4e0f2 |
| stockholm | fua | 575–583 (9, done) | `149b5257` | 265 | 230 | 26 (18–32) | 1.69 | 0b4e0f2 |
| oslo | fua | 584–592 (9, done) | `47a4f74c` | 339 | 310 | 34 (19–46) | 2.07 | 0b4e0f2 |
| helsinki | fua | 593–601 (9, done) | `78321316` | 365 | 318 | 35 (26–44) | 2.41 | 0b4e0f2 |
| lyon | fua | 602–610 (9, done) | `1404a50e` | 245 | 208 | 23 (17–31) | 1.61 | 0b4e0f2 |
| strasbourg | fua | 611–619 (9, done) | `8bfe6202` | 131 | 97 | 11 (8–13) | 0.83 | 0b4e0f2 |
| bordeaux | fua | 620–628 (9, done) | `5f5d0d9f` | 182 | 143 | 16 (12–19) | 1.05 | 0b4e0f2 |
| warsaw | fua | 629–637 (9, done) | `72a9a41e` | 418 | 339 | 38 (21–57) | 2.63 | 0b4e0f2 |
| krakow | fua | 638–646 (9, done) | `81a148c2` | 197 | 167 | 19 (12–27) | 1.43 | 0b4e0f2 |
| budapest | fua | 647–655 (9, done) | `0a58443e` | 218 | 184 | 20 (14–27) | 1.51 | 0b4e0f2 |
| prague | fua | 656–664 (9, done) | `678529b2` | 281 | 229 | 25 (19–32) | 1.62 | 0b4e0f2 |
| ljubljana | fua | 665–673 (9, done) | `81ef23ad` | 236 | 211 | 23 (17–28) | 1.57 | 0b4e0f2 |
| bratislava | fua | 674–682 (9, done) | `2e7369e0` | 130 | 104 | 12 (8–15) | 0.94 | 0b4e0f2 |

Totals: LAU invocations 1,927 s (run walls 1,569 s), FUA invocations 6,913 s (run walls 5,747 s);
the whole task, downloads included, took 2 h 36 min of wall clock. Per-year time grows with the size of
the clipped area: Strasbourg/Bordeaux LAU 2 s, Paris FUA 96 s (M3 v1: 98 s). The largest per-year
peak is Paris FUA 2026 (run 511) at 5,092,652 kB (4.86 GB), under the 8 GB gate.

Region sets (`regions_for`), all with `uncovered_km2` 0.0: as Task 15's current FUA merges
(paris 6, amsterdam 4, madrid 3, bordeaux 2, prague 2, strasbourg 2, utrecht 2, warsaw 2), plus
berlin FUA = brandenburg; every other series is the city's own region (vienna = austria,
copenhagen = denmark, budapest = hungary, bratislava = slovakia, ljubljana = slovenia,
helsinki = finland, stockholm = sweden, oslo = ostlandet, krakow = malopolskie,
wroclaw = dolnoslaskie, lyon = rhone-alpes, barcelona = cataluna).

- **R1** A published md5 equal to the md5 of zero bytes (`d41d8cd9…`) counts as no published md5: the download is verified by its computed md5 (`md5_source: computed`). Why: on 2026-10-03 Geofabrik's `.md5` sidecars for austria, hungary and slovakia (regenerated 11:29 UTC) held that value beside unchanged, non-empty files (Last-Modified 2026-09-25), so every fetch failed. The austria download's computed md5 equals the md5 Geofabrik published on 2026-10-01 (`ce458253…`), so its history set is M3's `1254c077`. Cost: these three files rest on a computed, not a published, checksum.
