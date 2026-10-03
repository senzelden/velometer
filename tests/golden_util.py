"""Shared golden-set assertions (Berlin's test and the per-country golden tests)."""

import warnings

import pytest

from velometer.trust import expects_newer_classifier


def check_golden(ways: list[dict], observed: dict[int, set[tuple]]) -> None:
    """Assert confirmed ways; skip if none is confirmed, else warn with the unconfirmed count."""
    confirmed = [w for w in ways if w["confirmed"]]
    unconfirmed = len(ways) - len(confirmed)
    if not confirmed:
        pytest.skip(f"0/{len(ways)} golden ways confirmed yet (awaiting review)")
    if unconfirmed:
        warnings.warn(
            f"{unconfirmed}/{len(ways)} golden ways unconfirmed (skipped)",
            UserWarning,
            stacklevel=2,
        )
    for w in confirmed:
        want = {(p["side"], p["tier"], p["rule"]) for p in w["proposed"]}
        assert observed[w["way_id"]] == want, (w["way_id"], w["name"])


def check_country_golden(
    cc: str, ways: list[dict], observed: dict[int, set[tuple]], classifier_version: str
) -> None:
    """`check_golden`, but a file with no confirmed way is skipped naming the country. Confirmed
    ways whose verdict needs a later classifier (`min_classifier`) are left out of the comparison
    and named in a skip, raised only after every other way has been asserted."""
    confirmed = sum(1 for w in ways if w["confirmed"])
    if not confirmed:
        pytest.skip(f"{cc}: 0/{len(ways)} confirmed (awaiting review)")
    later = [w for w in ways if w["confirmed"] and expects_newer_classifier(w, classifier_version)]
    check_golden([w for w in ways if w not in later], observed)
    if later:
        ids = ", ".join(str(w["way_id"]) for w in later)
        wants = sorted({w["min_classifier"] for w in later})
        pytest.skip(
            f"{cc}: way(s) {ids} expect classifier {', '.join(wants)} (report classifier "
            f"{classifier_version}); the other confirmed ways match"
        )
