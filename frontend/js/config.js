/**
 * Configuración global de Peru City Analytics.
 * En producción (Railway) el frontend y backend comparten dominio → /api/v1
 * En local apunta a localhost:8000.
 */
const PCA_CONFIG = {
  apiBase: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api/v1'
    : '/api/v1',
  defaultRange: 'week'
};
