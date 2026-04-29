/**
 * Lógica del resumen global del backoffice.
 * Carga todas las marcas, calcula totales y renderiza KPIs + tabla.
 */

var _refreshTimer = null;

document.addEventListener('DOMContentLoaded', function () {
  // Verificar sesion activa al cargar la pagina
  fetch('/api/v1/auth/check', { credentials: 'same-origin' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.authenticated) window.location.href = '/admin/login.html';
    })
    .catch(function() { window.location.href = '/admin/login.html'; });


  cargarResumen();
  // Auto-refresh cada 5 minutos
  _refreshTimer = setInterval(cargarResumen, 5 * 60 * 1000);
});

async function cargarResumen() {
  try {
    var json = await adminGetBrands();
    var brands = json.data || [];
    renderKPIsGlobales(brands);
    renderTablaMarcas(brands);
  } catch (e) {
    mostrarError(e.message || 'Error al cargar las marcas.');
  }
}

// ─── KPIs GLOBALES ────────────────────────────────────────────────────────

function renderKPIsGlobales(brands) {
  var activas       = brands.filter(function (b) { return b.active; }).length;
  var totalSesiones = 0;
  var totalDau      = 0;
  var totalHoras    = 0;

  brands.forEach(function (b) {
    if (!b.week_metrics) return;
    totalSesiones += b.week_metrics.sessions  || 0;
    totalDau      += b.week_metrics.dau        || 0;
    totalHoras    += b.week_metrics.total_hours || 0;
  });

  var kpis = [
    { valor: activas,                           label: 'Marcas activas',            icono: 'ion-ios-people' },
    { valor: fmt(totalSesiones),                label: 'Sesiones esta semana',       icono: 'ion-ios-pulse' },
    { valor: fmt(Math.round(totalDau)),         label: 'DAU promedio global',        icono: 'ion-person' },
    { valor: fmt(Math.round(totalHoras)) + 'h', label: 'Horas totales esta semana', icono: 'ion-ios-timer' },
  ];

  var section = document.getElementById('section-kpis');
  if (!section) return;

  var html = '';
  kpis.forEach(function (k) {
    html += '<div class="col-xs-6 col-sm-3 b-r b-b">' +
              '<div class="padding text-center">' +
                '<span class="text-muted"><i class="' + k.icono + ' text-muted" style="font-size:1.4rem;"></i></span>' +
                '<h2 class="_600 m-t-sm">' + k.valor + '</h2>' +
                '<p class="text-muted m-b-0">' + k.label + '</p>' +
              '</div>' +
            '</div>';
  });
  section.innerHTML = html;
}

// ─── TABLA DE MARCAS ──────────────────────────────────────────────────────

function renderTablaMarcas(brands) {
  var tbody = document.getElementById('tbody-brands');
  if (!tbody) return;

  if (!brands.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-a">No hay marcas registradas.</td></tr>';
    return;
  }

  var html = '';
  brands.forEach(function (b) {
    var m      = b.week_metrics || {};
    var badge  = renderHealthBadge(b.health, b.last_event_at);
    var logo   = b.logo_url
      ? '<img src="' + esc(b.logo_url) + '" alt="' + esc(b.name) + '" style="height:28px;width:28px;object-fit:contain;border-radius:3px;">'
      : '<span class="text-muted">—</span>';

    html += '<tr>' +
      '<td>' + logo + '</td>' +
      '<td><strong>' + esc(b.name) + '</strong><br><small class="text-muted">' + esc(b.slug) + '</small></td>' +
      '<td>' + fmt(m.sessions)                         + '</td>' +
      '<td>' + fmt(Math.round(m.dau || 0))             + '</td>' +
      '<td>' + fmtMin(m.avg_session_minutes)           + '</td>' +
      '<td>' + fmt(Math.round(m.total_hours || 0)) + 'h' + '</td>' +
      '<td>' + badge + '</td>' +
      '<td class="text-nowrap">' +
        '<div class="btn-group btn-group-sm">' +
          '<a href="/dashboard/?brand=' + esc(b.slug) + '" target="_blank" ' +
             'class="btn white b-a btn-sm" title="Ver dashboard">' +
            '<i class="ion-ios-analytics"></i>' +
          '</a>' +
          '<a href="/admin/marca-detalle.html?slug=' + esc(b.slug) + '" ' +
             'class="btn white b-a btn-sm" title="Editar">' +
            '<i class="ion-edit"></i>' +
          '</a>' +
          '<a href="/admin/script-generator.html?slug=' + esc(b.slug) + '" ' +
             'class="btn white b-a btn-sm" title="Ver Script">' +
            '<i class="ion-code"></i>' +
          '</a>' +
          '<button onclick="confirmDelete(\'' + esc(b.slug) + '\',\'' + esc(b.name) + '\')" ' +
             'class="btn btn-sm" title="Eliminar marca" ' +
             'style="background:#fee2e2;color:#dc2626;border:1px solid #fecaca;">' +
            '<i class="ion-trash-a"></i>' +
          '</button>' +
        '</div>' +
      '</td>' +
    '</tr>';
  });

  tbody.innerHTML = html;
}

// ─── HELPERS ──────────────────────────────────────────────────────────────



function fmt(n) {
  if (n === null || n === undefined || isNaN(n)) return '—';
  return Math.round(n).toLocaleString('es-PE');
}

function fmtMin(mins) {
  if (!mins && mins !== 0) return '—';
  mins = parseFloat(mins);
  if (mins < 60) return Math.round(mins) + ' min';
  var h = Math.floor(mins / 60);
  var m = Math.round(mins % 60);
  return h + 'h' + (m > 0 ? ' ' + m + 'min' : '');
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function mostrarError(msg) {
  var div = document.getElementById('section-error');
  var txt = document.getElementById('error-message');
  if (div && txt) { txt.textContent = msg; div.classList.remove('hide'); }
  console.error('[Admin]', msg);
}

function renderHealthBadge(health, lastEventAt) {
  var map = {
    ok:      { color: '#22c55e', label: 'Activo',              icon: 'ion-ios-checkmark-circle' },
    warning: { color: '#f59e0b', label: 'Sin datos recientes',  icon: 'ion-ios-alert'            },
    offline: { color: '#ef4444', label: 'Desconectado',         icon: 'ion-ios-close-circle'     }
  };
  var cfg = map[health] || map.offline;
  var timeAgo = '';
  if (lastEventAt) {
    var diff = Math.floor((Date.now() - new Date(lastEventAt)) / 60000);
    if (diff < 60)        timeAgo = ' · hace ' + diff + 'm';
    else if (diff < 1440) timeAgo = ' · hace ' + Math.floor(diff / 60) + 'h';
    else                  timeAgo = ' · hace ' + Math.floor(diff / 1440) + 'd';
  }
  return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:99px;' +
    'font-size:11px;font-weight:500;background:' + cfg.color + '22;color:' + cfg.color + ';">' +
    '<i class="' + cfg.icon + '"></i>' + cfg.label + timeAgo + '</span>';
}

// ─── MODAL ELIMINAR MARCA ─────────────────────────────────────────────────

var _deleteTargetSlug = '';

function confirmDelete(slug, name) {
  _deleteTargetSlug = slug;
  document.getElementById('modal-delete-text').textContent =
    '\u00bfEst\u00e1s seguro de que quer\u00e9s eliminar "' + name + '"?';
  document.getElementById('modal-delete-slug').textContent = slug;
  document.getElementById('modal-delete-confirm').value = '';
  document.getElementById('btn-confirm-delete').disabled = true;
  document.getElementById('btn-confirm-delete').style.opacity = '0.4';
  document.getElementById('modal-delete').style.display = 'flex';

  document.getElementById('modal-delete-confirm').oninput = function () {
    var match = this.value.trim() === _deleteTargetSlug;
    document.getElementById('btn-confirm-delete').disabled = !match;
    document.getElementById('btn-confirm-delete').style.opacity = match ? '1' : '0.4';
  };
}

function closeDeleteModal() {
  document.getElementById('modal-delete').style.display = 'none';
  _deleteTargetSlug = '';
}

async function executeDelete() {
  if (!_deleteTargetSlug) return;
  var btn = document.getElementById('btn-confirm-delete');
  btn.disabled = true;
  btn.innerHTML = '<i class="ion-load-c"></i> Eliminando…';
  try {
    await adminDeleteBrand(_deleteTargetSlug);
    closeDeleteModal();
    showToast('Marca eliminada correctamente', 'success');
    if (typeof cargarResumen === 'function') await cargarResumen();
    if (typeof cargarMarcas  === 'function') await cargarMarcas();
  } catch (e) {
    showToast('Error al eliminar: ' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '<i class="ion-trash-a"></i> Eliminar marca';
  }
}

function showToast(message, type) {
  var toast = document.createElement('div');
  toast.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:3000;' +
    'padding:12px 20px;border-radius:8px;font-size:13px;font-weight:500;' +
    'box-shadow:0 4px 20px rgba(0,0,0,0.15);' +
    'background:' + (type === 'success' ? '#22c55e' : '#ef4444') + ';' +
    'color:#fff;';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(function () { toast.remove(); }, 3000);
}
