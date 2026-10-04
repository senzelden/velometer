import time

from velometer.memory import PeakRss


def test_peak_sees_an_allocation_inside_the_block():
    with PeakRss(interval_s=0.01) as before:
        pass
    with PeakRss(interval_s=0.01) as p:
        blob = bytearray(200 * 1024 * 1024)
        blob[::4096] = b"x" * len(blob[::4096])  # touch every page so it is resident
        time.sleep(0.1)  # the sampler thread only runs while the main thread releases the GIL
        del blob
    assert p.peak_mb >= 150
    assert p.peak_mb >= before.peak_mb + 150
