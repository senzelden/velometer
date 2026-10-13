"""Text Python builds at request time, in the page's language (M12 Task 7 fix round 1): the
comparison provenance line and the flag details. The English forms stay as they were; the German
ones keep source ids, md5s, run ids, rule codes and metric identifiers as code."""

from tests import test_timeseries as TT
from tests.test_m12_leak import english_words
from tests.test_reconcile import RUN, _fig
from velometer import reconcile as RC
from velometer import timeseries as T
from velometer.config import PresetParameters

MD5 = "e" * 32


def _figures():
    q = _fig("qecio_v2_10", "main_roads_km", 2149.6, "nuts3_DE300")
    q = q.model_copy(update={"note": "NUTS3 DE300; file md5 " + MD5})
    return [_fig("clean_cities_2025", "protected_km", 925), q]


def test_reconcile_provenance_english_is_unchanged():
    params = PresetParameters(clean_cities_basis="per_side")
    assert RC.provenance_line(RUN, _figures(), params) == (
        'run 6 · OSM 2026-09-30T20:22:42Z · classifier v1 `{"plain_cycleway_on_oneway":'
        '"traffic_side"}` · config `abababababab` (clean_cities_basis=per_side) · commit '
        "`0123456-dirty` · boundary lau `cdcdcdcdcdcd` · sources: clean_cities_2025 retrieved "
        f"2026-10-01; qecio_v2_10 retrieved 2026-10-01, file md5 {MD5}"
    )
    assert RC.provenance_line({**RUN, "config_sha256": None}, []) == (
        'run 6 · OSM 2026-09-30T20:22:42Z · classifier v1 `{"plain_cycleway_on_oneway":'
        '"traffic_side"}` · config `n/a` · commit `0123456-dirty` · boundary lau '
        "`cdcdcdcdcdcd` · sources: none"
    )


def test_reconcile_provenance_in_german_keeps_the_codes():
    line = RC.provenance_line(RUN, _figures(), PresetParameters(), lang="de")
    for code in (
        "6",
        "2026-09-30T20:22:42Z",
        "v1",
        "abababababab",
        "0123456-dirty",
        "cdcdcdcdcdcd",
        "clean_cities_2025",
        "qecio_v2_10",
        MD5,
        "clean_cities_basis",
    ):
        assert code in line, code  # fmt: skip
    assert "Lauf 6" in line and "Klassifikator v1" in line and "abgerufen" in line
    assert english_words(f"<p>{line}</p>") == []
    empty = RC.provenance_line({**RUN, "config_sha256": None}, [], lang="de")
    assert "k. A." in empty and english_words(f"<p>{empty}</p>") == []


def _details(points, lang="en"):
    return [f.detail for f in T.flags(points, TT.CFG, current_fraction=1.0, lang=lang)]


CAMPAIGN = [TT.pt("2018", 100, 10), TT.pt("2019", 100, 10), TT.pt("2020", 200, 40, share=0.9)]
DRIFT = [TT.pt("2018", 100, 10, legacy=100.0), TT.pt("2019", 100, 10, legacy=10.0)]


def test_flag_details_english_are_unchanged():
    assert _details(CAMPAIGN) == [
        "A+B km 100.0 -> 200.0 (needs 25.0); 40 edits (limit 20.0); km_jump and activity_spike;"
        " top mapper share 0.90"
    ]
    assert _details(DRIFT) == ["legacy_km 100.0 -> 10.0"]


def test_flag_details_in_german():
    (campaign,) = _details(CAMPAIGN, "de")
    (drift,) = _details(DRIFT, "de")
    assert "100,0" in campaign and "20,0" in campaign and "0,90" in campaign
    assert "km_jump" in campaign and "activity_spike" in campaign
    assert drift == "legacy_km 100,0 -> 10,0"
    assert english_words(f"<p>{campaign}</p>") == []
