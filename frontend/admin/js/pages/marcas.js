/**
 * Lógica de la página de gestión de marcas.
 * Carga la lista, permite toggle de token y desactivación con confirmación.
 */

var _slugParaDesactivar = '';
var _nombreParaDesactivar = '';

document.addEventListener('DOMContentLoaded', function () {
  // Verificar sesion activa al cargar la pagina
  fetch('/api/v1/auth/check')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.authenticated) window.location.href = '/admin/login.html';
    })
    .catch(function() { window.location.href = '/admin/login.html'; });


  cargarMarcas();

  // Botón de confirmación en el modal
  document.getElementById('btn-confirmar-desactivar').addEventListener('click', async function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Desactivando…';
    try {
      await adminDeleteBrand(_slugParaDesactivar);
      $('#modal-desactivar').modal('hide');
      mostrarExito('Marca "' + _nombreParaDesactivar + '" desactivada correctamente.');
      await cargarMarcas();
    } catch (e) {
      mostrarError('Error al desactivar: ' + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Desactivar';
    }
  });
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
          '<a href="/admin/script-generator.html?slug=' + esc(b.slug) + '" class="btn white b-a btn-sm" title="Ver Script"><i class="ion-ios-code"></i></a>' +
          (b.active
            ? '<button class="btn btn-danger btn-sm" onclick="confirmarDesactivar(\'' + esc(b.slug) + '\',\'' + esc(b.name) + '\')" title="Desactivar"><i class="ion-close-round"></i></button>'
            : '') +
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

// ─── MODAL DE DESACTIVACIÓN ───────────────────────────────────────────────

function confirmarDesactivar(slug, nombre) {
  _slugParaDesactivar    = slug;
  _nombreParaDesactivar  = nombre;
  document.getElementById('modal-desactivar-texto').textContent =
    '¿Desactivar "' + nombre + '"? El dashboard dejará de ser accesible.';
  $('#modal-desactivar').modal('show');
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
  var div = document.getElement