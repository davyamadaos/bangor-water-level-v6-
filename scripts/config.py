from __future__ import annotations

from dataclasses import dataclass

STATION_ID = "33008"
STATION_NAME = "Bangor"
TZ_NAME = "Europe/Dublin"

EPA_ZIP_URL = "https://epawebapp.epa.ie/Hydronet/output/internet/stations/CAS/33008/S/3_months.zip"
EPA_CHART_PNG_URL = "https://epawebapp.epa.ie/Hydronet/output/internet/stations/CAS/33008/S/extralarge_3m_extralarge.png"
EPA_STATION_URL = "https://epawebapp.epa.ie/hydronet/#33008"

# Met Eireann forecast points. These are intentionally catchment-oriented rather than app-location-only.
WEATHER_POINTS = [
    {
        "id": "nephin_beg",
        "name": "Nephin Beg uplands",
        "lat": 54.04,
        "lon": -9.62,
        "weight": 0.50,
    },
    {
        "id": "bangor_owenmore",
        "name": "Bangor Erris / Owenmore lower catchment",
        "lat": 54.145,
        "lon": -9.740,
        "weight": 0.35,
    },
    {
        "id": "crossmolina_deel",
        "name": "Crossmolina / River Deel context",
        "lat": 54.10,
        "lon": -9.32,
        "weight": 0.15,
    },
]

PRIMARY_WEATHER_POINT = {
    "id": "bangor_mid_catchment",
    "name": "Bangor / Owenmore catchment",
    "lat": 54.12084559360346,
    "lon": -9.575250065156835,
}

MET_LOCATIONFORECAST_URL = "https://openaccess.pf.api.met.ie/metno-wdb2ts/locationforecast"
MET_DAILY_RAIN_CSV_URL = "https://clidata.met.ie/cli/climate_data/webdata/dly1834.csv"

TIDE_HIGH_LOW_URL = (
    "https://erddap.marine.ie/erddap/tabledap/IMI_TidePrediction_HighLow.csv"
    "?stationID,time,longitude,latitude,tide_time_category,Water_Level_ODMalin"
    "&stationID=%22Ballyglass%22&time%3E=now-30days&time%3C=now%2B14days&orderBy(%22time%22)"
)
TIDE_SERIES_URL = (
    "https://erddap.marine.ie/erddap/tabledap/IMI-TidePrediction.csv"
    "?time,longitude,latitude,stationID,Water_Level,Water_Level_ODM"
    "&stationID=%22Ballyglass%22&time%3E=now-30days&time%3C=now%2B14days&orderBy(%22time%22)"
)

DATA_DIR = "data"
DEBUG_DIR = "data/debug"

# First-pass calibrated chart area for the EPA extralarge PNG. The extractor tries to detect bounds first
# and falls back to these values if detection is poor. Review debug JSON after deployment and tune if needed.
DEFAULT_PLOT_BOUNDS = {
    "left": 76,
    "top": 42,
    "right": 1215,
    "bottom": 554,
}

@dataclass(frozen=True)
class ForecastConfig:
    stable_threshold_mm_hr: float = 2.0
    max_stale_extrapolation_hours: float = 12.0
    png_gap_fill_interval_minutes: int = 15
    # Practical rainfall response coefficients. These require local calibration after events.
    rainfall_mm_to_level_m_upper_24h: float = 0.004
    rainfall_mm_to_level_m_lower_24h: float = 0.002
    recession_decay_per_hour: float = 0.88
    confidence_stale_hours_medium: float = 4.0
    confidence_stale_hours_low: float = 12.0

FORECAST_CONFIG = ForecastConfig()
