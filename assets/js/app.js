let appData = null;
let currentRange = '12h';

const sourceNames = {
  epa_station: 'EPA Station',
  epa_zip: 'EPA ZIP',
  epa_chart_png: 'EPA Chart PNG',
  met_eireann_forecast: 'Met Éireann forecast',
  met_eireann_daily_rain: 'Met Éireann rainfall',
  marine_high_low_tide: 'Marine high/low tide',
  marine_tide_series: 'Marine tide series',
  generated_latest_json: 'latest.json',
  generated_river_json: 'river.json',
  generated_rainfall_json: 'rainfall.json',
  generated_weather_json: 'weather.json',
  generated_tide_json: 'tide.json',
  generated_forecast_json: 'forecast.json',
  local_storage: 'Local device storage'
};

function getOffset() {
  return Number(document.getElementById('datumOffset').value || 0);
}

function applyTheme(value) {
  if (value === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', value);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function renderSources() {
  const links = appData?.metadata?.source_links || {};
  document.querySelectorAll('.card-sources').forEach(el => {
    const keys = (el.dataset.sources || '').split(',').map(s => s.trim()).filter(Boolean);
    const anchors = keys.map(key => {
      const href = links[key] || (key === 'local_storage' ? null : null);
      const name = sourceNames[key] || key;
      return href ? `<a href="${href}" target="_blank" rel="noopener">${name}</a>` : `<span>${name}</span>`;
    });
    el.innerHTML = `Sources: ${anchors.join(' · ')}`;
  });
}

function latestBySource(rows, source) {
  return [...(rows || [])].reverse().find(r => r.source === source);
}

function renderStatus() {
  const riverRows = appData?.river?.rows || [];
  const current = appData?.forecast?.current || latestBySource(riverRows, 'epa_png') || riverRows[riverRows.length - 1];
  const latestZip = latestBySource(riverRows, 'epa_zip');
  const latestPng = latestBySource(riverRows, 'epa_png');
  const offset = getOffset();
  const rate = Number(appData?.forecast?.rate_mm_hr ?? appData?.metadata?.rate_mm_hr ?? 0);
  const trend = appData?.forecast?.trend || appData?.metadata?.trend || 'Stable';

  setText('builtAt', `Data built: ${fmtDateTime(appData?.metadata?.built_at)} · Auto refresh: every 15 minutes`);
  setText('currentLevel', fmtLevel(Number(current?.level_m ?? NaN) + offset));
  setText('currentSource', sourceLabel(current?.source));
  setText('currentTime', fmtDateTime(current?.timestamp));
  setText('zipLevel', latestZip ? `${fmtLevel(Number(latestZip.level_m) + offset)} @ ${fmtDateTime(latestZip.timestamp)}` : '--');
  setText('estimatedLevel', appData?.forecast?.current ? `${fmtLevel(Number(appData.forecast.current.level_m) + offset)} @ ${fmtDateTime(appData.forecast.current.timestamp)}` : '--');
  setText('zipAge', latestZip ? ageText(latestZip.timestamp) : '--');
  setText('chartAge', latestPng ? ageText(latestPng.timestamp) : '--');
  setText('rate', `${Math.abs(rate).toFixed(0)} mm/hr`);
  setText('confidenceBadge', `Confidence: ${current?.confidence || '--'}`);

  const trendEl = document.getElementById('trend');
  trendEl.className = 'trend neutral';
  if (trend === 'Rising') { trendEl.textContent = '▲ Rising'; trendEl.className = 'trend rising'; }
  else if (trend === 'Falling') { trendEl.textContent = '▼ Falling'; trendEl.className = 'trend falling'; }
  else { trendEl.textContent = '► Stable'; }
}

function renderForecast() {
  const container = document.getElementById('forecastCards');
  const offset = getOffset();
  container.innerHTML = (appData?.forecast?.points || []).map(p => `
    <div class="forecast-item">
      <span>${p.label}</span>
      <strong>${fmtLevel(Number(p.level_m) + offset)}</strong>
      <span>${sourceLabel(p.source)}</span>
      <span>${p.confidence || ''}</span>
    </div>`).join('');
  setText('forecastBasis', appData?.forecast?.method?.description || 'Forecast basis: recent trend, rainfall, and catchment response lag.');
}

function renderSummary() {
  const tbody = document.getElementById('summaryBody');
  tbody.innerHTML = (appData?.summary12h || []).map(r => `
    <tr>
      <td>${r.date || fmtDate(r.timestamp)}</td>
      <td>${r.time || fmtTime(r.timestamp)}</td>
      <td>${fmtLevel(r.level_m)}</td>
      <td>${r.source || '--'}</td>
      <td>${fmtMm(r.rain_3h_mm)}</td>
    </tr>`).join('');
}

function renderRainfall() {
  const s = appData?.rainfall?.summary || {};
  setText('rainCurrent', fmtMm(s.current_rain_mm));
  setText('rain24', fmtMm(s.previous_24h_mm));
  setText('rain48', fmtMm(s.previous_48h_mm));
  setText('rain6f', fmtMm(s.next_6h_mm));
  setText('rain12f', fmtMm(s.next_12h_mm));
  setText('rain24f', fmtMm(s.next_24h_mm));
  setText('rain48f', fmtMm(s.next_48h_mm));
}

function renderTides() {
  const tbody = document.getElementById('tideBody');
  tbody.innerHTML = (appData?.tide?.display || []).map(r => {
    const type = String(r.type || '').toLowerCase().includes('high') ? '▲ High' : '▼ Low';
    return `<tr><td>${type}</td><td>${fmtTime(r.timestamp)}</td><td>${fmtLevel(r.height_m_od_malin)}</td><td>${fmtDate(r.timestamp)}</td></tr>`;
  }).join('') || '<tr><td colspan="4">No tide data available</td></tr>';
  renderTideChart(appData);
}

function renderWeather() {
  const current = appData?.weather?.current || {};
  const wind = windMpsToKmh(current.wind_speed_mps);
  setText('temperature', Number.isFinite(Number(current.temperature_c)) ? `${Number(current.temperature_c).toFixed(1)} °C` : '--');
  setText('weatherRain', fmtMm(current.rain_mm));
  setText('wind', wind == null ? '--' : `${wind} km/h ${current.wind_direction_name || ''}`.trim());
  setText('condition', current.symbol || current.wind_speed_name || '--');
  const daily = document.getElementById('dailyWeather');
  daily.innerHTML = (appData?.weather?.daily || []).map(d => `
    <div><strong>${new Date(d.date).toLocaleDateString('en-IE', { weekday: 'short' })}</strong><br>${d.temp_max_c ?? '--'}° / ${d.temp_min_c ?? '--'}°<br>${fmtMm(d.rain_mm)}<br>${d.summary}</div>
  `).join('');
}

function renderDataStatus() {
  const status = appData?.metadata?.statuses || {};
  const rows = Object.entries(status).map(([key, val]) => `<div><span>${key.replace('_', ' ')}</span><strong>${val.status || '--'}</strong></div>`);
  rows.push(`<div><span>Latest level source</span><strong>${sourceLabel(appData?.metadata?.latest_level?.source)}</strong></div>`);
  rows.push(`<div><span>Latest level age</span><strong>${appData?.metadata?.latest_age_hours ?? '--'} hours</strong></div>`);
  document.getElementById('dataStatus').innerHTML = rows.join('');
}

function renderAll() {
  if (!appData) return;
  document.getElementById('epaChartImage').src = `${appData.metadata.source_links.epa_chart_png}?v=${Date.now()}`;
  renderStatus();
  renderRiverChart(appData, currentRange, getOffset());
  renderSources();
  renderForecast();
  renderSummary();
  renderRainfall();
  renderTides();
  renderWeather();
  renderDataStatus();
}

async function loadData() {
  const response = await fetch(`./data/latest.json?v=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Failed to fetch data: ${response.status}`);
  appData = await response.json();
  renderAll();
}

function initControls() {
  document.getElementById('refreshBtn').addEventListener('click', () => window.location.reload());
  document.querySelectorAll('.range-buttons button').forEach(button => {
    button.addEventListener('click', () => {
      currentRange = button.dataset.range;
      document.querySelectorAll('.range-buttons button').forEach(b => b.classList.remove('active'));
      button.classList.add('active');
      renderRiverChart(appData, currentRange, getOffset());
    });
  });
  const offset = document.getElementById('datumOffset');
  offset.value = localStorage.getItem('datumOffset') || '0';
  offset.addEventListener('input', () => {
    localStorage.setItem('datumOffset', offset.value);
    renderAll();
  });
  const theme = document.getElementById('themeSelect');
  theme.value = localStorage.getItem('theme') || 'auto';
  applyTheme(theme.value);
  theme.addEventListener('change', () => {
    localStorage.setItem('theme', theme.value);
    applyTheme(theme.value);
  });
}

initControls();
loadData().catch(err => {
  console.error(err);
  setText('builtAt', 'Data failed to load. Check data/latest.json.');
});
setInterval(() => loadData().catch(console.error), 15 * 60 * 1000);
