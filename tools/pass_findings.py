"""Hold render passes to 0 findings (ruling R64): the CD workflow's check after its passes.

Each argument is `OUT=HOST`: a `tools/render_pass.py --out` directory and the host its `--url`
named, which counts as the pages' own host for that pass. Every pass's `results.json` is read
again and judged with render_pass's own `failures`; one markdown table row per pass goes to
stdout (`| pass | visits | with findings |`, for the job summary). The exit status is 1 when any
pass has a finding, visited nothing or left no results file, or when no pass is named.

    uv run python tools/pass_findings.py OUT=HOST [OUT=HOST ...]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_pass as rp  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("name at least one pass as OUT=HOST", file=sys.stderr)
        return 1
    bad = 0
    print("| pass | visits | with findings |\n|---|---|---|")
    for arg in args:
        out, _, host = arg.rpartition("=")
        path = Path(out) / "results.json"
        try:
            results = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"| {Path(out).name} | no results ({e.__class__.__name__}) | - |")
            bad += 1
            continue
        rp.SITE_HOST = host or None
        found = [r for r in results if rp.failures(r)]
        print(f"| {Path(out).name} | {len(results)} | {len(found)} |")
        for r in found:
            print(f"  {r['url']} {r['theme']} {r['width']}: {'; '.join(rp.failures(r))}",
                  file=sys.stderr)  # fmt: skip
        bad += len(found) + (not results)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
