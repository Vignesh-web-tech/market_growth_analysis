"""
run_market_analysis.py
Run the whole market growth analysis from the command line (with caching).

Examples (from the project folder):
    python run_market_analysis.py
    python run_market_analysis.py --refresh                 (ignore cache, recalculate)
    python run_market_analysis.py --cache-stats
    python run_market_analysis.py --clear-cache
    python run_market_analysis.py --write-default-inputs inputs.json
    python run_market_analysis.py --inputs inputs.json --competitors competitors.json

competitors.json format (annual revenue in Rs crore, from your competitor analysis):
    {"CompetitorA": 120.0, "CompetitorB": 45.5}
"""
import argparse
import json
import sys

from market_analysis.cache import RunCache
from market_analysis.config import load_inputs_json, save_default_inputs
from market_analysis.pipeline import run_all


def main() -> int:
    parser = argparse.ArgumentParser(description="Market growth analysis (TAM/SAM/SOM) with caching")
    parser.add_argument("--inputs", help="JSON file with input overrides")
    parser.add_argument("--competitors", help="JSON file: {name: revenue_in_rs_crore}")
    parser.add_argument("--out", default="market_output", help="output folder (default: market_output)")
    parser.add_argument("--refresh", action="store_true", help="ignore the cached copy and recalculate")
    parser.add_argument("--ttl", type=float, default=None,
                        help="cache lifetime in seconds (default 86400 = 24h, 0 = never expires)")
    parser.add_argument("--cache-stats", action="store_true", help="show cache statistics and exit")
    parser.add_argument("--clear-cache", action="store_true", help="delete all cached runs and exit")
    parser.add_argument("--write-default-inputs", metavar="FILE",
                        help="write all default inputs to FILE (edit it, then pass with --inputs) and exit")
    args = parser.parse_args()

    if args.write_default_inputs:
        save_default_inputs(args.write_default_inputs)
        print(f"Default inputs written to {args.write_default_inputs}")
        return 0

    if args.cache_stats:
        print(json.dumps(RunCache(args.out, args.ttl).stats(), indent=2))
        return 0

    if args.clear_cache:
        print(f"Cleared {RunCache(args.out, args.ttl).clear()} cached run(s).")
        return 0

    inputs = load_inputs_json(args.inputs) if args.inputs else None
    competitors = None
    if args.competitors:
        with open(args.competitors, "r", encoding="utf-8") as f:
            competitors = json.load(f)

    output = run_all(inputs, competitors, args.out, use_cache=not args.refresh, ttl_seconds=args.ttl)
    summary = output["result"]["summary"]
    cache = output["cache"]

    print("\n=== MARKET GROWTH ANALYSIS ===")
    if cache["hit"]:
        print(f"Cache                    : HIT (loaded from disk, {cache['age_seconds']}s old)")
    else:
        print("Cache                    : MISS (calculated fresh and stored)")
    low, high = summary["tam_range_cr"]
    print(f"TAM range                : Rs {low:,.0f} - {high:,.0f} crore")
    print(f"Top-down vs bottom-up OK : {summary['top_down_vs_bottom_up_credible']}")
    print(f"SAM (base year)          : Rs {summary['sam_2026_cr']:,.0f} crore")
    print(f"SAM {summary['sam_end_year']} (base case)   : Rs {summary['sam_end_base_cr']:,.0f} crore")
    print(f"SOM ARR final year       : Rs {summary['som_arr_end_cr']:,.1f} crore "
          f"(CAGR {summary['som_arr_cagr']:.0%})")
    print(f"\nResults folder: {output['run_dir']}")
    for name, path in output["files"]["charts"].items():
        print(f"  chart {name:12s}: {path}")
    print(f"  excel             : {output['files']['excel']}")
    print(f"  summary           : {output['files']['markdown']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
