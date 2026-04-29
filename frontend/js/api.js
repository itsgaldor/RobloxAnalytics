/**
 * Módulo de comunicación con el backend de Peru City Analytics.
 * Todas las funciones son async y manejan errores con mensajes en español.
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
 * Obtiene métricas del dashboard.
 * @param {string} slug
 * @param {string} range - 'day' | 'week' | 'month' | 'custom'
 * @param {string|null} dateFrom - YYYY-MM-DD (solo cuando range='custom')
 * @param {string|null} dateTo   - YYYY-MM-DD (solo cuando range='custom')
 */
async function fetchMetrics(slug, range, dateFrom, dateTo) {
  try {
    let url = `${PCA_CONFIG.apiBase}/${slug}/metrics?compare=true`;
    if (range === 'custom' && dateFrom && dateTo) {
      url += `&date_from=${dateFrom}&date_to=${dateTo}`;
    } else {
      url += `&range=${range || 'week'}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Error al obtener métricas: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) throw new Error('Error de red al obtener métricas.');
    throw err;
  }
}

/**
 * Obtiene las métricas diarias para una marca y rango.
 * @param {string} slug
 * @param {string} range
 * @param {string|null} dateFrom
 * @param {string|null} dateTo
 */
async function fetchDailyMetrics(slug, range, dateFrom, dateTo) {
  try {
    let url;
    if (range === 'custom' && dateFrom && dateTo) {
      url = `${PCA_CONFIG.apiBase}/${slug}/metrics/daily?date_from=${dateFrom}&date_to=${dateTo}`;
    } else {
      const dailyRange = range === 'day' ? 'week' : (range || 'week');
      url = `${PCA_CONFIG.apiBase}/${slug}/metrics/daily?range=${dailyRange}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Error al obtener métricas diarias: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) throw new Error('Error de red al obtener métricas diarias.');
    throw err;
  }
}

async function triggerRefresh(slug) {
  try {
    const res = await fetch(`${PCA_CONFIG.apiBase}/${slug}/refresh`, { method: 'POST' });
    if (!res.ok) throw new Error(`Error al refrescar: ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) throw new Error('Error de red al refrescar los datos.');
    throw err;
  }
}

/**
 * Construye la URL de exportación CSV.
 * @param {string} slug
 * @param {string} range
 * @param {string|null} dateFrom
 * @param {string|null} dateTo
 */
function getExportUrl(slug, range, dateFrom, dateTo) {
  if (range === 'custom' && dateFrom && dateTo) {
    return `${PCA_CONFIG.apiBase}/${slug}/export.csv?date_from=${dateFrom}&date_to=${dateTo}`;
  }
  return `${PCA_CONFIG.apiBase}/${slug}/export.csv?range=${range || 'week'}`;
}
