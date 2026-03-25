import React, { createContext, useContext, useState, useCallback } from 'react';

type Language = 'zh' | 'en';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
}

const translations: Record<Language, Record<string, string>> = {
  zh: {
    // Common
    'app.title': '蛋白质结构评估系统',
    'app.subtitle': '多靶点蛋白质结构评估平台',
    'app.loading': '加载中...',
    'app.error': '出错了',
    'app.cancel': '取消',
    'app.save': '保存',
    'app.delete': '删除',
    'app.edit': '编辑',
    'app.preview': '预览',
    'app.create': '创建',
    'app.submit': '提交',
    'app.close': '关闭',
    'app.back': '返回',
    'app.refresh': '刷新',
    'app.search': '搜索',
    'app.reset': '重置',
    'app.confirm': '确认',
    'app.success': '成功',
    'app.failed': '失败',

    // Navigation
    'nav.dashboard': '评估任务',
    'nav.newEvaluation': '新建评估',
    'nav.settings': '设置',
    'nav.templates': 'Prompt模板',

    // Language
    'language.zh': '中文',
    'language.en': 'English',
    'language.switch': '切换语言',

    // Dashboard
    'dashboard.title': '评估任务管理',
    'dashboard.newJob': '新建评估任务',
    'dashboard.noJobs': '暂无评估任务',
    'dashboard.createFirst': '创建您的第一个任务',
    'dashboard.status.pending': '待处理',
    'dashboard.status.processing': '处理中',
    'dashboard.status.completed': '已完成',
    'dashboard.status.failed': '失败',
    'dashboard.status.paused': '已暂停',
    'dashboard.status.all': '全部状态',
    'dashboard.stats.total': '总任务数',
    'dashboard.stats.running': '运行中',
    'dashboard.stats.pending': '待处理',
    'dashboard.stats.completed': '已完成',
    'dashboard.stats.failed': '失败',
    'dashboard.stats.paused': '已暂停',
    'dashboard.filter': '筛选',
    'dashboard.searchPlaceholder': '搜索任务...',
    'dashboard.noTasksFound': '未找到任务',
    'dashboard.noTasksDescription': '还没有创建任何评估任务',
    'dashboard.matchingTasks': '找到 {count} 个匹配任务',

    // Templates
    'templates.title': 'Prompt模板管理',
    'templates.single': '单蛋白分析模板',
    'templates.batch': '批量分析模板',
    'templates.newTemplate': '新建模板',
    'templates.default': '默认',
    'templates.setDefault': '设为默认',
    'templates.edit': '编辑模板',
    'templates.create': '创建模板',
    'templates.name': '模板名称',
    'templates.description': '描述',
    'templates.content': '模板内容',
    'templates.variables': '可用变量',
    'templates.createdAt': '创建于',
    'templates.updatedAt': '更新于',
    'templates.noTemplates': '暂无模板',
    'templates.createFirst': '创建第一个模板',
    'templates.deleteConfirm': '确定要删除模板 "{name}" 吗？',
    'templates.variable.proteinName': '蛋白质名称',
    'templates.variable.uniprotId': 'UniProt ID',
    'templates.variable.geneName': '基因名称',
    'templates.variable.pdbId': 'PDB ID',
    'templates.variable.resolution': '分辨率',
    'templates.variable.method': '实验方法',
    'templates.variable.sequenceLength': '序列长度',
    'templates.variable.molecularWeight': '分子量',

    // 3D Viewer
    'viewer.color.chain': '按链',
    'viewer.color.rainbow': '彩虹',
    'viewer.loading': '正在加载3D结构...',
    'viewer.error': '无法加载3D结构',
    'viewer.viewOnSite': '在官网查看',
    'viewer.controls': '拖拽旋转 • 滚轮缩放 • 右键平移',

    // Target Card
    'target.pdbStructures': 'PDB结构',
    'target.noPdbStructures': '暂无PDB结构',
    'target.qualityScore': '质量评分',
    'target.sequence': '序列',
    'target.function': '功能',
    'target.geneName': '基因名称',
    'target.organism': '物种',
    'target.length': '长度',
    'target.selectAll': '全选',
    'target.selected': '已选择',
    'target.structures': '个结构',

    // Templates Page
    'templates.return': '返回',
    'templates.refresh': '刷新',
    'templates.singleTab': '单蛋白分析模板',
    'templates.batchTab': '批量分析模板',
    'templates.close': '关闭',
    'templates.loading': '加载中...',
    'templates.noSingleTemplates': '还没有创建任何单蛋白分析模板',
    'templates.noBatchTemplates': '还没有创建任何批量分析模板',
    'templates.about': '关于 Prompt 模板',
    'templates.singleDesc': '单蛋白分析模板用于单个蛋白质的结构功能分析',
    'templates.batchDesc': '批量分析模板用于多个蛋白质之间的关系分析',
    'templates.defaultDesc': '默认模板将在创建新评估时自动使用',
    'templates.markdownDesc': '模板支持 Markdown 格式，可以使用变量占位符',

    // TemplateEditor Page
    'editor.title': '编辑器',
    'editor.name': '模板名称 *',
    'editor.namePlaceholder': '输入模板名称',
    'editor.description': '描述',
    'editor.descPlaceholder': '输入模板描述（可选）',
    'editor.variables': '快速插入变量',
    'editor.content': '模板内容 *',
    'editor.contentPlaceholder': '输入模板内容（支持 Markdown 格式）',
    'editor.untitled': '未命名模板',
    'editor.supportedMarkdown': '支持的 Markdown 语法',
    'editor.availableVars': '可用变量',

    // CreateJob Page
    'createJob.configMulti': '配置多靶点评估参数',
    'createJob.close': '关闭',
    'createJob.tips': '提示',
    'createJob.tip1': '支持从 UniProt 数据库获取蛋白质结构信息',
    'createJob.tip2': '并行模式同时处理所有靶点，速度更快',
    'createJob.tip3': '串行模式按顺序处理，适合资源受限场景',
    'createJob.tip4': '优先级范围为 1-10，数值越大优先级越高',

    // Settings Page
    'settings.addModel': '添加模型',
    'settings.loading': '加载中...',
    'settings.configName': '配置名称',
    'settings.configPlaceholder': '例如：DeepSeek Reasoner',
    'settings.apiTypeLabel': 'API 类型',
    'settings.cancel': '取消',
  },
  en: {
    // Common
    'app.title': 'Protein Structure Evaluation System',
    'app.subtitle': 'Multi-target Protein Structure Evaluation Platform',
    'app.loading': 'Loading...',
    'app.error': 'Error',
    'app.cancel': 'Cancel',
    'app.save': 'Save',
    'app.delete': 'Delete',
    'app.edit': 'Edit',
    'app.preview': 'Preview',
    'app.create': 'Create',
    'app.submit': 'Submit',
    'app.close': 'Close',
    'app.back': 'Back',
    'app.refresh': 'Refresh',
    'app.search': 'Search',
    'app.reset': 'Reset',
    'app.confirm': 'Confirm',
    'app.success': 'Success',
    'app.failed': 'Failed',

    // Navigation
    'nav.dashboard': 'Evaluation Tasks',
    'nav.newEvaluation': 'New Evaluation',
    'nav.settings': 'Settings',
    'nav.templates': 'Prompt Templates',

    // Language
    'language.zh': '中文',
    'language.en': 'English',
    'language.switch': 'Switch Language',

    // Dashboard
    'dashboard.title': 'Evaluation Task Management',
    'dashboard.newJob': 'New Evaluation Task',
    'dashboard.noJobs': 'No evaluation tasks',
    'dashboard.createFirst': 'Create your first task',
    'dashboard.status.pending': 'Pending',
    'dashboard.status.processing': 'Processing',
    'dashboard.status.completed': 'Completed',
    'dashboard.status.failed': 'Failed',
    'dashboard.status.paused': 'Paused',
    'dashboard.status.all': 'All Status',
    'dashboard.stats.total': 'Total Tasks',
    'dashboard.stats.running': 'Running',
    'dashboard.stats.pending': 'Pending',
    'dashboard.stats.completed': 'Completed',
    'dashboard.stats.failed': 'Failed',
    'dashboard.stats.paused': 'Paused',
    'dashboard.filter': 'Filter',
    'dashboard.searchPlaceholder': 'Search tasks...',
    'dashboard.noTasksFound': 'No tasks found',
    'dashboard.noTasksDescription': 'No evaluation tasks have been created yet',
    'dashboard.matchingTasks': 'Found {count} matching tasks',

    // Templates
    'templates.title': 'Prompt Template Management',
    'templates.single': 'Single Protein Template',
    'templates.batch': 'Batch Analysis Template',
    'templates.newTemplate': 'New Template',
    'templates.default': 'Default',
    'templates.setDefault': 'Set as Default',
    'templates.edit': 'Edit Template',
    'templates.create': 'Create Template',
    'templates.name': 'Template Name',
    'templates.description': 'Description',
    'templates.content': 'Template Content',
    'templates.variables': 'Available Variables',
    'templates.createdAt': 'Created at',
    'templates.updatedAt': 'Updated at',
    'templates.noTemplates': 'No Templates',
    'templates.createFirst': 'Create First Template',
    'templates.deleteConfirm': 'Are you sure you want to delete template "{name}"?',
    'templates.variable.proteinName': 'Protein Name',
    'templates.variable.uniprotId': 'UniProt ID',
    'templates.variable.geneName': 'Gene Name',
    'templates.variable.pdbId': 'PDB ID',
    'templates.variable.resolution': 'Resolution',
    'templates.variable.method': 'Method',
    'templates.variable.sequenceLength': 'Sequence Length',
    'templates.variable.molecularWeight': 'Molecular Weight',

    // 3D Viewer
    'viewer.color.chain': 'By Chain',
    'viewer.color.rainbow': 'Rainbow',
    'viewer.loading': 'Loading 3D structure...',
    'viewer.error': 'Failed to load 3D structure',
    'viewer.viewOnSite': 'View on Website',
    'viewer.controls': 'Drag to rotate • Scroll to zoom • Right-click to pan',

    // Target Card
    'target.pdbStructures': 'PDB Structures',
    'target.noPdbStructures': 'No PDB Structures',
    'target.qualityScore': 'Quality Score',
    'target.sequence': 'Sequence',
    'target.function': 'Function',
    'target.geneName': 'Gene Name',
    'target.organism': 'Organism',
    'target.length': 'Length',
    'target.selectAll': 'Select All',
    'target.selected': 'Selected',
    'target.structures': 'structures',

    // Templates Page
    'templates.return': 'Back',
    'templates.refresh': 'Refresh',
    'templates.singleTab': 'Single Protein Template',
    'templates.batchTab': 'Batch Analysis Template',
    'templates.close': 'Close',
    'templates.loading': 'Loading...',
    'templates.noSingleTemplates': 'No single protein templates created yet',
    'templates.noBatchTemplates': 'No batch analysis templates created yet',
    'templates.about': 'About Prompt Templates',
    'templates.singleDesc': 'Single protein templates are used for structure-function analysis of individual proteins',
    'templates.batchDesc': 'Batch analysis templates are used for relationship analysis between multiple proteins',
    'templates.defaultDesc': 'Default template will be automatically used when creating new evaluations',
    'templates.markdownDesc': 'Templates support Markdown format and can use variable placeholders',

    // TemplateEditor Page
    'editor.title': 'Editor',
    'editor.name': 'Template Name *',
    'editor.namePlaceholder': 'Enter template name',
    'editor.description': 'Description',
    'editor.descPlaceholder': 'Enter template description (optional)',
    'editor.variables': 'Quick Insert Variables',
    'editor.content': 'Template Content *',
    'editor.contentPlaceholder': 'Enter template content (supports Markdown format)',
    'editor.untitled': 'Untitled Template',
    'editor.supportedMarkdown': 'Supported Markdown Syntax',
    'editor.availableVars': 'Available Variables',

    // CreateJob Page
    'createJob.configMulti': 'Configure multi-target evaluation parameters',
    'createJob.close': 'Close',
    'createJob.tips': 'Tips',
    'createJob.tip1': 'Supports getting protein structure information from UniProt database',
    'createJob.tip2': 'Parallel mode processes all targets simultaneously, faster',
    'createJob.tip3': 'Serial mode processes in order, suitable for resource-limited scenarios',
    'createJob.tip4': 'Priority range is 1-10, higher number means higher priority',

    // Settings Page
    'settings.addModel': 'Add Model',
    'settings.loading': 'Loading...',
    'settings.configName': 'Config Name',
    'settings.configPlaceholder': 'e.g., DeepSeek Reasoner',
    'settings.apiTypeLabel': 'API Type',
    'settings.cancel': 'Cancel',
  }
};

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = localStorage.getItem('app-language');
    return (saved as Language) || 'zh';
  });

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('app-language', lang);
  }, []);

  const t = useCallback((key: string): string => {
    return translations[language][key] || key;
  }, [language]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLanguage = (): LanguageContextType => {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};
