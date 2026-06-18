from __future__ import annotations

import traceback
from datetime import timedelta

from config import EPA_CHART_PNG_URL, EPA_STATION_URL, EPA_ZIP_URL, MET_DAILY_RAIN_CSV_URL, MET_LOCATIONFORECAST_URL, TIDE_HIGH_LOW_URL, TIDE_SERIES_URL
from extract_epa_png import extract_epa_png
from fetch_epa_zip import fetch_epa_zip
from fetch_rainfall import fetch_rainfall
from fetch_tides import fetch_tides
from fetch_weather import fetch_weather
from forecast import forecast_levels, robust_rate_mm_hr, trend_label
from merge_series import merge_river
from utils import iso, local_date_label, local_time_label, nearest_row, now_local, parse_time, safe_float, sum_between, write_json


def _run_step(name, fn, fallback):
    try:
        data = fn()
        return data, {"status": "ok"}
    except Exception as exc:
        return fallback, {"status": "error", "error": str(exc), "traceback": traceback.format_exc()[-4000:]}


def build_summary(river_rows, rainfall, forecast):
    now = now_local()
    rain_rows = rainfall.get("observed", []) + rainfall.get("forecast", [])
    summary = []
    # rolling 12 hours at 3-hour clock increments, plus current and next 3-hour forecast.
    base = now.replace(minute=0, second=0, microsecond=0)
    base = base.replace(hour=(base.hour // 3) * 3)
    times = [base - timedelta(hours=9), base - timedelta(hours=6), base - timedelta(hours=3), base]
    times.append(now)
    times.append(base + timedelta(hours=3))

    for t in times:
        fpoint = None
        source = None
        row = nearest_row(river_rows, t, tolerance_minutes=60)
        if t > now:
            fpoint = nearest_row(forecast.get("points", []), t, tolerance_minutes=180)
            row = fpoint or row
        if row is None and abs((t - now).total_seconds()) < 1800:
            row = forecast.get("current")
        if row is None:
            level = None
            source = "--"
        else:
            level = row.get("level_m")
            source = {"epa_zip": "ZIP", "epa_png": "Chart", "estimated": "Est.", "forecast": "Fcst"}.get(row.get("source"), row.get("source", "--"))
        rain_start = t - timedelta(hours=3)
        rain = sum_between(rain_rows, rain_start, t, "rain_mm")
        summary.append(
            {
                "timestamp": iso(t),
                "date": local_date_label(t),
                "time": "Current" if abs((t - now).total_seconds()) < 60 else local_time_label(t),
                "level_m": round(float(level), 3) if level is not None else None,
                "source": source,
                "rain_3h_mm": round(rain, 1),
                "rain_source": "forecast" if t > now else "observed/forecast blend",
            }
        )
    return summary


def main() -> None:
    statuses = {}
    zip_data, statuses["epa_zip"] = _run_step("epa_zip", fetch_epa_zip, {"rows": [], "source_url": EPA_ZIP_URL})
    png_data, statuses["epa_png"] = _run_step("epa_png", lambda: extract_epa_png(zip_data.get("rows", [])), {"rows": [], "source_url": EPA_CHART_PNG_URL})
    river = merge_river(zip_data, png_data)
    rainfall, statuses["rainfall"] = _run_step("rainfall", fetch_rainfall, {"observed": [], "forecast": [], "summary": {}, "source_url": MET_LOCATIONFORECAST_URL})
    weather, statuses["weather"] = _run_step("weather", fetch_weather, {"current": None, "daily": [], "source_url": MET_LOCATIONFORECAST_URL})
    tide, statuses["tide"] = _run_step("tide", fetch_tides, {"display": [], "series": [], "source_high_low_url": TIDE_HIGH_LOW_URL, "source_series_url": TIDE_SERIES_URL})
    forecast = forecast_levels(river.get("rows", []), rainfall)

    river_rows = river.get("rows", [])
    latest = river_rows[-1] if river_rows else None
    now = now_local()
    latest_age_hours = round((now - parse_time(latest["timestamp"])).total_seconds() / 3600, 2) if latest else None
    rate = robust_rate_mm_hr(river_rows) if river_rows else 0.0
    summary = build_summary(river_rows, rainfall, forecast)

    metadata = {
        "built_at": iso(now),
        "station": river.get("station"),
        "latest_level": latest,
        "latest_age_hours": latest_age_hours,
        "trend": trend_label(rate),
        "rate_mm_hr": round(rate, 1),
        "statuses": statuses,
        "source_links": {
            "epa_station": EPA_STATION_URL,
            "epa_zip": EPA_ZIP_URL,
            "epa_chart_png": EPA_CHART_PNG_URL,
            "met_eireann_forecast": MET_LOCATIONFORECAST_URL,
            "met_eireann_daily_rain": MET_DAILY_RAIN_CSV_URL,
            "marine_high_low_tide": TIDE_HIGH_LOW_URL,
            "marine_tide_series": TIDE_SERIES_URL,
            "generated_latest_json": "./data/latest.json",
            "generated_river_json": "./data/river.json",
            "generated_rainfall_json": "./data/rainfall.json",
            "generated_weather_json": "./data/weather.json",
            "generated_tide_json": "./data/tide.json",
            "generated_forecast_json": "./data/forecast.json",
        },
    }

    latest_json = {
        "metadata": metadata,
        "river": river,
        "rainfall": rainfall,
        "weather": weather,
        "tide": tide,
        "forecast": forecast,
        "summary12h": summary,
    }
    write_json("data/metadata.json", metadata)
    write_json("data/latest.json", latest_json)
    print(f"Built latest.json with {len(river_rows)} river rows")


if __name__ == "__main__":
    main()
