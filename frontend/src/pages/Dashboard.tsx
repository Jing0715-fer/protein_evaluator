import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw, Search, Settings, FileText, Sun, Moon, LayoutGrid, List, Activity } from 'lucide-react';
import { useJobs } from '../contexts/JobContext';
import { useLanguage } from '../contexts/LanguageContext';
import { useTheme } from '../contexts/ThemeContext';
import { JobCard } from '../components/JobCard';
import { JobRow } from '../components/JobRow';
import { Sparkline } from '../components/Sparkline';
import { Button } from '../components/Button';
import { LanguageSwitcher } from '../components/LanguageSwitcher';
import type { Job } from '../components/JobCard';

// ─── Helix pattern SVG ─────────────────────────────────────────────────────────
const HelixPattern: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} viewBox="0 0 200 120" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <g opacity="0.12">
      <ellipse cx="100" cy="60" rx="55" ry="80" stroke="currentColor" strokeWidth="1" strokeDasharray="3 5"/>
      <ellipse cx="100" cy="60" rx="35" ry="80" stroke="currentColor" strokeWidth="0.75" strokeDasharray="2 4"/>
      <path d="M65 15 Q 100 32, 135 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M135 32 Q 100 49, 65 32" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M65 50 Q 100 67, 135 50" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M135 67 Q 100 84, 65 67" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M65 85 Q 100 102, 135 85" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx="65" cy="15" r="3.5" fill="currentColor"/>
      <circle cx="135" cy="32" r="3.5" fill="currentColor"/>
      <circle cx="65" cy="50" r="3.5" fill="currentColor"/>
      <circle cx="135" cy="67" r="3.5" fill="currentColor"/>
      <circle cx="65" cy="85" r="3.5" fill="currentColor"/>
      <circle cx="100" cy="60" r="5" fill="currentColor" opacity="0.6"/>
    </g>
  </svg>
);

// ─── Stat card with gradient left border + sparkline ─────────────────────────
interface StatCardProps {
  label: string;
  value: number | string;
  sparkData: number[];
  color: string;
  sub?: string;
  gradientFrom: string;
  gradientTo: string;
}

const StatCard: React.FC<StatCardProps> = ({ label, value, sparkData, color, sub, gradientFrom, gradientTo }) => (
  <div className="relative overflow-hidden rounded-xl bg-white dark:bg-[#0f1525] border border-gray-200/80 dark:border-gray-700/60 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 group">
    {/* Gradient top-left accent */}
    <div className="absolute -top-6 -left-6 w-20 h-20 rounded-full opacity-[0.06] group-hover:opacity-[0.1] transition-opacity"
      style={{ background: `radial-gradient(circle, ${color}, transparent)` }} />
    {/* Left color border */}
    <div className="absolute left-0 top-0 bottom-0 w-0.5" style={{ background: `linear-gradient(to bottom, ${gradientFrom}, ${gradientTo})` }} />
    <div className="p-3 pl-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-3xl font-bold text-gray-800 dark:text-gray-100 leading-none">{value}</div>
          <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mt-1.5 uppercase tracking-wider">{label}</div>
          {sub && <div className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sub}</div>}
        </div>
        <div className="flex-shrink-0 pt-1">
          <Sparkline data={sparkData} color={color} width={52} height={24} />
        </div>
      </div>
    </div>
  </div>
);

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const { theme, toggleTheme } = useTheme();
  const { jobs, isLoading, error, totalJobs, fetchJobs, deleteJob, clearError } = useJobs();

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  useEffect(() => {
    fetchJobs({ sort_by: 'created_at', sort_order: 'desc' });
  }, [fetchJobs]);

  const filteredJobs = jobs.filter((job) => {
    const matchesStatus = statusFilter ? job.status === statusFilter : true;
    const matchesSearch = searchQuery
      ? job.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        job.description?.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    return matchesStatus && matchesSearch;
  });

  const statusCounts = jobs.reduce(
    (acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  // Sparkline data: 7-day buckets
  const sparklineData = React.useMemo(() => {
    const days = 7;
    const now = new Date();
    const buckets = { completed: Array(days).fill(0), running: Array(days).fill(0), total: Array(days).fill(0) };
    jobs.forEach((job) => {
      if (!job.createdAt) return;
      const diff = Math.floor((now.getTime() - new Date(job.createdAt).getTime()) / 86400000);
      if (diff < 0 || diff >= days) return;
      const idx = days - 1 - diff;
      buckets.total[idx]++;
      if (job.status === 'completed') buckets.completed[idx]++;
      if (job.status === 'running' || job.status === 'processing') buckets.running[idx]++;
    });
    return buckets;
  }, [jobs]);

  const handleRefresh = () => {
    fetchJobs({ status: statusFilter || undefined, sort_by: 'created_at', sort_order: 'desc' });
  };

  const handleJobClick = (job: Job) => navigate(`/jobs/${job.id}`);
  const handleDeleteJob = async (job: Job) => {
    const confirmMsg = language === 'zh'
      ? `确定要删除任务 "${job.title}" 吗？`
      : `Are you sure you want to delete task "${job.title}"?`;
    if (window.confirm(confirmMsg)) await deleteJob(job.id);
  };

  const statusOptions = [
    { value: '', label: t('dashboard.status.all') },
    { value: 'pending', label: t('dashboard.status.pending') },
    { value: 'processing', label: t('dashboard.status.processing') },
    { value: 'completed', label: t('dashboard.status.completed') },
    { value: 'failed', label: t('dashboard.status.failed') },
    { value: 'paused', label: t('dashboard.status.paused') },
  ];

  const empty = searchQuery || statusFilter;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a]">

      {/* ── HEADER ────────────────────────────────────────────────────── */}
      <header className="bg-white dark:bg-[#0f1525] border-b border-gray-200 dark:border-gray-700/60 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Brand */}
            <div className="flex items-center gap-3 flex-shrink-0">
              <div className="relative">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <path d="M12 2 C 7 2, 4 6, 4 12 C 4 18, 7 22, 12 22 C 17 22, 20 18, 20 12 C 20 6, 17 2, 12 2Z" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M8 7 Q 12 10, 16 7" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M16 12 Q 12 15, 8 12" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                    <path d="M8 17 Q 12 20, 16 17" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                {/* Status dot */}
                <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-green-500 border-2 border-white dark:border-[#0f1525] shadow-sm"
                  title={language === 'zh' ? '系统正常' : 'System operational'} />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-base font-bold text-gray-800 dark:text-gray-100 leading-tight">{t('app.title')}</h1>
                <p className="text-xs text-gray-400 dark:text-gray-500 leading-tight">{t('app.subtitle')}</p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <button onClick={toggleTheme}
                className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                title={theme === 'dark' ? '浅色模式' : '深色模式'}>
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
              <LanguageSwitcher />
              <Button variant="ghost" className="text-gray-600 dark:text-gray-400 text-sm hidden md:flex" onClick={() => navigate('/templates')}>
                <FileText className="w-4 h-4 mr-1.5" />
                {t('nav.templates')}
              </Button>
              <Button variant="ghost" className="text-gray-600 dark:text-gray-400 text-sm" onClick={() => navigate('/settings')}>
                <Settings className="w-4 h-4" />
              </Button>
              <div className="h-5 w-px bg-gray-200 dark:bg-gray-700 mx-1" />
              <Button variant="outline" onClick={handleRefresh} disabled={isLoading}
                className="border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 text-sm">
                <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              <Button className="bg-amber-500 hover:bg-amber-600 text-white shadow-sm text-sm"
                onClick={() => navigate('/jobs/new')}>
                <Plus className="w-4 h-4 mr-1.5" />
                <span className="hidden sm:inline">{t('dashboard.newJob')}</span>
                <span className="sm:hidden">{language === 'zh' ? '新建' : 'New'}</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* ── MAIN ───────────────────────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">

        {/* Hero banner with helix pattern */}
        <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-[#0f1525] via-[#111d38] to-[#0d1933] dark:from-[#0f1525] dark:via-[#111d38] dark:to-[#0d1933] mb-8 shadow-xl shadow-black/10">
          {/* Helix bg */}
          <div className="absolute right-0 top-0 w-64 h-full text-amber-400/20 pointer-events-none" aria-hidden="true">
            <HelixPattern className="w-full h-full" />
          </div>
          <div className="absolute inset-0 bg-gradient-to-r from-amber-500/[0.04] to-transparent pointer-events-none" aria-hidden="true" />

          <div className="relative px-6 py-5 sm:px-8 sm:py-6 flex flex-col sm:flex-row items-start sm:items-center gap-5">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-500/10 border border-green-500/20 text-green-400 text-xs font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                  {language === 'zh' ? '平台运行正常' : 'Platform Operational'}
                </span>
                {(statusCounts.processing || 0) > 0 && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium">
                    <Activity className="w-3 h-3" />
                    {language === 'zh' ? `${statusCounts.processing} 个运行中` : `${statusCounts.processing} Running`}
                  </span>
                )}
              </div>
              <h2 className="text-xl sm:text-2xl font-bold text-white/90 mb-1 leading-tight">
                {language === 'zh' ? '多靶点蛋白质结构评估平台' : 'Multi-Target Protein Structure Evaluation'}
              </h2>
              <p className="text-white/40 text-sm max-w-lg leading-relaxed">
                {language === 'zh'
                  ? '基于 AlphaFold2 与 AI 大模型，对蛋白质结构进行深度质量评估，生成可解释的结构-功能分析报告。'
                  : 'Deep protein structure quality assessment powered by AlphaFold2 and AI LLMs, generating interpretable structure-function analysis reports.'}
              </p>
            </div>
            <div className="flex-shrink-0 flex gap-3">
              <Button size="lg" className="bg-amber-500 hover:bg-amber-600 text-white shadow-lg shadow-amber-500/25"
                onClick={() => navigate('/jobs/new')}>
                <Plus className="w-4 h-4 mr-2" />
                {language === 'zh' ? '新建任务' : 'New Task'}
              </Button>
              <Button size="lg" variant="outline"
                className="border-white/20 text-white/70 hover:text-white hover:border-white/40 bg-white/5 text-sm"
                onClick={() => navigate('/templates')}>
                {language === 'zh' ? '使用模板' : 'Templates'}
              </Button>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-center justify-between">
            <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
            <button onClick={clearError} className="text-red-500 hover:text-red-600 text-sm ml-4">{t('app.close')}</button>
          </div>
        )}

        {/* Stats cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          <StatCard label={t('dashboard.stats.total')} value={totalJobs}
            sparkData={sparklineData.total} color="#64748b"
            gradientFrom="#4b5563" gradientTo="#374151"
            sub={language === 'zh' ? '全部时间' : 'All time'} />
          <StatCard label={t('dashboard.stats.running')} value={statusCounts.processing || 0}
            sparkData={sparklineData.running} color="#3b82f6"
            gradientFrom="#3b82f6" gradientTo="#1d4ed8"
            sub={(statusCounts.processing || 0) > 0 ? (language === 'zh' ? '处理中...' : 'Processing...') : (language === 'zh' ? '空闲' : 'Idle')} />
          <StatCard label={t('dashboard.stats.pending')} value={statusCounts.pending || 0}
            sparkData={[0,0,0,0,0,0,statusCounts.pending||0]} color="#f59e0b"
            gradientFrom="#f59e0b" gradientTo="#d97706" />
          <StatCard label={t('dashboard.stats.completed')} value={statusCounts.completed || 0}
            sparkData={sparklineData.completed} color="#22c55e"
            gradientFrom="#22c55e" gradientTo="#15803d"
            sub={language === 'zh' ? '成功完成' : 'Completed'} />
          <StatCard label={t('dashboard.stats.failed')} value={statusCounts.failed || 0}
            sparkData={[0,0,0,0,0,0,statusCounts.failed||0]} color="#ef4444"
            gradientFrom="#ef4444" gradientTo="#b91c1c"
            sub={language === 'zh' ? '需检查' : 'Needs review'} />
          <StatCard label={t('dashboard.stats.paused')} value={statusCounts.paused || 0}
            sparkData={[0,0,0,0,0,0,statusCounts.paused||0]} color="#9ca3af"
            gradientFrom="#9ca3af" gradientTo="#6b7280" />
        </div>

        {/* Filter + search */}
        <div className="mb-6 flex flex-wrap items-center gap-3">
          {/* Status pill filters */}
          <div className="flex items-center gap-1 p-1 bg-white dark:bg-[#0f1525] border border-gray-200 dark:border-gray-700/60 rounded-xl shadow-sm">
            {statusOptions.map((opt) => (
              <button key={opt.value} onClick={() => setStatusFilter(opt.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  statusFilter === opt.value
                    ? 'bg-gray-800 dark:bg-[#162032] text-white shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                }`}>
                {opt.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="flex-1 min-w-[180px] max-w-sm relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input type="text" placeholder={t('dashboard.searchPlaceholder')}
              value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#0f1525] rounded-xl text-sm text-gray-800 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-500/40 focus:border-amber-500/60 transition-all shadow-sm" />
          </div>

          {/* View toggle */}
          <div className="flex items-center bg-white dark:bg-[#0f1525] border border-gray-200 dark:border-gray-700/60 rounded-xl p-1 shadow-sm">
            <button onClick={() => setViewMode('grid')}
              className={`p-1.5 rounded-lg transition-all ${viewMode === 'grid' ? 'bg-gray-800 dark:bg-[#162032] shadow-sm text-amber-500' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}`}>
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button onClick={() => setViewMode('list')}
              className={`p-1.5 rounded-lg transition-all ${viewMode === 'list' ? 'bg-gray-800 dark:bg-[#162032] shadow-sm text-amber-500' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}`}>
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Results summary */}
        {(searchQuery || statusFilter) && (
          <div className="mb-4 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span>
              {filteredJobs.length} {language === 'zh' ? '个任务' : 'task(s)'}
              <span className="text-gray-400 dark:text-gray-500"> · {jobs.length} {language === 'zh' ? '总计' : 'total'}</span>
            </span>
            <button onClick={() => { setSearchQuery(''); setStatusFilter(''); }}
              className="text-amber-600 dark:text-amber-400 hover:underline text-xs font-medium">
              {language === 'zh' ? '清除筛选' : 'Clear'}
            </button>
          </div>
        )}

        {/* Loading */}
        {isLoading && jobs.length === 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="h-44 rounded-xl bg-gray-100 dark:bg-[#0f1525] border border-gray-200 dark:border-gray-700/60 animate-pulse" />
            ))}
          </div>
        ) : filteredJobs.length === 0 ? (
          /* Empty state */
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-amber-500/10 to-blue-500/10 border border-amber-500/20 mb-6">
              <svg width="40" height="40" viewBox="0 0 100 100" fill="none" className="text-amber-500/50" aria-hidden="true">
                <path d="M50 8 C 28 8, 12 28, 12 50 C 12 72, 28 92, 50 92 C 72 92, 88 72, 88 50 C 88 28, 72 8, 50 8Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M25 25 Q 50 40, 75 25" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M75 42 Q 50 57, 25 42" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M25 58 Q 50 73, 75 58" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="50" cy="50" r="5" fill="currentColor" opacity="0.5"/>
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-700 dark:text-gray-100 mb-2">
              {empty ? (language === 'zh' ? '没有匹配的任务' : 'No matching tasks') : (language === 'zh' ? '还没有评估任务' : 'No tasks yet')}
            </h3>
            <p className="text-gray-400 dark:text-gray-500 mb-8 max-w-sm mx-auto text-sm">
              {empty
                ? (language === 'zh' ? '试试调整筛选条件' : 'Try adjusting your filters')
                : (language === 'zh' ? '开始你的第一次蛋白质结构评估' : 'Start your first protein structure evaluation')}
            </p>
            {empty ? (
              <Button variant="outline" onClick={() => { setSearchQuery(''); setStatusFilter(''); }}>
                {language === 'zh' ? '清除筛选' : 'Clear filters'}
              </Button>
            ) : (
              <Button size="lg" className="shadow-lg shadow-amber-500/20" onClick={() => navigate('/jobs/new')}>
                <Plus className="w-5 h-5 mr-2" />
                {t('dashboard.createFirst')}
              </Button>
            )}
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredJobs.map((job) => (
              <JobCard key={job.id} job={job} onClick={handleJobClick}
                onMenuClick={(job) => {
                  const confirmMsg = language === 'zh' ? `删除 "${job.title}"？` : `Delete "${job.title}"?`;
                  if (window.confirm(confirmMsg)) handleDeleteJob(job);
                }} />
            ))}
          </div>
        ) : (
          <div className="bg-white dark:bg-[#0f1525] border border-gray-200 dark:border-gray-700/60 rounded-xl overflow-hidden shadow-sm">
            <div className="flex items-center gap-4 px-4 py-2.5 border-b border-gray-100 dark:border-gray-700/60 bg-gray-50 dark:bg-[#162032]/60 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider">
              <div className="w-8 flex-shrink-0" />
              <div className="flex-1">{language === 'zh' ? '任务名称' : 'Task'}</div>
              <div className="hidden sm:block w-24 text-center">{language === 'zh' ? '进度' : 'Progress'}</div>
              <div className="hidden md:flex w-24">{language === 'zh' ? '靶点数' : 'Targets'}</div>
              <div className="hidden sm:flex w-28">{language === 'zh' ? '创建时间' : 'Created'}</div>
              <div className="w-8 flex-shrink-0" />
            </div>
            {filteredJobs.map((job) => (
              <JobRow key={job.id} job={job} onClick={handleJobClick}
                onMenuClick={(job) => {
                  const confirmMsg = language === 'zh' ? `删除 "${job.title}"？` : `Delete "${job.title}"?`;
                  if (window.confirm(confirmMsg)) handleDeleteJob(job);
                }} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};
