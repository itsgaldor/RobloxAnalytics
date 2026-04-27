/**
 * Lógica del generador de Script de Roblox.
 * Carga las marcas, genera el script con el token embebido y permite
 * copiarlo o descargarlo como .lua.
 */

var _scriptActual = '';
var _slugActual   = '';
var _nombreActual = '';

document.addEventListener('DOMContentLoaded', async function () {
  // Verificar sesion activa al cargar la pagina
  fetch('/api/v1/auth/check')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.authenticated) window.location.href = '/admin/login.html';
    })
    .catch(function() { window.location.href = '/admin/login.html'; });


  await cargarMarcas();

  // Cambio de marca en el select
  document.getElementById('select-marca').addEventListener('change', async function () {
    var slug = this.value;
    if (!slug) return;
    await cargarScript(slug);
  });

  // Botón copiar
  document.getElementById('btn-copiar').addEventListener('click', copiarScript);

  // Botón descargar
  document.getElementById('btn-descargar').addEventListener('click', descargarScript);
});

// ─── CARGA DE MARCAS ──────────────────────────────────────────────────────

async function cargarMarcas() {
  try {
    var json   = await adminGetBrands();
    var brands = (json.data || []).filter(function (b) { return b.active; });
    var select = document.getElementById('select-marca');

    select.innerHTML = '<option value="">— Seleccioná una marca —</option>';
    brands.forEach(function (b) {
      var opt    = document.createElement('option');
      opt.value  = b.slug;
      opt.textContent = b.name + ' (' + b.slug + ')';
      select.appendChild(opt);
    });

    // Pre-seleccionar si viene ?slug en la URL
    var params = new URLSearchParams(window.location.search);
    var preSlug = params.get('slug');
    if (preSlug) {
      select.value = preSlug;
      if (select.value === preSlug) {
        await cargarScript(preSlug);
      }
    }
  } catch (e) {
    mostrarError('No se pudieron cargar las marcas: ' + e.message);
  }
}

// ─── GENERAR SCRIPT ───────────────────────────────────────────────────────

async function cargarScript(slug) {
  var boxScript       = document.getElementById('box-script');
  var boxInstrucciones = document.getElementById('box-instrucciones');
  var alertSeg        = document.getElementById('alert-seguridad');
  var pre             = document.getElementById('script-pre');

  // Estado de carga
  pre.textContent = '-- Generando script…';
  boxScript.style.display = '';

  try {
    var json = await adminGetScript(slug);
    var data = json.data;
    _scriptActual = data.script;
    _slugActual   = data.brand_slug;

    // Buscar nombre desde el select
    var select = document.getElementById('select-marca');
    _nombreActual = select.options[select.selectedIndex]
      ? select.options[select.selectedIndex].textContent.split(' (')[0]
      : slug;

    // Mostrar script
    pre.textContent = _scriptActual;
    document.getElementById('script-titulo').textContent = 'Script de Lua — ' + _nombreActual;

    // Instrucciones
    document.getElementById('verify-msg').textContent =
      '[PCA] Peru City Analytics activo — Marca: ' + _nombreActual;
    document.getElementById('link-dashboard').href =
      '/dashboard/?brand=' + encodeURIComponent(slug);
    document.getElementById('link-dashboard').textContent =
      'Ver dashboard de ' + _nombreActual;
    boxInstrucciones.style.display = '';

    // Aviso de seguridad
    document.getElementById('texto-seguridad').textContent =
      'Este Script contiene el API token de "' + _nombreActual + '". ' +
      'No compartirlo públicamente ni subirlo a repositorios de GitHub. ' +
      'Si el token se compromete, regenerarlo desde la edición de la marca.';
    alertSeg.style.display = '';

  } catch (e) {
    pre.textContent = '-- Error al generar el script: ' + e.message;
    mostrarError(e.message);
  }
}

// ─── COPIAR ───────────────────────────────────────────────────────────────

function copiarScript() {
  if (!_scriptActual) return;
  var btn = document.getElementById('btn-copiar');
  navigator.clipboard.writeText(_scriptActual).then(function () {
    var orig = btn.innerHTML;
    btn.innerHTML = '<i class="ion-checkmark"></i> ¡Copiado! ✓';
    setTimeout(function () { btn.innerHTML = orig; }, 2000);
  }).catch(function () {
    // Fallback para navegadores sin clipboard API
    var textarea = document.createElement('textarea');
    textarea.value = _scriptActual;
    textarea.style.position = 'fixed';
    textarea.style.opacity  = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    var orig = btn.innerHTML;
    btn.innerHTML = '<i class="ion-checkmark"></i> ¡Copiado! ✓';
    setTimeout(function () { btn.innerHTML = orig; }, 2000);
  });
}

// ─── DESCARGAR ────────────────────────────────────────────────────────────

function descargarScript() {
  if (!_scriptActual) return;

  var hoy      = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  var filename = 'pca_' + (_slugActual || 'script') + '_' + hoy + '.lua';
  var blob     = new Blob([_scriptActual], { type: 'text/plain;charset=utf-8' });
  var url      = URL.createObjectURL(blob);

  var a    = document.createElement('a');
  a.href   = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── HELPERS ──────────────────────────────────────────────────────────────

function mostrarError(msg) {
  var div = document.getElementById('section-error');
  var txt = document.getElementById('error-message');
  if (div && txt) { txt.textContent = msg; div.classList.remove('hide'); }
  console.error('[Admin Script Generator]', msg);
}
