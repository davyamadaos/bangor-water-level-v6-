from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

from config import TIDE_HIGH_LOW_URL, TIDE_SERIES_URL
from utils import iso, now_local, safe_float, write_json


def _read_erddap_csv(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    lines = response.text.splitlines()
    # ERDDAP CSV has header row followed by units row. Drop units row if present.
    if len(lines) > 1 and "UTC" in lines[1]:
        text = "\n".join([lines[0]] + lines[2:])
    else:
        text = response.text
    return pd.read_csv(StringIO(text))


def fetch_tides() -> dict:
    high_low_rows = []
    series_rows = []

    try:
        df = _read_erddap_csv(TIDE_HIGH_LOW_URL)
        for _, r in df.iterrows():
            high_low_rows.append(
                {
                    "timestamp": iso(str(r.get("time"))),
                    "type": str(r.get("tide_time_category", "")).strip(),
                    "height_m_od_malin": safe_float(r.get("Water_Level_ODMalin")),
                    "station": str(r.get("stationID", "Ballyglass")),
                    "source": "marine_institute_high_low",
                }
            )
    except Exception as exc:
        high_low_rows = []
        high_low_error = str(exc)
    else:
        high_low_error = None

    try:
        df = _read_erddap_csv(TIDE_SERIES_URL)
        for _, r in df.iterrows():
            height = safe_float(r.get("Water_Level_ODM"), safe_float(r.get("Water_Level")))
            series_rows.append(
                {
                    "timestamp": iso(str(r.get("time"))),
                    "height_m": height,
                    "station": str(r.get("stationID", "Ballyglass")),
                    "source": "marine_institute_tide_series",
                }
            )
    except Exception as exc:
        series_rows = []
        series_error = str(exc)
    else:
        series_error = None

    now = now_local()
    today = now.date()
    display = []
    for row in high_low_rows:
        dt = __import__("dateutil").parser.parse(row["timestamp"]).astimezone(now.tzinfo)
        if today <= dt.date() <= (today + __import__("datetime").timedelta(days=1)):
            display.append(row)
    display = sorted(display, key=lambda r: r["timestamp"])[:6]

    result = {
        "source_high_low_url": TIDE_HIGH_LOW_URL,
        "source_series_url": TIDE_SERIES_URL,
        "high_low": high_low_rows,
        "series": series_rows,
        "display": display,
        "errors": {"high_low": high_low_error, "series": series_error},
        "built_at": iso(now),
    }
    write_json("data/tide.json", result)
    return result


if __name__ == "__main__":
    data = fetch_tides()
    print(f"Tides high_low={len(data['high_low'])}, series={len(data['series'])}")
