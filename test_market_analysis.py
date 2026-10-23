"""
test_market_analysis.py
1. Checks that the code reproduces the numbers in the "Market Growth Calculation" PDF.
2. Checks that the cache works (hit, miss on changed inputs, expiry, refresh, clear).
Run:  python test_market_analysis.py      (or:  pytest -q)
"""
import tempfile
import time

from market_analysis.cache import RunCache
from market_analysis.calculations import cagr, run_analysis, years_to_double
from market_analysis.config import build_inputs
from market_analysis.pipeline import run_all


def approx(a, b, tol=0.005):
    return abs(a - b) <= tol * abs(b)


def test_pdf_numbers():
    res = run_analysis(build_inputs())
    ms = res["market_size"]

    assert approx(ms["tam_top_down_cr"], 8595)
    assert approx(ms["tam_bottom_up_cr"], 10608)
    assert ms["credible"] is True
    assert approx(ms["msme_ad_spend_yoy"], 0.20, 0.01)

    assert approx(res["sam"]["sam_cr"], 3182)
    assert approx(res["scenarios"]["conservative"]["sam_end_cr"], 6400)
    assert approx(res["scenarios"]["base"]["sam_end_cr"], 7918)
    assert approx(res["scenarios"]["aggressive"]["sam_end_cr"], 9711)

    assert approx(res["som"]["arr_cr"][-1], 51)
    assert approx(res["som"]["arr_cr"][0], 1.8)
    assert approx(res["som"]["arr_cagr_year1_to_end"], 1.31, 0.01)
    assert approx(res["som"]["share_of_sam_businesses"], 0.016, 0.02)
    assert approx(res["som"]["share_of_base_sam_revenue"], 0.0064, 0.03)

    assert 0.30 < res["churn"]["annual_churn"] < 0.33
    assert approx(years_to_double(0.20), 3.6)
    assert approx(cagr(924.1, 2057.7, 5), 0.174, 0.01)


def test_cache():
    with tempfile.TemporaryDirectory() as tmp:
        first = run_all(out_dir=tmp)
        assert first["cache"]["hit"] is False

        second = run_all(out_dir=tmp)
        assert second["cache"]["hit"] is True
        assert second["key"] == first["key"]
        assert second["result"]["summary"] == first["result"]["summary"]

        # changed input -> different key -> miss
        changed = run_all(build_inputs({"price_per_customer_per_year": 72000}), out_dir=tmp)
        assert changed["cache"]["hit"] is False
        assert changed["key"] != first["key"]

        # refresh ignores the cached copy
        refreshed = run_all(out_dir=tmp, use_cache=False)
        assert refreshed["cache"]["hit"] is False

        # expiry
        time.sleep(0.05)
        expired = run_all(out_dir=tmp, ttl_seconds=0.01)
        assert expired["cache"]["hit"] is False

        # stats and clear
        cache = RunCache(tmp)
        stats = cache.stats()
        assert stats["entry_count"] == 2
        assert stats["hits"] >= 1 and stats["misses"] >= 3
        assert cache.clear() == 2
        assert cache.stats()["entry_count"] == 0


if __name__ == "__main__":
    test_pdf_numbers()
    print("PDF number checks passed.")
    test_cache()
    print("Cache checks passed.")
    print("All checks passed.")
