from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any

import numpy as np

from config import FORECAST_CONFIG
from utils import iso, now_local, parse_time, safe_float, sum_between, write_json


def robust_rate_mm_hr(rows: list[dict[str, Any]], window_hours: float = 3.0) -> float:
    if len(rows) < 2:
        return 0.0
    latest_time = parse_time(rows[-1]["timestamp"])
    recent = [r for r in rows if (latest_time - parse_time(r["timestamp"])).total_seconds() <= window_hours * 3600]
    if len(recent) < 2:
        recent = rows[-min(8, len(rows)):]
    xs = np.array([(parse_time(r["timestamp"]) - parse_time(recent[0]["timestamp"])).total_seconds() / 3600 for r in recent])
    ys = np.array([safe_float(r.get("level_m"), 0.0) or 0.0 for r in recent])
    if len(xs) < 2 or float(xs[-1] - xs[0]) == 0:
        return 0.0
    slope_m_hr = float(np.polyfit(xs, ys, 1)[0])
    return slope_m_hr * 1000.0


def trend_label(rate_mm_hr: float) -> str:
    threshold = FORECAST_CONFIG.stable_threshold_mm_hr
    if rate_mm_hr > threshold:
        return "Rising"
    if rate_mm_hr < -threshold:
        return "Falling"
    return "Stable"


def confidence_for(latest_age_hours: float, source: str, extraction_confidence: str | None = None) -> str:
    if source == "epa_png" and extraction_confidence == "low":
        return "Low"
    if latest_age_hours >= FORECAST_CONFIG.confidence_stale_hours_low:
        return "Low"
    if latest_age_hours >= FORECAST_CONFIG.confidence_stale_hours_medium or source == "epa_png":
        return "Medium"
    return "High"


def estimate_current(rows: list[dict[str, Any]], rate_mm_hr: float) -> dict[str, Any] | None:
    if not rows:
        return None
    latest = rows[-1]
    now = now_local()
    latest_time = parse_time(latest["timestamp"])
    age_hours = max(0.0, (now - latest_time).total_seconds() / 3600)
    capped_age = min(age_hours, FORECAST_CONFIG.max_stale_extrapolation_hours)
    level = (safe_float(latest.get("level_m"), 0.0) or 0.0) + (rate_mm_hr / 1000.0) * capped_age
    if latest.get("source") == "epa_png" and age_hours <= 0.5:
        quality = "chart_derived_current"
        source = "epa_png"
    else:
        quality = "estimated_current"
        source = "estimated"
    return {
        "timestamp": iso(now),
        "level_m": round(level, 3),
        "source": source,
        "quality": quality,
        "confidence": confidence_for(age_hours, str(latest.get("source", "")), latest.get("confidence")),
        "basis_timestamp": latest["timestamp"],
        "basis_level_m": latest.get("level_m"),
        "age_hours": round(age_hours, 2),
    }


def _rain_rows(rainfall: dict) -> list[dict[str, Any]]:
    rows = []
    rows.extend(rainfall.get("observed", []))
    rows.extend(rainfall.get("forecast", []))
    return rows


def forecast_levels(river_rows: list[dict[str, Any]], rainfall: dict) -> dict[str, Any]:
    now = now_local()
    rate = robust_rate_mm_hr(river_rows)
    current = estimate_current(river_rows, rate)
    if current is None:
        result = {"points": [], "status": "no_river_data"}
        write_json("data/forecast.json", result)
        return result

    rain_rows = _rain_rows(rainfall)
    current_level = safe_float(current["level_m"], 0.0) or 0.0
    horizons = [0, 3, 6, 12, 24]
    points = []
    for h in horizons:
        ts = now + timedelta(hours=h)
        if h == 0:
            level = current_level
            source = current["source"]
            quality = current["quality"]
        else:
            # Momentum decays through time, while rainfall response accumulates after a practical lag.
            momentum_m = 0.0
            for hour in range(1, h + 1):
                momentum_m += (rate / 1000.0) * (FORECAST_CONFIG.recession_decay_per_hour ** hour)
            rain_0_h = sum_between(rain_rows, now, ts, "rain_mm")
            rain_response_m = rain_0_h * FORECAST_CONFIG.rainfall_mm_to_level_m_upper_24h
            level = current_level + momentum_m + rain_response_m
            source = "forecast"
            quality = "forecast"

        points.append(
            {
                "label": "Now" if h == 0 else f"+{h}h",
                "hours_ahead": h,
                "timestamp": iso(ts),
                "level_m": round(level, 3),
                "source": source,
                "quality": quality,
                "confidence": current["confidence"] if h <= 3 else ("Low" if current["confidence"] == "Medium" else "Medium"),
            }
        )

    result = {
        "built_at": iso(now),
        "trend": trend_label(rate),
        "rate_mm_hr": round(rate, 1),
        "current": current,
        "points": points,
        "method": {
            "name": "Practical hybrid trend-rainfall forecast",
            "description": "Recent river momentum with rainfall response and recession damping. Requires local calibration after events.",
        },
    }
    write_json("data/forecast.json", result)
    return result
