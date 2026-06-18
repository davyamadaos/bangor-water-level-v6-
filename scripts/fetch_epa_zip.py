from __future__ import annotations

import io
import zipfile
from io import StringIO

import pandas as pd
import requests

from config import EPA_ZIP_URL, STATION_ID, STATION_NAME
from utils import iso, safe_float, write_json


def fetch_epa_zip() -> dict:
    response = requests.get(EPA_ZIP_URL, timeout=90)
    response.raise_for_status()

    z = zipfile.ZipFile(io.BytesIO(response.content))
    csv_names = [name for name in z.namelist() if name.lower().endswith(".csv")]
    if not csv_names:
        raise RuntimeError("No CSV file found in EPA ZIP")

    raw_lines = z.read(csv_names[0]).decode("utf-8", errors="replace").splitlines()
    rows = [line for line in raw_lines if line.strip() and not line.startswith("#")]

    df = pd.read_csv(
        StringIO("\n".join(rows)),
        sep=";",
        header=None,
        names=["timestamp", "value", "absolute", "quality"],
    )

    out_rows = []
    for _, r in df.iterrows():
        level = safe_float(r.get("absolute"))
        if level is None:
            continue
        try:
            ts = iso(str(r["timestamp"]))
        except Exception:
            continue
        out_rows.append(
            {
                "timestamp": ts,
                "level_m": round(level, 3),
                "source": "epa_zip",
                "quality": str(r.get("quality", "observed")),
                "confidence": "high",
            }
        )

    result = {
        "station": {"id": STATION_ID, "name": STATION_NAME, "source": "EPA Hydronet"},
        "source_url": EPA_ZIP_URL,
        "rows": out_rows,
    }
    write_json("data/river_zip.json", result)
    return result


if __name__ == "__main__":
    data = fetch_epa_zip()
    print(f"EPA ZIP rows: {len(data['rows'])}")
