from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Iterable

from dateutil import parser
from zoneinfo import ZoneInfo

from config import TZ_NAME

TZ = ZoneInfo(TZ_NAME)


def ensure_dirs() -> None:
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/debug", exist_ok=True)


def now_local() -> datetime:
    return datetime.now(tz=TZ)


def parse_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parser.parse(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def iso(dt: str | datetime) -> str:
    return parse_time(dt).isoformat(timespec="seconds")


def write_json(path: str, data: Any) -> None:
    ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)


def read_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except (TypeError, ValueError):
        return default


def dedupe_sorted(rows: Iterable[dict[str, Any]], time_key: str = "timestamp") -> list[dict[str, Any]]:
    by_ts: dict[str, dict[str, Any]] = {}
    priority = {"epa_zip": 4, "epa_png": 3, "estimated": 2, "forecast": 1}
    for row in rows:
        ts = iso(row[time_key])
        r = dict(row)
        r[time_key] = ts
        existing = by_ts.get(ts)
        if existing is None or priority.get(r.get("source", ""), 0) >= priority.get(existing.get("source", ""), 0):
            by_ts[ts] = r
    return [by_ts[k] for k in sorted(by_ts)]


def nearest_row(rows: list[dict[str, Any]], target: datetime, key: str = "timestamp", tolerance_minutes: float = 60) -> dict[str, Any] | None:
    best = None
    best_delta = None
    for row in rows:
        dt = parse_time(row[key])
        delta = abs((dt - target).total_seconds()) / 60
        if delta <= tolerance_minutes and (best_delta is None or delta < best_delta):
            best = row
            best_delta = delta
    return best


def sum_between(rows: list[dict[str, Any]], start: datetime, end: datetime, value_key: str = "rain_mm") -> float:
    total = 0.0
    for row in rows:
        dt = parse_time(row["timestamp"])
        if start < dt <= end:
            total += safe_float(row.get(value_key), 0.0) or 0.0
    return total


def local_date_label(dt: str | datetime) -> str:
    return parse_time(dt).strftime("%d/%m/%y")


def local_time_label(dt: str | datetime) -> str:
    return parse_time(dt).strftime("%H:%M")
