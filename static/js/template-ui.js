// Template UI - Main Application
(function() {
  'use strict';

  // ========== App State ==========
  var AppState = {
    currentView: 'dashboard',
    language: 'zh',
    jobs: [],
    selectedJob: null,
    selectedJobId: null,
    isLoading: false,
    error: null,
    statusFilter: null,
    searchQuery: ''
  };

  // ========== DOM Elements ==========
  var mainContent;

  // ========== Initialize ==========
  function init() {
    console.log('init() called');
    mainContent = document.getElementById('main-content');
    console.log('mainContent found:', !!mainContent);

    if (!mainContent) {
      console.error('main-content element not found!');
      document.body.innerHTML = '<h1>ERROR: main-content not found</h1>';
      return;
    }

    // Immediately show something to prove it works
    mainContent.innerHTML = '<div style="padding:20px;"><h1>Loading...</h1><p>Init called at ' + new Date().toISOString() + '</p></div>';

    // Check if dependencies loaded
    if (typeof I18n === 'undefined') {
      mainContent.innerHTML += '<p style="color:red;">ERROR: I18n not loaded</p>';
      return;
    }
    if (typeof ApiClient === 'undefined') {
      mainContent.innerHTML += '<p style="color:red;">ERROR: ApiClient not loaded</p>';
      return;
    }

    mainContent.innerHTML += '<p style="color:green;">Dependencies OK. Language: ' + I18n.getLang() + '</p>';

    // Initialize language
    AppState.language = I18n.getLang();
    updateLanguageToggle();

    // Setup router
    setupRouter();
    mainContent.innerHTML += '<p>Router setup complete</p>';

    // Setup event listeners
    setupEventListeners();
    mainContent.innerHTML += '<p>Event listeners setup complete</p>';

    // Listen for language changes
    document.addEventListener('langchange', function(e) {
      AppState.language = e.detail;
      updateLanguageToggle();
      handleRouteChange();
    });

    // Initial route
    mainContent.innerHTML += '<p>Calling handleRouteChange...</p>';
    handleRouteChange();
    mainContent.innerHTML += '<p>handleRouteChange complete</p>';
  }

  // ========== Router ==========
  function setupRouter() {
    window.addEventListener('hashchange', handleRouteChange);
  }

  function handleRouteChange() {
    console.log('handleRouteChange called, hash:', window.location.hash);
    var hash = window.location.hash || '#/';
    var path = hash.slice(1);

    // Close SSE connections when navigating
    if (typeof SSEManager !== 'undefined') {
      if (!path.startsWith('/jobs/') || path === '/jobs/new') {
        SSEManager.disconnectAll();
      }
    }

    if (path === '/' || path === '' || path === '/jobs') {
      showDashboard();
    } else if (path === '/jobs/new') {
      showCreateJob();
    } else if (path.startsWith('/jobs/')) {
      var parts = path.split('/');
      var jobId = parts[2];
      if (jobId) {
        showJobDetail(jobId);
      }
    } else if (path === '/settings') {
      showSettings();
    } else if (path === '/templates') {
      showTemplates();
    } else {
      showDashboard();
    }

    // Update active nav
    updateActiveNav(path);
  }

  function updateActiveNav(path) {
    document.querySelectorAll('.nav-link').forEach(function(link) {
      link.classList.remove('active');
      var href = link.getAttribute('href');
      if (href === '#' + path || (path === '/' && href === '#/')) {
        link.classList.add('active');
      }
    });
  }

  // ========== Event Listeners ==========
  function setupEventListeners() {
    // Language toggle
    document.addEventListener('click', function(e) {
      if (e.target.id === 'lang-toggle') {
        I18n.toggle();
      }
    });
  }

  function updateLanguageToggle() {
    var label = document.getElementById('lang-label');
    if (label) {
      label.textContent = I18n.getLang() === 'zh' ? 'EN' : '中文';
    }
  }

// ========== View: Dashboard ==========
  async function showDashboard() {
    AppState.currentView = 'dashboard';
    renderLoading();

    try {
      var result = await ApiClient.Jobs.list({ limit: 100 });

      if (result.success) {
        AppState.jobs = result.jobs || [];
        renderDashboard(AppState.jobs, result.total);
      } else {
        renderError(result.error || 'Failed to load jobs');
      }
    } catch (err) {
      renderError(err.message);
    }
  }

  function renderDashboard(jobs, total) {
    var lang = AppState.language;
    var stats = calculateStats(jobs);

    var html = '<div class="dashboard">' +
      '<header class="dashboard-header">' +
        '<div class="header-title">' +
          '<h1>' + I18n.t('dashboard.title') + '</h1>' +
        '</div>' +
        '<div class="header-actions">' +
          '<button class="btn-secondary" onclick="location.reload()">' +
            I18n.t('common.refresh') +
          '</button>' +
          '<a href="#/jobs/new" class="btn btn-primary">' +
            '+ ' + I18n.t('dashboard.newJob') +
          '</a>' +
        '</div>' +
      '</header>' +

      '<div class="stats-grid">' +
        '<div class="stat-card">' +
          '<div class="stat-value">' + (total || 0) + '</div>' +
          '<div class="stat-label">' + I18n.t('dashboard.stats.total') + '</div>' +
        '</div>' +
        '<div class="stat-card stat-running">' +
          '<div class="stat-value">' + stats.running + '</div>' +
          '<div class="stat-label">' + I18n.t('dashboard.stats.running') + '</div>' +
        '</div>' +
        '<div class="stat-card stat-pending">' +
          '<div class="stat-value">' + stats.pending + '</div>' +
          '<div class="stat-label">' + I18n.t('dashboard.stats.pending') + '</div>' +
        '</div>' +
        '<div class="stat-card stat-completed">' +
          '<div class="stat-value">' + stats.completed + '</div>' +
          '<div class="stat-label">' + I18n.t('dashboard.stats.completed') + '</div>' +
        '</div>' +
        '<div class="stat-card stat-failed">' +
          '<div class="stat-value">' + stats.failed + '</div>' +
          '<div class="stat-label">' + I18n.t('dashboard.stats.failed') + '</div>' +
        '</div>' +
        '<div class="stat-card stat-paused">' +
          '<div class="stat-value">' + stats.paused + '</div>' +
          '<div class="stat-label">' + I18n.t('dashboard.stats.paused') + '</div>' +
        '</div>' +
      '</div>' +

      '<div class="filter-bar">' +
        '<div class="filter-buttons">' +
          '<button class="filter-btn ' + (AppState.statusFilter === null ? 'active' : '') + '" onclick="filterByStatus(null)">' + I18n.t('common.filterAll') + '</button>' +
          '<button class="filter-btn ' + (AppState.statusFilter === 'pending' ? 'active' : '') + '" onclick="filterByStatus(\'pending\')">' + I18n.t('common.filterPending') + '</button>' +
          '<button class="filter-btn ' + (AppState.statusFilter === 'processing' ? 'active' : '') + '" onclick="filterByStatus(\'processing\')">' + I18n.t('common.filterProcessing') + '</button>' +
          '<button class="filter-btn ' + (AppState.statusFilter === 'completed' ? 'active' : '') + '" onclick="filterByStatus(\'completed\')">' + I18n.t('common.filterCompleted') + '</button>' +
          '<button class="filter-btn ' + (AppState.statusFilter === 'failed' ? 'active' : '') + '" onclick="filterByStatus(\'failed\')">' + I18n.t('common.filterFailed') + '</button>' +
          '<button class="filter-btn ' + (AppState.statusFilter === 'paused' ? 'active' : '') + '" onclick="filterByStatus(\'paused\')">' + I18n.t('common.filterPaused') + '</button>' +
        '</div>' +
        '<input type="text" class="search-input" placeholder="' + I18n.t('dashboard.searchPlaceholder') + '" value="' + escapeHtml(AppState.searchQuery) + '" oninput="searchJobs(this.value)">' +
      '</div>' +

      '<div class="jobs-grid" id="jobs-grid">' +
        renderJobCards(filterJobs(jobs)) +
      '</div>' +
    '</div>';

    mainContent.innerHTML = html;
  }

  function calculateStats(jobs) {
    var stats = { pending: 0, running: 0, completed: 0, failed: 0, paused: 0 };
    jobs.forEach(function(job) {
      var status = job.status;
      if (status === 'pending') stats.pending++;
      else if (status === 'processing' || status === 'running') stats.running++;
      else if (status === 'completed') stats.completed++;
      else if (status === 'failed') stats.failed++;
      else if (status === 'paused') stats.paused++;
    });
    return stats;
  }

  function filterJobs(jobs) {
    var filtered = jobs;
    if (AppState.statusFilter) {
      filtered = filtered.filter(function(j) { return j.status === AppState.statusFilter; });
    }
    if (AppState.searchQuery) {
      var q = AppState.searchQuery.toLowerCase();
      filtered = filtered.filter(function(j) {
        return (j.name && j.name.toLowerCase().includes(q)) ||
               (j.job_id && j.job_id.toLowerCase().includes(q));
      });
    }
    return filtered;
  }

  function renderJobCards(jobs) {
    if (jobs.length === 0) {
      return '<div class="empty-state">' + I18n.t('dashboard.noJobs') + '</div>';
    }

    var html = '';
    jobs.forEach(function(job) {
      var statusClass = I18n.getStatusClass(job.status);
      var badgeClass = I18n.getStatusBadge(job.status);
      html += '<div class="job-card" onclick="navigateTo(\'/jobs/' + job.job_id + '\')">' +
        '<div class="job-card-header">' +
          '<span class="job-title">' + escapeHtml(job.name || 'Untitled') + '</span>' +
          '<span class="' + badgeClass + '">' + I18n.t('status.' + job.status) + '</span>' +
        '</div>' +
        '<div class="job-meta">' +
          '<span>ID: ' + job.job_id + '</span>' +
          '<span>' + job.target_count + ' targets</span>' +
          '<span>' + formatDate(job.created_at) + '</span>' +
        '</div>';
      if (job.status === 'processing' || job.status === 'running') {
        html += '<div class="progress-bar-mini">' +
          '<div class="progress-fill-mini" style="width: ' + (job.progress || 0) + '%"></div>' +
        '</div>';
      }
      html += '</div>';
    });
    return html;
  }

  window.filterByStatus = function(status) {
    AppState.statusFilter = status;
    var filtered = filterJobs(AppState.jobs);
    document.getElementById('jobs-grid').innerHTML = renderJobCards(filtered);
    document.querySelectorAll('.filter-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.textContent === (status === null ? I18n.t('common.filterAll') : I18n.t('status.' + status) || status));
    });
  };

  window.searchJobs = function(query) {
    AppState.searchQuery = query;
    var filtered = filterJobs(AppState.jobs);
    document.getElementById('jobs-grid').innerHTML = renderJobCards(filtered);
  };

  // ========== View: Job Detail ==========
  async function showJobDetail(jobId) {
    AppState.currentView = 'job-detail';
    AppState.selectedJobId = jobId;
    renderLoading();

    try {
      var lang = AppState.language;
      var result = await ApiClient.Jobs.get(jobId, lang);

      if (result.success) {
        AppState.selectedJob = result;
        renderJobDetail(result);

        // Start SSE connection if job is active
        var status = result.job.status;
        if (status === 'processing' || status === 'running' || status === 'pending' || status === 'paused') {
          startProgressStream(jobId);
        }
      } else {
        renderError(result.error || 'Failed to load job');
      }
    } catch (err) {
      renderError(err.message);
    }
  }

  function startProgressStream(jobId) {
    SSEManager.connect(jobId, function(data) {
      updateProgress(data);
    }, function(err) {
      console.error('SSE error:', err);
    });
  }

  function updateProgress(data) {
    // Update progress bar
    var progressFill = document.querySelector('.progress-fill');
    if (progressFill && data.progress !== undefined) {
      progressFill.style.width = data.progress + '%';
    }

    // Update progress text
    var progressText = document.getElementById('progress-text');
    if (progressText && data.progress !== undefined) {
      progressText.textContent = data.progress + '%';
    }

    // Update latest log
    var latestLog = document.getElementById('latest-log');
    if (latestLog && data.latest_log) {
      latestLog.textContent = data.latest_log;
    }

    // Update status if changed
    if (data.status) {
      var statusBadge = document.querySelector('.status-badge');
      if (statusBadge) {
        statusBadge.className = 'status-badge ' + I18n.getStatusClass(data.status);
        statusBadge.textContent = I18n.t('status.' + data.status);
      }

      // If job completed or failed, disconnect SSE
      if (data.status === 'completed' || data.status === 'failed') {
        SSEManager.disconnect(AppState.selectedJobId);
      }
    }
  }

  function renderJobDetail(result) {
    var job = result.job;
    var targets = result.targets || [];
    var statistics = result.statistics || {};
    var lang = AppState.language;
    var hasMultipleTargets = targets.length > 1;

    var html = '<div class="job-detail">' +
      '<header class="job-header">' +
        '<div class="job-info">' +
          '<a href="#/" class="btn btn-secondary btn-sm">' + I18n.t('common.back') + '</a>' +
          '<div class="job-title-block">' +
            '<h1>' + escapeHtml(job.name || 'Untitled') + '</h1>' +
            '<span class="status-badge ' + I18n.getStatusClass(job.status) + '">' + I18n.t('status.' + job.status) + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="job-controls">' +
          renderJobControls(job) +
        '</div>' +
      '</header>' +

      '<div class="progress-section">' +
        '<div class="progress-header">' +
          '<span id="progress-text">' + I18n.t('job.progress') + ': ' + (statistics.completed || 0) + '/' + (statistics.total || 0) + '</span>' +
          '<span id="progress-percent">' + (statistics.percentage || 0) + '%</span>' +
        '</div>' +
        '<div class="progress-bar">' +
          '<div class="progress-fill" style="width: ' + (statistics.percentage || 0) + '%"></div>' +
        '</div>' +
        '<div class="mt-4 text-sm text-muted">' +
          I18n.t('log.currentStep') + ': <span id="latest-log">' + (result.latest_log || '-') + '</span>' +
        '</div>' +
      '</div>' +

      '<div class="tabs">' +
        '<button class="tab active" data-tab="overview">' + I18n.t('job.overview') + '</button>';

    if (hasMultipleTargets) {
      html += '<button class="tab" data-tab="interactions">' + I18n.t('job.interactions') + '</button>';
    }

    html += '<button class="tab" data-tab="report">' + I18n.t('job.report') + '</button>' +
      '</div>' +

      '<div class="tab-content active" id="tab-overview">' +
        renderOverviewTab(targets, job) +
      '</div>';

    if (hasMultipleTargets) {
      html += '<div class="tab-content" id="tab-interactions">' +
        renderInteractionsTab(job.job_id) +
      '</div>';
    }

    html += '<div class="tab-content" id="tab-report">' +
        renderReportTab(job, targets, job.status) +
      '</div>' +
    '</div>';

    mainContent.innerHTML = html;

    // Setup tab switching
    document.querySelectorAll('.tab').forEach(function(tab) {
      tab.addEventListener('click', function() {
        switchTab(this.dataset.tab);
      });
    });
  }

  function renderJobControls(job) {
    var html = '';
    var status = job.status;

    if (status === 'pending' || status === 'failed') {
      html += '<button class="btn btn-success" onclick="jobAction(\'start\')">' + I18n.t('job.start') + '</button>';
    }
    if (status === 'processing' || status === 'running') {
      html += '<button class="btn btn-secondary" onclick="jobAction(\'pause\')">' + I18n.t('job.pause') + '</button>';
    }
    if (status === 'paused') {
      html += '<button class="btn btn-success" onclick="jobAction(\'resume\')">' + I18n.t('job.resume') + '</button>';
    }
    if (status !== 'completed' && status !== 'cancelled') {
      html += '<button class="btn btn-danger" onclick="jobAction(\'cancel\')">' + I18n.t('job.cancel') + '</button>';
    }
    html += '<button class="btn btn-secondary" onclick="jobAction(\'restart\')">' + I18n.t('job.restart') + '</button>';

    return html;
  }

  window.jobAction = async function(action) {
    var jobId = AppState.selectedJobId;
    try {
      var result;
      switch (action) {
        case 'start':
          result = await ApiClient.Jobs.start(jobId);
          if (result.success) startProgressStream(jobId);
          break;
        case 'pause':
          result = await ApiClient.Jobs.pause(jobId);
          break;
        case 'resume':
          result = await ApiClient.Jobs.resume(jobId);
          if (result.success) startProgressStream(jobId);
          break;
        case 'cancel':
          result = await ApiClient.Jobs.cancel(jobId);
          break;
        case 'restart':
          result = await ApiClient.Jobs.restart(jobId, {});
          if (result.success) startProgressStream(jobId);
          break;
      }
      if (result && result.success) {
        showJobDetail(jobId);
      } else if (result) {
        alert(result.error || 'Action failed');
      }
    } catch (err) {
      alert(err.message);
    }
  };

  window.switchTab = function(tabName) {
    document.querySelectorAll('.tab').forEach(function(t) {
      t.classList.toggle('active', t.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(function(c) {
      c.classList.toggle('active', c.id === 'tab-' + tabName);
    });
  };

  function renderOverviewTab(targets, job) {
    if (!targets || targets.length === 0) {
      return '<div class="empty-state">No targets found</div>';
    }

    var html = '<div class="target-list">';
    targets.forEach(function(target) {
      html += renderTargetCard(target);
    });
    html += '</div>';
    return html;
  }

  function renderTargetCard(target) {
    var eval_ = target.evaluation || {};
    var pdb_data = eval_.pdb_data || {};
    var structures = pdb_data.structures || [];
    var uniprot = target.uniprot_metadata || {};

    var html = '<div class="target-card">' +
      '<div class="target-header">' +
        '<div class="target-info">' +
          '<span class="target-uniprot">' + target.uniprot_id + '</span>' +
          '<span class="target-gene">' + (uniprot.gene_name || '-') + '</span>' +
        '</div>' +
        '<span class="' + I18n.getStatusBadge(target.status) + '">' + I18n.t('status.' + target.status) + '</span>' +
      '</div>' +
      '<div class="target-body">' +
        '<div class="pdb-grid">';

    if (structures.length > 0) {
      structures.forEach(function(pdb) {
        html += '<div class="pdb-item">' +
          '<div class="pdb-header">' +
            '<span class="pdb-id"><a href="https://www.rcsb.org/structure/' + pdb.pdb_id + '" target="_blank">' + pdb.pdb_id + '</a></span>' +
            '<span class="badge badge-secondary">' + (pdb.resolution || '-') + 'A</span>' +
          '</div>' +
          '<div class="pdb-meta">' +
            '<span>' + (pdb.method || '-') + '</span>' +
            '<span>' + (pdb.chain_count || '-') + ' chains</span>' +
          '</div>' +
        '</div>';
      });
    } else {
      html += '<div class="text-muted text-sm">' + I18n.t('target.noPdb') + '</div>';
    }

    html += '</div></div></div>';
    return html;
  }

  async function renderInteractionsTab(jobId) {
    try {
      var result = await ApiClient.Jobs.getChainInteractions(jobId);
      if (result.success) {
        return renderChainInteractions(result);
      }
    } catch (err) {
      console.error('Failed to load interactions:', err);
    }
    return '<div class="empty-state">' + I18n.t('interactions.noInteractions') + '</div>';
  }

  function renderChainInteractions(data) {
    var nodes = data.nodes || [];
    var direct = data.direct_interactions || [];
    var indirect = data.indirect_interactions || [];

    if (nodes.length === 0) {
      return '<div class="empty-state">' + I18n.t('interactions.noInteractions') + '</div>';
    }

    var html = '<div class="network-container">' +
      '<div class="network-header">' +
        '<h3>' + I18n.t('interactions.network') + '</h3>' +
        '<div class="network-legend">' +
          '<div class="legend-item"><span class="legend-dot input"></span> Input</div>' +
          '<div class="legend-item"><span class="legend-dot target"></span> Target</div>' +
          '<div class="legend-item"><span class="legend-line direct"></span> Direct</div>' +
          '<div class="legend-item"><span class="legend-line indirect"></span> Indirect</div>' +
        '</div>' +
      '</div>' +
      '<canvas id="network-canvas" class="network-canvas"></canvas>' +
    '</div>' +
    '<div class="mt-4">' +
      '<h3>' + I18n.t('interactions.direct') + ' (' + direct.length + ')</h3>' +
      renderInteractionTable(direct, 'direct') +
      '<h3 class="mt-4">' + I18n.t('interactions.indirect') + ' (' + indirect.length + ')</h3>' +
      renderInteractionTable(indirect, 'indirect') +
    '</div>';

    // Draw network after render
    setTimeout(function() {
      drawNetwork(nodes, direct, indirect);
    }, 100);

    return html;
  }

  function renderInteractionTable(interactions, type) {
    if (interactions.length === 0) {
      return '<div class="text-muted text-sm">No interactions</div>';
    }

    var html = '<table>';
    html += '<thead><tr><th>Source</th><th>Target</th><th>' + I18n.t('interactions.score') + '</th><th>' + I18n.t('interactions.pdb') + '</th></tr></thead>';
    html += '<tbody>';
    interactions.forEach(function(int) {
      html += '<tr>';
      html += '<td>' + int.source_uniprot + '</td>';
      html += '<td>' + int.target_uniprot + '</td>';
      html += '<td>' + (int.score || 0).toFixed(3) + '</td>';
      html += '<td>' + (int.pdb_ids ? int.pdb_ids.join(', ') : '-') + '</td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
  }

  function drawNetwork(nodes, direct, indirect) {
    var canvas = document.getElementById('network-canvas');
    if (!canvas) return;

    var ctx = canvas.getContext('2d');
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = 400;

    // Simple force-directed layout
    var positions = calculateNodePositions(nodes, canvas.width, canvas.height);

    // Draw direct interactions (solid green lines)
    ctx.strokeStyle = '#10B981';
    ctx.lineWidth = 2;
    direct.forEach(function(int) {
      var source = positions.find(function(p) { return p.id === int.source_uniprot; });
      var target = positions.find(function(p) { return p.id === int.target_uniprot; });
      if (source && target) {
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }
    });

    // Draw indirect interactions (dashed yellow lines)
    ctx.strokeStyle = '#F59E0B';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    indirect.forEach(function(int) {
      var source = positions.find(function(p) { return p.id === int.source_uniprot; });
      var target = positions.find(function(p) { return p.id === int.target_uniprot; });
      if (source && target) {
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }
    });
    ctx.setLineDash([]);

    // Draw nodes
    nodes.forEach(function(node) {
      var pos = positions.find(function(p) { return p.id === node.id; });
      if (!pos) return;

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, node.is_input ? 20 : 15, 0, Math.PI * 2);
      ctx.fillStyle = node.is_input ? '#6366F1' : '#8B5CF6';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = '#fff';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, pos.x, pos.y);
    });
  }

  function calculateNodePositions(nodes, width, height) {
    var positions = [];
    var centerX = width / 2;
    var centerY = height / 2;
    var radius = Math.min(width, height) / 3;

    nodes.forEach(function(node, i) {
      if (nodes.length === 1) {
        positions.push({ id: node.id, x: centerX, y: centerY });
      } else {
        var angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
        positions.push({
          id: node.id,
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle)
        });
      }
    });
    return positions;
  }

  function renderReportTab(job, targets, jobStatus) {
    // Only show report if job is completed
    if (jobStatus !== 'completed') {
      return '<div class="empty-state">' + I18n.t('job.reportNotReady') + '</div>';
    }

    // Get AI analysis from first target's evaluation
    var aiAnalysis = null;
    if (targets && targets.length > 0) {
      var evalData = targets[0].evaluation || {};
      var aiData = evalData.ai_analysis || {};
      if (typeof aiData === 'object') {
        aiAnalysis = AppState.language === 'zh' ? (aiData.analysis || '') : (aiData.analysis_en || aiData.analysis || '');
      }
    }

    if (!aiAnalysis) {
      return '<div class="empty-state">' + I18n.t('job.noReport') + '</div>';
    }

    // Render markdown if available
    if (typeof marked !== 'undefined') {
      aiAnalysis = marked.parse(aiAnalysis);
    }

    return '<div class="report-section"><div class="report-content">' + aiAnalysis + '</div></div>';
  }

  // ========== View: Create Job ==========
  async function showCreateJob() {
    AppState.currentView = 'create-job';
    renderCreateJobForm();
  }

  function renderCreateJobForm() {
    var html = '<div class="create-job">' +
      '<header class="page-header">' +
        '<a href="#/" class="btn btn-secondary btn-sm">' + I18n.t('common.back') + '</a>' +
        '<h1>' + I18n.t('create.title') + '</h1>' +
      '</header>' +

      '<div class="card">' +
        '<div class="card-body">' +
          '<div class="form-group">' +
            '<label class="form-label">' + I18n.t('create.jobName') + '</label>' +
            '<input type="text" id="job-name" class="form-input" placeholder="' + I18n.t('create.jobNamePlaceholder') + '">' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">' + I18n.t('create.description') + '</label>' +
            '<textarea id="job-description" class="form-textarea" placeholder="' + I18n.t('create.descriptionPlaceholder') + '"></textarea>' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">' + I18n.t('create.uniprotIds') + '</label>' +
            '<textarea id="job-uniprot-ids" class="form-textarea" placeholder="' + I18n.t('create.uniprotIdsPlaceholder') + '"></textarea>' +
            '<div class="form-help">支持每行一个或用逗号分隔多个ID</div>' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">' + I18n.t('create.mode') + '</label>' +
            '<select id="job-mode" class="form-select">' +
              '<option value="parallel">' + I18n.t('create.modeParallel') + '</option>' +
              '<option value="sequential">' + I18n.t('create.modeSequential') + '</option>' +
            '</select>' +
          '</div>' +
          '<div class="form-group">' +
            '<label class="form-label">' + I18n.t('create.priority') + ' (1-10)</label>' +
            '<input type="number" id="job-priority" class="form-input" value="5" min="1" max="10">' +
          '</div>' +
          '<div class="form-actions">' +
            '<button class="btn btn-primary" onclick="submitCreateJob()">' + I18n.t('create.createBtn') + '</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>';

    mainContent.innerHTML = html;
  }

  window.submitCreateJob = async function() {
    var name = document.getElementById('job-name').value.trim();
    var description = document.getElementById('job-description').value.trim();
    var uniprotIdsRaw = document.getElementById('job-uniprot-ids').value.trim();
    var mode = document.getElementById('job-mode').value;
    var priority = parseInt(document.getElementById('job-priority').value) || 5;

    if (!uniprotIdsRaw) {
      alert('Please enter UniProt IDs');
      return;
    }

    // Parse UniProt IDs
    var uniprotIds = uniprotIdsRaw.split(/[\s,\n]+/).filter(function(id) { return id.length > 0; });

    if (uniprotIds.length === 0) {
      alert('Please enter valid UniProt IDs');
      return;
    }

    var jobData = {
      name: name || 'Evaluation ' + new Date().toLocaleString(),
      description: description,
      uniprot_ids: uniprotIds,
      evaluation_mode: mode,
      priority: priority
    };

    try {
      var result = await ApiClient.Jobs.create(jobData);
      if (result.success) {
        window.location.hash = '/jobs/' + result.job_id;
      } else {
        alert(result.error || 'Failed to create job');
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // ========== View: Settings ==========
  async function showSettings() {
    AppState.currentView = 'settings';
    renderLoading();

    try {
      var result = await ApiClient.Models.list();
      if (result.success) {
        renderSettings(result.models || []);
      } else {
        renderError(result.error);
      }
    } catch (err) {
      renderError(err.message);
    }
  }

  function renderSettings(models) {
    window._cachedModels = models;

    var html = '<div class="settings-page">' +
      '<header class="page-header">' +
        '<a href="#/" class="btn btn-secondary btn-sm">' + I18n.t('common.back') + '</a>' +
        '<h1>' + I18n.t('settings.title') + '</h1>' +
      '</header>' +

      '<button class="btn btn-primary mb-4" onclick="showAddModelForm()">' +
        '+ ' + I18n.t('settings.addModel') +
      '</button>' +

      '<div class="models-grid" id="models-list">' +
        renderModelCards(models) +
      '</div>' +

      '<div id="model-form-container"></div>' +
    '</div>';

    mainContent.innerHTML = html;
  }

  function renderModelCards(models) {
    if (models.length === 0) {
      return '<div class="empty-state">No models configured</div>';
    }

    var html = '';
    models.forEach(function(m) {
      html += '<div class="model-card ' + (m.isDefault ? 'is-default' : '') + '">' +
        '<div class="model-header">' +
          '<span class="model-name">' + escapeHtml(m.name) + '</span>' +
          '<span class="api-type-badge">' + (m.apiType === 'anthropic' ? 'Anthropic' : 'OpenAI') + '</span>' +
        '</div>' +
        '<div class="model-details">' +
          '<div class="model-detail"><label>Model:</label><span>' + escapeHtml(m.model) + '</span></div>' +
          '<div class="model-detail"><label>Base URL:</label><span>' + escapeHtml(m.baseUrl || '-') + '</span></div>' +
          '<div class="model-detail"><label>Temperature:</label><span>' + m.temperature + '</span></div>' +
          '<div class="model-detail"><label>Max Tokens:</label><span>' + m.maxTokens + '</span></div>' +
        '</div>' +
        '<div class="model-actions">';
      if (!m.isDefault) {
        html += '<button class="btn btn-sm btn-secondary" onclick="setDefaultModel(\'' + m.id + '\')">' + I18n.t('settings.setDefault') + '</button>';
      }
      html += '<button class="btn btn-sm btn-secondary" onclick="testModel(\'' + m.id + '\')">' + I18n.t('settings.test') + '</button>' +
        '<button class="btn btn-sm btn-secondary" onclick="editModel(\'' + m.id + '\')">' + I18n.t('common.edit') + '</button>' +
        '<button class="btn btn-sm btn-danger" onclick="deleteModel(\'' + m.id + '\')">' + I18n.t('common.delete') + '</button>' +
      '</div>' +
      '<div class="test-result" id="test-result-' + m.id + '"></div>' +
    '</div>';
    });
    return html;
  }

  window.showAddModelForm = function() {
    showModelForm({});
  };

  window.editModel = function(modelId) {
    var models = window._cachedModels || [];
    var model = models.find(function(m) { return m.id === modelId; });
    if (model) {
      showModelForm(model);
    }
  };

  window.showModelForm = function(model) {
    model = model || {};
    var html = '<div class="card mt-4">' +
      '<div class="card-header">' +
        '<h3>' + (model.id ? 'Edit Model' : 'Add Model') + '</h3>' +
      '</div>' +
      '<div class="card-body">' +
        '<input type="hidden" id="model-id" value="' + (model.id || '') + '">' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.modelName') + '</label>' +
          '<input type="text" id="model-name" class="form-input" value="' + escapeHtml(model.name || '') + '">' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.apiType') + '</label>' +
          '<select id="model-api-type" class="form-select">' +
            '<option value="openai" ' + (model.apiType !== 'anthropic' ? 'selected' : '') + '>' + I18n.t('settings.openai') + '</option>' +
            '<option value="anthropic" ' + (model.apiType === 'anthropic' ? 'selected' : '') + '>' + I18n.t('settings.anthropic') + '</option>' +
          '</select>' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.model') + '</label>' +
          '<input type="text" id="model-model" class="form-input" value="' + escapeHtml(model.model || '') + '" placeholder="e.g. gpt-4o, claude-3-5-sonnet">' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.baseUrl') + '</label>' +
          '<input type="text" id="model-base-url" class="form-input" value="' + escapeHtml(model.baseUrl || '') + '" placeholder="https://api.openai.com/v1">' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.apiKey') + '</label>' +
          '<input type="password" id="model-api-key" class="form-input" value="' + escapeHtml(model.apiKey || '') + '" placeholder="sk-...">' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.temperature') + '</label>' +
          '<input type="number" id="model-temperature" class="form-input" value="' + (model.temperature || 0.3) + '" step="0.1" min="0" max="2">' +
        '</div>' +
        '<div class="form-group">' +
          '<label class="form-label">' + I18n.t('settings.maxTokens') + '</label>' +
          '<input type="number" id="model-max-tokens" class="form-input" value="' + (model.maxTokens || 20000) + '">' +
        '</div>' +
        '<div class="form-actions">' +
          '<button class="btn btn-primary" onclick="saveModel()">' + I18n.t('settings.save') + '</button>' +
          '<button class="btn btn-secondary" onclick="showSettings()">' + I18n.t('settings.cancel') + '</button>' +
        '</div>' +
      '</div>' +
    '</div>';
    document.getElementById('model-form-container').innerHTML = html;
  };

  window.saveModel = async function() {
    var model = {
      id: document.getElementById('model-id').value,
      name: document.getElementById('model-name').value,
      apiType: document.getElementById('model-api-type').value,
      model: document.getElementById('model-model').value,
      baseUrl: document.getElementById('model-base-url').value,
      apiKey: document.getElementById('model-api-key').value,
      temperature: parseFloat(document.getElementById('model-temperature').value) || 0.3,
      maxTokens: parseInt(document.getElementById('model-max-tokens').value) || 20000
    };

    try {
      var result = await ApiClient.Models.save([model]);
      if (result.success) {
        showSettings();
      } else {
        alert(result.error || 'Failed to save');
      }
    } catch (err) {
      alert(err.message);
    }
  };

  window.testModel = async function(modelId) {
    var models = window._cachedModels || [];
    var model = models.find(function(m) { return m.id === modelId; });
    if (!model) return;

    var testResultEl = document.getElementById('test-result-' + modelId);
    testResultEl.textContent = 'Testing...';
    testResultEl.className = 'test-result';

    try {
      var result = await ApiClient.Models.test(model);
      if (result.success) {
        testResultEl.textContent = I18n.t('settings.testSuccess');
        testResultEl.className = 'test-result success';
      } else {
        testResultEl.textContent = (result.error || I18n.t('settings.testFailed'));
        testResultEl.className = 'test-result error';
      }
    } catch (err) {
      testResultEl.textContent = err.message;
      testResultEl.className = 'test-result error';
    }
  };

  window.deleteModel = async function(modelId) {
    if (!confirm('Delete this model?')) return;

    var models = window._cachedModels || [];
    models = models.filter(function(m) { return m.id !== modelId; });

    try {
      var result = await ApiClient.Models.save(models);
      if (result.success) {
        showSettings();
      } else {
        alert(result.error);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  window.setDefaultModel = async function(modelId) {
    var models = window._cachedModels || [];
    models.forEach(function(m) {
      m.isDefault = (m.id === modelId);
    });

    try {
      var result = await ApiClient.Models.save(models);
      if (result.success) {
        showSettings();
      } else {
        alert(result.error);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // ========== View: Templates ==========
  async function showTemplates() {
    AppState.currentView = 'templates';
    renderLoading();

    try {
      var singleResult = await ApiClient.Templates.list();
      var batchResult = await ApiClient.Templates.listBatch();

      if (singleResult.success || batchResult.success) {
        renderTemplates(singleResult.templates || [], batchResult.templates || []);
      } else {
        renderError(singleResult.error || 'Failed to load templates');
      }
    } catch (err) {
      renderError(err.message);
    }
  }

  function renderTemplates(singleTemplates, batchTemplates) {
    var html = '<div class="templates-page">' +
      '<header class="page-header">' +
        '<a href="#/" class="btn btn-secondary btn-sm">' + I18n.t('common.back') + '</a>' +
        '<h1>' + I18n.t('templates.title') + '</h1>' +
      '</header>' +

      '<div class="tabs">' +
        '<button class="tab active" data-template-tab="single">' + I18n.t('templates.single') + '</button>' +
        '<button class="tab" data-template-tab="batch">' + I18n.t('templates.batch') + '</button>' +
      '</div>' +

      '<div class="tab-content active" id="template-tab-single">' +
        '<div class="template-list">' +
          renderTemplateCards(singleTemplates) +
        '</div>' +
      '</div>' +
      '<div class="tab-content" id="template-tab-batch">' +
        '<div class="template-list">' +
          renderTemplateCards(batchTemplates) +
        '</div>' +
      '</div>' +
    '</div>';

    mainContent.innerHTML = html;

    document.querySelectorAll('[data-template-tab]').forEach(function(tab) {
      tab.addEventListener('click', function() {
        document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
        document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
        tab.classList.add('active');
        document.getElementById('template-tab-' + tab.dataset.templateTab).classList.add('active');
      });
    });
  }

  function renderTemplateCards(templates) {
    if (templates.length === 0) {
      return '<div class="empty-state">No templates</div>';
    }

    return templates.map(function(t) {
      var card = '<div class="template-card ' + (t.is_default ? 'is-default' : '') + '">' +
        '<div class="template-header">' +
          '<h3>' + escapeHtml(t.name) + '</h3>';
      if (t.is_default) {
        card += '<span class="badge badge-primary">Default</span>';
      }
      card += '</div>' +
        '<p class="template-description">' + escapeHtml(t.description || t.description_en || '') + '</p>' +
        '<div class="template-actions">' +
          '<button class="btn btn-sm btn-secondary" onclick="deleteTemplate(' + t.id + ')">' + I18n.t('templates.delete') + '</button>';
      if (!t.is_default) {
        card += '<button class="btn btn-sm btn-secondary" onclick="setDefaultTemplate(' + t.id + ')">' + I18n.t('templates.default') + '</button>';
      }
      card += '</div></div>';
      return card;
    }).join('');
  }

  window.deleteTemplate = async function(templateId) {
    if (!confirm('Delete this template?')) return;

    try {
      var result = await ApiClient.Templates.delete(templateId);
      if (result.success) {
        showTemplates();
      } else {
        alert(result.error);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  window.setDefaultTemplate = async function(templateId) {
    try {
      var result = await ApiClient.Templates.setDefault(templateId);
      if (result.success) {
        showTemplates();
      } else {
        alert(result.error);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  // ========== Utility Functions ==========
  function renderLoading() {
    mainContent.innerHTML = '<div class="loading-spinner">' +
      '<div class="spinner"></div>' +
      '<p>' + I18n.t('common.loading') + '</p>' +
    '</div>';
  }

  function renderError(message) {
    mainContent.innerHTML = '<div class="error-message">' +
      '<strong>' + I18n.t('common.error') + ':</strong> ' + escapeHtml(message) +
    '</div>' +
    '<button class="btn btn-secondary" onclick="history.back()">' + I18n.t('common.back') + '</button>';
  }

  function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    var date = new Date(dateStr);
    return date.toLocaleString(AppState.language === 'zh' ? 'zh-CN' : 'en-US');
  }

  function navigateTo(path) {
    window.location.hash = path;
  }

  // Expose utilities globally
  window.navigateTo = navigateTo;
  window.escapeHtml = escapeHtml;
  window.formatDate = formatDate;

  // ========== Start Application ==========
  document.addEventListener('DOMContentLoaded', init);
})();
