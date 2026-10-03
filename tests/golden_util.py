"""Shared golden-set assertions (Berlin's test and the per-country golden tests)."""

import warnings

import pytest


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


def check_country_golden(cc: str, ways: list[dict], observed: dict[int, set[tuple]]) -> None:
    """`check_golden`, but a file with no confirmed way is skipped naming the country."""
    confirmed = sum(1 for w in ways if w["confirmed"])
    if not confirmed:
        pytest.skip(f"{cc}: 0/{len(ways)} confirmed (awaiting review)")
    check_golden(ways, observed)
