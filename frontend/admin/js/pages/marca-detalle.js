/**
 * Lógica de la página de crear/editar marca.
 * Detecta el modo según ?slug= en la URL.
 */

var _modo     = 'crear';   // 'crear' | 'editar'
var _slug     = '';
var _tokenVal = '';        // valor actual del token (modo editar)

document.addEventListener('DOMContentLoaded', async function () {
  // Verificar sesion activa al cargar la pagina
  fetch('/api/v1/auth/check', { credentials: 'same-origin' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.authenticated) window.location.href = '/admin/login.html';
    })
    .catch(function() { window.location.href = '/admin/login.html'; });


  var params = new URLSearchParams(window.location.search);
  _slug = params.get('slug') || '';
  _modo = _slug ? 'editar' : 'crear';

  // Inicializar controles de color
  initColor();
  // Inicializar previews de imagen
  initImagePreviews();
  // Slug: validación live (solo en crear)
  initSlugValidation();

  if (_modo === 'editar') {
    document.getElementById('form-titulo').textContent  = 'Cargando…';
    document.getElementById('header-titulo').textContent = 'Cargando…';
    // Slug no editable en modo editar
    var slugInput = document.getElementById('input-slug');
    slugInput.value    = _slug;
    slugInput.disabled = true;
    document.getElementById('group-slug').style.opacity = '0.6';

    try {
      var json = await adminGetBrand(_slug);
      poblarFormulario(json.data);
    } catch (e) {
      mostrarError('No se pudo cargar la marca: ' + e.message);
    }
  }

  // Guardar
  document.getElementById('form-marca').addEventListener('submit', async function (e) {
    e.preventDefault();
    await guardar();
  });

  // Sección token (modo editar)
  if (_modo === 'editar') {
    document.getElementById('section-token').style.display = '';
    initTokenControls();
  }
});

// ─── POBLAR EN MODO EDITAR ────────────────────────────────────────────────

function poblarFormulario(brand) {
  document.getElementById('form-titulo').textContent   = 'Editando: ' + brand.name;
  document.getElementById('header-titulo').textContent = 'Editando: ' + brand.name;

  document.getElementById('input-name').value    = brand.name    || '';
  document.getElementById('input-slug').value    = brand.slug    || '';
  document.getElementById('input-universe').value = brand.universe_id || '';
  document.getElementById('input-logo').value    = brand.logo_url   || '';
  document.getElementById('input-banner').value  = brand.banner_url || '';

  // Color
  var hex = brand.primary_color || '#000000';
  document.getElementById('input-color-hex').value   = hex;
  document.getElementById('input-color-picker').value = hex;
  document.getElementById('color-preview-box').style.background = hex;

  // Preview logo/banner si hay URL
  triggerImagePreview('input-logo', 'logo-preview', 'logo-img');
  triggerImagePreview('input-banner', 'banner-preview', 'banner-img');

  // Token (oculto)
  _tokenVal = brand.api_token || '';
  document.getElementById('token-display').textContent = '••••••••••••••••';

  // Botones extra
  var btnDash   = document.getElementById('btn-ver-dashboard');
  var btnScript = document.getElementById('btn-ver-script');
  if (btnDash)   { btnDash.href   = '/dashboard/?brand=' + encodeURIComponent(brand.slug); btnDash.style.display   = ''; }
  if (btnScript) { btnScript.href = '/admin/script-generator.html?slug=' + encodeURIComponent(brand.slug); btnScript.style.display = ''; }
}

// ─── GUARDAR ──────────────────────────────────────────────────────────────

async function guardar() {
  ocultarError();
  if (!validar()) return;

  var btn = document.getElementById('btn-guardar');
  btn.disabled    = true;
  btn.textContent = 'Guardando…';

  var data = {
    name:          document.getElementById('input-name').value.trim(),
    primary_color: document.getElementById('input-color-hex').value.trim(),
    logo_url:      document.getElementById('input-logo').value.trim()    || null,
    banner_url:    document.getElementById('input-banner').value.trim()  || null,
    universe_id:   document.getElementById('input-universe').value.trim() || null,
  };

  try {
    if (_modo === 'crear') {
      data.slug = document.getElementById('input-slug').value.trim();
      await adminCreateBrand(data);
    } else {
      await adminUpdateBrand(_slug, data);
    }
    window.location.href = '/admin/marcas.html';
  } catch (e) {
    if (e.status === 409) {
      // Slug duplicado
      var slugErr = document.getElementById('slug-error');
      if (slugErr) { slugErr.textContent = 'Este slug ya existe.'; slugErr.style.display = ''; }
    } else {
      mostrarError(e.message || 'Error al guardar.');
    }
    btn.disabled    = false;
    btn.textContent = 'Guardar';
  }
}

// ─── VALIDACIONES ─────────────────────────────────────────────────────────

function validar() {
  var ok    = true;
  var name  = document.getElementById('input-name').value.trim();
  var color = document.getElementById('input-color-hex').value.trim();

  if (!name) {
    mostrarError('El nombre es obligatorio.');
    ok = false;
  }
  if (!color.match(/^#[0-9A-Fa-f]{6}$/)) {
    document.getElementById('color-error').textContent = 'Color inválido. Usá formato #RRGGBB.';
    document.getElementById('color-error').style.display = '';
    ok = false;
  }
  if (_modo === 'crear') {
    var slug = document.getElementById('input-slug').value.trim();
    if (!slug || !slug.match(/^[a-z0-9-]+$/)) {
      var slugErr = document.getElementById('slug-error');
      slugErr.textContent = 'El slug solo puede tener letras minúsculas, números y guiones.';
      slugErr.style.display = '';
      ok = false;
    }
  }
  return ok;
}

// ─── COLOR ────────────────────────────────────────────────────────────────

function initColor() {
  var picker  = document.getElementById('input-color-picker');
  var hexInput = document.getElementById('input-color-hex');
  var preview  = document.getElementById('color-preview-box');

  picker.addEventListener('input', function () {
    hexInput.value = picker.value;
    preview.style.background = picker.value;
    document.getElementById('color-error').style.display = 'none';
  });

  hexInput.addEventListener('input', function () {
    var val = hexInput.value.trim();
    document.getElementById('color-error').style.display = 'none';
    if (val.match(/^#[0-9A-Fa-f]{6}$/)) {
      picker.value = val;
      preview.style.background = val;
    }
  });
}

// ─── SLUG LIVE VALIDATION ─────────────────────────────────────────────────

function initSlugValidation() {
  if (_modo !== 'crear') return;
  var input   = document.getElementById('input-slug');
  var preview = document.getElementById('slug-preview');
  var error   = document.getElementById('slug-error');
  input.addEventListener('input', function () {
    var val = input.value.trim();
    error.style.display = 'none';
    if (val && val.match(/^[a-z0-9-]+$/)) {
      preview.textContent = 'URL: /dashboard/?brand=' + val;
    } else if (val) {
      error.textContent   = 'Solo letras minúsculas (a-z), números y guiones.';
      error.style.display = '';
      preview.textContent = '';
    } else {
      preview.textContent = '';
    }
  });
}

// ─── PREVIEWS DE IMAGEN ───────────────────────────────────────────────────

function initImagePreviews() {
  ['logo', 'banner'].forEach(function (tipo) {
    var input = document.getElementById('input-' + tipo);
    input.addEventListener('input', function () {
      triggerImagePreview('input-' + tipo, tipo + '-preview', tipo + '-img');
    });
  });
}

function triggerImagePreview(inputId, previewId, imgId) {
  var val     = document.getElementById(inputId).value.trim();
  var preview = document.getElementById(previewId);
  var img     = document.getElementById(imgId);
  if (val) {
    img.src = val;
    preview.style.display = '';
  } else {
    preview.style.display = 'none';
  }
}

// ─── TOKEN CONTROLS ───────────────────────────────────────────────────────

function initTokenControls() {
  var tokenDisplay = document.getElementById('token-display');
  var eyeIcon      = document.getElementById('eye-token');
  var visible      = false;

  // Toggle visibilidad
  document.getElementById('btn-toggle-token').addEventListener('click', function () {
    visible = !visible;
    tokenDisplay.textContent = visible ? _tokenVal : '••••••••••••••••';
    eyeIcon.className        = visible ? 'ion-eye-disabled' : 'ion-eye';
  });

  // Copiar token actual
  document.getElementById('btn-copy-token').addEventListener('click', function () {
    if (!_tokenVal) return;
    navigator.clipboard.writeText(_tokenVal).then(function () {
      var btn = document.getElementById('btn-copy-token');
      var orig = btn.innerHTML;
      btn.innerHTML = '<i class="ion-checkmark"></i>';
      setTimeout(function () { btn.innerHTML = orig; }, 2000);
    });
  });

  // Abrir modal de regeneración
  document.getElementById('btn-regenerar').addEventListener('click', function () {
    $('#modal-regen').modal('show');
  });

  // Confirmar regeneración
  document.getElementById('btn-confirmar-regen').addEventListener('click', async function () {
    var btn = this;
    btn.disabled    = true;
    btn.textContent = 'Regenerando…';
    try {
      var json = await adminRegenerateToken(_slug);
      var newToken = json.data.api_token;
      _tokenVal = newToken;
      tokenDisplay.textContent = '••••••••••••••••';
      visible = false;
      eyeIcon.className = 'ion-eye';

      // Mostrar nuevo token
      document.getElementById('new-token-value').textContent = newToken;
      document.getElementById('new-token-box').style.display = '';

      $('#modal-regen').modal('hide');
    } catch (e) {
      mostrarError('Error al regenerar: ' + e.message);
    } finally {
      btn.disabled    = false;
      btn.textContent = 'Regenerar';
    }
  });

  // Copiar nuevo token
  document.getElementById('btn-copy-new-token').addEventListener('click', function () {
    var val = document.getElementById('new-token-value').textContent;
    if (!val) return;
    navigator.clipboard.writeText(val).then(function () {
      var btn = document.getElementById('btn-copy-new-token');
      var orig = btn.innerHTML;
      btn.innerHTML = '<i class="ion-checkmark"></i> Copiado';
      setTimeout(function () { btn.innerHTML = orig; }, 2000);
    });
  });
}

// ─── HELPERS ───────────────────────────────────────────────────────────���──

function mostrarError(msg) {
  var div = document.getElementById('section-error');
  var txt = document.getElementById('error-message');
  if (div && txt) { txt.textContent = msg; div.classList.remove('hide'); }
}

function ocultarError() {
  var div = document.getElementById('section-error');
  if (div) div.classList.add('hide');
  document.getElementById('color-error').style.display = 'none';
  document.getElementById('slug-error').style.display  = 'none';
}
