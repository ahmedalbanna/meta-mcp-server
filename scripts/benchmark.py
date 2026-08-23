#!/usr/bin/env python3
"""Benchmark: p95 for list_* and throttle — Phase 6.3.

Measures mocked tool latencies offline (no network). Targets:
- throttle p95 <200ms
- list_* p95 <400ms
- pytest --cov ensures coverage
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
from unittest import mock

from tests.conftest import Recorder, register_all


def percentile(data, p=95):
    if not data:
        return 0
    data = sorted(data)
    k = (len(data) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[int(k)]
    d0 = data[f] * (c - k)
    d1 = data[c] * (k - f)
    return d0 + d1


def bench_tool(recorder, tool_name, samples=50, **kwargs):
    fn = recorder.tools[tool_name]
    times = []
    for _ in range(samples):
        t0 = time.perf_counter()
        fn(**kwargs)
        times.append((time.perf_counter() - t0) * 1000)  # ms
    times.sort()
    avg = sum(times) / len(times)
    p95 = percentile(times, 95)
    p50 = percentile(times, 50)
    return {"avg": avg, "p50": p50, "p95": p95, "min": min(times), "max": max(times)}


def main() -> int:
    print("Benchmark — Phase 6.3 (offline, mocked SDK)")
    print("=" * 60)
    # Mock SDK
    with (
        mock.patch.multiple("facebook_business.api.FacebookAdsApi", init=mock.DEFAULT, get_default_api=mock.DEFAULT),
        mock.patch("src.helpers.api_call", return_value={"data": [], "paging": {}}),
        mock.patch("src.helpers.page_api_call", return_value={"data": []}),
        mock.patch("src.helpers.get_page_api"),
        mock.patch("src.instagram.requests"),
        mock.patch("facebook_business.adobjects.adaccount.AdAccount"),
        mock.patch("facebook_business.adobjects.campaign.Campaign"),
        mock.patch("facebook_business.adobjects.adset.AdSet"),
        mock.patch("facebook_business.adobjects.ad.Ad"),
        mock.patch("facebook_business.adobjects.customaudience.CustomAudience"),
    ):
        recorder = Recorder()
        register_all(recorder)

        # Benchmark list_* (target p95 <400ms)
        list_tools = [t for t in recorder.tools if t.startswith("list_")]
        print(f"\nlist_* tools ({len(list_tools)}):")
        for tool in sorted(list_tools)[:6]:
            try:
                res = bench_tool(recorder, tool, samples=30, limit=25)
                status = "✓" if res["p95"] < 400 else "✗"
                print(
                    f"  {status} {tool:30} avg {res['avg']:.1f}ms p50 {res['p50']:.1f} p95 {res['p95']:.1f} max {res['max']:.1f}"
                )
            except Exception as e:
                print(f"  ! {tool} error: {e}")

        # Benchmark throttle concurrent
        print("\nThrottle concurrent (target p95 <200ms for acquire/release):")
        import threading

        from src.throttle import MAX_CONCURRENT, concurrent_count

        times = []

        def work():
            from src.throttle import concurrency_limit

            @concurrency_limit()
            def dummy():
                time.sleep(0.005)
                return 1

            t0 = time.perf_counter()
            dummy()
            times.append((time.perf_counter() - t0) * 1000)

        threads = [threading.Thread(target=work) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if times:
            avg = sum(times) / len(times)
            p95 = percentile(times, 95)
            status = "✓" if p95 < 200 else "✗"
            print(
                f"  {status} throttle avg {avg:.1f}ms p95 {p95:.1f} max {max(times):.1f} (MAX_CONCURRENT={MAX_CONCURRENT}, final={concurrent_count()})"
            )

        # Cached insights benchmark (Phase 6.1) — second call should be faster
        print("\nCached insights (Phase 6.1) — get_account_insights cached 60s:")
        try:
            # First call (miss)
            t0 = time.perf_counter()
            recorder.tools["get_account_insights"](date_preset="last_30d")
            t1 = (time.perf_counter() - t0) * 1000
            # Second call (hit)
            t0 = time.perf_counter()
            recorder.tools["get_account_insights"](date_preset="last_30d")
            t2 = (time.perf_counter() - t0) * 1000
            print(f"  first {t1:.1f}ms, second {t2:.1f}ms (cached {'✓' if t2 < t1 else '≈'})")
        except Exception as e:
            print(f"  ! cached insights error: {e}")

        print("\nDone — run `pytest --cov=src --cov-report=term-missing` for coverage")
        print("and `k6 run scripts/k6_load.js` for load (20 VUs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
