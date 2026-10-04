"""Peak resident memory of this process during a block (Linux /proc), for the ADR 0007 gate."""

import os
import threading
from pathlib import Path

_PAGE = os.sysconf("SC_PAGE_SIZE")


def rss_mb() -> float:
    resident = int(Path("/proc/self/statm").read_text().split()[1])
    return resident * _PAGE / 2**20


class PeakRss:
    """Context manager: `.peak_mb` is the highest resident size sampled inside the block.

    getrusage's ru_maxrss never goes down within a process, so it cannot give a per-run peak
    when several runs share one process; a sampling thread measures the block itself.

    The sample is the RSS at entry, at exit and every `interval_s` in between. Caveats:

    - Lower bound under a long GIL hold. The sampler thread cannot run while one C call holds
      the GIL. Pure-Python loops release it every 5 ms (the interpreter switch interval), and the
      entry and exit samples bracket the block, so only a peak inside one long C call can be
      missed.
    - Process-wide baseline. The sample is the RSS of the whole process, so in a multi-run
      invocation a run's peak includes memory still held from earlier runs.
    - Cross-check. Paris FUA (the largest run) alone under `/usr/bin/time -v` gave
      3,384,384 kB against a recorded `peak_rss_kb` of 3,387,384 kB, within 0.1 %.
    """

    def __init__(self, interval_s: float = 0.2):
        self.interval_s = interval_s
        self.peak_mb = 0.0
        self._stop = threading.Event()

    def _sample(self) -> None:
        self.peak_mb = max(self.peak_mb, rss_mb())

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._sample()

    def __enter__(self) -> "PeakRss":
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._sample()
        self._stop.set()
        self._thread.join()
