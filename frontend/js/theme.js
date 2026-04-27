/**
 * Toggle de tema claro/oscuro para Peru City Analytics.
 * Usa la clase 'dark' en div#app, igual que la plantilla Aside internamente.
 */

var THEME_KEY = 'pca-theme';

/**
 * Aplica el tema guardado en localStorage ANTES del primer render
 * para evitar el flash de contenido sin estilo (FOUC).
 */
function initTheme() {
  var saved = localStorage.getItem(THEME_KEY);
  var theme = saved !== null ? saved : 'dark';  // dark es el default
  var app = document.getElementById('app') ||
            document.querySelector('.app') ||
            document.querySelector('[id="app"]');
  if (!app) return;

  app.classList.toggle('dark', theme === 'dark');
  _updateThemeIcon(theme === 'dark');
}

/**
 * Alterna entre modo claro y oscuro y persiste la elección.
 */
function toggleTheme() {
  var app = document.getElementById('app');
  if (!app) return;

  var isDark = app.classList.toggle('dark');
  localStorage.setItem(THEME_KEY, isDark ? 'dark' : '');
  _updateThemeIcon(isDark);
}

/**
 * Actualiza el ícono del botón de tema.
 * @param {boolean} isDark
 */
function _updateThemeIcon(isDark) {
  var icon = document.querySelector('#btn-theme-toggle i');
  if (!icon) return;
  // Sol = modo claro, luna = modo oscuro
  icon.className = isDark ? 'ion-ios-moon' : 'ion-ios-sunny';
}

// Aplicar tema inmediatamente al cargar el script (antes de DOMContentLoaded)
// para que el fondo oscuro aparezca antes de que se pinte el contenido
(function () {
  var saved = localStorage.getItem(THEME_KEY);
  var theme = saved !== null ? saved : 'dark';  // dark es el default
  if (theme === 'dark') {
    document.documentElement.classList.add('dark-init');
  }
})();

/**
 * Sidebar colapsable — toggle + persistencia en localStorage.
 */
function initSidebar() {
  // Restaurar preferencia guardada
  var pref = localStorage.getItem('pca-sidebar');
  var app = document.querySelector('.app') || document.getElementById('app');
  if (app && pref === 'folded') {
    app.classList.add('folded');
  }

  // Conectar botón hamburguesa del navbar
  var toggleBtn = document.querySelector('[data-toggle="modal"][data-target="#aside"], .navbar-toggle, #btn-sidebar-toggle');
  if (toggleBtn && app) {
    // Reemplazar el comportamiento modal por el toggle de folded
    toggleBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      var isFolded = app.classList.toggle('folded');
      localStorage.setItem('pca-sidebar', isFolded ? 'folded' : 'expanded');
    }, true);
  }
}
