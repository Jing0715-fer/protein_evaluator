// API Client for Template UI
(function() {
  'use strict';

  const API_BASE = '/api/v2/evaluate/multi';
  const EVAL_API = '/api/evaluation';

  // ========== Helper Functions ==========
  async function fetchJSON(url, options) {
    options = options || {};
    options.headers = Object.assign({
      'Content-Type': 'application/json'
    }, options.headers);

    var resp = await fetch(url, options);
    var data = await resp.json();
    return data;
  }

  function post(url, data) {
    return fetchJSON(url, {
      method: 'POST',
      body: JSON.stringify(data || {})
    });
  }

  function put(url, data) {
    return fetchJSON(url, {
      method: 'PUT',
      body: JSON.stringify(data || {})
    });
  }

  // ========== Jobs API ==========
  var JobsAPI = {
    list: async function(params) {
      params = params || {};
      var query = [];
      if (params.status) query.push('status=' + encodeURIComponent(params.status));
      if (params.limit) query.push('limit=' + encodeURIComponent(params.limit));
      if (params.offset) query.push('offset=' + encodeURIComponent(params.offset));
      if (params.sort_by) query.push('sort_by=' + encodeURIComponent(params.sort_by));
      if (params.sort_order) query.push('sort_order=' + encodeURIComponent(params.sort_order));
      var url = API_BASE + (query.length ? '?' + query.join('&') : '');
      return fetchJSON(url);
    },

    get: async function(jobId, lang) {
      lang = lang || 'zh';
      return fetchJSON(API_BASE + '/' + jobId + '?lang=' + lang);
    },

    create: async function(data) {
      return post(API_BASE, data);
    },

    update: async function(jobId, data) {
      return put(API_BASE + '/' + jobId, data);
    },

    delete: async function(jobId) {
      return fetchJSON(API_BASE + '/' + jobId, { method: 'DELETE' });
    },

    // Job controls
    start: async function(jobId) {
      return post(API_BASE + '/' + jobId + '/start');
    },

    pause: async function(jobId) {
      return post(API_BASE + '/' + jobId + '/pause');
    },

    resume: async function(jobId) {
      return post(API_BASE + '/' + jobId + '/resume');
    },

    cancel: async function(jobId) {
      return post(API_BASE + '/' + jobId + '/cancel');
    },

    restart: async function(jobId, params) {
      params = params || {};
      return post(API_BASE + '/' + jobId + '/restart', params);
    },

    // Progress
    getProgress: async function(jobId) {
      return fetchJSON(API_BASE + '/' + jobId + '/progress');
    },

    // Targets
    getTargets: async function(jobId, params) {
      params = params || {};
      var query = [];
      if (params.status) query.push('status=' + encodeURIComponent(params.status));
      if (params.limit) query.push('limit=' + encodeURIComponent(params.limit));
      var url = API_BASE + '/' + jobId + '/targets';
      if (query.length) url += '?' + query.join('&');
      return fetchJSON(url);
    },

    getTargetDetail: async function(jobId, targetId) {
      return fetchJSON(API_BASE + '/' + jobId + '/targets/' + targetId);
    },

    // Interactions
    getInteractions: async function(jobId, params) {
      params = params || {};
      var query = [];
      if (params.relationship_type) query.push('relationship_type=' + encodeURIComponent(params.relationship_type));
      if (params.min_score) query.push('min_score=' + encodeURIComponent(params.min_score));
      if (params.limit) query.push('limit=' + encodeURIComponent(params.limit));
      var url = API_BASE + '/' + jobId + '/interactions';
      if (query.length) url += '?' + query.join('&');
      return fetchJSON(url);
    },

    getChainInteractions: async function(jobId) {
      return fetchJSON(API_BASE + '/' + jobId + '/interactions/chain');
    },

    // PDB
    getPdb: async function(pdbId) {
      return fetchJSON(API_BASE + '/pdb/' + pdbId);
    },

    // Logs
    getLogs: async function(jobId) {
      return fetchJSON(API_BASE + '/' + jobId + '/logs');
    },

    // Report
    generateReport: async function(jobId, params) {
      return post(API_BASE + '/' + jobId + '/report', params || {});
    }
  };

  // ========== Templates API ==========
  var TemplatesAPI = {
    list: async function() {
      return fetchJSON(EVAL_API + '/templates');
    },

    listBatch: async function() {
      return fetchJSON(EVAL_API + '/batch-templates');
    },

    get: async function(id) {
      return fetchJSON(EVAL_API + '/templates/' + id);
    },

    getBatch: async function(id) {
      return fetchJSON(EVAL_API + '/batch-templates/' + id);
    },

    create: async function(data) {
      return post(EVAL_API + '/templates', data);
    },

    createBatch: async function(data) {
      return post(EVAL_API + '/batch-templates', data);
    },

    update: async function(id, data) {
      return put(EVAL_API + '/templates/' + id, data);
    },

    updateBatch: async function(id, data) {
      return put(EVAL_API + '/batch-templates/' + id, data);
    },

    delete: async function(id) {
      return fetchJSON(EVAL_API + '/templates/' + id, { method: 'DELETE' });
    },

    deleteBatch: async function(id) {
      return fetchJSON(EVAL_API + '/batch-templates/' + id, { method: 'DELETE' });
    },

    setDefault: async function(id) {
      return post(EVAL_API + '/templates/' + id + '/set-default');
    },

    setDefaultBatch: async function(id) {
      return post(EVAL_API + '/batch-templates/' + id + '/set-default');
    }
  };

  // ========== Models API ==========
  var ModelsAPI = {
    list: async function() {
      return fetchJSON(EVAL_API + '/models');
    },

    save: async function(models) {
      return put(EVAL_API + '/models', { models: models });
    },

    test: async function(model) {
      return post(EVAL_API + '/models/test', model);
    }
  };

  // ========== Health API ==========
  var HealthAPI = {
    check: async function() {
      return fetchJSON('/health');
    }
  };

  // ========== Export ==========
  window.ApiClient = {
    Jobs: JobsAPI,
    Templates: TemplatesAPI,
    Models: ModelsAPI,
    Health: HealthAPI
  };
})();
