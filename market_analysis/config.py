"""
config.py
All inputs (assumptions) for the market growth analysis live here.
Change a value here (or pass it in a JSON file / API request) and every
number, chart and report updates. Never hard-code these numbers elsewhere.

Units used everywhere:
  - money in the results is in INR crore (1 crore = 10,000,000)
  - price and ARPU inputs are in plain rupees per customer per year
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

CRORE = 10_000_000
LAKH = 100_000


@dataclass
class MarketInputs:
    # ---- timeline -------------------------------------------------------
    base_year: int = 2026
    forecast_years: int = 5  # forecast to base_year + forecast_years (2031)

    # ---- published market data (top-down) -------------------------------
    # India MSME digital ad spend (Pitch Madison): Rs 35,814 cr (2025) -> Rs 42,976 cr (2026)
    msme_digital_ad_spend_prev_cr: float = 35_814.0
    msme_digital_ad_spend_cr: float = 42_976.0
    # Share of ad spend that goes to execution + follow-up tools/agencies (5-20%; 20% incl. follow-up)
    tool_share_of_ad_spend: float = 0.20

    # ---- bottom-up inputs -----------------------------------------------
    total_businesses: float = 8.84 * CRORE   # Udyam registrations (June 2026)
    pct_advertising_online: float = 0.02     # ASSUMPTION - validate with survey
    price_per_customer_per_year: float = 60_000.0  # ASSUMPTION - validate with pilots (Rs/yr)

    # ---- SAM filter -------------------------------------------------------
    sam_share: float = 0.30  # ASSUMPTION: our 5 verticals/languages/states = 30% of advertisers

    # ---- SAM growth scenarios (per year) ----------------------------------
    growth_conservative: float = 0.15
    growth_base: float = 0.20
    growth_aggressive: float = 0.25

    # ---- driver-based forecast ---------------------------------------------
    advertiser_growth: float = 0.10   # advertisers +10% / year
    ai_adoption_start: float = 0.10   # 10% of advertisers use AI ad/lead tools today
    ai_adoption_step: float = 0.05    # +5 percentage points per year
    price_growth: float = 0.05        # price +5% / year

    # ---- our plan (SOM) -------------------------------------------------------
    # Active customers at the END of each year (2027..2031)
    planned_customers: List[int] = field(default_factory=lambda: [300, 1200, 3000, 5500, 8500])
    monthly_churn: float = 0.03       # ASSUMPTION - replace with pilot cohort data

    # ---- Bass diffusion model ------------------------------------------------
    bass_p: float = 0.03              # innovation (own marketing/sales)
    bass_q: float = 0.38              # imitation (word of mouth)
    bass_ceiling_share: float = 0.03  # share of SAM businesses we could EVER win (market potential m)

    # ---- reporting / checks ----------------------------------------------------
    usd_inr: float = 85.0
    tolerance: float = 0.25           # top-down vs bottom-up must agree within 25%

    def validate(self) -> None:
        if self.forecast_years < 2:
            raise ValueError("forecast_years must be at least 2")
        if len(self.planned_customers) != self.forecast_years:
            raise ValueError(
                f"planned_customers needs exactly {self.forecast_years} values "
                f"(one per forecast year), got {len(self.planned_customers)}"
            )
        for name in (
            "tool_share_of_ad_spend",
            "pct_advertising_online",
            "sam_share",
            "monthly_churn",
            "bass_ceiling_share",
            "tolerance",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")
        if self.monthly_churn >= 1:
            raise ValueError("monthly_churn must be below 1")
        for name in ("price_per_customer_per_year", "total_businesses", "usd_inr",
                     "msme_digital_ad_spend_cr", "msme_digital_ad_spend_prev_cr"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")


def build_inputs(overrides: Optional[Dict[str, Any]] = None) -> MarketInputs:
    """Defaults + optional overrides (dict). Unknown keys raise ValueError."""
    base = MarketInputs()
    if overrides:
        valid = {f.name for f in fields(MarketInputs)}
        unknown = set(overrides) - valid
        if unknown:
            raise ValueError(f"Unknown input(s): {sorted(unknown)}. Valid inputs: {sorted(valid)}")
        data = asdict(base)
        data.update(overrides)
        base = MarketInputs(**data)
    base.validate()
    return base


def load_inputs_json(path: str | Path) -> MarketInputs:
    with open(path, "r", encoding="utf-8") as f:
        return build_inputs(json.load(f))


def save_default_inputs(path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(MarketInputs()), f, indent=2)
