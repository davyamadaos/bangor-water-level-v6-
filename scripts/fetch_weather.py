from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import timedelta
from typing import Any

import requests

from config import MET_LOCATIONFORECAST_URL, PRIMARY_WEATHER_POINT, WEATHER_POINTS
from utils import iso, now_local, safe_float, write_json


def _fetch_xml(lat: float, lon: float) -> ET.Element:
    url = f"{MET_LOCATIONFORECAST_URL}?lat={lat};long={lon}"
    response = requests.get(url, timeout=90, headers={"User-Agent": "bangor-water-level-v5"})
    response.raise_for_status()
    return ET.fromstring(response.text)


def _parse_forecast(root: ET.Element, point: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for time_el in root.findall(".//time"):
        from_time = time_el.get("from")
        to_time = time_el.get("to")
        loc = time_el.find("location")
        if not from_time or loc is None:
            continue

        row: dict[str, Any] = {
            "timestamp": iso(from_time),
            "to_timestamp": iso(to_time or from_time),
            "point_id": point["id"],
            "point_name": point["name"],
        }
        temp = loc.find("temperature")
        wind_speed = loc.find("windSpeed")
        wind_dir = loc.find("windDirection")
        precip = loc.find("precipitation")
        humidity = loc.find("humidity")
        pressure = loc.find("pressure")
        symbol = loc.find("symbol")

        if temp is not None:
            row["temperature_c"] = safe_float(temp.get("value"))
        if wind_speed is not None:
            row["wind_speed_mps"] = safe_float(wind_speed.get("mps"))
            row["wind_speed_name"] = wind_speed.get("name")
        if wind_dir is not None:
            row["wind_direction_deg"] = safe_float(wind_dir.get("deg"))
            row["wind_direction_name"] = wind_dir.get("name")
        if precip is not None:
            row["rain_mm"] = safe_float(precip.get("value"), 0.0)
            row["rain_min_mm"] = safe_float(precip.get("minvalue"), None)
            row["rain_max_mm"] = safe_float(precip.get("maxvalue"), None)
        if humidity is not None:
            row["humidity_pct"] = safe_float(humidity.get("value"))
        if pressure is not None:
            row["pressure_hpa"] = safe_float(pressure.get("value"))
        if symbol is not None:
            row["symbol"] = symbol.get("id") or symbol.get("number")

        if "rain_mm" in row or "temperature_c" in row:
            rows.append(row)
    return rows


def fetch_weather() -> dict:
    all_points = []
    for point in [PRIMARY_WEATHER_POINT] + WEATHER_POINTS:
        try:
            root = _fetch_xml(point["lat"], point["lon"])
            rows = _parse_forecast(root, point)
            all_points.append({"point": point, "rows": rows, "status": "ok"})
        except Exception as exc:
            all_points.append({"point": point, "rows": [], "status": "error", "error": str(exc)})

    primary_rows = next((p["rows"] for p in all_points if p["point"]["id"] == PRIMARY_WEATHER_POINT["id"]), [])
    now = now_local()
    current = min(primary_rows, key=lambda r: abs((__import__("dateutil").parser.parse(r["timestamp"]) - now).total_seconds()), default=None)

    daily = []
    for day in range(7):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day)
        end = start + timedelta(days=1)
        rows = [r for r in primary_rows if start <= __import__("dateutil").parser.parse(r["timestamp"]).astimezone(now.tzinfo) < end]
        temps = [safe_float(r.get("temperature_c")) for r in rows if safe_float(r.get("temperature_c")) is not None]
        rain = sum(safe_float(r.get("rain_mm"), 0.0) or 0.0 for r in rows)
        daily.append(
            {
                "date": start.date().isoformat(),
                "temp_min_c": round(min(temps), 1) if temps else None,
                "temp_max_c": round(max(temps), 1) if temps else None,
                "rain_mm": round(rain, 1),
                "summary": "Rain" if rain >= 1.0 else "Dry",
            }
        )

    result = {
        "source_url": MET_LOCATIONFORECAST_URL,
        "primary_point": PRIMARY_WEATHER_POINT,
        "points": all_points,
        "current": current,
        "daily": daily,
    }
    write_json("data/weather.json", result)
    return result


if __name__ == "__main__":
    result = fetch_weather()
    print(f"Weather points: {len(result['points'])}")
