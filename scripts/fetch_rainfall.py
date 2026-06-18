from __future__ import annotations

from datetime import timedelta
from typing import Any

import requests

from config import MET_DAILY_RAIN_CSV_URL, MET_LOCATIONFORECAST_URL, WEATHER_POINTS
from fetch_weather import _fetch_xml, _parse_forecast
from utils import iso, now_local, parse_time, safe_float, write_json


def _weighted_forecast_rows() -> list[dict[str, Any]]:
    by_time: dict[str, dict[str, Any]] = {}
    for point in WEATHER_POINTS:
        try:
            rows = _parse_forecast(_fetch_xml(point["lat"], point["lon"]), point)
        except Exception:
            rows = []
        for row in rows:
            if "rain_mm" not in row:
                continue
            key = row["timestamp"]
            rec = by_time.setdefault(key, {"timestamp": key, "weighted_rain_mm": 0.0, "weight_total": 0.0, "points": []})
            weight = float(point.get("weight", 1.0))
            rain = safe_float(row.get("rain_mm"), 0.0) or 0.0
            rec["weighted_rain_mm"] += rain * weight
            rec["weight_total"] += weight
            rec["points"].append({"point_id": point["id"], "rain_mm": rain, "weight": weight})

    out = []
    for rec in by_time.values():
        total_weight = rec.pop("weight_total") or 1.0
        rec["rain_mm"] = round(rec.pop("weighted_rain_mm") / total_weight, 2)
        rec["source"] = "met_eireann_forecast"
        out.append(rec)
    return sorted(out, key=lambda r: r["timestamp"])


def _try_fetch_daily_rain() -> list[dict[str, Any]]:
    # This station file is useful as a low-resolution fallback. It is not used for sub-daily rainfall bars.
    try:
        response = requests.get(MET_DAILY_RAIN_CSV_URL, timeout=60)
        response.raise_for_status()
        lines = response.text.splitlines()
        rows = []
        for line in lines[-60:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4 or not parts[0][:4].isdigit():
                continue
            rain = None
            for p in reversed(parts):
                val = safe_float(p)
                if val is not None:
                    rain = val
                    break
            if rain is not None:
                rows.append({"raw": line, "rain_mm": rain, "source": "met_eireann_daily_station"})
        return rows
    except Exception:
        return []


def fetch_rainfall() -> dict:
    now = now_local()
    forecast_rows = _weighted_forecast_rows()
    # Observed rainfall is approximated from nowcast/forecast rows before build time where available.
    observed_rows = [r for r in forecast_rows if parse_time(r["timestamp"]) <= now]
    future_rows = [r for r in forecast_rows if parse_time(r["timestamp"]) > now]

    def total_next(hours: int) -> float:
        end = now + timedelta(hours=hours)
        return round(sum(safe_float(r.get("rain_mm"), 0.0) or 0.0 for r in future_rows if parse_time(r["timestamp"]) <= end), 1)

    def total_prev(hours: int) -> float:
        start = now - timedelta(hours=hours)
        return round(sum(safe_float(r.get("rain_mm"), 0.0) or 0.0 for r in observed_rows if parse_time(r["timestamp"]) >= start), 1)

    result = {
        "source_url": MET_LOCATIONFORECAST_URL,
        "daily_station_source_url": MET_DAILY_RAIN_CSV_URL,
        "points": WEATHER_POINTS,
        "observed": observed_rows,
        "forecast": future_rows,
        "daily_station_recent": _try_fetch_daily_rain(),
        "summary": {
            "current_rain_mm": round(safe_float(observed_rows[-1].get("rain_mm"), 0.0) or 0.0, 1) if observed_rows else 0.0,
            "previous_24h_mm": total_prev(24),
            "previous_48h_mm": total_prev(48),
            "next_6h_mm": total_next(6),
            "next_12h_mm": total_next(12),
            "next_24h_mm": total_next(24),
            "next_48h_mm": total_next(48),
        },
        "built_at": iso(now),
    }
    write_json("data/rainfall.json", result)
    return result


if __name__ == "__main__":
    data = fetch_rainfall()
    print(data["summary"])
