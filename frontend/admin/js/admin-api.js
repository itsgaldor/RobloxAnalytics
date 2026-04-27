/**
 * admin-api.js — Módulo de comunicación con el backend para el backoffice.
 * Todas las funciones son async y usan el mismo PCA_CONFIG.apiBase del dashboard.
 */

/**
 * Helper interno para fetch con manejo de errores consistente.
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<any>} JSON parseado
 */
async function _adminFetch(url, options) {
  try {
    const res = await fetch(url, options);
    const json = await res.json();
    if (!res.ok) {
      const msg = (json && json.error) ? json.error : `Error ${res.status}`;
      const err = new Error(msg);
      err.status = res.status;
      err.body   = json;
      throw err;
    }
    return json;
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('No se pudo conectar con el servidor.');
    }
    throw err;
  }
}

/**
 * Lista todas las marcas con métricas de la semana y health status.
 * @returns {Promise<{data: Array}>}
 */
async function adminGetBrands() {
  return _adminFetch(`${PCA_CONFIG.apiBase}/admin/brands`);
}

/**
 * Detalle completo de una marca.
 * @param {string} slug
 * @returns {Promise<{data: Object}>}
 */
async function adminGetBrand(slug) {
  return _adminFetch(`${PCA_CONFIG.apiBase}/admin/brands/${encodeURIComponent(slug)}`);
}

/**
 * Crear nueva marca.
 * @param {{name, slug, primary_color, logo_url?, banner_url?, universe_id?}} data
 * @returns {Promise<{data: Object}>}
 */
async function adminCreateBrand(data) {
  return _adminFetch(`${PCA_CONFIG.apiBase}/admin/brands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

/**
 * Actualizar una marca existente.
 * @param {string} slug
 * @param {{name?, primary_color?, logo_url?, banner_url?, universe_id?}} data
 * @returns {Promise<{data: Object}>}
 */
async function adminUpdateBrand(slug, data) {
  return _adminFetch(`${PCA_CONFIG.apiBase}/admin/brands/${encodeURIComponent(slug)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

/**
 * Soft delete de una marca (active=false).
 * @param {string} slug
 * @returns {Promise<{data: Object}>}
 */
async function adminDeleteBrand(slug) {
  return _adminFetch(`${PCA_CONFIG.apiBase}/admin/brands/${encodeURIComponent(slug)}`, {
    method: 'DELETE',
  });
}

/**
 * Regenerar el api_token de una marca.
 * @param {string} slug
 * @returns {Promise<{data: {slug, api_token, regenerated_at}}>}
 */
async function adminRegenerateToken(slug) {
  return _adminFetch(
    `${PCA_CONFIG.apiBase}/admin/brands/${encodeURIComponent(slug)}/regenerate-token`,
    { method: 'POST' }
  );
}

/**
 * Obtener el Script de Lua generado para una marca.
 * @param {string} slug
 * @returns {Promise<{data: {script, brand_slug, api_token, generated_at}}>}
 */
async function adminGetScript(slug) {
  return _adminFetch(
    `${PCA_CONFIG.apiBase}/admin/brands/${encodeURIComponent(slug)}/script`
  );
}

/**
 * Genera un reporte PDF y lo descarga directamente en el browser.
 * @param {string} slug
 * @param {{date_from, date_to, kpis, include_ai, language}} params
 */
async function generateReport(slug, params) {
  const response = await fetch(
    `${PCA_CONFIG.apiBase}/admin/brands/${encodeURIComponent(slug)}/report`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }
  );

  if (!response.ok) {
    let msg = `Error ${response.status}`;
    try {
      const err = await response.json();
      msg = (err && err.detail && err.detail.error) ? err.detail.error
           : (err && err.detail)                    ? String(err.detail)
           : msg;
    } catch (_) {}
    const e = new Error(msg);
    e.status = response.status;
    throw e;
  }

  // Descargar el blob PDF directamente
  const blob = await response.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `reporte_${slug}_${params.date_from}_${params.date_to}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
