from __future__ import annotations

import json
import math
import os
from datetime import timedelta
from typing import Any

import cv2
import numpy as np
import pytesseract
import requests
from PIL import Image

from config import DEFAULT_PLOT_BOUNDS, EPA_CHART_PNG_URL, FORECAST_CONFIG, STATION_ID, STATION_NAME
from utils import iso, now_local, parse_time, write_json


def download_png(path: str = "data/debug/epa_chart_latest.png") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    response = requests.get(EPA_CHART_PNG_URL, timeout=90)
    response.raise_for_status()
    with open(path, "wb") as f:
        f.write(response.content)
    return path


def detect_plot_bounds(img: np.ndarray) -> dict[str, int]:
    """Detect a likely chart plot rectangle. Falls back to calibrated bounds if uncertain."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=160, minLineLength=250, maxLineGap=8)
    h, w = gray.shape
    verticals: list[int] = []
    horizontals: list[int] = []
    if lines is not None:
        for line in lines[:, 0, :]:
            x1, y1, x2, y2 = [int(v) for v in line]
            if abs(x1 - x2) < 4 and abs(y2 - y1) > 250:
                verticals.append(x1)
            if abs(y1 - y2) < 4 and abs(x2 - x1) > 250:
                horizontals.append(y1)

    if len(verticals) >= 2 and len(horizontals) >= 2:
        left = max(0, min(verticals))
        right = min(w - 1, max(verticals))
        top = max(0, min(horizontals))
        bottom = min(h - 1, max(horizontals))
        if right - left > 600 and bottom - top > 250:
            return {"left": left, "top": top, "right": right, "bottom": bottom, "method": "detected"}

    out = dict(DEFAULT_PLOT_BOUNDS)
    out["method"] = "default_calibrated"
    return out


def ocr_axis_text(image_path: str) -> str:
    try:
        image = Image.open(image_path)
        # OCR the full image and preserve for diagnostics only. The numeric extraction is CV-based.
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as exc:
        return f"OCR unavailable: {exc}"


def extract_line_pixels(img: np.ndarray, bounds: dict[str, int]) -> list[tuple[int, int]]:
    left, top, right, bottom = bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]
    crop = img[top:bottom, left:right]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # EPA hydrographs commonly use saturated coloured lines. This mask avoids grey axes/gridlines.
    mask_sat = cv2.inRange(hsv, np.array([0, 45, 30]), np.array([179, 255, 230]))
    # Remove common red title/annotation artefacts by restricting to line-like connected components later.
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask_sat, cv2.MORPH_OPEN, kernel)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    candidates = []
    for label in range(1, num_labels):
        x, y, ww, hh, area = stats[label]
        if area < 50:
            continue
        if ww < 60:
            continue
        candidates.append((label, x, y, ww, hh, area))

    if not candidates:
        return []

    # The hydrograph line should be one of the widest components.
    candidates.sort(key=lambda item: (item[3], item[5]), reverse=True)
    selected = candidates[0][0]
    selected_mask = (labels == selected).astype(np.uint8)

    points: list[tuple[int, int]] = []
    for x in range(selected_mask.shape[1]):
        ys = np.where(selected_mask[:, x] > 0)[0]
        if len(ys) == 0:
            continue
        y = int(np.median(ys))
        points.append((left + x, top + y))
    return points


def infer_level_range(zip_rows: list[dict[str, Any]]) -> tuple[float, float]:
    if not zip_rows:
        return 98.5, 100.5
    levels = [float(r["level_m"]) for r in zip_rows[-96:] if r.get("level_m") is not None]
    if not levels:
        return 98.5, 100.5
    lo = min(levels)
    hi = max(levels)
    pad = max(0.05, (hi - lo) * 0.35)
    return round(lo - pad, 3), round(hi + pad, 3)


def points_to_series(points: list[tuple[int, int]], bounds: dict[str, int], zip_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map pixels to timestamps and levels using the latest ZIP observation as temporal anchor.

    The EPA PNG does not expose structured values. This first-pass method assumes the 3-month chart spans
    approximately 90 days and that the right edge is the most recent chart update rounded to 15 minutes.
    It is therefore marked medium confidence and should be tuned using the debug output.
    """
    if not points:
        return []

    left, top, right, bottom = bounds["left"], bounds["top"], bounds["right"], bounds["bottom"]
    level_min, level_max = infer_level_range(zip_rows)
    current = now_local()
    minute = (current.minute // 15) * 15
    right_time = current.replace(minute=minute, second=0, microsecond=0)
    left_time = right_time - timedelta(days=90)
    span_seconds = (right_time - left_time).total_seconds()

    latest_zip_time = parse_time(zip_rows[-1]["timestamp"]) if zip_rows else left_time
    interval = timedelta(minutes=FORECAST_CONFIG.png_gap_fill_interval_minutes)

    raw = []
    for x, y in points:
        frac_x = (x - left) / max(1, (right - left))
        frac_y = (bottom - y) / max(1, (bottom - top))
        ts = left_time + timedelta(seconds=span_seconds * frac_x)
        level = level_min + (level_max - level_min) * frac_y
        if ts > latest_zip_time - timedelta(minutes=30):
            raw.append((ts, level))

    if not raw:
        return []

    buckets: dict[str, list[float]] = {}
    for ts, level in raw:
        rounded_minute = (ts.minute // 15) * 15
        bts = ts.replace(minute=rounded_minute, second=0, microsecond=0)
        key = iso(bts)
        buckets.setdefault(key, []).append(level)

    rows = []
    for key in sorted(buckets):
        vals = buckets[key]
        if not vals:
            continue
        rows.append(
            {
                "timestamp": key,
                "level_m": round(float(np.median(vals)), 3),
                "source": "epa_png",
                "quality": "chart_derived",
                "confidence": "medium",
            }
        )
    return rows


def extract_epa_png(zip_rows: list[dict[str, Any]] | None = None) -> dict:
    zip_rows = zip_rows or []
    image_path = download_png()
    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError("Failed to read downloaded EPA PNG")

    bounds = detect_plot_bounds(img)
    points = extract_line_pixels(img, bounds)
    rows = points_to_series(points, bounds, zip_rows)
    ocr_text = ocr_axis_text(image_path)

    debug = {
        "image_path": image_path,
        "bounds": bounds,
        "line_points_detected": len(points),
        "rows_derived": len(rows),
        "ocr_text_sample": ocr_text[:2000],
        "notes": [
            "PNG-derived values are inferred from a plotted chart and should not be labelled as raw observations.",
            "If values are offset, tune DEFAULT_PLOT_BOUNDS or level range calibration in scripts/config.py and scripts/extract_epa_png.py.",
        ],
    }
    write_json("data/debug/epa_chart_extraction.json", debug)

    result = {
        "station": {"id": STATION_ID, "name": STATION_NAME, "source": "EPA Hydronet PNG"},
        "source_url": EPA_CHART_PNG_URL,
        "extraction": debug,
        "rows": rows,
    }
    write_json("data/river_png_derived.json", result)
    return result


if __name__ == "__main__":
    result = extract_epa_png([])
    print(json.dumps({"rows": len(result["rows"]), "source": result["source_url"]}, indent=2))
