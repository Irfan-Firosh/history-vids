"""TokenBucket must gate ALL callers off one shared clock, not one floor per caller.

The bug this exists to prevent: giving each worker its own minimum interval. Eight workers each
honouring a 3-second floor independently issue 160 requests/minute against a 20 rpm limit — Agnes
429s immediately. One shared bucket must pace every acquisition, regardless of which thread (or how
many different worker threads) calls it.
"""

from __future__ import annotations

import threading
import time

from studio.rate_limit import TokenBucket


def test_bucket_is_shared_across_threads_not_per_thread():
    # The easy bug: each worker honours its own 3s floor, so 4 workers acquiring in parallel would
    # return near-instantly if the floor were per-thread. One shared bucket must gate them all.
    bucket = TokenBucket(rpm=60)  # 1/s
    started = time.monotonic()
    threads = [threading.Thread(target=bucket.acquire) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert time.monotonic() - started >= 2.9  # 4 acquisitions at 1/s ≥ 3s of spacing


def test_bucket_holds_configured_rate_under_concurrent_load():
    """Spawns many threads hammering ONE bucket simultaneously and measures the actual spacing —
    proves the limiter neither bursts past the configured rpm nor over-throttles (needlessly slower
    than the configured rate). Uses a high rpm so the whole test runs in ~1s, deterministically."""
    rpm = 1200  # 20/s → 0.05s interval; high rate keeps this test fast
    interval = 60.0 / rpm
    n = 20
    bucket = TokenBucket(rpm=rpm)

    started = time.monotonic()
    threads = [threading.Thread(target=bucket.acquire) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - started

    expected = (n - 1) * interval
    assert elapsed >= expected - 0.05  # rate not exceeded: real spacing, not a burst
    assert elapsed <= expected + 0.75  # not needlessly slower than the configured rate


def test_bucket_shared_rate_holds_with_multiple_acquisitions_per_worker():
    """Each of a handful of "worker" threads acquires several times in a row (closer to how a
    ThreadPoolExecutor worker would loop over several frames) — the total throughput must still
    match ONE shared rpm budget, not (rpm-per-worker × worker count)."""
    rpm = 1200
    interval = 60.0 / rpm
    n_workers, per_worker = 4, 5
    total = n_workers * per_worker
    bucket = TokenBucket(rpm=rpm)

    def worker() -> None:
        for _ in range(per_worker):
            bucket.acquire()

    started = time.monotonic()
    threads = [threading.Thread(target=worker) for _ in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.monotonic() - started

    expected = (total - 1) * interval
    # If each worker instead honoured its own floor independently (the bug this bucket prevents),
    # elapsed would be ~(per_worker - 1) * interval — n_workers times faster than asserted here.
    assert elapsed >= expected - 0.05
    assert elapsed <= expected + 0.75
