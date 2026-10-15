"""Pick the series and change-map colours by rule (M13 Task 4). A dev tool, not shipped.

The rule is the one tests/test_colour.py and tests/test_a11y.py hold the palettes to: every
colour >= 3:1 against its grounds, every pair >= CIEDE2000 20 in normal vision and in simulated
deuteranopia and protanopia (Machado 2009), and for the change colours gained/lost >= 25. Among
the palettes that pass, it keeps the one closest to the current colours (least summed normal-vision
Delta E, slot by slot), so the look stays.

Candidates are an OKLCH grid (gamut-clipped to sRGB) plus the current colours. The search is a
local search with restarts over a precomputed pairwise matrix (numpy CIEDE2000); the winner is
re-checked with velometer.report.colour, the code the tests use.

    uv run python tools/pick_palette.py                         # all four palettes, seed 13
    uv run python tools/pick_palette.py series-light --seed 2   # one, another restart seed

The search is randomised (restarts from greedy passing palettes), so seeds can land on different
local optima; the M13 pick is the best of seeds 1-4 per palette (task 4 report).
"""

import itertools
import math
import random
import sys

import numpy as np

from velometer.report.colour import _MACHADO, _hex, _linear, contrast, delta, lab

VISIONS = ("normal", "deuteranopia", "protanopia")
FLOOR, GAINED_LOST = 20.0, 25.0
MARGIN = 0.05  # searched above the floors: the float32 matrix may differ from colour.delta
LIGHT_GROUNDS = ("#ffffff", "#fcfcfa", "#f4f3ef")  # --surface, --paper, --panel (light)
DARK_GROUNDS = ("#151514", "#1d1d1b", "#262623")  # --paper, --surface, --panel (dark)

# the M12 palettes: the look to keep (light = charts.SERIES_COLOURS and change.CATEGORY_COLOURS
# then, dark = the app.css dark tokens then), so a re-run reproduces the M13 pick
CURRENT = {
    "series-light": ["#2a78d6", "#eb6834", "#35a186", "#bf8500",
                     "#d96d98", "#8753cd", "#52514e", "#008300"],
    "series-dark": ["#5e98ed", "#e77648", "#49a294", "#c1902d",
                    "#d97b99", "#b07fea", "#979693", "#5dad42"],
    "change-light": ["#1baf7a", "#eb6834", "#eda100", "#2a78d6"],
    "change-dark": ["#58c394", "#e77648", "#ffb948", "#6895e8"],
}  # fmt: skip
# light: the series rule's two grounds (the panel never grounds a series mark, test_a11y.py's
# NOT_ON_PANEL); the change colours are graphics on all three. Dark: all three grounds
GROUNDS = {
    "series-light": LIGHT_GROUNDS[:2],
    "series-dark": DARK_GROUNDS,
    "change-light": LIGHT_GROUNDS,
    "change-dark": DARK_GROUNDS,
}
# OKLCH lightness of the grid. Light: the brief's 0.45-0.62 holds at most six colours that pass
# (a randomised clique search found no seventh), so the grid reaches down to 0.30, where eight do
L_RANGE = {"light": (0.30, 0.66), "dark": (0.55, 0.99)}


def oklch_hex(L: float, C: float, h: float) -> str | None:
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    if any(c < -1e-4 or c > 1 + 1e-4 for c in rgb):
        return None
    return _hex(rgb)


def candidates(theme: str, grounds) -> list[str]:
    lo, hi = L_RANGE[theme]
    out = set()
    for L in np.arange(lo, hi + 1e-9, 0.02):
        for C in np.arange(0.0, 0.30, 0.025):
            for h in range(0, 360, 6 if C else 360):
                x = oklch_hex(float(L), float(C), h)
                if x and all(contrast(x, g) >= 3.0 for g in grounds):
                    out.add(x)
    return sorted(out)


def _sim(hexcolour: str, vision: str) -> str:
    if vision == "normal":
        return hexcolour
    m, rgb = _MACHADO[vision], _linear(hexcolour)
    return _hex(tuple(sum(m[i][j] * rgb[j] for j in range(3)) for i in range(3)))


def _de2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 between every row of lab1 and every row of lab2 (broadcast)."""
    L1, a1, b1 = (lab1[:, None, i] for i in range(3))
    L2, a2, b2 = (lab2[None, :, i] for i in range(3))
    cbar = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(cbar**7 / (cbar**7 + 25.0**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dlp, dcp = L2 - L1, c2p - c1p
    dhp = h2p - h1p
    dhp = np.where(dhp > 180, dhp - 360, np.where(dhp < -180, dhp + 360, dhp))
    dhp = np.where(c1p * c2p == 0, 0.0, dhp)
    dHp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dhp / 2))
    lbp, cbp = (L1 + L2) / 2, (c1p + c2p) / 2
    hsum, hdiff = h1p + h2p, np.abs(h1p - h2p)
    hbp = np.where(
        c1p * c2p == 0,
        hsum,
        np.where(hdiff <= 180, hsum / 2, np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)),
    )
    t = (
        1
        - 0.17 * np.cos(np.radians(hbp - 30))
        + 0.24 * np.cos(np.radians(2 * hbp))
        + 0.32 * np.cos(np.radians(3 * hbp + 6))
        - 0.20 * np.cos(np.radians(4 * hbp - 63))
    )
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    rc = 2 * np.sqrt(cbp**7 / (cbp**7 + 25.0**7))
    sl = 1 + 0.015 * (lbp - 50) ** 2 / np.sqrt(20 + (lbp - 50) ** 2)
    sc, sh = 1 + 0.045 * cbp, 1 + 0.015 * cbp * t
    rt = -np.sin(np.radians(2 * dtheta)) * rc
    return np.sqrt(
        (dlp / sl) ** 2 + (dcp / sc) ** 2 + (dHp / sh) ** 2 + rt * (dcp / sc) * (dHp / sh)
    )


def matrices(cands: list[str]) -> np.ndarray:
    """Worst-vision pairwise Delta E over the candidates (float32, in row chunks)."""
    n = len(cands)
    worst = np.full((n, n), np.inf, dtype=np.float32)
    for v in VISIONS:
        labs = np.array([lab(_sim(c, v)) for c in cands])
        for i in range(0, n, 400):
            worst[i : i + 400] = np.minimum(worst[i : i + 400], _de2000(labs[i : i + 400], labs))
    return worst


def _assign(colours: list[int], to_current: np.ndarray) -> list[int]:
    """The slot order of `colours` with the least summed Delta E to the current slots."""
    k = len(colours)
    sub = to_current[colours]  # colour x slot
    perms = np.array(list(itertools.permutations(range(k))), dtype=np.int8)
    cost = sub[perms, np.arange(k)].sum(axis=1)
    order = perms[int(np.argmin(cost))]
    # perms[p][c] is the slot of colour c
    pick = [0] * k
    for c, slot in enumerate(order):
        pick[slot] = colours[c]
    return pick


def search(name: str, tries: int = 4000, seed: int = 13, keep: tuple[int, ...] = ()):
    """(colours, shortfall, summed Delta E to current, min pairwise Delta E, candidates).
    `keep`: slots (0-based) whose current colour stays as it is."""
    theme = name.split("-")[1]
    current, grounds = CURRENT[name], GROUNDS[name]
    cands = candidates(theme, grounds)
    cands = sorted(set(cands) | {c for c in current if all(contrast(c, g) >= 3 for g in grounds)})
    worst = matrices(cands)
    to_current = _de2000(np.array([lab(c) for c in cands]), np.array([lab(c) for c in current]))
    for i in keep:  # only the current colour itself may fill a kept slot
        to_current[:, i] = np.where(np.array(cands) == current[i], 0.0, 1e6)
    n, k = len(cands), len(current)
    pair_floor = np.full((k, k), FLOOR + MARGIN)
    if name.startswith("change"):
        pair_floor[0, 1] = pair_floor[1, 0] = GAINED_LOST + MARGIN  # gained, lost
    ok = worst >= FLOOR + MARGIN
    ok_strict = worst >= GAINED_LOST + MARGIN
    rng = random.Random(seed)

    def shortfall(pick) -> float:
        return sum(
            max(0.0, pair_floor[i, j] - worst[pick[i], pick[j]])
            for i, j in itertools.combinations(range(k), 2)
        )

    def score(pick):
        return (round(shortfall(pick), 6), float(sum(to_current[pick[i], i] for i in range(k))))

    def improve(pick):
        """Swap one slot at a time for the candidate that lowers (shortfall, distance) most."""
        cur, improved = score(pick), True
        while improved:
            improved = False
            for i in rng.sample(range(k), k):
                others = [j for j in range(k) if j != i]
                short = np.zeros(n)
                for j in others:
                    short += np.maximum(0.0, pair_floor[i, j] - worst[:, pick[j]])
                rest = sum(
                    max(0.0, pair_floor[a, b] - worst[pick[a], pick[b]])
                    for a, b in itertools.combinations(others, 2)
                )
                dist = to_current[:, i] + sum(to_current[pick[j], j] for j in others)
                short = np.round(short + rest, 6)
                short[pick] = np.inf  # no colour twice
                c = int(np.lexsort((dist, short))[0])
                s = (float(short[c]), float(dist[c]))
                if s < cur:
                    pick, cur, improved = pick[:i] + [c] + pick[i + 1 :], s, True
        return cur, pick

    def floor_ok(a: int, b: int) -> np.ndarray:
        """The pass matrix for slots a and b: the gained/lost pair has the higher floor."""
        return ok_strict if name.startswith("change") and {a, b} == {0, 1} else ok

    def improve2(pick, width: int = 300):
        """Swap two slots at once, keeping the palette passing: for each pair of slots (i, j),
        each of the `width` candidates nearest slot i's current colour that fit, with the nearest
        that fits slot j beside it. Then single swaps again. Only for passing palettes."""
        cur, improved = score(pick), True
        while improved:
            improved = False
            for i, j in itertools.permutations(range(k), 2):
                others = [x for x in range(k) if x not in (i, j)]
                fits_i, fits_j = np.ones(n, bool), np.ones(n, bool)
                for x in others:
                    fits_i &= floor_ok(i, x)[:, pick[x]]
                    fits_j &= floor_ok(j, x)[:, pick[x]]
                base = sum(to_current[pick[x], x] for x in others)
                idx = np.flatnonzero(fits_i)
                for c in idx[np.argsort(to_current[idx, i])[:width]]:
                    g = np.flatnonzero(fits_j & floor_ok(i, j)[c])
                    if not len(g):
                        continue
                    d = base + to_current[c, i] + to_current[g, j].min()
                    if d < cur[1] - 1e-9:
                        pick = list(pick)
                        pick[i], pick[j] = int(c), int(g[np.argmin(to_current[g, j])])
                        cur, improved = score(pick), True
        return improve(pick)

    def build():
        """A random greedy palette that passes: kept slots first, then slot by slot in random
        order, among the candidates that pass with every colour chosen so far either one of the
        nearest to the slot's current colour or one of the best connected (which leaves the most
        room for the slots still open); None on a dead end."""
        free = np.ones(n, bool)
        chosen = {}
        near = rng.choice((0.0, 0.25, 0.5))  # how often a step goes for the nearest
        for i in [*keep, *rng.sample([j for j in range(k) if j not in keep], k - len(keep))]:
            idx = np.flatnonzero(free)
            if not len(idx):
                return None
            if i in keep:
                top = idx[to_current[idx, i] == 0][:1]
                if not len(top):
                    return None
            elif rng.random() < near:
                top = idx[np.argsort(to_current[idx, i])[:8]]
            else:
                deg = ok[np.ix_(idx, idx)].sum(1) if len(idx) < 2000 else ok[idx].sum(1)
                top = idx[np.argsort(-deg)[: max(1, len(idx) // 20)]]
            c = int(rng.choice(list(top)))
            chosen[i] = c
            free &= ok[c]
            free[c] = False
        pick = [chosen[i] for i in range(k)]
        if name.startswith("change") and not ok_strict[pick[0], pick[1]]:
            return None
        return _assign(pick, to_current) if not name.startswith("change") else pick

    # start from the nearest candidates to the current colours, then from random passing ones
    best = improve([int(np.argmin(to_current[:, i])) for i in range(k)])
    found = [best]
    for _ in range(tries):
        pick = build()
        if pick is not None and shortfall(pick) < 1e-9:
            found.append(improve(pick))
    found = sorted({tuple(p): (s, p) for s, p in found}.values())[:10]
    for s, p in found:  # the ten best go through the two-slot swaps
        if s[0] == 0:
            best = min(best, improve2(p))
    (short, dist), pick = best
    colours = [cands[i] for i in pick]
    floor = min(delta(a, b, v) for v in VISIONS for a, b in itertools.combinations(colours, 2))
    return colours, short, dist, floor, len(cands)


def report(name: str, seed: int) -> None:
    colours, short, dist, floor, n = search(name, tries=6000, seed=seed)
    grounds = GROUNDS[name]
    print(f"{name} (seed {seed}): {n} candidates; shortfall {short:.3f}")
    print(f"  summed Delta E to the M12 colours: {dist:.1f}")
    print(f"  colours: {colours}")
    print(f"  min pairwise Delta E over {', '.join(VISIONS)}: {floor:.2f}")
    if name.startswith("change"):
        gl = min(delta(colours[0], colours[1], v) for v in VISIONS)
        print(f"  gained/lost min Delta E: {gl:.2f}")
    for cur, new in zip(CURRENT[name], colours, strict=True):
        c = min(contrast(new, g) for g in grounds)
        print(f"  {cur} -> {new}  (Delta E {delta(cur, new):5.1f}, min contrast {c:.2f})")


if __name__ == "__main__":
    args = sys.argv[1:]
    seed = int(args.pop(args.index("--seed") + 1)) if "--seed" in args else 13
    args = [a for a in args if a != "--seed"]
    for name in args or CURRENT:
        report(name, seed)
