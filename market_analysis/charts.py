"""
charts.py
Creates the PNG charts recommended in the guide:
  1. TAM -> SAM -> SOM on one linear scale
  2. Market growth scenarios (conservative / base / aggressive)
  3. Our revenue forecast (ARR by year, customers under each bar)
  4. Where growth comes from (waterfall)
  5. Sensitivity (tornado)
  6. Bass curve vs our plan
  7. Competitor context (only if competitors were supplied)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import matplotlib

matplotlib.use("Agg")  # no GUI needed (works on servers / FastAPI)
import matplotlib.pyplot as plt  # noqa: E402

BLUE = "#2563eb"
GREY = "#c4bfb3"
DARK = "#444444"


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _fmt(value: float) -> str:
    return f"Rs {value:,.0f} cr" if value >= 100 else f"Rs {value:,.1f} cr"


def chart_tam_sam_som(res: Dict, out_dir: Path) -> Path:
    tam = res["market_size"]["tam_bottom_up_cr"]
    sam = res["sam"]["sam_cr"]
    som = res["som"]["arr_cr"][-1]
    labels = ["SOM (year %d ARR)" % res["som"]["years"][-1], "SAM (%d)" % res["years"][0], "TAM (%d)" % res["years"][0]]
    values = [som, sam, tam]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.barh(labels, values, color=[GREY, BLUE, GREY])
    notes = [f"{_fmt(som)}  ({som / sam:.1%} of SAM)", f"{_fmt(sam)}  ({sam / tam:.1%} of TAM)", _fmt(tam)]
    for y, (v, note) in enumerate(zip(values, notes)):
        ax.text(v + tam * 0.01, y, note, va="center", fontsize=9, color=DARK)
    ax.set_xlim(0, tam * 1.35)
    ax.set_title("Our serviceable market is a small slice of the total (bottom-up, one scale)")
    ax.set_xlabel("Rs crore per year")
    return _save(fig, out_dir, "01_tam_sam_som.png")


def chart_scenarios(res: Dict, out_dir: Path) -> Path:
    years = res["years"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name, data in res["scenarios"].items():
        is_base = name == "base"
        ax.plot(years, data["series_cr"], color=BLUE if is_base else GREY,
                linewidth=3 if is_base else 2, linestyle="-" if is_base else "--",
                marker="o" if is_base else None,
                label=f"{name.title()} ({data['growth']:.0%}/yr) -> {_fmt(data['sam_end_cr'])}")
    ax.set_title("SAM growth scenarios")
    ax.set_ylabel("Rs crore per year")
    ax.set_xticks(years)
    ax.legend()
    ax.grid(alpha=0.3)
    return _save(fig, out_dir, "02_sam_scenarios.png")


def chart_som(res: Dict, out_dir: Path) -> Path:
    som = res["som"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    colors = [GREY] * (len(som["years"]) - 1) + [BLUE]
    bars = ax.bar(range(len(som["years"])), som["arr_cr"], color=colors)
    ax.set_xticks(range(len(som["years"])))
    ax.set_xticklabels([f"{y}\n{c:,} customers" for y, c in zip(som["years"], som["customers"])])
    for bar, value in zip(bars, som["arr_cr"]):
        ax.text(bar.get_x() + bar.get_width() / 2, value, _fmt(value), ha="center", va="bottom", fontsize=9)
    ax.set_title(f"Planned ARR reaches {_fmt(som['arr_cr'][-1])} by year {len(som['years'])} "
                 f"({som['arr_cagr_year1_to_end']:.0%} CAGR from year 1)")
    ax.set_ylabel("ARR, Rs crore")
    return _save(fig, out_dir, "03_som_arr.png")


def chart_waterfall(res: Dict, out_dir: Path) -> Path:
    w = res["drivers"]["waterfall"]
    labels = ["Start", "More\nadvertisers", "More AI\nadoption", "Higher\nprice", "End"]
    deltas = [w["start"], w["more_advertisers"], w["more_ai_adoption"], w["higher_price"], w["end"]]
    bottoms = [0, w["start"], w["start"] + w["more_advertisers"],
               w["start"] + w["more_advertisers"] + w["more_ai_adoption"], 0]
    colors = [GREY, BLUE, BLUE, BLUE, GREY]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(labels, deltas, bottom=bottoms, color=colors)
    for x, (d, b) in enumerate(zip(deltas, bottoms)):
        ax.text(x, b + d, _fmt(d), ha="center", va="bottom", fontsize=9)
    ax.set_title("Where growth comes from (driver-based forecast, AI-tool-using market)")
    ax.set_ylabel("Rs crore per year")
    return _save(fig, out_dir, "04_growth_waterfall.png")


def chart_tornado(res: Dict, out_dir: Path) -> Path:
    s = res["sensitivity"]
    items = list(reversed(s["items"]))  # biggest swing at top
    base = s["base_cr"]
    fig, ax = plt.subplots(figsize=(9, 4))
    for y, item in enumerate(items):
        ax.barh(y, item["low_cr"] - base, left=base, color=GREY)
        ax.barh(y, item["high_cr"] - base, left=base, color=BLUE)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([item["input"] for item in items])
    ax.axvline(base, color=DARK, linewidth=1)
    ax.set_title(f"Sensitivity of base-case SAM {res['years'][-1]} to +/-{s['swing']:.0%} change in each input")
    ax.set_xlabel("Rs crore per year")
    return _save(fig, out_dir, "05_sensitivity_tornado.png")


def chart_bass(res: Dict, out_dir: Path) -> Path:
    bass = res["bass"]["rows"]
    som = res["som"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(som["years"], som["customers"], color=BLUE, marker="o", linewidth=3, label="Our sales plan (active customers)")
    ax.plot([r["year"] for r in bass], [r["cumulative_adopters"] for r in bass], color=GREY,
            marker="o", linestyle="--", label="Bass curve (cumulative adopters, analogue p and q)")
    ax.set_title("Sales plan vs Bass adoption curve")
    ax.set_ylabel("Customers")
    ax.set_xticks(som["years"])
    ax.legend()
    ax.grid(alpha=0.3)
    return _save(fig, out_dir, "06_bass_vs_plan.png")


def chart_competitors(res: Dict, out_dir: Path):
    rows = [r for r in res["competitors"] if not r["name"].startswith("_")]
    if not rows:
        return None
    rows = list(reversed(rows))
    fig, ax = plt.subplots(figsize=(9, 0.6 * len(rows) + 2))
    colors = [BLUE if r["name"].startswith("Us") else GREY for r in rows]
    ax.barh([r["name"] for r in rows], [r["revenue_cr"] for r in rows], color=colors)
    for y, r in enumerate(rows):
        ax.text(r["revenue_cr"], y, " " + _fmt(r["revenue_cr"]), va="center", fontsize=9)
    ax.set_title("Competitor revenue vs our plan (same scale)")
    ax.set_xlabel("Rs crore per year")
    return _save(fig, out_dir, "07_competitors.png")


def make_all_charts(res: Dict, out_dir) -> Dict[str, Path]:
    out_dir = Path(out_dir)
    paths = {
        "tam_sam_som": chart_tam_sam_som(res, out_dir),
        "scenarios": chart_scenarios(res, out_dir),
        "som": chart_som(res, out_dir),
        "waterfall": chart_waterfall(res, out_dir),
        "tornado": chart_tornado(res, out_dir),
        "bass": chart_bass(res, out_dir),
    }
    competitors = chart_competitors(res, out_dir)
    if competitors:
        paths["competitors"] = competitors
    return paths
