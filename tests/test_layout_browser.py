"""The phone cascade in a real browser (M13 task 5). The regex tests in test_a11y.py read the
stylesheet for a rule; these ask Chrome what the cascade computes: the Figures tables stack below
700 px (a 1280 px window at 200 % zoom is 640 px), the other stacking tables below 600 px, and
nothing spills sideways."""

import pytest

from tests.test_app_base import rich  # noqa: F401  (`rich` is a fixture)
from tests.test_export import _export
from tests.test_tools import needs_chrome, rp  # noqa: F401  (`rp` is a fixture)

pytestmark = [pytest.mark.slow, needs_chrome]

BASE = "/velometer/"
FIGURES = "city/berlin/figures"
COMPARE = "compare"

PROBE = """(() => {
  const shown = (sel) => [...new Set([...document.querySelectorAll(sel)]
    .map((e) => getComputedStyle(e).display))];
  return {cell: shown('table.figures td'), compare: shown('.compare-table td'),
          wide: document.documentElement.scrollWidth - window.innerWidth,
          tables: document.querySelectorAll('table.figures').length,
          ours: (() => { const e = document.querySelector('table.diffs td:nth-child(4)');
            return e && getComputedStyle(e).textAlign; })(),
          head: (() => { const e = document.querySelector('table.figures thead');
            const c = e && getComputedStyle(e); return c && [c.position, c.display]; })()};
})()"""


@pytest.fixture
def probe(rp, rich, tmp_path):  # noqa: F811
    out = tmp_path / "site"
    _export(rich, out, BASE)

    def run(path, width, ready):
        with rp.serve(out, BASE) as origin, rp.chrome(rp.CHROME) as devtools:
            t = rp.open_tab(devtools, width, "light")
            try:
                errors = rp.navigate(t, origin + BASE + path)
                assert not errors, errors
                assert t.wait_js(f"document.querySelector('{ready}') !== null", 15), ready
                return t.js(PROBE)
            finally:
                t.close()

    return run


@pytest.mark.parametrize("width", [390, 640])
def test_the_figures_tables_are_cards_at_200_percent_zoom_and_on_phones(probe, width):
    got = probe(FIGURES, width, "table.figures td")
    assert got["tables"] >= 1, got
    assert got["cell"] == ["block"], got
    assert got["wide"] <= 0, got


def test_the_figures_tables_are_tables_on_a_desktop(probe):
    got = probe(FIGURES, 1280, "table.figures td")
    assert got["cell"] == ["table-cell"], got


def test_the_compare_table_stays_a_table_at_640(probe):
    # it stacks below 600 px only: the 700 px rule is scoped to the Figures tables
    got = probe(COMPARE, 640, ".compare-table td")
    assert got["compare"] == ["table-cell"], got
    assert got["wide"] <= 0, got


def test_the_figures_cards_hide_the_header_row_visually_and_align_ours_right(probe):
    # twin of test_the_stack_pattern_is_one_phone_rule_set / ..._align_ours_with_theirs_and_gap
    got = probe(FIGURES, 640, "table.figures td")
    assert got["head"][0] == "absolute", got
    assert got["head"][1] != "none", got  # visually hidden, still there for screen readers
    assert got["ours"] == "right", got
