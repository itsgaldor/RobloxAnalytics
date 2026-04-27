/**
 * Módulo de comunicación con el backend de Peru City Analytics.
 * Todas las funciones son async y manejan errores con mensajes en español.
 */

/**
 * Obtiene la configuración pública de una marca.
 * @param {string} slug - Slug de la marca (ej: 'yape', 'demo')
 * @returns {Promise<{slug, name, logo_url, banner_url, primary_color}>}
 */
async function fetchBrandConfig(slug) {
  try {
    const res = await fetch(`${PCA_CONFIG.apiBase}/${slug}/config`);
    if (!res.ok) {
      if (res.status === 404) throw new Error(`La marca '${slug}' no existe.`);
      throw new Error(`Error del servidor: ${res.status}`);
    }
    const json = await res.json();
    return json.data;
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('No se pudo conectar con el servidor. Verificá que el backend esté corriendo.');
    }
    throw err;
  }
}

/**
 * Obtiene las métricas del dashboard para una marca y rango.
 * @param {string} slug
 * @param {'day'|'week'|'month'} range
 * @returns {Promise<{data: {public: Object, private: Object}}>}
 */
async function fetchMetrics(slug, range) {
  try {
    const res = await fetch(`${PCA_CONFIG.apiBase}/${slug}/metrics?range=${range}&compare=true`);
    if (!res.ok) throw new Error(`Error al obtener métricas: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Error de red al obtener métricas.');
    }
    throw err;
  }
}

/**
 * Obtiene las métricas diarias para una marca y rango.
 * @param {string} slug
 * @param {'week'|'month'} range
 * @returns {Promise<{data: Array}>}
 */
async function fetchDailyMetrics(slug, range) {
  // El endpoint /metrics/daily solo acepta week o month — day no es válido
  const dailyRange = range === 'day' ? 'week' : range;
  try {
    const res = await fetch(`${PCA_CONFIG.apiBase}/${slug}/metrics/daily?range=${dailyRange}`);
    if (!res.ok) throw new Error(`Error al obtener métricas diarias: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Error de red al obtener métricas diarias.');
    }
    throw err;
  }
}

/**
 * Dispara el refresh de caché del dashboard.
 * @param {string} slug
 * @returns {Promise<{data: {refreshed_at: string}}>}
 */
async function triggerRefresh(slug) {
  try {
    const res = await fetch(`${PCA_CONFIG.apiBase}/${slug}/refresh`, { method: 'POST' });
    if (!res.ok) throw new Error(`Error al refrescar: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Error de red al refrescar los datos.');
    }
    throw err;
  }
}

/**
 * Construye la URL de exportación CSV (sin hacer fetch).
 * @param {string} slug
 * @param {'day'|'week'|'month'} range
 * @returns {string} URL lista para usar en window.location.href
 */
function getExportUrl(slug, range) {
  return `${PCA_CONFIG.apiBase}/${slug}/export.csv?range=${range}`;
}
