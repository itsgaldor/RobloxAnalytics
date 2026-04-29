/**
 * Lógica principal del dashboard de Peru City Analytics.
 * Compatible con Chart.js v2.2.1 (usa lineTension, no tension).
 */

// ─── ESTADO GLOBAL ─────────────────────────────────────────────────────────
var currentSlug       = '';
var currentRange      = PCA_CONFIG.defaultRange || 'week';
var customDateFrom    = null;   // string YYYY-MM-DD
var customDateTo      = null;   // string YYYY-MM-DD
var brandConfig       = {};
var mainChart         = null;
var serverChart       = null;
var currentMetric     = 'sessions';
var currentPubSeries  = [];
var currentPrivSeries = [];
var currentPrevSeries = [];

// ─── INIT ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function () {
  initTheme();
  initSidebar();

  currentSlug = getSlugFromUrl();
  if (!currentSlug) {
    mostrarError('No se especificó una marca válida. Usá /dashboard/?brand=yape o /dashboard/?brand=demo');
    return;
  }

  try {
    brandConfig = await fetchBrandConfig(currentSlug);
    applyWhitelabel(brandConfig);
    renderScriptStatus(brandConfig.health, brandConfig.last_event_at);
  } catch (e) {
    if (e.message && e.message.indexOf('no existe') !== -1) {
      window.location.href = '/dashboard/404-marca.html?brand=' + encodeURIComponent(currentSlug);
      return;
    }
    mostrarError('No se pudo cargar la configuración de la marca: ' + e.message);
    return;
  }

  initRangeButtons();
  initDatePicker();
  initRefreshButton();
  initExportButton();
  initThemeButton();
  initMetricButtons();

  await loadDashboard(currentSlug, currentRange);
});

// ─── HELPERS ──────────────────────────────────────────────────────────────

function getSlugFromUrl() {
  var params = new URLSearchParams(window.location.search);
  var brand = params.get('brand');
  if (brand) return brand.trim();
  var parts = window.location.pathname.replace(/\/$/, '').split('/');
  var idx = parts.indexOf('dashboard');
  if (idx !== -1 && parts[idx + 1]) return parts[idx + 1].trim();
  return '';
}

function formatNumber(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Math.round(n).toLocaleString('es-PE');
}

function formatMinutes(mins) {
  if (!mins && mins !== 0) return '—';
  mins = parseFloat(mins);
  if (mins < 60) return Math.round(mins) + ' min';
  var h = Math.floor(mins / 60);
  var m = Math.round(mins % 60);
  return h + 'h' + (m > 0 ? ' ' + m + 'min' : '');
}

function formatDateStr(dateStr) {
  if (!dateStr) return '';
  var parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  return parts[2] + '/' + parts[1] + '/' + parts[0];
}

function formatDateShort(dateStr) {
  // Accepts 'YYYY-MM-DD' string or Date object
  if (!dateStr) return '';
  if (dateStr instanceof Date) {
    return dateStr.toLocaleDateString('es-PE', { day: '2-digit', month: 'short' });
  }
  var parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  return parts[2] + '/' + parts[1];
}

function hexToRgba(hex, alpha) {
  if (!hex || hex.length < 7) return 'rgba(108, 58, 222, ' + alpha + ')';
  var r = parseInt(hex.slice(1, 3), 16);
  var g = parseInt(hex.slice(3, 5), 16);
  var b = parseInt(hex.slice(5, 7), 16);
  return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
}

function calcVariation(current, previous) {
  if (previous === null || previous === undefined || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

function renderVariation(pct, rangeLabel) {
  if (pct === null || pct === undefined) return '';
  var rounded = Math.round(pct * 10) / 10;
  var sign    = rounded >= 0 ? '+' : '';
  var cls     = rounded >= 0 ? 'text-success' : 'text-danger';
  var icon    = rounded >= 0 ? 'fa-arrow-up'  : 'fa-arrow-down';
  var label   = rangeLabel || 'vs anterior';
  return '<div class="pca-variation">' +
           '<span class="' + cls + '">' +
             '<i class="fa ' + icon + '"></i> ' + sign + rounded + '%' +
           '</span>' +
           '<small class="text-muted"> ' + label + '</small>' +
         '</div>';
}

function getComparisonLabel() {
  if (currentRange === 'custom' && customDateFrom && customDateTo) {
    // Calcular período anterior del mismo tamaño
    var from = new Date(customDateFrom + 'T00:00:00Z');
    var to   = new Date(customDateTo   + 'T00:00:00Z');
    var days = Math.round((to - from) / 86400000);
    var prevTo   = new Date(from - 86400000);
    var prevFrom = new Date(prevTo - (days - 1) * 86400000);
    return 'vs ' + formatDateShort(prevFrom) + ' — ' + formatDateShort(prevTo);
  }
  var labels = { day: 'vs ayer', week: 'vs semana anterior', month: 'vs mes anterior' };
  return labels[currentRange] || 'vs anterior';
}

// ─── RANGO DE FECHAS ──────────────────────────────────────────────────────

function initRangeButtons() {
  var buttons = document.querySelectorAll('[data-range]');
  buttons.forEach(function (btn) {
    if (btn.dataset.range === currentRange) btn.classList.add('btn-theme-active');
    btn.addEventListener('click', async function () {
      var range = this.dataset.range;
      if (range === currentRange && currentRange !== 'custom') return;
      buttons.forEach(function (b) { b.classList.remove('btn-theme-active'); });
      document.getElementById('btn-range-custom').classList.remove('btn-theme-active');
      this.classList.add('btn-theme-active');
      currentRange = range;
      customDateFrom = null;
      customDateTo   = null;
      var label = document.getElementById('custom-range-label');
      if (label) label.textContent = 'Personalizado';
      await loadDashboard(currentSlug, currentRange);
    });
  });
}

// ─── DATE PICKER ─────────────────────────────────────────────────────────

function initDatePicker() {
  var picker    = document.getElementById('custom-date-picker');
  var btnCustom = document.getElementById('btn-range-custom');
  var btnApply  = document.getElementById('btn-date-apply');
  var btnCancel = document.getElementById('btn-date-cancel');
  var dateFrom  = document.getElementById('date-from');
  var dateTo    = document.getElementById('date-to');
  var errorEl   = document.getElementById('date-picker-error');

  if (!picker || !btnCustom) return;

  // Valores por defecto: últimos 7 días
  var today   = new Date();
  var weekAgo = new Date(today - 7 * 86400000);
  dateFrom.value = weekAgo.toISOString().split('T')[0];
  dateTo.value   = today.toISOString().split('T')[0];
  dateTo.max     = today.toISOString().split('T')[0];

  // Toggle
  btnCustom.addEventListener('click', function (e) {
    e.stopPropagation();
    picker.style.display = picker.style.display === 'none' ? 'block' : 'none';
  });

  // Cerrar al hacer click fuera
  document.addEventListener('click', function (e) {
    if (!picker.contains(e.target) && e.target !== btnCustom) {
      picker.style.display = 'none';
    }
  });

  // Validación en tiempo real
  dateFrom.addEventListener('change', function () {
    dateTo.min = dateFrom.value;
    validateDateRange();
  });
  dateTo.addEventListener('change', validateDateRange);

  function validateDateRange() {
    var from = new Date(dateFrom.value + 'T00:00:00Z');
    var to   = new Date(dateTo.value   + 'T00:00:00Z');
    var days = Math.round((to - from) / 86400000);
    errorEl.style.display = 'none';
    if (to < from) {
      errorEl.textContent = 'La fecha de fin debe ser posterior a la de inicio';
      errorEl.style.display = 'block';
      btnApply.disabled = true;
      return false;
    }
    if (days > 90) {
      errorEl.textContent = 'El rango máximo es de 90 días';
      errorEl.style.display = 'block';
      btnApply.disabled = true;
      return false;
    }
    btnApply.disabled = false;
    return true;
  }

  btnCancel.addEventListener('click', function () {
    picker.style.display = 'none';
  });

  btnApply.addEventListener('click', async function () {
    if (!validateDateRange()) return;

    customDateFrom = dateFrom.value;
    customDateTo   = dateTo.value;
    currentRange   = 'custom';

    // Actualizar label del botón
    var label = document.getElementById('custom-range-label');
    if (label) label.textContent = formatDateShort(customDateFrom) + ' — ' + formatDateShort(customDateTo);

    // Marcar botón personalizado como activo
    document.querySelectorAll('[data-range]').forEach(function (b) { b.classList.remove('btn-theme-active'); });
    btnCustom.classList.add('btn-theme-active');
    picker.style.display = 'none';

    await loadDashboard(currentSlug, 'custom');
  });
}

// ─── REFRESH ──────────────────────────────────────────────────────────────

function initRefreshButton() {
  var btn = document.getElementById('btn-refresh');
  if (!btn) return;
  btn.addEventListener('click', async function () {
    var icon = btn.querySelector('i');
    btn.disabled = true;
    if (icon) icon.classList.add('spin');
    try {
      await triggerRefresh(currentSlug);
      await loadDashboard(currentSlug, currentRange);
    } catch (e) {
      mostrarError('Error al refrescar: ' + e.message);
    } finally {
      btn.disabled = false;
      if (icon) icon.classList.remove('spin');
    }
  });
}

// ─── EXPORT ───────────────────────────────────────────────────────────────

function initExportButton() {
  var btn = document.getElementById('btn-export');
  if (!btn) return;
  btn.addEventListener('click', function () {
    window.location.href = getExportUrl(currentSlug, currentRange, customDateFrom, customDateTo);
  });
}

// ─── DARK MODE ────────────────────────────────────────────────────────────

function initThemeButton() {
  var btn = document.getElementById('btn-theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', function () { toggleTheme(); });
}

// ─── TOGGLE DE MÉTRICA ────────────────────────────────────────────────────

function initMetricButtons() {
  var buttons = document.querySelectorAll('[data-metric]');
  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var metric = this.dataset.metric;
      if (metric === currentMetric) return;
      updateLineChart(metric);
    });
  });
}

function updateLineChart(metric) {
  currentMetric = metric;
  if (!mainChart) return;

  var pubSeries  = currentPubSeries;
  var privSeries = currentPrivSeries;
  var baseSeries = pubSeries.length >= privSeries.length ? pubSeries : privSeries;

  var newData;
  if (metric === 'sessions') {
    newData = baseSeries.map(function (d, i) {
      return ((pubSeries[i]  && pubSeries[i].sessions)  || 0) +
             ((privSeries[i] && privSeries[i].sessions) || 0);
    });
  } else if (metric === 'dau') {
    newData = baseSeries.map(function (d, i) {
      return ((pubSeries[i]  && pubSeries[i].dau)  || 0) +
             ((privSeries[i] && privSeries[i].dau) || 0);
    });
  } else if (metric === 'avg_minutes') {
    newData = baseSeries.map(function (d, i) {
      return (pubSeries[i] && pubSeries[i].avg_minutes) || 0;
    });
  } else {
    return;
  }

  mainChart.data.datasets[0].data  = newData;
  mainChart.data.datasets[0].label = getLabelForMetric(metric);

  if (currentPrevSeries.length > 0 && mainChart.data.datasets[1]) {
    mainChart.data.datasets[1].data = currentPrevSeries.map(function (d) {
      return d.sessions || 0;
    });
  }

  mainChart.update();

  document.querySelectorAll('[data-metric]').forEach(function (btn) {
    btn.classList.toggle('active-metric', btn.dataset.metric === metric);
  });
}

function getLabelForMetric(metric) {
  var map = { sessions: 'Sesiones', dau: 'DAU', avg_minutes: 'Tiempo prom. (min)' };
  return map[metric] || metric;
}

// ─── CARGA DE DATOS ───────────────────────────────────────────────────────

async function loadDashboard(slug, range) {
  mostrarLoading();
  var errDiv = document.getElementById('section-error');
  if (errDiv) errDiv.classList.add('hide');

  var dfrom = range === 'custom' ? customDateFrom : null;
  var dto   = range === 'custom' ? customDateTo   : null;

  try {
    var results = await Promise.all([
      fetchMetrics(slug, range, dfrom, dto),
      fetchDailyMetrics(slug, range, dfrom, dto)
    ]);
    renderKPIs(results[0].data);
    renderCharts(results[0].data);
    renderTable(results[1].data);

    var lu = document.getElementById('last-updated');
    if (lu) {
      var now = new Date();
      lu.textContent = 'Actualizado ' + now.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
    }
  } catch (e) {
    renderEmptyState('section-kpis', 'ion-ios-alert-outline', 'Error al cargar los datos', e.message);
    mostrarError('Error al cargar los datos: ' + e.message);
  }
}

// ─── LOADING / ERROR ──────────────────────────────────────────────────────

function mostrarLoading() {
  var kpis = document.getElementById('section-kpis');
  if (kpis) {
    var html = '';
    for (var i = 0; i < 5; i++) {
      html += '<div class="b-r"><div class="padding">' +
              '<div class="pca-loading" style="min-height:110px;border-radius:4px;"></div>' +
              '</div></div>';
    }
    kpis.innerHTML = html;
  }
  var tbody = document.querySelector('#table-daily tbody');
  if (tbody) {
    var rows = '';
    for (var j = 0; j < 7; j++) {
      rows += '<tr><td colspan="7"><div class="pca-loading" style="min-height:18px;"></div></td></tr>';
    }
    tbody.innerHTML = rows;
  }
}

function mostrarError(mensaje) {
  var errDiv = document.getElementById('section-error');
  var errMsg = document.getElementById('error-message');
  if (errDiv && errMsg) {
    errMsg.textContent = mensaje;
    errDiv.classList.remove('hide');
  }
  console.error('[PCA Error]', mensaje);
}

// ─── ESTADOS VACÍOS ───────────────────────────────────────────────────────

function renderEmptyState(containerId, icon, title, subtitle) {
  var el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML =
    '<div style="width:100%;padding:56px 24px;text-align:center;color:var(--text-muted,#64748b);">' +
      '<i class="' + (icon || 'ion-ios-analytics-outline') + '" style="font-size:52px;opacity:0.25;display:block;margin-bottom:16px;"></i>' +
      '<p style="font-size:14px;font-weight:500;margin:0 0 6px;color:inherit;">' + (title || '') + '</p>' +
      (subtitle ? '<p style="font-size:12px;margin:0;opacity:0.7;">' + subtitle + '</p>' : '') +
    '</div>';
}

// ─── KPIs ─────────────────────────────────────────────────────────────────

function renderKPIs(data) {
  var pub  = data['public']  || {};
  var priv = data['private'] || {};
  var prev = data['previous'] || null;

  var totalSessions = (pub.sessions || 0) + (priv.sessions || 0);
  if (totalSessions === 0 && !(pub.mau || 0) && !(priv.mau || 0)) {
    renderEmptyState('section-kpis', 'ion-ios-analytics-outline',
      'Sin sesiones en este período',
      'Probá con un rango de fechas diferente');
    return;
  }

  var compLabel  = getComparisonLabel();
  var totalDau   = parseFloat(pub.dau || 0) + parseFloat(priv.dau || 0);
  var totalMau   = (pub.mau || 0) + (priv.mau || 0);
  var avgMinutes = pub.avg_session_minutes || 0;
  var totalHours = (pub.total_hours || 0) + (priv.total_hours || 0);

  var kpis = [
    { valor: formatNumber(totalSessions),           rawTarget: totalSessions,           tipo: 'number',  label: 'Sesiones totales',         icono: 'ion-ios-people',  pub: formatNumber(pub.sessions),                      priv: formatNumber(priv.sessions),                      varPct: prev ? calcVariation(totalSessions, prev.sessions) : null },
    { valor: formatNumber(Math.round(totalDau)),    rawTarget: Math.round(totalDau),    tipo: 'number',  label: 'Usuarios activos / día',    icono: 'ion-person',      pub: formatNumber(Math.round(pub.dau || 0)),           priv: formatNumber(Math.round(priv.dau || 0)),           varPct: prev ? calcVariation(totalDau, prev.dau) : null },
    { valor: formatNumber(totalMau),                rawTarget: totalMau,                tipo: 'number',  label: 'Usuarios activos (30 días)',icono: 'ion-calendar',    pub: formatNumber(pub.mau),                           priv: formatNumber(priv.mau),                           varPct: prev ? calcVariation(totalMau, prev.mau) : null },
    { valor: formatMinutes(avgMinutes),             rawTarget: avgMinutes,              tipo: 'minutes', label: 'Tiempo promedio sesión',    icono: 'ion-clock',       pub: formatMinutes(pub.avg_session_minutes),           priv: formatMinutes(priv.avg_session_minutes),           varPct: prev ? calcVariation(avgMinutes, prev.avg_session_minutes) : null },
    { valor: formatNumber(Math.round(totalHours)) + 'h', rawTarget: Math.round(totalHours), tipo: 'hours', label: 'Horas totales de juego', icono: 'ion-ios-timer',   pub: formatNumber(Math.round(pub.total_hours || 0)) + 'h', priv: formatNumber(Math.round(priv.total_hours || 0)) + 'h', varPct: prev ? calcVariation(totalHours, prev.total_hours) : null }
  ];

  var section = document.getElementById('section-kpis');
  if (!section) return;

  var html = '';
  kpis.forEach(function (kpi) {
    html += '<div class="b-r kpi-card">' +
              '<div class="padding text-center">' +
                '<div class="m-b-sm"><i class="' + kpi.icono + ' text-brand" style="font-size:28px;"></i></div>' +
                '<h2 class="_600 m-t-xs m-b-xs kpi-value" data-target="' + (kpi.rawTarget || 0) + '" data-type="' + (kpi.tipo || 'number') + '">' + kpi.valor + '</h2>' +
                '<p class="text-muted m-b-xs" style="font-size:0.82rem;">' + kpi.label + '</p>' +
                '<div class="m-b-xs">' +
                  '<span class="label info m-x-xs">Púb: ' + kpi.pub + '</span>' +
                  '<span class="label default m-x-xs">Priv: ' + kpi.priv + '</span>' +
                '</div>' +
                renderVariation(kpi.varPct, compLabel) +
              '</div>' +
            '</div>';
  });

  section.innerHTML = html;

  requestAnimationFrame(function() {
    section.querySelectorAll('.kpi-value[data-target]').forEach(function(el) {
      var target = parseFloat(el.dataset.target) || 0;
      var type   = el.dataset.type || 'number';
      animateCounter(el, target, 900, function(val) {
        if (type === 'hours')   return Math.round(val) + 'h';
        if (type === 'minutes') return formatMinutes(val);
        return formatNumber(Math.round(val));
      });
    });
  });
}

// ─── CHARTS ───────────────────────────────────────────────────────────────

var TOOLTIP_DEFAULTS = {
  enabled: true,
  mode: 'nearest',
  intersect: false,
  backgroundColor: 'rgba(15,23,42,0.92)',
  titleFontSize: 11,
  titleFontColor: '#94a3b8',
  bodyFontSize: 13,
  bodyFontColor: '#f1f5f9',
  bodyFontStyle: 'bold',
  borderColor: 'rgba(255,255,255,0.08)',
  borderWidth: 1,
  cornerRadius: 6,
  xPadding: 12,
  yPadding: 10,
  displayColors: false,
  caretSize: 6
};

function renderCharts(data) {
  var pub  = data['public']  || {};
  var priv = data['private'] || {};
  var prev = data['previous'] || null;

  var pubSeries  = pub.time_series  || [];
  var privSeries = priv.time_series || [];
  var prevSeries = (prev && prev.time_series) ? prev.time_series : [];

  currentPubSeries  = pubSeries;
  currentPrivSeries = privSeries;
  currentPrevSeries = prevSeries;

  if (!pubSeries.length && !privSeries.length) {
    renderEmptyState('section-charts', 'ion-ios-stats-outline',
      'Sin datos de gráficos', 'No hay series temporales para el período seleccionado');
    return;
  }

  var baseSeries = pubSeries.length >= privSeries.length ? pubSeries : privSeries;
  var labels = baseSeries.map(function (d) { return formatDateShort(d.date); });
  var color  = (brandConfig && brandConfig.primary_color) ? brandConfig.primary_color : '#6C3ADE';

  currentMetric = 'sessions';
  document.querySelectorAll('[data-metric]').forEach(function (btn) {
    btn.classList.toggle('active-metric', btn.dataset.metric === 'sessions');
  });

  function smartStep(values) {
    var max = Math.max.apply(null, values.concat([1]));
    if (max <= 10)   return 1;
    if (max <= 50)   return 5;
    if (max <= 200)  return 20;
    if (max <= 500)  return 50;
    if (max <= 2000) return 200;
    return Math.ceil(max / 10 / 100) * 100;
  }

  var ctx1 = document.getElementById('chart-sessions');
  if (ctx1) {
    if (mainChart) { mainChart.destroy(); mainChart = null; }

    var totalByDay  = baseSeries.map(function (d, i) {
      return ((pubSeries[i]  && pubSeries[i].sessions)  || 0) +
             ((privSeries[i] && privSeries[i].sessions) || 0);
    });
    var hasPrevData = prevSeries.length > 0;
    var prevData    = prevSeries.map(function (d) { return d.sessions || 0; });

    var datasets = [{
      label: 'Período actual',
      data: totalByDay,
      borderColor: color,
      backgroundColor: hexToRgba(color, 0.12),
      fill: true,
      borderWidth: 2.5,
      lineTension: 0.3,
      pointRadius: 4,
      pointHoverRadius: 7,
      pointHitRadius: 20
    }];

    if (hasPrevData) {
      datasets.push({
        label: getComparisonLabel(),
        data: prevData,
        borderColor: hexToRgba(color, 0.4),
        backgroundColor: 'transparent',
        fill: false,
        borderWidth: 1.5,
        borderDash: [5, 5],
        lineTension: 0.3,
        pointRadius: 2,
        pointHoverRadius: 5,
        pointHitRadius: 10
      });
    }

    mainChart = new Chart(ctx1, {
      type: 'line',
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        legend: { display: hasPrevData, position: 'top', labels: { fontSize: 11, boxWidth: 20, padding: 16 } },
        tooltips: Object.assign({}, TOOLTIP_DEFAULTS, {
          callbacks: {
            title: function (items) { return items[0] ? items[0].xLabel : ''; },
            label: function (item, d) {
              var label = d.datasets[item.datasetIndex].label || '';
              var val   = item.yLabel;
              if (currentMetric === 'avg_minutes') return label + ': ' + Math.round(val) + ' min';
              if (currentMetric === 'total_hours')  return label + ': ' + Math.round(val) + 'h';
              return label + ': ' + Number(val).toLocaleString('es-PE');
            }
          }
        }),
        hover: { mode: 'nearest', intersect: false, animationDuration: 100 },
        scales: {
          xAxes: [{ gridLines: { display: false }, ticks: { fontSize: 11 } }],
          yAxes: [{ ticks: {
            beginAtZero: true, fontSize: 11,
            stepSize: smartStep(totalByDay),
            callback: function (v) {
              if (v % 1 !== 0) return '';
              return v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v;
            }
          }}]
        }
      }
    });
  }

  var ctx2 = document.getElementById('chart-server-type');
  if (ctx2) {
    if (serverChart) { serverChart.destroy(); serverChart = null; }
    serverChart = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Público',  data: pubSeries.map(function(d){return d.sessions||0;}),  backgroundColor: hexToRgba(color, 0.85) },
          { label: 'Privado',  data: privSeries.map(function(d){return d.sessions||0;}), backgroundColor: hexToRgba(color, 0.35) }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        legend: { display: true, position: 'top', labels: { fontSize: 11 } },
        tooltips: Object.assign({}, TOOLTIP_DEFAULTS, {
          mode: 'index', intersect: false, displayColors: true,
          callbacks: {
            title: function (items) { return items[0] ? items[0].xLabel : ''; },
            label: function (item, d) {
              return (d.datasets[item.datasetIndex].label || '') + ': ' +
                     Math.round(item.yLabel).toLocaleString('es-PE');
            }
          }
        }),
        hover: { mode: 'index', intersect: false },
        scales: {
          xAxes: [{ stacked: true, gridLines: { display: false }, ticks: { fontSize: 11 } }],
          yAxes: [{ stacked: true, ticks: {
            beginAtZero: true, fontSize: 11,
            stepSize: smartStep(pubSeries.map(function(d){return d.sessions||0;}).concat(privSeries.map(function(d){return d.sessions||0;}))),
            callback: function (v) { return v % 1 !== 0 ? '' : v >= 1000 ? (v/1000).toFixed(1)+'k' : v; }
          }}]
        }
      }
    });
  }
}

// ─── TABLA DIARIA ─────────────────────────────────────────────────────────

function renderTable(rows) {
  var tbody = document.querySelector('#table-daily tbody');
  if (!tbody) return;

  if (!rows || rows.length === 0) {
    renderEmptyState('section-table', 'ion-ios-list-outline',
      'Sin datos diarios', 'No hay registros para el período seleccionado');
    return;
  }

  var html = '';
  rows.forEach(function (row) {
    var parts = row.date ? String(row.date).split('-') : [];
    var dateStr = parts.length === 3 ? parts[2] + '/' + parts[1] + '/' + parts[0] : (row.date || '—');
    var avgMin = row.avg_minutes || 0;
    var timeStr = avgMin < 60 ? Math.round(avgMin) + ' min' : Math.floor(avgMin/60) + 'h ' + Math.round(avgMin%60) + 'min';
    html += '<tr>' +
      '<td>' + dateStr + '</td>' +
      '<td>' + (row.sessions || 0).toLocaleString('es-PE') + '</td>' +
      '<td>' + (row.unique_users || 0).toLocaleString('es-PE') + '</td>' +
      '<td>' + timeStr + '</td>' +
      '<td>' + Math.round(row.total_hours || 0).toLocaleString('es-PE') + 'h</td>' +
      '<td>' + (row.public_sessions || 0).toLocaleString('es-PE') + '</td>' +
      '<td>' + (row.private_sessions || 0).toLocaleString('es-PE') + '</td>' +
      '</tr>';
  });
  tbody.innerHTML = html;
}

// ─── SCRIPT STATUS BADGE ─────────────────────────────────────────────────

function renderScriptStatus(health, lastEventAt) {
  var el = document.getElementById('script-status');
  if (!el) return;
  var configs = {
    ok:      { color: '#22c55e', icon: 'ion-ios-checkmark-circle', label: 'Script activo',      bg: 'rgba(34,197,94,0.15)'  },
    warning: { color: '#f59e0b', icon: 'ion-ios-alert',            label: 'Sin datos recientes', bg: 'rgba(245,158,11,0.15)' },
    offline: { color: '#ef4444', icon: 'ion-ios-close-circle',     label: 'Script desconectado', bg: 'rgba(239,68,68,0.15)'  }
  };
  var cfg = configs[health] || configs.offline;
  var timeAgo = 'nunca conectado';
  if (lastEventAt) {
    var diff = Math.floor((Date.now() - new Date(lastEventAt)) / 60000);
    timeAgo = diff < 60 ? 'hace ' + diff + ' min' : diff < 1440 ? 'hace ' + Math.floor(diff/60) + 'h' : 'hace ' + Math.floor(diff/1440) + 'd';
  }
  el.innerHTML =
    '<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:99px;' +
    'background:' + cfg.bg + ';border:1px solid ' + cfg.color + '33;font-size:11px;font-weight:500;' +
    'color:' + cfg.color + ';cursor:default;" title="Último dato recibido: ' + timeAgo + '">' +
    '<i class="' + cfg.icon + '" style="font-size:13px;"></i>' + cfg.label +
    '<span style="opacity:0.7;font-weight:400;">(' + timeAgo + ')</span></span>';
}

// ─── ANIMACIÓN DE CONTADOR ────────────────────────────────────────────────

function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

function animateCounter(element, targetValue, duration, formatter) {
  if (targetValue === 0) { element.textContent = formatter(0); return; }
  var startTime = null;
  function update(currentTime) {
    if (!startTime) startTime = currentTime;
    var progress = Math.min((currentTime - startTime) / duration, 1);
    element.textContent = formatter(Math.round(targetValue * easeOutCubic(progress)));
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}
