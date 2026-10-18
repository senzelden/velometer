"""M15: the deploy dry run end to end, against real Caddy (Docker) and wrangler (npx).
Slow: needs Docker or npx and the network (an image pull, an npm fetch)."""

import shutil
import subprocess

import pytest
import yaml

from tests.helpers import load_script
from tests.test_app_base import build_rich
from tests.test_export import _content
from velometer.app import export

pytestmark = pytest.mark.slow
dr = load_script("tools/deploy_dryrun.py")

SITE_VALUES = {
    "datalab": {
        "name": "Zählwerk Berlin Datalab",
        "url": "https://datalab.example.org/",
        "lang": "de",
    },
    "impressum_url": "https://datalab.example.org/impressum",
    "privacy_url": "https://datalab.example.org/datenschutz",
}


@pytest.fixture(scope="module")
def public_site(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("m15-dryrun")
    r = build_rich(tmp)
    db_path, cfg, maps, docs, plans = r
    (cfg / "site.yaml").write_text(
        yaml.safe_dump(SITE_VALUES, allow_unicode=True), encoding="utf-8"
    )
    out = tmp / "site"
    export.run_export(out, "/", db_path, cfg, maps, docs, _content(r), plans, False, public=True)
    return out


def _docker_ok() -> bool:
    return bool(shutil.which("docker")) and (
        subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    )


def test_caddy_serves_the_export_as_documented(public_site):
    if not _docker_ok():
        pytest.skip("Docker is not available")
    assert dr.main(["--site", str(public_site), "--server", "caddy"]) == 0


def test_wrangler_pages_dev_serves_the_export(public_site):
    if not shutil.which("npx"):
        pytest.skip("npx is not available")
    assert dr.main(["--site", str(public_site), "--server", "wrangler"]) == 0
