from __future__ import annotations

from config import STATION_ID, STATION_NAME
from utils import dedupe_sorted, write_json


def merge_river(zip_data: dict, png_data: dict) -> dict:
    zip_rows = zip_data.get("rows", [])
    png_rows = png_data.get("rows", [])
    latest_zip_ts = zip_rows[-1]["timestamp"] if zip_rows else None

    rows = []
    rows.extend(zip_rows)
    if latest_zip_ts:
        rows.extend([r for r in png_rows if r.get("timestamp") > latest_zip_ts])
    else:
        rows.extend(png_rows)

    merged = dedupe_sorted(rows)
    result = {
        "station": {"id": STATION_ID, "name": STATION_NAME, "source": "EPA Hydronet"},
        "rows": merged,
        "sources": {
            "epa_zip": zip_data.get("source_url"),
            "epa_png": png_data.get("source_url"),
        },
    }
    write_json("data/river.json", result)
    return result
