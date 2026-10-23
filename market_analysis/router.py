"""
router.py
FastAPI endpoints for the market growth analysis (with caching).

To add this to an existing FastAPI app, put these two lines in your main file:

    from market_analysis.router import router as market_router
    app.include_router(market_router)

Endpoints:
    GET    /market/analysis?refresh=false   run with default inputs (cached)
    POST   /market/analysis                 run with your inputs / competitor revenues (cached)
    GET    /market/charts/{name}?key=...    chart PNG (latest run if key is omitted)
    GET    /market/report/excel?key=...     Excel workbook
    GET    /market/report/summary?key=...   Markdown summary
    GET    /market/cache                    cache statistics
    DELETE /market/cache                    clear the cache
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .cache import RunCache, is_valid_key
from .config import build_inputs
from .pipeline import run_all

router = APIRouter(prefix="/market", tags=["market-analysis"])

OUTPUT_DIR = Path("market_output")

CHART_FILES = {
    "tam_sam_som": "01_tam_sam_som.png",
    "scenarios": "02_sam_scenarios.png",
    "som": "03_som_arr.png",
    "waterfall": "04_growth_waterfall.png",
    "tornado": "05_sensitivity_tornado.png",
    "bass": "06_bass_vs_plan.png",
    "competitors": "07_competitors.png",
}


class AnalysisRequest(BaseModel):
    # Any field from MarketInputs, e.g. {"pct_advertising_online": 0.03, "price_per_customer_per_year": 72000}
    inputs: Dict[str, Any] = Field(default_factory=dict)
    # Optional: {"CompetitorA": 120.0}  (annual revenue in Rs crore, from your competitor analysis)
    competitors: Optional[Dict[str, float]] = None
    # false = ignore the cached copy and recalculate (refresh)
    use_cache: bool = True


def _execute(inputs_dict: Dict[str, Any], competitors: Optional[Dict[str, float]], use_cache: bool) -> Dict[str, Any]:
    try:
        inputs = build_inputs(inputs_dict)
        output = run_all(inputs, competitors, OUTPUT_DIR, use_cache=use_cache)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    key = output["key"]
    return {
        "summary": output["result"]["summary"],
        "result": output["result"],
        "cache": output["cache"],
        "chart_urls": {name: f"/market/charts/{name}?key={key}" for name in output["files"]["charts"]},
        "excel_url": f"/market/report/excel?key={key}",
        "summary_url": f"/market/report/summary?key={key}",
    }


def _run_dir(key: Optional[str]) -> Path:
    cache = RunCache(OUTPUT_DIR)
    if key is None:
        key = cache.latest_key()
        if key is None:
            raise HTTPException(status_code=404, detail="Nothing generated yet. Call /market/analysis first.")
    if not is_valid_key(key):
        raise HTTPException(status_code=422, detail="Invalid key")
    return cache.run_dir(key)


@router.get("/analysis")
def analysis_default(refresh: bool = False):
    return _execute({}, None, use_cache=not refresh)


@router.post("/analysis")
def analysis_custom(body: AnalysisRequest):
    return _execute(body.inputs, body.competitors, use_cache=body.use_cache)


@router.get("/charts/{name}")
def get_chart(name: str, key: Optional[str] = None):
    filename = CHART_FILES.get(name)
    if filename is None:
        raise HTTPException(status_code=404, detail=f"Unknown chart. Choose from {sorted(CHART_FILES)}")
    path = _run_dir(key) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Chart not found for this run.")
    return FileResponse(path, media_type="image/png")


@router.get("/report/excel")
def get_excel(key: Optional[str] = None):
    path = _run_dir(key) / "market_analysis.xlsx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found for this run.")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="market_analysis.xlsx",
    )


@router.get("/report/summary")
def get_summary(key: Optional[str] = None):
    path = _run_dir(key) / "market_summary.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Summary not found for this run.")
    return FileResponse(path, media_type="text/markdown", filename="market_summary.md")


@router.get("/cache")
def cache_stats():
    return RunCache(OUTPUT_DIR).stats()


@router.delete("/cache")
def cache_clear():
    return {"cleared_entries": RunCache(OUTPUT_DIR).clear()}
