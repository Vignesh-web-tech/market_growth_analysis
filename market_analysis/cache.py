"""
cache.py
Disk cache for analysis runs.

How it works
  - Every run is identified by a key = SHA-256 of (cache version + all inputs + competitors).
  - Same inputs  -> same key -> results (JSON, charts, Excel, summary) are loaded from disk
    instead of being recalculated.
  - Any changed input -> new key -> fresh calculation, stored as a new cache entry.
  - Entries expire after a TTL (default 24 hours). TTL of 0 means "never expires".

Folder layout (inside the output folder, default market_output/):
    runs/<key>/result.json, meta.json, *.png, market_analysis.xlsx, market_summary.md
    latest.txt        key of the most recent run (used by the chart/report download endpoints)
    stats.json        hit / miss counters

Change the TTL with the environment variable MARKET_CACHE_TTL_SECONDS or the ttl_seconds argument.
If you change the calculation code, bump CACHE_VERSION so old entries are ignored.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

CACHE_VERSION = "1"
DEFAULT_TTL_SECONDS = float(os.environ.get("MARKET_CACHE_TTL_SECONDS", 24 * 3600))
KEY_PATTERN = re.compile(r"^[0-9a-f]{16}$")


def make_key(inputs: Dict[str, Any], competitors: Optional[Dict[str, float]]) -> str:
    payload = json.dumps(
        {"v": CACHE_VERSION, "inputs": inputs, "competitors": competitors or {}},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def is_valid_key(key: str) -> bool:
    return bool(KEY_PATTERN.match(key or ""))


class RunCache:
    def __init__(self, out_dir: str | Path, ttl_seconds: Optional[float] = None):
        self.out_dir = Path(out_dir)
        self.root = self.out_dir / "runs"
        self.ttl = DEFAULT_TTL_SECONDS if ttl_seconds is None else float(ttl_seconds)
        self.stats_path = self.out_dir / "stats.json"
        self.latest_path = self.out_dir / "latest.txt"

    # ---- paths ---------------------------------------------------------
    def run_dir(self, key: str) -> Path:
        if not is_valid_key(key):
            raise ValueError("invalid cache key")
        return self.root / key

    # ---- read / write ----------------------------------------------------
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        run_dir = self.run_dir(key)
        meta_path = run_dir / "meta.json"
        result_path = run_dir / "result.json"
        if not (meta_path.exists() and result_path.exists()):
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            age = time.time() - meta["created_at"]
            if self.ttl > 0 and age > self.ttl:
                return None  # expired
            files = self._absolute_files(run_dir, meta["files"])
            if not all(Path(p).exists() for p in self._flatten(files)):
                return None  # some output file was deleted -> recalculate
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (ValueError, KeyError, OSError):
            return None  # corrupt entry -> recalculate
        return {"result": result, "files": files, "age_seconds": age}

    def put(self, key: str, result: Dict[str, Any], files: Dict[str, Any]) -> None:
        run_dir = self.run_dir(key)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
        meta = {"created_at": time.time(), "key": key, "files": files}
        (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    # ---- latest run pointer ----------------------------------------------
    def set_latest(self, key: str) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path.write_text(key, encoding="utf-8")

    def latest_key(self) -> Optional[str]:
        if not self.latest_path.exists():
            return None
        key = self.latest_path.read_text(encoding="utf-8").strip()
        return key if is_valid_key(key) else None

    # ---- stats ---------------------------------------------------------------
    def record(self, hit: bool) -> None:
        stats = self._read_stats()
        stats["hits" if hit else "misses"] += 1
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.stats_path.write_text(json.dumps(stats), encoding="utf-8")

    def stats(self) -> Dict[str, Any]:
        counters = self._read_stats()
        entries = []
        total_bytes = 0
        if self.root.exists():
            for entry in sorted(self.root.iterdir()):
                meta_path = entry / "meta.json"
                if not meta_path.exists():
                    continue
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                total_bytes += size
                try:
                    created = json.loads(meta_path.read_text(encoding="utf-8"))["created_at"]
                    age = time.time() - created
                except (ValueError, KeyError, OSError):
                    age = -1
                entries.append({"key": entry.name, "age_seconds": round(age, 1),
                                "expired": bool(self.ttl > 0 and age > self.ttl),
                                "size_kb": round(size / 1024, 1)})
        lookups = counters["hits"] + counters["misses"]
        return {
            "entries": entries,
            "entry_count": len(entries),
            "total_size_kb": round(total_bytes / 1024, 1),
            "ttl_seconds": self.ttl,
            "hits": counters["hits"],
            "misses": counters["misses"],
            "hit_rate": round(counters["hits"] / lookups, 3) if lookups else None,
        }

    # ---- maintenance -----------------------------------------------------------
    def prune_expired(self) -> int:
        removed = 0
        for item in self.stats()["entries"]:
            if item["expired"]:
                shutil.rmtree(self.root / item["key"], ignore_errors=True)
                removed += 1
        return removed

    def clear(self) -> int:
        count = self.stats()["entry_count"]
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
        for path in (self.stats_path, self.latest_path):
            if path.exists():
                path.unlink()
        return count

    # ---- helpers ---------------------------------------------------------------
    def _read_stats(self) -> Dict[str, int]:
        try:
            data = json.loads(self.stats_path.read_text(encoding="utf-8"))
            return {"hits": int(data.get("hits", 0)), "misses": int(data.get("misses", 0))}
        except (ValueError, OSError):
            return {"hits": 0, "misses": 0}

    @staticmethod
    def _absolute_files(run_dir: Path, files: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "charts": {name: str(run_dir / fn) for name, fn in files["charts"].items()},
            "excel": str(run_dir / files["excel"]),
            "markdown": str(run_dir / files["markdown"]),
        }

    @staticmethod
    def _flatten(files: Dict[str, Any]):
        yield from files["charts"].values()
        yield files["excel"]
        yield files["markdown"]
