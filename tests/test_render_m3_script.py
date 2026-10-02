import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from velometer import cli  # noqa: E402
from velometer import timeseries as T  # noqa: E402

_PATH = Path(__file__).resolve().parent.parent / "scripts" / "render_m3_timeseries.py"
_spec = importlib.util.spec_from_file_location("render_m3_timeseries", _PATH)
render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render)

YEARS = range(2018, 2027)


def _p(label, headline=1.0):
    ts = "2026-09-30T00:00:00Z" if label == T.CURRENT else f"{label}-01-01T00:00:00Z"
    return T.YearPoint(label, 1, ts, headline, 0.0, dict.fromkeys("ABCDE", 0.0), None, None, None)


def test_chart_selects_runs_with_the_cli_selector():
    assert render.run_selector is cli.run_selector


def test_points_sit_at_their_year_so_a_gap_stays_a_gap():
    fig, ax = plt.subplots()
    full = [_p(str(y)) for y in YEARS] + [_p(T.CURRENT)]
    gappy = [_p("2018"), _p("2020"), _p(T.CURRENT)]
    render._headline_lines(
        ax, [("full", full, {}, "k", "-"), ("gappy", gappy, {"2020": None}, "r", "-")], YEARS
    )
    assert list(ax.lines[0].get_xdata()) == list(range(10))
    assert list(ax.lines[1].get_xdata()) == [0, 2, 9]  # 2020 lines up with the full series
    ring = ax.collections[1].get_offsets()  # the flagged 2020 point of the gappy series
    assert [tuple(map(float, o)) for o in ring] == [(2.0, 1.0)]
    plt.close(fig)


def test_slots_cover_every_year_and_now_only_with_a_current_point():
    slots = render._slots([[_p("2018"), _p("2026")]], YEARS)
    assert [x for x, _ in slots] == list(range(9)) and slots[-1][1] == "2026"
    slots = render._slots([[_p("2026")], [_p("2026"), _p(T.CURRENT)]], YEARS)
    assert slots[-1] == (9, "now\n2026-09")
