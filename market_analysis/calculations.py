"""
calculations.py
Pure calculation functions. No plotting, no files, no web code in here.
Every function takes a MarketInputs object and returns plain Python numbers /
lists / dicts, so results are JSON-safe and easy to test.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Optional

from .config import CRORE, MarketInputs


# --------------------------------------------------------------------------
# 1. Core formulas
# --------------------------------------------------------------------------
def cagr(start: float, end: float, years: int) -> float:
    """CAGR = (End / Start) ^ (1 / years) - 1"""
    if start <= 0 or years <= 0:
        raise ValueError("start must be > 0 and years must be > 0")
    return (end / start) ** (1 / years) - 1


def future_value(today: float, rate: float, years: int) -> float:
    """Future value = Today x (1 + rate) ^ years"""
    return today * (1 + rate) ** years


def yoy(previous: float, current: float) -> float:
    """YoY growth = (this year - last year) / last year"""
    return (current - previous) / previous


def years_to_double(rate: float) -> float:
    """Rule of 72: 72 / (rate in %)"""
    return 72 / (rate * 100)


# --------------------------------------------------------------------------
# 2. Market size: top-down, bottom-up, reconcile
# --------------------------------------------------------------------------
def top_down_tam_cr(i: MarketInputs) -> float:
    """Published MSME digital ad spend x share spent on tools/agency (INR crore)."""
    return i.msme_digital_ad_spend_cr * i.tool_share_of_ad_spend


def online_advertisers(i: MarketInputs) -> float:
    """Number of businesses that advertise online."""
    return i.total_businesses * i.pct_advertising_online


def bottom_up_tam_cr(i: MarketInputs) -> float:
    """Advertisers x price per customer per year (INR crore)."""
    return online_advertisers(i) * i.price_per_customer_per_year / CRORE


def market_size(i: MarketInputs) -> Dict:
    td = top_down_tam_cr(i)
    bu = bottom_up_tam_cr(i)
    gap = abs(bu - td) / td  # gap measured against the top-down number
    low, high = min(td, bu), max(td, bu)
    avg_budget_per_business = i.msme_digital_ad_spend_prev_cr * CRORE / online_advertisers(i)
    return {
        "online_advertisers": online_advertisers(i),
        "avg_ad_budget_per_business_rs": avg_budget_per_business,  # sanity check (~Rs 2 lakh)
        "tam_top_down_cr": td,
        "tam_bottom_up_cr": bu,
        "gap_pct": gap,
        "credible": gap <= i.tolerance,
        "tam_range_low_cr": low,
        "tam_range_high_cr": high,
        "tam_range_usd_bn": [low * CRORE / i.usd_inr / 1e9, high * CRORE / i.usd_inr / 1e9],
        "msme_ad_spend_yoy": yoy(i.msme_digital_ad_spend_prev_cr, i.msme_digital_ad_spend_cr),
    }


# --------------------------------------------------------------------------
# 3. SAM and scenarios
# --------------------------------------------------------------------------
def sam_businesses(i: MarketInputs) -> float:
    return online_advertisers(i) * i.sam_share


def sam_cr(i: MarketInputs) -> float:
    return sam_businesses(i) * i.price_per_customer_per_year / CRORE


def sam_scenarios(i: MarketInputs) -> Dict[str, Dict]:
    start = sam_cr(i)
    n = i.forecast_years
    rates = {
        "conservative": i.growth_conservative,
        "base": i.growth_base,
        "aggressive": i.growth_aggressive,
    }
    out = {}
    for name, rate in rates.items():
        series = [future_value(start, rate, t) for t in range(n + 1)]
        out[name] = {
            "growth": rate,
            "series_cr": series,
            "sam_end_cr": series[-1],
            "cagr": cagr(start, series[-1], n),
            "years_to_double": years_to_double(rate),
        }
    return out


# --------------------------------------------------------------------------
# 4. Driver-based forecast: advertisers x AI adoption x price
# --------------------------------------------------------------------------
def driver_forecast(i: MarketInputs) -> Dict:
    n = i.forecast_years
    rows: List[Dict] = []
    for t in range(n + 1):
        adv = online_advertisers(i) * (1 + i.advertiser_growth) ** t
        adoption = min(i.ai_adoption_start + i.ai_adoption_step * t, 1.0)
        price = i.price_per_customer_per_year * (1 + i.price_growth) ** t
        rows.append({
            "year": i.base_year + t,
            "advertisers": adv,
            "ai_adoption": adoption,
            "price_rs": price,
            "market_cr": adv * adoption * price / CRORE,
        })

    first, last = rows[0], rows[-1]
    # Waterfall: change one driver at a time, in this order
    start_cr = first["market_cr"]
    after_adv = last["advertisers"] * first["ai_adoption"] * first["price_rs"] / CRORE
    after_adoption = last["advertisers"] * last["ai_adoption"] * first["price_rs"] / CRORE
    end_cr = last["market_cr"]
    waterfall = {
        "start": start_cr,
        "more_advertisers": after_adv - start_cr,
        "more_ai_adoption": after_adoption - after_adv,
        "higher_price": end_cr - after_adoption,
        "end": end_cr,
    }
    return {"rows": rows, "waterfall": waterfall, "cagr": cagr(start_cr, end_cr, n)}


# --------------------------------------------------------------------------
# 5. SOM: our plan, churn stress test, Bass curve
# --------------------------------------------------------------------------
def plan_som(i: MarketInputs) -> Dict:
    n = i.forecast_years
    customers = list(i.planned_customers)
    arr_cr = [c * i.price_per_customer_per_year / CRORE for c in customers]
    sam_end_base = sam_scenarios(i)["base"]["sam_end_cr"]
    return {
        "years": [i.base_year + t for t in range(1, n + 1)],
        "customers": customers,
        "arr_cr": arr_cr,
        "arr_cagr_year1_to_end": cagr(arr_cr[0], arr_cr[-1], n - 1),
        "share_of_sam_businesses": customers[-1] / sam_businesses(i),
        "share_of_base_sam_revenue": arr_cr[-1] / sam_end_base,
    }


def churn_stress_test(i: MarketInputs) -> Dict:
    """How many customers must sales add each year to hit the plan, given churn?"""
    annual_churn = 1 - (1 - i.monthly_churn) ** 12
    rows = []
    previous = 0
    for year_offset, target in enumerate(i.planned_customers, start=1):
        churned = previous * annual_churn
        retained = previous - churned
        gross_adds_needed = max(target - retained, 0)
        rows.append({
            "year": i.base_year + year_offset,
            "opening_customers": previous,
            "customers_lost_to_churn": churned,
            "net_adds": target - previous,
            "gross_adds_needed": gross_adds_needed,
            "closing_customers": target,
        })
        previous = target
    return {"annual_churn": annual_churn, "rows": rows}


def bass_curve(i: MarketInputs) -> Dict:
    """
    Bass diffusion: new adopters in a year = (p + q * adopted/m) * (m - adopted)
    m = SAM businesses x ceiling share (customers we could EVER win).
    Use analogue p, q until you have 5+ periods of real data, then refit.
    """
    m = sam_businesses(i) * i.bass_ceiling_share
    adopted = 0.0
    rows = []
    for t in range(1, i.forecast_years + 1):
        new = (i.bass_p + i.bass_q * adopted / m) * (m - adopted)
        adopted += new
        rows.append({
            "year": i.base_year + t,
            "new_adopters": new,
            "cumulative_adopters": adopted,
            "arr_cr": adopted * i.price_per_customer_per_year / CRORE,
        })
    return {"market_potential_m": m, "p": i.bass_p, "q": i.bass_q, "rows": rows}


# --------------------------------------------------------------------------
# 6. Sensitivity (tornado chart data)
# --------------------------------------------------------------------------
def sensitivity(i: MarketInputs, swing: float = 0.20) -> Dict:
    """Which input moves the 2031 base-case SAM the most? Each input +/- 20% (relative)."""
    n = i.forecast_years

    def sam_end(pct, price, share, growth):
        return i.total_businesses * pct * share * price / CRORE * (1 + growth) ** n

    base_args = dict(
        pct=i.pct_advertising_online,
        price=i.price_per_customer_per_year,
        share=i.sam_share,
        growth=i.growth_base,
    )
    base_value = sam_end(**base_args)
    labels = {
        "pct": "% advertising online",
        "price": "Price per customer",
        "share": "SAM share of advertisers",
        "growth": "SAM growth rate",
    }
    items = []
    for key, label in labels.items():
        low_args, high_args = dict(base_args), dict(base_args)
        low_args[key] = base_args[key] * (1 - swing)
        high_args[key] = base_args[key] * (1 + swing)
        low, high = sam_end(**low_args), sam_end(**high_args)
        items.append({"input": label, "low_cr": low, "high_cr": high, "swing_cr": abs(high - low)})
    items.sort(key=lambda x: x["swing_cr"], reverse=True)
    return {"base_cr": base_value, "swing": swing, "items": items}


# --------------------------------------------------------------------------
# 7. Competitor context (connect to your competitor analysis project)
# --------------------------------------------------------------------------
def competitor_context(i: MarketInputs, competitors: Optional[Dict[str, float]]) -> List[Dict]:
    """
    competitors = {"Competitor name": annual revenue in INR crore}.
    Fill this from your competitor analysis output (Tracxn / Inc42 / company reports).
    """
    if not competitors:
        return []
    som = plan_som(i)
    rows = [{"name": k, "revenue_cr": float(v)} for k, v in competitors.items()]
    rows.append({"name": f"Us (plan {som['years'][-1]})", "revenue_cr": som["arr_cr"][-1]})
    rows.sort(key=lambda r: r["revenue_cr"], reverse=True)
    total = sum(r["revenue_cr"] for r in rows if not r["name"].startswith("Us"))
    for r in rows:
        r["share_of_base_sam_2026"] = r["revenue_cr"] / sam_cr(i)
    rows.append({"name": "_incumbents_total", "revenue_cr": total,
                 "share_of_base_sam_2026": total / sam_cr(i)})
    return rows


# --------------------------------------------------------------------------
# 8. Run everything
# --------------------------------------------------------------------------
def run_analysis(i: MarketInputs, competitors: Optional[Dict[str, float]] = None) -> Dict:
    i.validate()
    ms = market_size(i)
    scenarios = sam_scenarios(i)
    drivers = driver_forecast(i)
    som = plan_som(i)
    churn = churn_stress_test(i)
    bass = bass_curve(i)

    result = {
        "inputs": asdict(i),
        "years": [i.base_year + t for t in range(i.forecast_years + 1)],
        "market_size": ms,
        "sam": {
            "sam_businesses": sam_businesses(i),
            "sam_cr": sam_cr(i),
            "share_of_tam": sam_cr(i) / ms["tam_bottom_up_cr"],
        },
        "scenarios": scenarios,
        "drivers": drivers,
        "som": som,
        "churn": churn,
        "bass": bass,
        "sensitivity": sensitivity(i),
        "competitors": competitor_context(i, competitors),
    }
    result["summary"] = {
        "tam_range_cr": [ms["tam_range_low_cr"], ms["tam_range_high_cr"]],
        "sam_2026_cr": result["sam"]["sam_cr"],
        "sam_end_year": i.base_year + i.forecast_years,
        "sam_end_base_cr": scenarios["base"]["sam_end_cr"],
        "som_arr_end_cr": som["arr_cr"][-1],
        "som_arr_cagr": som["arr_cagr_year1_to_end"],
        "top_down_vs_bottom_up_credible": ms["credible"],
    }
    return result
