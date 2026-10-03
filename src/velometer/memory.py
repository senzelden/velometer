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
