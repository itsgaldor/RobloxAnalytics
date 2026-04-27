/**
 * Logica del generador de reportes PDF del backoffice.
 */

var _progressMessages = {
  base:   ['Calculando metricas...', 'Preparando datos...', 'Construyendo PDF...'],
  withAi: ['Calculando metricas...', 'Preparando datos...', 'Generando analisis con IA...', 'Construyendo PDF...'],
};
var _progressTimer = null;

document.addEventListener('DOMContentLoaded', function () {
  cargarMarcas();
  setDefaultDates();

  document.getElementById('select-marca').addEventListener('change', function () {
    var slug = this.value;
    document.getElementById('section-form').style.display = slug ? '' : 'none';
  });

  document.getElementById('toggle-ai').addEventListener('change', function () {
    document.getElementById('ai-desc').style.display = this.checked ? '' : 'none';
    this.nextElementSibling.textContent = this.checked
      ? 'Incluir analisis con IA ✓'
      : 'No incluir analisis de IA';
  });

  document.getElementById('btn-generate').addEventListener('click', generarReporte);
});

// ── Cargar marcas activas en el selector ─────────────────────────────────────

async function cargarMarcas() {
  try {
    var json = await adminGetBrands();
    var activas = (json.data || []).filter(function (b) { return b.active; });
    var sel = document.getElementById('select-marca');
    activas.forEach(function (b) {
      var opt = document.createElement('option');
      opt.value       = b.slug;
      opt.textContent = b.name;
      sel.appendChild(opt);
    });
  } catch (e) {
    mostrarError('Error al cargar las marcas: ' + e.message);
  }
}

// ── Fechas por defecto: ultimos 7 dias ───────────────────────────────────────

function setDefaultDates() {
  var today = new Date();
  var week  = new Date(today);
  week.setDate(today.getDate() - 6);

  function toISO(d) {
    return d.toISOString().slice(0, 10);
  }

  document.getElementById('input-date-from').value = toISO(week);
  document.getElementById('input-date-to').value   = toISO(today);
}

// ── Validacion del formulario ─────────────────────────────────────────────────

function validarFormulario() {
  var slug     = document.getElementById('select-marca').value;
  var dateFrom = document.getElementById('input-date-from').value;
  var dateTo   = document.getElementById('input-date-to').value;
  var kpis     = Array.from(document.querySelectorAll('input[name="kpi"]:checked'))
                      .map(function (cb) { return cb.value; });

  if (!slug)          { mostrarError('Selecciona una marca.'); return null; }
  if (!dateFrom)      { mostrarError('Ingresa la fecha de inicio.'); return null; }
  if (!dateTo)        { mostrarError('Ingresa la fecha de fin.'); return null; }
  if (dateTo < dateFrom) { mostrarError('La fecha fin debe ser >= fecha inicio.'); return null; }

  var diff = (new Date(dateTo) - new Date(dateFrom)) / (1000 * 60 * 60 * 24);
  if (diff > 90) { mostrarError('El rango maximo es 90 dias.'); return null; }
  if (!kpis.length) { mostrarError('Selecciona al menos un KPI.'); return null; }

  return {
    slug:       slug,
    date_from:  dateFrom,
    date_to:    dateTo,
    kpis:       kpis,
    include_ai: document.getElementById('toggle-ai').checked,
    language:   document.querySelector('input[name="language"]:checked').value,
  };
}

// ── Mensajes de progreso ciclicos ─────────────────────────────────────────────

function startProgress(includeAi) {
  var msgs = includeAi ? _progressMessages.withAi : _progressMessages.base;
  var idx  = 0;
  var el   = document.getElementById('progress-text');
  el.textContent = msgs[0];

  _progressTimer = setInterval(function () {
    idx = Math.min(idx + 1, msgs.length - 1);
    el.textContent = msgs[idx];
  }, includeAi ? 3000 : 1500);
}

function stopProgress() {
  if (_progressTimer) { clearInterval(_progressTimer); _progressTimer = null; }
}

// ── Generacion del reporte ────────────────────────────────────────────────────

async function generarReporte() {
  ocultarAlerta();
  var params = validarFormulario();
  if (!params) return;

  var btn     = document.getElementById('btn-generate');
  var spinner = document.getElementById('section-spinner');
  var success = document.getElementById('section-success');

  btn.disabled = true;
  spinner.style.display = '';
  success.style.display = 'none';
  startProgress(params.include_ai);

  try {
    var slug = params.slug;
    delete params.slug;
    await generateReport(slug, params);
    mostrarExito('Reporte generado correctamente.');
  } catch (e) {
    mostrarError('Error al generar el reporte: ' + e.message);
  } finally {
    stopProgress();
    btn.disabled = false;
    spinner.style.display = 'none';
  }
}

// ── Helpers de UI ─────────────────────────────────────────────────────────────

function mostrarError(msg) {
  var div = document.getElementById('section-error');
  var txt = document.getElementById('error-message');
  if (div && txt) { txt.textContent = msg; div.style.display = ''; }
  console.error('[Reportes]', msg);
}

function mostrarExito(msg) {
  var div = document.getElementById('section-success');
  var txt = document.getElementById('success-message');
  if (div && txt) {
    txt.textContent = msg;
    div.style.display = '';
    setTimeout(function () { div.style.display = 'none'; }, 3000);
  }
}

function ocultarAlerta() {
  var div = document.getElementById('section-error');
  if (div) div.style.display = 'none';
}
