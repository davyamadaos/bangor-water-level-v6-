# Bangor Water Level Dashboard V5

Static GitHub Pages dashboard for Bangor river level situational awareness. The app uses EPA Hydronet structured data, EPA chart-derived gap filling, rainfall, weather, tide predictions, and a practical trend-rainfall forecast.

## Key Features

1. Current river status card with current level, source, trend, rate, observation age, and confidence.
2. Combined river level and rainfall chart with Chart.js time ranges: 6h, 12h, 24h, 48h, 7d, 30d, 3m.
3. EPA official chart shown immediately below the app-generated river chart.
4. EPA PNG computer-vision extraction to fill the gap when the EPA ZIP is stale.
5. Rainfall bars and cumulative rainfall in the river chart.
6. Forecast cards for Now, +3h, +6h, +12h, and +24h.
7. Tide and weather cards.
8. Small source links at the base of every card.
9. Mobile-first layout, local datum offset, dark mode, manual refresh, and 15-minute auto-refresh.

## Data Sources

- EPA Hydronet Bangor Station 33008 ZIP: `https://epawebapp.epa.ie/Hydronet/output/internet/stations/CAS/33008/S/3_months.zip`
- EPA Hydronet Bangor chart PNG: `https://epawebapp.epa.ie/Hydronet/output/internet/stations/CAS/33008/S/extralarge_3m_extralarge.png`
- Met Éireann location forecast API: `https://openaccess.pf.api.met.ie/metno-wdb2ts/locationforecast`
- Met Éireann daily rainfall CSV reference: `https://clidata.met.ie/cli/climate_data/webdata/dly1834.csv`
- Marine Institute Ballyglass high/low tide prediction: ERDDAP `IMI_TidePrediction_HighLow`
- Marine Institute Ballyglass tide series: ERDDAP `IMI-TidePrediction`

## Repository Structure

```text
.
├── index.html
├── manifest.json
├── requirements.txt
├── README.md
├── assets/
│   ├── css/styles.css
│   └── js/
│       ├── app.js
│       ├── charts.js
│       └── format.js
├── scripts/
│   ├── config.py
│   ├── extract_epa_png.py
│   ├── fetch_epa_zip.py
│   ├── fetch_rainfall.py
│   ├── fetch_tides.py
│   ├── fetch_weather.py
│   ├── forecast.py
│   ├── merge_series.py
│   ├── update_all.py
│   └── utils.py
├── data/
│   └── generated JSON files
└── .github/workflows/update.yml
```

## Deployment

1. Create a new GitHub repository or branch.
2. Copy the contents of this package into the repository root.
3. Commit and push.
4. In GitHub, open **Settings > Pages**.
5. Set source to **Deploy from a branch**.
6. Select the branch and root folder.
7. Open **Actions** and manually run **Update Bangor Water Level Data** once.
8. Confirm that `data/latest.json` has been generated.
9. Open the GitHub Pages URL.

## Local Test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/update_all.py
python -m http.server 8000
```

Then open `http://localhost:8000`.

## EPA PNG Extraction Notes

The EPA chart PNG is not a structured data feed. V5 uses computer vision to extract the plotted hydrograph line and OCR for diagnostic axis text. Extracted values are labelled as `EPA chart-derived`, not raw observations. Review `data/debug/epa_chart_extraction.json` and `data/debug/epa_chart_latest.png` after deployment. If the extracted values are offset, tune `DEFAULT_PLOT_BOUNDS` and the level calibration logic in `scripts/config.py` and `scripts/extract_epa_png.py`.

## Forecast Notes

The forecast model is intentionally practical and transparent. It combines recent river momentum, rainfall forecast response, and recession damping. Coefficients in `scripts/config.py` should be calibrated after observed rainfall events.

## Known Limitations

- EPA PNG extraction is inherently less reliable than structured data.
- Rainfall observation is approximate unless a suitable sub-daily local rainfall feed is added.
- Forecast outputs should be treated as situational guidance, not formal flood forecasting.
