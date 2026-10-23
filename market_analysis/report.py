"""
report.py
Writes the results to an Excel workbook and a short Markdown summary.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


def _crore(value: float) -> str:
    return f"Rs {value:,.0f} crore"


def to_markdown(res: Dict) -> str:
    ms = res["market_size"]
    sam = res["sam"]
    som = res["som"]
    sc = res["scenarios"]
    s = res["summary"]
    churn = res["churn"]
    last_year = res["years"][-1]
    usd_low, usd_high = ms["tam_range_usd_bn"]

    lines = [
        "# Market Growth Analysis - Summary",
        "",
        "## Market size (TAM)",
        f"- Top-down TAM: {_crore(ms['tam_top_down_cr'])}",
        f"- Bottom-up TAM: {_crore(ms['tam_bottom_up_cr'])}",
        f"- Gap between the two: {ms['gap_pct']:.1%} "
        f"({'within' if ms['credible'] else 'OUTSIDE'} the {res['inputs']['tolerance']:.0%} tolerance)",
        f"- TAM range: {_crore(ms['tam_range_low_cr'])} to {_crore(ms['tam_range_high_cr'])} "
        f"(about ${usd_low:.2f}-{usd_high:.2f} billion)",
        f"- MSME digital ad spend growth (YoY): {ms['msme_ad_spend_yoy']:.1%}",
        "",
        "## SAM",
        f"- SAM businesses: {sam['sam_businesses']:,.0f}",
        f"- SAM ({res['years'][0]}): {_crore(sam['sam_cr'])} ({sam['share_of_tam']:.0%} of bottom-up TAM)",
        "",
        f"## SAM scenarios to {last_year}",
    ]
    for name, d in sc.items():
        lines.append(f"- {name.title()} ({d['growth']:.0%}/yr): {_crore(d['sam_end_cr'])} (CAGR {d['cagr']:.1%})")

    lines += [
        "",
        "## SOM (our plan)",
        f"- Year-{len(som['years'])} customers: {som['customers'][-1]:,}",
        f"- Year-{len(som['years'])} ARR: {_crore(som['arr_cr'][-1])}",
        f"- ARR CAGR year 1 to year {len(som['years'])}: {som['arr_cagr_year1_to_end']:.0%}",
        f"- Share of SAM businesses: {som['share_of_sam_businesses']:.1%}",
        f"- Share of base-case {last_year} SAM revenue: {som['share_of_base_sam_revenue']:.1%}",
        "",
        "## Churn stress test",
        f"- Monthly churn {res['inputs']['monthly_churn']:.0%} = about {churn['annual_churn']:.0%} lost per year",
    ]
    for r in churn["rows"]:
        lines.append(
            f"- {r['year']}: need {r['gross_adds_needed']:,.0f} new customers "
            f"(net growth {r['net_adds']:,.0f}, lost to churn {r['customers_lost_to_churn']:,.0f})"
        )

    lines += [
        "",
        "## Assumptions to validate (survey + pilots)",
        f"- % of businesses advertising online: {res['inputs']['pct_advertising_online']:.1%}",
        f"- Price per customer per year: Rs {res['inputs']['price_per_customer_per_year']:,.0f}",
        f"- SAM share of advertisers: {res['inputs']['sam_share']:.0%}",
        f"- Monthly churn: {res['inputs']['monthly_churn']:.0%}",
        f"- Bass p / q: {res['inputs']['bass_p']} / {res['inputs']['bass_q']} (analogue values)",
    ]
    return "\n".join(lines) + "\n"


def to_excel(res: Dict, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    inputs_df = pd.DataFrame(
        [(k, ", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in res["inputs"].items()],
        columns=["input", "value"],
    )
    ms = res["market_size"]
    summary_df = pd.DataFrame(
        [
            ("Top-down TAM (Rs cr)", ms["tam_top_down_cr"]),
            ("Bottom-up TAM (Rs cr)", ms["tam_bottom_up_cr"]),
            ("Gap (vs top-down)", ms["gap_pct"]),
            ("Credible (within tolerance)", ms["credible"]),
            ("Online advertisers", ms["online_advertisers"]),
            ("SAM businesses", res["sam"]["sam_businesses"]),
            ("SAM (Rs cr)", res["sam"]["sam_cr"]),
            ("SAM share of TAM", res["sam"]["share_of_tam"]),
            ("SOM ARR final year (Rs cr)", res["som"]["arr_cr"][-1]),
            ("SOM ARR CAGR", res["som"]["arr_cagr_year1_to_end"]),
            ("SOM share of SAM businesses", res["som"]["share_of_sam_businesses"]),
            ("SOM share of base SAM revenue", res["som"]["share_of_base_sam_revenue"]),
        ],
        columns=["metric", "value"],
    )
    scenarios_df = pd.DataFrame({"year": res["years"]})
    for name, d in res["scenarios"].items():
        scenarios_df[f"{name}_sam_cr"] = d["series_cr"]

    som_df = pd.DataFrame({
        "year": res["som"]["years"],
        "customers": res["som"]["customers"],
        "arr_cr": res["som"]["arr_cr"],
    })
    churn_df = pd.DataFrame(res["churn"]["rows"])
    bass_df = pd.DataFrame(res["bass"]["rows"])
    drivers_df = pd.DataFrame(res["drivers"]["rows"])
    waterfall_df = pd.DataFrame(list(res["drivers"]["waterfall"].items()), columns=["step", "rs_cr"])
    sens_df = pd.DataFrame(res["sensitivity"]["items"])
    comp_df = pd.DataFrame(res["competitors"]) if res["competitors"] else pd.DataFrame(columns=["name", "revenue_cr"])

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        inputs_df.to_excel(writer, sheet_name="Inputs", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        scenarios_df.to_excel(writer, sheet_name="SAM_Scenarios", index=False)
        drivers_df.to_excel(writer, sheet_name="Driver_Forecast", index=False)
        waterfall_df.to_excel(writer, sheet_name="Waterfall", index=False)
        som_df.to_excel(writer, sheet_name="SOM_Plan", index=False)
        churn_df.to_excel(writer, sheet_name="Churn_Test", index=False)
        bass_df.to_excel(writer, sheet_name="Bass_Model", index=False)
        sens_df.to_excel(writer, sheet_name="Sensitivity", index=False)
        comp_df.to_excel(writer, sheet_name="Competitors", index=False)
    return path
