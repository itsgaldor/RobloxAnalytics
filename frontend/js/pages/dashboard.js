/**
 * Lógica principal del dashboard de Peru City Analytics.
 * Compatible con Chart.js v2.2.1 (usa lineTension, no tension).
 */

// ─── ESTADO GLOBAL ─────────────────────────────────────────────────────────
var currentSlug       = '';
var currentRange      = PCA_CONFIG.defaultRange || 'week';
var brandConfig       = {};
var mainChart         = null;   // Chart.js — línea de sesiones diarias
var serverChart       = null;   // Chart.js — barras público vs privado
var currentMetric     = 'sessions';  // métrica activa del gráfico de línea
var currentPubSeries  = [];     // caché de series para el toggle de métrica
var currentPrivSeries = [];

// ─── INIT ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function () {
  initTheme();

  currentSlug = getSlugFromUrl();
  if (!currentSlug) {
    mostrarError('No se especificó una marca válida. Usá /dashboard/?brand=yape o /dashboard/?brand=demo');
    return;
  }

  try {
    brandConfig = await fetchBrandConfig(currentSlug);
    applyWhitelabel(brandConfig);
  } catch (e) {
    // Si la marca no existe, redirigir a la página de error 404
    if (e.message && e.message.indexOf('no existe') !== -1) {
      window.location.href = '/dashboard/404-marca.html?brand=' + encodeURIComponent(currentSlug);
      return;
    }
    mostrarError('No se pudo cargar la configuración de la marca: ' + e.message);
    return;
  }

  initRangeButtons();
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

function formatDate(dateStr) {
  if (!dateStr) return '';
  var parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  return parts[2] + '/' + parts[1] + '/' + parts[0];
}

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  var parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  return parts[2] + '/' + parts[1];
}

/**
 * Convierte un color HEX a rgba() — necesario para Chart.js v2
 * que no soporta colores hex con canal alpha (#rrggbbaa).
 * @param {string} hex - Color en formato #RRGGBB
 * @param {number} alpha - Opacidad entre 0 y 1
 * @returns {string} rgba(r, g, b, alpha)
 */
function hexToRgba(hex, alpha) {
  if (!hex || hex.length < 7) return 'rgba(108, 58, 222, ' + alpha + ')';
  var r = parseInt(hex.slice(1, 3), 16);
  var g = parseInt(hex.slice(3, 5), 16);
  var b = parseInt(hex.slice(5, 7), 16);
  return 'rgba(' + r + ', ' + g + ', ' + b + ', ' + alpha + ')';
}

/**
 * Calcula la variación porcentual entre dos valores.
 * @param {number} current - Valor actual
 * @param {number} previous - Valor del período anterior
 * @returns {number|null} Variación % o null si no hay dato previo
 */
function calcVariation(current, previous) {
  if (previous === null || previous === undefined || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

/**
 * Genera el HTML del badge de variación % para un KPI.
 * @param {number|null} pct - Porcentaje de variación (puede ser negativo)
 * @returns {string} HTML string con el badge, o cadena vacía si no hay dato
 */
function renderVariation(pct) {
  if (pct === null || pct === undefined) return '';
  var rounded = Math.round(pct * 10) / 10;
  var sign    = rounded >= 0 ? '+' : '';
  var cls     = rounded >= 0 ? 'text-success' : 'text-danger';
  var icon    = rounded >= 0 ? 'fa-arrow-up'  : 'fa-arrow-down';
  return '<div class="pca-variation">' +
           '<span class="' + cls + '">' +
             '<i class="fa ' + icon + '"></i> ' + sign + rounded + '%' +
           '</span>' +
           '<small class="text-muted"> vs anterior</small>' +
         '</div>';
}

// ─── RANGO DE FECHAS ──────────────────────────────────────────────────────

function initRangeButtons() {
  var buttons = document.querySelectorAll('[data-range]');
  buttons.forEach(function (btn) {
    if (btn.dataset.range === currentRange) btn.classList.add('btn-theme-active');
    btn.addEventListener('click', async function () {
      var range = this.dataset.range;
      if (range === currentRange) return;
      buttons.forEach(function (b) { b.classList.remove('btn-theme-active'); });
      this.classList.add('btn-theme-active');
      currentRange = range;
      await loadDashboard(currentSlug, currentRange);
    });
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
    window.location.href = getExportUrl(currentSlug, currentRange);
  });
}

// ─── DARK MODE ────────────────────────────────────────────────────────────

function initThemeButton() {
  var btn = document.getElementById('btn-theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', function () { toggleTheme(); });
}

// ─── TOGGLE DE MÉTRICA EN EL GRÁFICO DE LÍNEA ─────────────────────────────

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

/**
 * Actualiza la serie del gráfico de línea sin reconstruir el Chart completo.
 * @param {'sessions'|'dau'|'avg_minutes'} metric
 */
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
    // Promedio de duración: usar serie pública como referencia (la más representativa)
    newData = baseSeries.map(function (d, i) {
      return (pubSeries[i] && pubSeries[i].avg_minutes) || 0;
    });
  } else {
    return;
  }

  mainChart.data.datasets[0].data  = newData;
  mainChart.data.datasets[0].label = getLabelForMetric(metric);
  mainChart.update();

  // Actualizar estado visual de los botones de toggle
  document.querySelectorAll('[data-metric]').forEach(function (btn) {
    if (btn.dataset.metric === metric) {
      btn.classList.add('active-metric');
    } else {
      btn.classList.remove('active-metric');
    }
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

  try {
    var results = await Promise.all([
      fetchMetrics(slug, range),
      fetchDailyMetrics(slug, range)
    ]);
    renderKPIs(results[0].data);
    renderCharts(results[0].data);
    renderTable(results[1].data);

    // Actualizar indicador de "última actualización"
    var lu = document.getElementById('last-updated');
    if (lu) {
      var now = new Date();
      lu.textContent = 'Actualizado ' + now.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });
    }
  } catch (e) {
    mostrarError('Error al cargar los datos: ' + e.message);
  }
}

// ─── LOADING / ERROR ──────────────────────────────────────────────────────

function mostrarLoading() {
  var kpis = document.getElementById('section-kpis');
  if (kpis) {
    var html = '';
    for (var i = 0; i < 5; i++) {
      html += '<div class="b-r">' +
                '<div class="padding">' +
                  '<div class="pca-loading" style="min-height:110px;border-radius:4px;"></div>' +
                '</div>' +
              '</div>';
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

// ─── KPIs ─────────────────────────────────────────────────────────────────

function renderKPIs(data) {
  var pub  = data['public']  || {};
  var priv = data['private'] || {};
  var prev = data['previous'] || null;   // puede ser null si compare=false

  var totalSessions = (pub.sessions || 0) + (priv.sessions || 0);
  var totalDau      = parseFloat(pub.dau || 0) + parseFloat(priv.dau || 0);
  // MAU: ventana de 30 días fija — se suman ambos tipos
  var totalMau      = (pub.mau || 0) + (priv.mau || 0);
  var avgMinutes    = pub.avg_session_minutes || 0;
  var totalHours    = (pub.total_hours || 0) + (priv.total_hours || 0);

  var kpis = [
    {
      valor:    formatNumber(totalSessions),
      label:    'Sesiones totales',
      icono:    'ion-ios-people',
      pub:      formatNumber(pub.sessions),
      priv:     formatNumber(priv.sessions),
      varPct:   prev ? calcVariation(totalSessions, prev.sessions) : null
    },
    {
      valor:    formatNumber(Math.round(totalDau)),
      label:    'Usuarios activos / día',
      icono:    'ion-person',
      pub:      formatNumber(Math.round(pub.dau || 0)),
      priv:     formatNumber(Math.round(priv.dau || 0)),
      varPct:   prev ? calcVariation(totalDau, prev.dau) : null
    },
    {
      valor:    formatNumber(totalMau),
      label:    'Usuarios activos (30 días)',
      icono:    'ion-calendar',
      pub:      formatNumber(pub.mau),
      priv:     formatNumber(priv.mau),
      varPct:   prev ? calcVariation(totalMau, prev.mau) : null
    },
    {
      valor:    formatMinutes(avgMinutes),
      label:    'Tiempo promedio sesión',
      icono:    'ion-clock',
      pub:      formatMinutes(pub.avg_session_minutes),
      priv:     formatMinutes(priv.avg_session_minutes),
      varPct:   prev ? calcVariation(avgMinutes, prev.avg_session_minutes) : null
    },
    {
      valor:    formatNumber(Math.round(totalHours)) + 'h',
      label:    'Horas totales de juego',
      icono:    'ion-ios-timer',
      pub:      formatNumber(Math.round(pub.total_hours || 0)) + 'h',
      priv:     formatNumber(Math.round(priv.total_hours || 0)) + 'h',
      varPct:   prev ? calcVariation(totalHours, prev.total_hours) : null
    }
  ];

  var section = document.getElementById('section-kpis');
  if (!section) return;

  var html = '';
  kpis.forEach(function (kpi) {
    html += '<div class="b-r">' +
              '<div class="padding text-center">' +
                '<div class="m-b-sm"><i class="' + kpi.icono + ' text-brand" style="font-size:28px;"></i></div>' +
                '<h2 class="_600 m-t-xs m-b-xs">' + kpi.valor + '</h2>' +
                '<p class="text-muted m-b-xs" style="font-size:0.82rem;">' + kpi.label + '</p>' +
                '<div class="m-b-xs">' +
                  '<span class="label info m-x-xs">Púb: ' + kpi.pub + '</span>' +
                  '<span class="label default m-x-xs">Priv: ' + kpi.priv + '</span>' +
                '</div>' +
                renderVariation(kpi.varPct) +
              '</div>' +
            '</div>';
  });

  section.innerHTML = html;
}

// ─── CHARTS ───────────────────────────────────────────────────────────────

function renderCharts(data) {
  var pub  = data['public']  || {};
  var priv = data['private'] || {};

  var pubSeries  = pub.time_series  || [];
  var privSeries = priv.time_series || [];

  // Cachear series para el toggle de métrica
  currentPubSeries  = pubSeries;
  currentPrivSeries = privSeries;

  // Necesitamos series con datos para renderizar
  if (!pubSeries.length && !privSeries.length) return;

  var baseSeries = pubSeries.length >= privSeries.length ? pubSeries : privSeries;
  var labels = baseSeries.map(function (d) { return formatDateShort(d.date); });

  var color = (brandConfig && brandConfig.primary_color) ? brandConfig.primary_color : '#6C3ADE';

  // Resetear métrica activa a 'sessions' al cargar nuevos datos
  currentMetric = 'sessions';
  document.querySelectorAll('[data-metric]').forEach(function (btn) {
    if (btn.dataset.metric === 'sessions') {
      btn.classList.add('active-metric');
    } else {
      btn.classList.remove('active-metric');
    }
  });

  // ── Helper: stepSize inteligente según el máximo del dataset ─────────
  function smartStep(values) {
    var max = Math.max.apply(null, values.concat([1]));
    if (max <= 10)   return 1;
    if (max <= 50)   return 5;
    if (max <= 200)  return 20;
    if (max <= 500)  return 50;
    if (max <= 2000) return 200;
    return Math.ceil(max / 10 / 100) * 100;
  }

  // ── Gráfico 1: Línea — sesiones totales diarias ───────────────────────
  var ctx1 = document.getElementById('chart-sessions');
  if (ctx1) {
    if (mainChart) { mainChart.destroy(); mainChart = null; }

    var totalByDay = baseSeries.map(function (d, i) {
      return ((pubSeries[i]  && pubSeries[i].sessions)  || 0) +
             ((privSeries[i] && privSeries[i].sessions) || 0);
    });

    mainChart = new Chart(ctx1, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Sesiones',
          data: totalByDay,
          borderColor: color,
          backgroundColor: hexToRgba(color, 0.15),
          fill: true,
          borderWidth: 2,
          lineTension: 0.3,
          pointRadius: 4,
          pointHoverRadius: 7,
          pointHitRadius: 30        // área de detección generosa — v2 requiere esto en el dataset
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        legend: { display: false },
        tooltips: {
          enabled: true,
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(0,0,0,0.75)',
          titleFontColor: '#ffffff',
          titleFontSize: 12,
          bodyFontColor: '#ffffff',
          bodyFontSize: 13,
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1,
          cornerRadius: 4,
          xPadding: 10,
          yPadding: 8,
          callbacks: {
            title: function (tooltipItems) {
              return tooltipItems[0].xLabel;
            },
            label: function (tooltipItem, data) {
              var label = data.datasets[tooltipItem.datasetIndex].label || '';
              var value = tooltipItem.yLabel;
              if (label === 'Tiempo prom. (min)') return label + ': ' + Math.round(value) + ' min';
              if (label === 'Horas totales') return label + ': ' + Math.round(value) + 'h';
              return label + ': ' + Math.round(value).toLocaleString('es-PE');
            }
          }
        },
        hover: { mode: 'index', intersect: false },
        scales: {
          xAxes: [{ gridLines: { display: false }, ticks: { fontSize: 11 } }],
          yAxes: [{
            ticks: {
              beginAtZero: true,
              fontSize: 11,
              stepSize: smartStep(totalByDay),
              callback: function (value) {
                if (value % 1 !== 0) return '';
                if (value >= 1000) return (value / 1000).toFixed(1) + 'k';
                return value;
              }
            }
          }]
        }
      }
    });
  }

  // ── Gráfico 2: Barras apiladas — público vs privado ───────────────────
  var ctx2 = document.getElementById('chart-server-type');
  if (ctx2) {
    if (serverChart) { serverChart.destroy(); serverChart = null; }

    serverChart = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Público',
            data: pubSeries.map(function (d) { return d.sessions || 0; }),
            backgroundColor: hexToRgba(color, 0.85)
          },
          {
            label: 'Privado',
            data: privSeries.map(function (d) { return d.sessions || 0; }),
            backgroundColor: hexToRgba(color, 0.35)
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        legend: { display: true, position: 'top', labels: { fontSize: 11 } },
        tooltips: {
          enabled: true,
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(0,0,0,0.75)',
          titleFontColor: '#ffffff',
          bodyFontColor: '#ffffff',
          bodyFontSize: 13,
          cornerRadius: 4,
          xPadding: 10,
          yPadding: 8,
          callbacks: {
            label: function (tooltipItem, data) {
              var label = data.datasets[tooltipItem.datasetIndex].label || '';
              return label + ': ' + Math.round(tooltipItem.yLabel).toLocaleString('es-PE');
            }
          }
        },
        hover: { mode: 'index', intersect: false },
        scales: {
          xAxes: [{ stacked: true, gridLines: { display: false }, ticks: { fontSize: 11 } }],
          yAxes: [{ stacked: true, ticks: {
            beginAtZero: true,
            fontSize: 11,
            stepSize: smartStep(pubSeries.map(function(d){ return d.sessions||0; }).concat(privSeries.map(function(d){ return d.sessions||0; }))),
            callback: function (value) {
              if (value % 1 !== 0) return '';
              if (value >= 1000) return (value / 1000).toFixed(1) + 'k';
              return value;
            }
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
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-a">Sin datos para el período seleccionado.</td></tr>';
    return;
  }

  var html = '';
  rows.forEach(function (row) {
    var dateStr = row.date ? row.date.replace(/-/g, '/') : '—';
    // Formato dd/mm/yyyy
    var parts = row.date ? row.date.split('-') : [];
    if (parts.length === 3) dateStr = parts[2] + '/' + parts[1] + '/' + parts[0];

    var avgMin = row.avg_minutes || 0;
    var timeStr = avgMin < 60
      ? Math.round(avgMin) + ' min'
      : Math.floor(avgMin / 60) + 'h ' + Math.round(avgMin % 60) + 'min';

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
