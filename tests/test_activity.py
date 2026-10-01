from pathlib import Path

import pytest
import yaml

from velometer.config import ConfigError, default_config_dir, load_activity
from velometer.models import ActivityYear
from velometer.pipeline.activity import activity, cycling_tags

FIX = Path(__file__).parent / "fixtures" / "history"
CFG = load_activity(default_config_dir() / "activity.yaml")


def _rows(name, years):
    return {
        r.year: r
        for r in activity(
            FIX / name, years, CFG, city_id="t", boundary_kind="lau", history_set_md5="h"
        )
    }


def test_counts_per_year_follow_the_window_rule():
    rows = _rows("mini.osh", range(2018, 2024))
    # Window for Y is [Y-1-01-01, Y-01-01). The brief expected 1 for 2018, but the fixture also
    # has way 2 v1 (2017-01-01, highway=cycleway): ways 1 and 2 are both created in 2017 -> 2.
    assert rows[2018].n_edits == 2
    assert rows[2019].n_edits == 1  # way 4 v1 (2018-03); its v2 only adds surface (not cycling)
    assert rows[2020].n_edits == 1  # way 1 v2 (2019-03) adds segregated
    assert rows[2021].n_edits == 0
    assert rows[2022].n_ways_created_cycling == 1  # way 3 created 2021-02
    assert rows[2023].n_ways_deleted_cycling == 1  # way 3 deleted 2022-08
    assert rows[2018].n_ways_created_cycling == 2
    assert rows[2020].n_ways_created_cycling == 0  # a tag change is not a creation


def test_non_cycling_tag_change_is_not_an_edit():
    rows = _rows("edits.osh", range(2020, 2021))
    # way 10 v2 (changeset 11) only adds name=: not counted, nor its changeset
    assert rows[2020].n_edits == 4
    assert rows[2020].n_changesets == 3  # 10, 12 (two edits), 13


def test_top_mapper_share_and_mapper_count():
    r = _rows("edits.osh", range(2020, 2021))[2020]
    assert r.n_mappers == 2  # uid 7 and the anonymous bucket (uid 0)
    assert r.top_mapper_share == pytest.approx(3 / 4)


def test_year_without_edits_stores_zeros():
    rows = activity(
        FIX / "mini.osh",
        range(2030, 2031),
        CFG,
        city_id="t",
        boundary_kind="lau",
        history_set_md5="h",
    )
    assert rows == [
        ActivityYear(
            city_id="t",
            boundary_kind="lau",
            year=2030,
            history_set_md5="h",
            n_edits=0,
            n_changesets=0,
            n_mappers=0,
            top_mapper_share=0.0,
            n_ways_created_cycling=0,
            n_ways_deleted_cycling=0,
        )
    ]


def test_one_row_per_year():
    rows = activity(
        FIX / "mini.osh",
        range(2018, 2024),
        CFG,
        city_id="t",
        boundary_kind="lau",
        history_set_md5="h",
    )
    assert [r.year for r in rows] == list(range(2018, 2024))


def test_no_uid_leaves_the_function():
    rows = activity(
        FIX / "edits.osh",
        range(2018, 2024),
        CFG,
        city_id="t",
        boundary_kind="lau",
        history_set_md5="h",
    )
    assert all("uid" not in r.model_dump() for r in rows)
    assert not any("uid" in k for k in ActivityYear.model_fields)


def test_cycling_tags_highway_only_for_listed_values():
    assert cycling_tags({"highway": "cycleway", "name": "x"}, CFG) == {"highway": "cycleway"}
    assert cycling_tags({"highway": "residential"}, CFG) == {}
    assert cycling_tags(
        {"highway": "residential", "cycleway:left": "lane", "oneway:bicycle": "no"}, CFG
    ) == {"cycleway:left": "lane", "oneway:bicycle": "no"}
    assert cycling_tags({"sidewalk:both:bicycle": "yes", "surface": "asphalt"}, CFG) == {
        "sidewalk:both:bicycle": "yes"
    }


def test_activity_config_rejects_unknown_keys(tmp_path: Path):
    data = yaml.safe_load((default_config_dir() / "activity.yaml").read_text())
    data["flags"]["bogus"] = 1
    p = tmp_path / "activity.yaml"
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(ConfigError, match="activity.yaml"):
        load_activity(p)


def test_window_end_is_exclusive():
    rows = _rows("window_edges.osh", range(2023, 2025))
    # way 20 v1 is at exactly 2023-01-01T00:00:00Z: it belongs to 2024's window, not 2023's
    assert rows[2023].n_edits == 0
    assert rows[2024].n_edits == 6


def test_deleted_version_with_leftover_tags_counts_as_deletion():
    r = _rows("window_edges.osh", range(2024, 2025))[2024]
    # way 21 v2 is visible=false but still carries highway=cycleway: a deletion regardless.
    # Deletions: way 21 v2, way 22 v2 -> 2.
    assert r.n_ways_deleted_cycling == 2


def test_delete_then_recreate_counts_created_again():
    r = _rows("window_edges.osh", range(2024, 2025))[2024]
    # created: way 20 v1, way 21 v1, way 22 v1, way 22 v3 (recreation) -> 4
    assert r.n_ways_created_cycling == 4
