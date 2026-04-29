/**
 * Lógica de la página de gestión de marcas.
 * Carga la lista, permite toggle de token y desactivación con confirmación.
 */

document.addEventListener('DOMContentLoaded', function () {
  // Verificar sesion activa al cargar la pagina
  fetch('/api/v1/auth/check', { credentials: 'same-origin' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.authenticated) window.location.href = '/admin/login.html';
    })
    .catch(function() { window.location.href = '/admin/login.html'; });


  cargarMarcas();

});

async function cargarMarcas() {
  try {
    var json = await adminGetBrands();
    renderTablaMarcas(json.data || []);
  } catch (e) {
    mostrarError(e.message || 'Error al cargar las marcas.');
  }
}

function renderTablaMarcas(brands) {
  var tbody = document.getElementById('tbody-marcas');
  if (!tbody) return;

  if (!brands.length) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-a">No hay marcas registradas.</td></tr>';
    return;
  }

  var html = '';
  brands.forEach(function (b) {
    var logo = b.logo_url
      ? '<img src="' + esc(b.logo_url) + '" alt="" style="height:28px;width:28px;object-fit:contain;border-radius:3px;" onerror="this.style.display=\'none\'">'
      : '<span class="text-muted">—</span>';

    var colorDot = '<span class="pca-color-dot" style="background:' + esc(b.primary_color) + ';"></span> ' +
                   '<small class="text-muted">' + esc(b.primary_color) + '</small>';

    // Token oculto por defecto con toggle
    var tokenId  = 'token-' + b.slug;
    var tokenEl  = '<span id="' + tokenId + '" class="pca-token-hidden">••••••••••••••••</span>' +
                   '<span class="pca-token-full" id="' + tokenId + '-full" style="display:none;font-size:0.75rem;word-break:break-all;">' + esc(b.api_token) + '</span>' +
                   ' <button class="btn btn-xs white b-a" onclick="toggleToken(\'' + esc(b.slug) + '\')" title="Mostrar/ocultar token">' +
                   '<i class="ion-eye" id="eye-' + esc(b.slug) + '"></i></button>';

    var estadoBadge = b.active
      ? '<span class="label label-success">Activa</span>'
      : '<span class="label label-default">Inactiva</span>';

    var fechaCreacion = b.created_at ? b.created_at.slice(0, 10) : '—';

    html += '<tr' + (b.active ? '' : ' class="text-muted"') + '>' +
      '<td>' + logo + '</td>' +
      '<td><strong>' + esc(b.name) + '</strong><br><small class="text-muted">' + esc(b.slug) + '</small></td>' +
      '<td>' + colorDot + '</td>' +
      '<td><small>' + esc(b.universe_id || '—') + '</small></td>' +
      '<td>' + tokenEl + '</td>' +
      '<td>' + estadoBadge + '</td>' +
      '<td><small>' + fechaCreacion + '</small></td>' +
      '<td class="text-nowrap">' +
        '<div class="btn-group btn-group-sm">' +
          '<a href="/dashboard/?brand=' + esc(b.slug) + '" target="_blank" class="btn white b-a btn-sm" title="Ver dashboard"><i class="ion-ios-analytics"></i></a>' +
          '<a href="/admin/marca-detalle.html?slug=' + esc(b.slug) + '" class="btn white b-a btn-sm" title="Editar"><i class="ion-edit"></i></a>' +
          '<a href="/admin/script-generator.html?slug=' + esc(b.slug) + '" class="btn white b-a btn-sm" title="Ver Script"><i class="ion-code"></i></a>' +
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

// ─── TOGGLE DE TOKEN ──────────────────────────────────────────────────────

function toggleToken(slug) {
  var hidden = document.getElementById('token-' + slug);
  var full   = document.getElementById('token-' + slug + '-full');
  var eye    = document.getElementById('eye-' + slug);
  if (!hidden || !full) return;

  var visible = full.style.display !== 'none';
  hidden.style.display = visible ? ''      : 'none';
  full.style.display   = visible ? 'none'  : '';
  if (eye) {
    eye.className = visible ? 'ion-eye' : 'ion-eye-disabled';
  }
}

// ─── HELPERS ──────────────────────────────────────────────────────────────

function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function mostrarError(msg) {
  var div = document.getElementById('section-error');
  var txt = document.getElementById('error-message');
  if (div && txt) { txt.textContent = msg; div.classList.remove('hide'); }
  console.error('[Admin]', msg);
}

function mostrarExito(msg) {
  var div = document.getElementById('section-success');
  var txt = document.getElementById('success-message');
  if (div && txt) { txt.textContent = msg; div.classList.remove('hide'); }
  setTimeout(function() { if (div) div.classList.add('hide'); }, 3000);
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
