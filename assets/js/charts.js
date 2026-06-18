let riverChart = null;
let tideChart = null;

const rangeHours = {
  '6h': 6,
  '12h': 12,
  '24h': 24,
  '48h': 48,
  '7d': 168,
  '30d': 720,
  '3m': 2160
};

function withOffset(row, offset) {
  return { ...row, x: new Date(row.timestamp), y: Number(row.level_m) + offset };
}

function filterByRange(rows, range, timeKey = 'timestamp') {
  if (!Array.isArray(rows) || rows.length === 0) return [];
  if (range === '3m') return rows;
  const end = Date.now();
  const start = end - (rangeHours[range] || 12) * 3600000;
  return rows.filter(r => new Date(r[timeKey]).getTime() >= start && new Date(r[timeKey]).getTime() <= end + 24 * 3600000);
}

function rainfallSeries(data, range) {
  const rainfall = data.rainfall || {};
  const rows = [...(rainfall.observed || []), ...(rainfall.forecast || [])];
  const filtered = filterByRange(rows, range);
  let cumulative = 0;
  return {
    bars: filtered.map(r => ({ x: new Date(r.timestamp), y: Number(r.rain_mm || 0), source: r.source })),
    cumulative: filtered.map(r => {
      cumulative += Number(r.rain_mm || 0);
      return { x: new Date(r.timestamp), y: Number(cumulative.toFixed(2)), source: r.source };
    })
  };
}

function renderRiverChart(data, range, offset) {
  const ctx = document.getElementById('riverChart');
  const riverRows = filterByRange(data.river?.rows || [], range);
  const zip = riverRows.filter(r => r.source === 'epa_zip').map(r => withOffset(r, offset));
  const png = riverRows.filter(r => r.source === 'epa_png').map(r => withOffset(r, offset));
  const forecast = (data.forecast?.points || []).map(r => withOffset(r, offset));
  const rain = rainfallSeries(data, range);

  if (riverChart) riverChart.destroy();
  riverChart = new Chart(ctx, {
    data: {
      datasets: [
        { type: 'line', label: 'Observed level, EPA ZIP', data: zip, yAxisID: 'yLevel', borderWidth: 2, pointRadius: 0, tension: 0.2 },
        { type: 'line', label: 'Derived level, EPA chart', data: png, yAxisID: 'yLevel', borderWidth: 2, pointRadius: 2, tension: 0.2 },
        { type: 'line', label: 'Forecast level', data: forecast, yAxisID: 'yLevel', borderWidth: 2, borderDash: [6, 6], pointRadius: 4, tension: 0.2 },
        { type: 'bar', label: 'Rainfall', data: rain.bars, yAxisID: 'yRain', borderWidth: 0, order: 5 },
        { type: 'line', label: 'Cumulative rainfall', data: rain.cumulative, yAxisID: 'yRain', borderWidth: 1, stepped: true, pointRadius: 0, order: 4 }
      ]
    },
    plugins: [{
      id: 'latestLabels',
      afterDatasetsDraw(chart) {
        const ctx = chart.ctx;
        [0, 1, 2].forEach(datasetIndex => {
          const meta = chart.getDatasetMeta(datasetIndex);
          if (!meta.data.length || chart.data.datasets[datasetIndex].hidden) return;
          const point = meta.data[meta.data.length - 1];
          const value = chart.data.datasets[datasetIndex].data[chart.data.datasets[datasetIndex].data.length - 1]?.y;
          if (!Number.isFinite(value)) return;
          ctx.save();
          ctx.font = 'bold 11px sans-serif';
          ctx.fillText(`${value.toFixed(3)} m`, point.x + 8, point.y - 8);
          ctx.restore();
        });
      }
    }],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      interaction: { intersect: false, mode: 'nearest' },
      plugins: {
        legend: { display: true, labels: { boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label(context) {
              const raw = context.raw || {};
              const label = context.dataset.label || '';
              const suffix = context.dataset.yAxisID === 'yRain' ? ' mm' : ' m';
              const value = Number(context.parsed.y).toFixed(context.dataset.yAxisID === 'yRain' ? 1 : 3);
              return `${label}: ${value}${suffix}${raw.source ? ` (${sourceLabel(raw.source)})` : ''}`;
            }
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: ['6h', '12h', '24h'].includes(range) ? 'hour' : 'day' },
          ticks: { maxRotation: 0, autoSkip: true }
        },
        yLevel: { type: 'linear', position: 'left', title: { display: true, text: 'River level (m)' } },
        yRain: { type: 'linear', position: 'right', title: { display: true, text: 'Rainfall (mm)' }, grid: { drawOnChartArea: false }, beginAtZero: true }
      }
    }
  });
}

function renderTideChart(data) {
  const ctx = document.getElementById('tideChart');
  const rows = data.tide?.series || [];
  const now = Date.now();
  const start = now - 24 * 3600000;
  const end = now + 36 * 3600000;
  const series = rows
    .filter(r => new Date(r.timestamp).getTime() >= start && new Date(r.timestamp).getTime() <= end)
    .map(r => ({ x: new Date(r.timestamp), y: Number(r.height_m) }));
  if (tideChart) tideChart.destroy();
  tideChart = new Chart(ctx, {
    type: 'line',
    data: { datasets: [{ label: 'Tide level', data: series, borderWidth: 2, pointRadius: 0, tension: 0.25 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { type: 'time', time: { unit: 'hour' } },
        y: { title: { display: true, text: 'Height (m)' } }
      }
    }
  });
}
