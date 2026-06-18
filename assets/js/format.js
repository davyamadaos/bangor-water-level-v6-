function fmtLevel(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(3)} m` : '--';
}

function fmtMm(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)} mm` : '--';
}

function fmtDateTime(value) {
  if (!value) return '--';
  return new Date(value).toLocaleString('en-IE', {
    day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit'
  });
}

function fmtTime(value) {
  if (!value) return '--';
  return new Date(value).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' });
}

function fmtDate(value) {
  if (!value) return '--';
  return new Date(value).toLocaleDateString('en-IE', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function ageText(timestamp) {
  if (!timestamp) return '--';
  const hours = (Date.now() - new Date(timestamp).getTime()) / 3600000;
  if (hours < 1) return `${Math.max(0, Math.round(hours * 60))} minutes ago`;
  return `${hours.toFixed(1)} hours ago`;
}

function sourceLabel(source) {
  const map = {
    epa_zip: 'EPA ZIP',
    epa_png: 'EPA chart-derived',
    estimated: 'Estimated',
    forecast: 'Forecast'
  };
  return map[source] || source || '--';
}

function windMpsToKmh(value) {
  return Number.isFinite(Number(value)) ? Math.round(Number(value) * 3.6) : null;
}
