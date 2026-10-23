"""
pipeline.py
Runs the full market growth analysis with caching:
  same inputs -> loaded from the disk cache (fast)
  new inputs  -> calculated, charts + Excel + summary saved, stored in the cache
Used by the command-line script and the FastAPI router.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from .cache import RunCache, make_key
from .calculations import run_analysis
from .charts import make_all_charts
from .config import MarketInputs, build_inputs
from .report import to_excel, to_markdown


def run_all(
    inputs: Optional[MarketInputs] = None,
    competitors: Optional[Dict[str, float]] = None,
    out_dir: str | Path = "market_output",
    use_cache: bool = True,
    ttl_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    use_cache=False -> ignore any cached copy, recalculate, and overwrite the cache entry (a "refresh").
    ttl_seconds     -> cache lifetime; None = default (24h or MARKET_CACHE_TTL_SECONDS), 0 = never expires.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs = inputs or build_inputs()
    inputs.validate()

    cache = RunCache(out_dir, ttl_seconds)
    key = make_key(asdict(inputs), competitors)

    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            cache.record(hit=True)
            cache.set_latest(key)
            return {
                "result": hit["result"],
                "files": hit["files"],
                "key": key,
                "run_dir": str(cache.run_dir(key)),
                "cache": {"hit": True, "key": key, "age_seconds": round(hit["age_seconds"], 1)},
            }

    run_dir = cache.run_dir(key)
    run_dir.mkdir(parents=True, exist_ok=True)

    result = run_analysis(inputs, competitors)
    chart_paths = make_all_charts(result, run_dir)
    to_excel(result, run_dir / "market_analysis.xlsx")
    (run_dir / "market_summary.md").write_text(to_markdown(result), encoding="utf-8")

    files_relative = {
        "charts": {name: Path(p).name for name, p in chart_paths.items()},
        "excel": "market_analysis.xlsx",
        "markdown": "market_summary.md",
    }
    cache.put(key, result, files_relative)
    cache.record(hit=False)
    cache.set_latest(key)

    return {
        "result": result,
        "files": {
            "charts": {name: str(run_dir / fn) for name, fn in files_relative["charts"].items()},
            "excel": str(run_dir / files_relative["excel"]),
            "markdown": str(run_dir / files_relative["markdown"]),
        },
        "key": key,
        "run_dir": str(run_dir),
        "cache": {"hit": False, "key": key, "age_seconds": 0.0},
    }
