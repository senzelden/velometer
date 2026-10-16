"""The Orca pass session environment under a locale (M14 Task 11); no dbus, Orca or Chrome."""

import os

import pytest

from tests.helpers import load_script


@pytest.fixture(scope="module")
def orca():
    return load_script("tools/orca_pass.py")


@pytest.fixture
def locpath(tmp_path):
    (tmp_path / "locale" / "de_DE.UTF-8").mkdir(parents=True)
    return tmp_path / "locale"


@pytest.fixture
def live_desktop(monkeypatch):
    """A caller with a real display, a language list and a locale of its own."""
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("LANGUAGE", "en")
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")


def test_locale_sets_the_session_and_keeps_it_isolated(orca, locpath, tmp_path, live_desktop):
    before = dict(os.environ)
    env = orca.isolated_env(tmp_path / "env", "de_DE.UTF-8", locpath)
    assert env["LANG"] == env["LC_ALL"] == "de_DE.UTF-8"
    assert env["LOCPATH"] == str(locpath.resolve())
    assert "LANGUAGE" not in env
    assert "DISPLAY" not in env and "DBUS_SESSION_BUS_ADDRESS" not in env
    assert env["WAYLAND_DISPLAY"] != "wayland-0"
    assert not os.path.exists(env["WAYLAND_DISPLAY"])
    assert env["GSETTINGS_BACKEND"] == "memory"
    assert env["HOME"].startswith(str(tmp_path))
    assert dict(os.environ) == before


def test_without_a_locale_the_callers_is_inherited(orca, tmp_path, live_desktop):
    env = orca.isolated_env(tmp_path / "env")
    assert env["LANG"] == "en_US.UTF-8"
    assert "LOCPATH" not in env and "LC_ALL" not in env


def test_chrome_gets_the_language_part(orca, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(orca.subprocess, "Popen", lambda cmd, **k: seen.append(cmd))
    monkeypatch.setattr(orca.rp, "free_port", lambda: 1)
    monkeypatch.setattr(orca.rp, "wait_http", lambda *a: None)
    orca.start_chrome("chrome", tmp_path, "about:blank", "de_DE.UTF-8")
    orca.start_chrome("chrome", tmp_path, "about:blank")
    assert "--lang=de" in seen[0]
    assert not any(arg.startswith("--lang") for arg in seen[1])


def test_a_missing_locale_fails_fast(orca, locpath, tmp_path):
    with pytest.raises(ValueError, match="needs --locale"):
        orca.isolated_env(tmp_path / "e1", None, locpath)
    with pytest.raises(ValueError, match="not a directory"):
        orca.isolated_env(tmp_path / "e2", "de_DE.UTF-8", tmp_path / "nope")
    with pytest.raises(ValueError, match="not in"):
        orca.isolated_env(tmp_path / "e3", "fr_FR.UTF-8", locpath)


def test_main_exits_2_on_a_missing_locale(orca, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(orca.shutil, "which", lambda t: "/bin/" + t)
    args = ["--site", str(tmp_path), "--out", str(tmp_path / "out"), "--locpath", str(tmp_path)]
    assert orca.main(args) == 2
    assert "needs --locale" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
