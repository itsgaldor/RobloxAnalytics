/**
 * Aplica la configuración visual de la marca al DOM.
 * Modifica logo, banner, nombre y color primario del sidebar.
 * @param {{slug, name, logo_url, banner_url, primary_color}} config
 */
function applyWhitelabel(config) {
  // 1. Título de la pestaña
  document.title = config.name + ' — Peru City Analytics';

  // 2. Logo en el sidebar
  var logo = document.getElementById('brand-logo');
  if (logo) {
    logo.src = config.logo_url || '';
    logo.alt = config.name;
  }

  // 3. Banner y nombre en el header
  var banner = document.getElementById('brand-banner');
  if (banner) {
    banner.src = config.banner_url || '';
    banner.alt = config.name;
  }
  var brandName = document.getElementById('brand-name');
  if (brandName) {
    brandName.textContent = config.name;
  }

  // 4. Color primario — inyectar <style> dinámico en <head>
  // Remover tema previo si existe (para soportar cambios de marca sin recargar)
  var existingStyle = document.getElementById('pca-brand-theme');
  if (existingStyle) existingStyle.remove();

  var color = config.primary_color || '#6C3ADE';

  // Derivar una versión más oscura (~15%) para hover/active
  function darken(hex, pct) {
    var n = parseInt(hex.slice(1), 16);
    var r = Math.max(0, ((n >> 16) & 0xff) - Math.round(255 * pct));
    var g = Math.max(0, ((n >>  8) & 0xff) - Math.round(255 * pct));
    var b = Math.max(0, ((n >>  0) & 0xff) - Math.round(255 * pct));
    return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
  }
  var colorDark = darken(color.length === 7 ? color : '#6C3ADE', 0.12);

  var style = document.createElement('style');
  style.id = 'pca-brand-theme';
  style.textContent = `
    :root { --brand-primary: ${color}; --brand-primary-dark: ${colorDark}; }

    /* Sidebar — forzar color de marca */
    #aside,
    .navside,
    div.app > aside,
    aside.navside {
      background-color: ${color} !important;
      border-right: none !important;
    }

    /* Links del nav */
    .navside .nav li a,
    aside .nav li a {
      color: rgba(255,255,255,0.80) !important;
    }
    .navside .nav li a:hover,
    aside .nav li a:hover,
    .navside .nav li.active a,
    aside .nav li.active a {
      color: #ffffff !important;
      background-color: rgba(0,0,0,0.18) !important;
    }

    /* Íconos del nav */
    .navside .nav li a i,
    aside .nav li a i {
      color: rgba(255,255,255,0.80) !important;
    }
    .navside .nav li a:hover i,
    aside .nav li a:hover i,
    .navside .nav li.active a i,
    aside .nav li.active a i {
      color: #ffffff !important;
    }

    /* Logo / brand en sidebar */
    .navside .navbar-brand,
    aside .navbar-brand {
      color: #ffffff !important;
      border-bottom: 1px solid rgba(255,255,255,0.15) !important;
    }

    /* Nav header label */
    .navside .nav-header span,
    aside .nav-header span {
      color: rgba(255,255,255,0.45) !important;
    }

    /* Scrollbar del sidebar */
    .navside::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
    .navside::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); }

    /* PACE bar */
    .pace .pace-progress {
      background-color: #ffffff !important;
    }

    /* Botón de rango activo */
    .btn-theme-active {
      background-color: ${color} !important;
      color: #ffffff !important;
      border-color: ${color} !important;
    }

    /* Toggle de métrica activo */
    .active-metric {
      background-color: ${color} !important;
      color: #ffffff !important;
      border-color: ${color} !important;
    }

    /* Utilidades de marca */
    .text-brand { color: ${color} !important; }
    .bg-brand   { background-color: ${color} !important; }

    /* Dark mode: sidebar mantiene color de marca */
    .dark #aside,
    .dark .navside,
    .dark aside.navside {
      background-color: ${color} !important;
    }
  `;
  document.head.appendChild(style);
}
