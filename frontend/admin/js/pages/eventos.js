/* ===================================================================
   eventos.js — Logs de eventos en tiempo real por marca
   Endpoint: GET /api/v1/admin/brands/{slug}/events?limit=200[&event_type=...]
   =================================================================== */

(function () {
  'use strict';

  /* ── Estado ─────────────────────────────────────────────────── */
  var state = {
    brands: [],
    selectedBrand: null,
    eventTypeFilter: 'all',
    autoRefresh: true,
    refreshInterval: null,
    REFRESH_MS: 10000,
    lastData: [],
    loading: false,
  };

  /* ── DOM refs ────────────────────────────────────────────────── */
  var $ = function (id) { return document.getElementById(id); };

  /* ── Init ────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function () {
    loadBrands();
    bindControls();
  });

  /* ── Cargar marcas ───────────────────────────────────────────── */
  function loadBrands() {
    fetch('/api/v1/admin/brands?limit=100', { credentials: 'include' })
      .then(function (r) { return r.json(); })
      .then(function (resp) {
        state.brands = (resp.data || []);
        var sel = $('select-brand');
        sel.innerHTML = '<option value="">— Seleccionar marca —</option>';
        state.brands.forEach(function (b) {
          var o = document.createElement('option');
          o.value = b.slug;
          o.textContent = b.name;
          sel.appendChild(o);
        });
      })
      .catch(function (e) {
        showError('No se pudo cargar la lista de marcas: ' + e.message);
      });
  }

  /* ── Controles ───────────────────────────────────────────────── */
  function bindControls() {
    /* Selector de marca */
    $('select-brand').addEventListener('change', function () {
      state.selectedBrand = this.value || null;
      if (state.selectedBrand) {
        showSection();
        loadEvents();
        startAutoRefresh();
      } else {
        hideSection();
        stopAutoRefresh();
      }
    });

    /* Filtros de tipo */
    document.querySelectorAll('[data-event-type]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('[data-event-type]').forEach(function (b) {
          b.classList.remove('active', 'btn-theme-active');
        });
        this.classList.add('active', 'btn-theme-active');
        state.eventTypeFilter = this.dataset.eventType;
        loadEvents();
      });
    });

    /* Toggle auto-refresh */
    $('btn-autorefresh').addEventListener('click', function () {
      state.autoRefresh = !state.autoRefresh;
      updateAutoRefreshUI();
      if (state.autoRefresh && state.selectedBrand) {
        loadEvents();
        startAutoRefresh();
      } else {
        stopAutoRefresh();
      }
    });

    /* Refresh manual */
    $('btn-refresh').addEventListener('click', function () {
      if (state.selectedBrand) loadEvents();
    });
  }

  /* ── Auto-refresh ────────────────────────────────────────────── */
  function startAutoRefresh() {
    stopAutoRefresh();
    if (!state.autoRefresh) return;
    state.refreshInterval = setInterval(function () {
      if (state.selectedBrand && !state.loading) loadEvents();
    }, state.REFRESH_MS);
  }

  function stopAutoRefresh() {
    if (state.refreshInterval) {
      clearInterval(state.refreshInterval);
      state.refreshInterval = null;
    }
  }

  function updateAutoRefreshUI() {
    var btn = $('btn-autorefresh');
    var icon = btn.querySelector('i');
    if (state.autoRefresh) {
      btn.classList.add('btn-theme-active');
      btn.title = 'Auto-refresh ON (cada 10s) — click para pausar';
      if (icon) { icon.className = 'ion-android-sync'; }
    } else {
      btn.classList.remove('btn-theme-active');
      btn.title = 'Auto-refresh pausado — click para activar';
      if (icon) { icon.className = 'ion-pause'; }
    }
  }

  /* ── Cargar eventos ──────────────────────────────────────────── */
  function loadEvents() {
    if (!state.selectedBrand || state.loading) return;
    state.loading = true;
    setRefreshSpinner(true);

    var url = '/api/v1/admin/brands/' + state.selectedBrand + '/events?limit=200';
    if (state.eventTypeFilter && state.eventTypeFilter !== 'all') {
      url += '&event_type=' + state.eventTypeFilter;
    }

    fetch(url, { credentials: 'include' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (resp) {
        if (resp.error) throw new Error(resp.error);
        state.lastData = resp.data || [];
        renderStats(state.lastData);
        renderTable(state.lastData);
        updateTimestamp();
        hideError();
      })
      .catch(function (e) {
        showError('Error al cargar eventos: ' + e.message);
      })
      .finally(function () {
        state.loading = false;
        setRefreshSpinner(false);
      });
  }

  /* ── Renderizar stats ────────────────────────────────────────── */
  function renderStats(events) {
    var now = Date.now();
    var oneHourAgo = now - 3600000;

    var activeSessions = 0;
    var eventsLastHour = 0;
    var typeCounts = { join: 0, heartbeat: 0, leave: 0 };

    events.forEach(function (ev) {
      if (ev.is_active) activeSessions++;

      /* Contar eventos de la última hora usando joined_at o last_heartbeat */
      var ts = ev.last_heartbeat || ev.joined_at;
      if (ts) {
        var t = new Date(ts).getTime();
        if (t >= oneHourAgo) eventsLastHour++;
      }

      if (typeCounts.hasOwnProperty(ev.event_type)) {
        typeCounts[ev.event_type]++;
      }
    });

    /* Tipo más frecuente */
    var mostFrequent = Object.keys(typeCounts).reduce(function (a, b) {
      return typeCounts[a] >= typeCounts[b] ? a : b;
    });

    setText('stat-active', activeSessions);
    setText('stat-hour', eventsLastHour);
    setText('stat-frequent', capitalize(mostFrequent));

    /* Badge en el título */
    var badge = $('badge-active');
    if (badge) {
      badge.textContent = activeSessions;
      badge.style.display = activeSessions > 0 ? '' : 'none';
    }
  }

  /* ── Renderizar tabla ────────────────────────────────────────── */
  function renderTable(events) {
    var tbody = document.querySelector('#table-events tbody');
    if (!tbody) return;

    if (!events || events.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted p-a-lg">'
        + '<i class="ion-ios-pulse" style="font-size:2rem;display:block;margin-bottom:8px;opacity:0.4;"></i>'
        + 'No hay eventos para mostrar</td></tr>';
      return;
    }

    tbody.innerHTML = events.map(function (ev) {
      return '<tr>'
        + '<td>' + eventTypeBadge(ev.event_type) + '</td>'
        + '<td><code style="font-size:12px;">' + shortId(ev.session_id) + '</code></td>'
        + '<td>' + serverBadge(ev.server_type) + '</td>'
        + '<td class="text-sm">' + fmtDatetime(ev.joined_at) + '</td>'
        + '<td class="text-sm">' + fmtDatetime(ev.last_heartbeat) + '</td>'
        + '<td class="text-sm">' + fmtDuration(ev.duration_seconds) + '</td>'
        + '<td>' + statusBadge(ev.is_active) + '</td>'
        + '</tr>';
    }).join('');
  }

  /* ── Helpers de formato ──────────────────────────────────────── */
  function shortId(id) {
    if (!id) return '—';
    return String(id).slice(0, 8) + '…';
  }

  function fmtDatetime(iso) {
    if (!iso) return '<span class="text-muted">—</span>';
    var d = new Date(iso);
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return pad(d.getDate()) + '/' + pad(d.getMonth() + 1)
      + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  function fmtDuration(secs) {
    if (secs === null || secs === undefined) return '<span class="text-muted">—</span>';
    var s = Math.round(secs);
    if (s < 60) return s + 's';
    var m = Math.floor(s / 60);
    var rem = s % 60;
    if (m < 60) return m + 'm ' + rem + 's';
    var h = Math.floor(m / 60);
    return h + 'h ' + (m % 60) + 'm';
  }

  function eventTypeBadge(type) {
    var colors = { join: '#22c55e', heartbeat: '#3b82f6', leave: '#ef4444' };
    var icons  = { join: 'ion-log-in', heartbeat: 'ion-ios-pulse', leave: 'ion-log-out' };
    var c = colors[type] || '#94a3b8';
    var i = icons[type]  || 'ion-help';
    return '<span style="display:inline-flex;align-items:center;gap:4px;'
      + 'background:' + c + '22;color:' + c + ';border:1px solid ' + c + '44;'
      + 'padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">'
      + '<i class="' + i + '"></i>' + capitalize(type || '—') + '</span>';
  }

  function serverBadge(type) {
    if (type === 'public') {
      return '<span class="label label-info" style="font-size:11px;">Público</span>';
    }
    if (type === 'private') {
      return '<span class="label label-warning" style="font-size:11px;">Privado</span>';
    }
    return '<span class="text-muted">—</span>';
  }

  function statusBadge(isActive) {
    if (isActive) {
      return '<span class="label label-success" style="font-size:11px;">'
        + '<i class="ion-record" style="font-size:8px;"></i> Activa</span>';
    }
    return '<span class="label label-default" style="font-size:11px;">Cerrada</span>';
  }

  function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  /* ── UI helpers ──────────────────────────────────────────────── */
  function setText(id, val) {
    var el = $(id);
    if (el) el.textContent = val;
  }

  function showSection() {
    var s = $('section-events');
    if (s) s.style.display = '';
  }

  function hideSection() {
    var s = $('section-events');
    if (s) s.style.display = 'none';
  }

  function showError(msg) {
    var el = $('section-error');
    if (!el) return;
    $('error-message').textContent = msg;
    el.style.display = '';
  }

  function hideError() {
    var el = $('section-error');
    if (el) el.style.display = 'none';
  }

  function setRefreshSpinner(on) {
    var icon = document.querySelector('#btn-refresh i');
    if (icon) {
      icon.className = on ? 'ion-load-c pca-spin' : 'ion-android-sync';
    }
  }

  function updateTimestamp() {
    var el = $('last-updated');
    if (!el) return;
    var now = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    el.textContent = 'Actualizado ' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }

})();
