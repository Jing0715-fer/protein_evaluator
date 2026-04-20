// Internationalization (Chinese/English) for Template UI
(function() {
  'use strict';

  const translations = {
    zh: {
      // Navigation
      'nav.dashboard': '评估任务',
      'nav.settings': '设置',
      'nav.templates': 'Prompt模板',
      'nav.newJob': '新建任务',

      // Dashboard
      'dashboard.title': '评估任务',
      'dashboard.newJob': '新建评估任务',
      'dashboard.stats.total': '总任务数',
      'dashboard.stats.running': '运行中',
      'dashboard.stats.pending': '待处理',
      'dashboard.stats.completed': '已完成',
      'dashboard.stats.failed': '失败',
      'dashboard.stats.paused': '已暂停',
      'dashboard.stats.stopped': '已停止',
      'dashboard.filter': '筛选',
      'dashboard.searchPlaceholder': '搜索任务...',
      'dashboard.noJobs': '暂无评估任务，点击上方按钮创建新任务',

      // Job Detail
      'job.overview': '概览',
      'job.interactions': '相互作用',
      'job.report': '报告',
      'job.start': '启动',
      'job.pause': '暂停',
      'job.resume': '继续',
      'job.cancel': '取消',
      'job.restart': '重启',
      'job.progress': '进度',
      'job.targets': '靶点',
      'job.status': '状态',
      'job.createdAt': '创建时间',
      'job.noReport': '报告将在任务完成后生成',

      // Targets
      'target.pdbStructures': 'PDB结构',
      'target.noPdb': '无PDB结构',
      'target.resolution': '分辨率',
      'target.method': '方法',

      // Interactions
      'interactions.direct': '直接互作',
      'interactions.indirect': '间接互作',
      'interactions.score': '置信度',
      'interactions.pdb': '共用结构',
      'interactions.noInteractions': '暂未发现靶点间相互作用',
      'interactions.network': '相互作用网络',

      // Create Job
      'create.title': '新建评估任务',
      'create.jobName': '任务名称',
      'create.jobNamePlaceholder': '输入任务名称',
      'create.description': '描述（可选）',
      'create.descriptionPlaceholder': '输入任务描述',
      'create.uniprotIds': 'UniProt IDs',
      'create.uniprotIdsPlaceholder': '输入UniProt IDs（每行一个或用逗号分隔）',
      'create.mode': '评估模式',
      'create.modeParallel': '并行（更快）',
      'create.modeSequential': '串行',
      'create.template': 'Prompt模板',
      'create.createBtn': '创建任务',
      'create.priority': '优先级',
      'create.maxPdb': '最大PDB数量',

      // Settings
      'settings.title': 'AI模型配置',
      'settings.addModel': '添加模型',
      'settings.modelName': '配置名称',
      'settings.apiType': 'API类型',
      'settings.openai': 'OpenAI兼容',
      'settings.anthropic': 'Anthropic兼容',
      'settings.model': '模型名称',
      'settings.baseUrl': 'API地址',
      'settings.apiKey': 'API密钥',
      'settings.temperature': 'Temperature',
      'settings.maxTokens': '最大Token数',
      'settings.test': '测试连接',
      'settings.default': '默认',
      'settings.setDefault': '设为默认',
      'settings.save': '保存配置',
      'settings.saved': '配置已保存',
      'settings.testSuccess': '连接成功',
      'settings.testFailed': '连接失败',

      // Templates
      'templates.title': 'Prompt模板管理',
      'templates.single': '单蛋白模板',
      'templates.batch': '批量分析模板',
      'templates.new': '新建模板',
      'templates.name': '模板名称',
      'templates.content': '模板内容',
      'templates.description': '描述',
      'templates.default': '设为默认',
      'templates.delete': '删除',
      'templates.edit': '编辑',
      'templates.save': '保存',
      'templates.cancel': '取消',

      // Status
      'status.pending': '待处理',
      'status.processing': '处理中',
      'status.running': '运行中',
      'status.completed': '已完成',
      'status.failed': '失败',
      'status.paused': '已暂停',
      'status.cancelled': '已取消',

      // Common
      'common.save': '保存',
      'common.cancel': '取消',
      'common.delete': '删除',
      'common.edit': '编辑',
      'common.loading': '加载中...',
      'common.error': '出错了',
      'common.success': '成功',
      'common.confirm': '确认',
      'common.back': '返回',
      'common.refresh': '刷新',
      'common.all': '全部',
      'common.filterAll': '全部状态',
      'common.filterPending': '待处理',
      'common.filterProcessing': '处理中',
      'common.filterCompleted': '已完成',
      'common.filterFailed': '失败',
      'common.filterPaused': '已暂停',

      // Log
      'log.currentStep': '当前步骤',
      'log.noLogs': '暂无日志'
    },
    en: {
      // Navigation
      'nav.dashboard': 'Evaluation Tasks',
      'nav.settings': 'Settings',
      'nav.templates': 'Prompt Templates',
      'nav.newJob': 'New Task',

      // Dashboard
      'dashboard.title': 'Evaluation Tasks',
      'dashboard.newJob': 'New Evaluation Task',
      'dashboard.stats.total': 'Total Tasks',
      'dashboard.stats.running': 'Running',
      'dashboard.stats.pending': 'Pending',
      'dashboard.stats.completed': 'Completed',
      'dashboard.stats.failed': 'Failed',
      'dashboard.stats.paused': 'Paused',
      'dashboard.stats.stopped': 'Stopped',
      'dashboard.filter': 'Filter',
      'dashboard.searchPlaceholder': 'Search tasks...',
      'dashboard.noJobs': 'No evaluation tasks yet, click above to create a new task',

      // Job Detail
      'job.overview': 'Overview',
      'job.interactions': 'Interactions',
      'job.report': 'Report',
      'job.start': 'Start',
      'job.pause': 'Pause',
      'job.resume': 'Resume',
      'job.cancel': 'Cancel',
      'job.restart': 'Restart',
      'job.progress': 'Progress',
      'job.targets': 'Targets',
      'job.status': 'Status',
      'job.createdAt': 'Created At',
      'job.noReport': 'Report will be generated after task completion',

      // Targets
      'target.pdbStructures': 'PDB Structures',
      'target.noPdb': 'No PDB structures',
      'target.resolution': 'Resolution',
      'target.method': 'Method',

      // Interactions
      'interactions.direct': 'Direct Interactions',
      'interactions.indirect': 'Indirect Interactions',
      'interactions.score': 'Confidence',
      'interactions.pdb': 'Shared Structures',
      'interactions.noInteractions': 'No interactions found between targets',
      'interactions.network': 'Interaction Network',

      // Create Job
      'create.title': 'New Evaluation Task',
      'create.jobName': 'Task Name',
      'create.jobNamePlaceholder': 'Enter task name',
      'create.description': 'Description (optional)',
      'create.descriptionPlaceholder': 'Enter task description',
      'create.uniprotIds': 'UniProt IDs',
      'create.uniprotIdsPlaceholder': 'Enter UniProt IDs (one per line or comma-separated)',
      'create.mode': 'Evaluation Mode',
      'create.modeParallel': 'Parallel (faster)',
      'create.modeSequential': 'Sequential',
      'create.template': 'Prompt Template',
      'create.createBtn': 'Create Task',
      'create.priority': 'Priority',
      'create.maxPdb': 'Max PDB Count',

      // Settings
      'settings.title': 'AI Model Configuration',
      'settings.addModel': 'Add Model',
      'settings.modelName': 'Config Name',
      'settings.apiType': 'API Type',
      'settings.openai': 'OpenAI Compatible',
      'settings.anthropic': 'Anthropic Compatible',
      'settings.model': 'Model Name',
      'settings.baseUrl': 'API URL',
      'settings.apiKey': 'API Key',
      'settings.temperature': 'Temperature',
      'settings.maxTokens': 'Max Tokens',
      'settings.test': 'Test Connection',
      'settings.default': 'Default',
      'settings.setDefault': 'Set as Default',
      'settings.save': 'Save Config',
      'settings.saved': 'Configuration saved',
      'settings.testSuccess': 'Connection successful',
      'settings.testFailed': 'Connection failed',

      // Templates
      'templates.title': 'Prompt Template Management',
      'templates.single': 'Single Protein Template',
      'templates.batch': 'Batch Analysis Template',
      'templates.new': 'New Template',
      'templates.name': 'Template Name',
      'templates.content': 'Template Content',
      'templates.description': 'Description',
      'templates.default': 'Set Default',
      'templates.delete': 'Delete',
      'templates.edit': 'Edit',
      'templates.save': 'Save',
      'templates.cancel': 'Cancel',

      // Status
      'status.pending': 'Pending',
      'status.processing': 'Processing',
      'status.running': 'Running',
      'status.completed': 'Completed',
      'status.failed': 'Failed',
      'status.paused': 'Paused',
      'status.cancelled': 'Cancelled',

      // Common
      'common.save': 'Save',
      'common.cancel': 'Cancel',
      'common.delete': 'Delete',
      'common.edit': 'Edit',
      'common.loading': 'Loading...',
      'common.error': 'Error',
      'common.success': 'Success',
      'common.confirm': 'Confirm',
      'common.back': 'Back',
      'common.refresh': 'Refresh',
      'common.all': 'All',
      'common.filterAll': 'All Status',
      'common.filterPending': 'Pending',
      'common.filterProcessing': 'Processing',
      'common.filterCompleted': 'Completed',
      'common.filterFailed': 'Failed',
      'common.filterPaused': 'Paused',

      // Log
      'log.currentStep': 'Current Step',
      'log.noLogs': 'No logs yet'
    }
  };

  let currentLang = localStorage.getItem('template-ui-lang') || 'zh';

  const I18n = {
    t: function(key) {
      return translations[currentLang][key] || translations['zh'][key] || key;
    },

    setLang: function(lang) {
      currentLang = lang;
      localStorage.setItem('template-ui-lang', lang);
      document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
    },

    getLang: function() {
      return currentLang;
    },

    toggle: function() {
      I18n.setLang(currentLang === 'zh' ? 'en' : 'zh');
    },

    // Helper to get status class
    getStatusClass: function(status) {
      const map = {
        'pending': 'status-pending',
        'processing': 'status-processing',
        'running': 'status-running',
        'completed': 'status-completed',
        'failed': 'status-failed',
        'paused': 'status-paused',
        'cancelled': 'status-paused'
      };
      return map[status] || 'status-pending';
    },

    getStatusBadge: function(status) {
      return 'badge badge-' + status;
    }
  };

  // Export to global
  window.I18n = I18n;
})();
