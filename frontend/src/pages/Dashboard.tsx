import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw, Filter, Search, Settings, FileText, Sun, Moon, LayoutGrid, List } from 'lucide-react';
import { useJobs } from '../contexts/JobContext';
import { useLanguage } from '../contexts/LanguageContext';
import { useTheme } from '../contexts/ThemeContext';
import { JobCard, type Job } from '../components/JobCard';
import { JobRow } from '../components/JobRow';
import { Sparkline } from '../components/Sparkline';
import { Button } from '../components/Button';

import { LanguageSwitcher } from '../components/LanguageSwitcher';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const { theme, toggleTheme } = useTheme();
  const {
    jobs,
    isLoading,
    error,
    totalJobs,
    fetchJobs,
    deleteJob,
    clearError,
  } = useJobs();

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Fetch jobs on mount
  useEffect(() => {
    fetchJobs({ sort_by: 'created_at', sort_order: 'desc' });
  }, [fetchJobs]);

  // Filter jobs
  const filteredJobs = jobs.filter((job) => {
    const matchesStatus = statusFilter ? job.status === statusFilter : true;
    const matchesSearch = searchQuery
      ? job.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        job.description?.toLowerCase().includes(searchQuery.toLowerCase())
      : true;
    return matchesStatus && matchesSearch;
  });

  // Get status counts
  const statusCounts = jobs.reduce(
    (acc, job) => {
      acc[job.status] = (acc[job.status] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  // Compute 7-day sparkline data per status
  const sparklineData = useMemo(() => {
    const days = 7;
    const now = new Date();
    const buckets: { completed: number[]; running: number[]; total: number[] } = {
      completed: Array(days).fill(0),
      running: Array(days).fill(0),
      total: Array(days).fill(0),
    };
    jobs.forEach((job) => {
      if (!job.createdAt) return;
      const d = new Date(job.createdAt);
      const diff = Math.floor((now.getTime() - d.getTime()) / 86400000);
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

  const handleJobClick = (job: Job) => {
    navigate(`/jobs/${job.id}`);
  };

  const handleDeleteJob = async (job: Job) => {
    const confirmMsg = language === 'zh'
      ? `确定要删除任务 "${job.title}" 吗？`
      : `Are you sure you want to delete task "${job.title}"?`;
    if (window.confirm(confirmMsg)) {
      await deleteJob(job.id);
    }
  };

  const statusOptions = [
    { value: '', label: t('dashboard.status.all') },
    { value: 'pending', label: t('dashboard.status.pending') },
    { value: 'processing', label: t('dashboard.status.processing') },
    { value: 'completed', label: t('dashboard.status.completed') },
    { value: 'failed', label: t('dashboard.status.failed') },
    { value: 'paused', label: t('dashboard.status.paused') },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0e1a] relative overflow-hidden">
      {/* Subtle dot grid background for dark mode */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.025] dark:opacity-[0.04]" aria-hidden="true">
        <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="dots" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="currentColor" className="text-gray-400"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dots)" />
        </svg>
      </div>
      {/* Gradient orb top-right */}
      <div className="pointer-events-none absolute -top-32 -right-32 w-96 h-96 rounded-full bg-amber-500/[0.02] dark:bg-amber-500/[0.03] blur-3xl" aria-hidden="true" />
      <div className="relative z-10">
      {/* Header */}
      <header className="bg-white dark:bg-[#0f1525] border-b border-gray-200 dark:border-gray-700/60 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500 dark:bg-amber-600 rounded-lg flex items-center justify-center">
                {/* Protein Helix SVG Logo */}
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M12 3 C 7 3, 4 6.5, 4 12 C 4 17.5, 7 21, 12 21 C 17 21, 20 17.5, 20 12 C 20 6.5, 17 3, 12 3Z" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M8 8 Q 12 10.5, 16 8" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <path d="M16 12 Q 12 14.5, 8 12" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <path d="M8 16 Q 12 18.5, 16 16" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <circle cx="12" cy="12" r="1.5" fill="white"/>
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">{t('app.title')}</h1>
                <p className="text-sm text-gray-500 dark:text-gray-300">{t('app.subtitle')}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                title={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
              >
                {theme === 'dark' ? <Sun className="w-5 h-5 text-gray-400" /> : <Moon className="w-5 h-5 text-gray-600" />}
              </button>
              <LanguageSwitcher />
              <Button variant="outline" onClick={() => navigate('/templates')}>
                <FileText className="w-4 h-4 mr-2" />
                {t('nav.templates')}
              </Button>
              <Button variant="outline" onClick={() => navigate('/settings')}>
                <Settings className="w-4 h-4 mr-2" />
                {t('nav.settings')}
              </Button>
              <div className="h-6 w-px bg-gray-600" />
              <Button variant="outline" onClick={handleRefresh} disabled={isLoading}>
                <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                {t('app.refresh')}
              </Button>
              <Button onClick={() => navigate('/jobs/new')}>
                <Plus className="w-4 h-4 mr-2" />
                {t('dashboard.newJob')}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Cards — professional dark glass */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          {/* Total */}
          <div className="relative overflow-hidden rounded-xl border border-gray-200/60 dark:border-gray-700/60 bg-gray-50 dark:bg-[#0f1525] p-4 flex flex-col gap-1">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-gray-400 to-gray-600" />
            <div className="absolute right-2 top-2"><Sparkline data={sparklineData.total} color="#64748b" width={48} height={20} /></div>
            <div className="text-3xl font-bold text-gray-800 dark:text-gray-100 pr-12">{totalJobs}</div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide uppercase">{t('dashboard.stats.total')}</div>
          </div>
          {/* Running */}
          <div className="relative overflow-hidden rounded-xl border border-blue-200/40 dark:border-blue-800/30 bg-gray-50 dark:bg-[#0f1525] p-4 flex flex-col gap-1">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-blue-400 to-blue-700" />
            <div className="absolute right-2 top-2"><Sparkline data={sparklineData.running} color="#3b82f6" width={48} height={20} /></div>
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 pr-12">{statusCounts.processing || 0}</div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide uppercase">{t('dashboard.stats.running')}</div>
          </div>
          {/* Pending */}
          <div className="relative overflow-hidden rounded-xl border border-yellow-200/40 dark:border-yellow-800/30 bg-gray-50 dark:bg-[#0f1525] p-4 flex flex-col gap-1">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-yellow-400 to-yellow-700" />
            <div className="absolute right-2 top-2"><Sparkline data={[0,0,0,0,0,0,statusCounts.pending||0]} color="#f59e0b" width={48} height={20} /></div>
            <div className="text-3xl font-bold text-yellow-600 dark:text-yellow-400 pr-12">{statusCounts.pending || 0}</div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide uppercase">{t('dashboard.stats.pending')}</div>
          </div>
          {/* Completed */}
          <div className="relative overflow-hidden rounded-xl border border-green-200/40 dark:border-green-800/30 bg-gray-50 dark:bg-[#0f1525] p-4 flex flex-col gap-1">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-green-400 to-green-700" />
            <div className="absolute right-2 top-2"><Sparkline data={sparklineData.completed} color="#22c55e" width={48} height={20} /></div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400 pr-12">{statusCounts.completed || 0}</div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide uppercase">{t('dashboard.stats.completed')}</div>
          </div>
          {/* Failed */}
          <div className="relative overflow-hidden rounded-xl border border-red-200/40 dark:border-red-800/30 bg-gray-50 dark:bg-[#0f1525] p-4 flex flex-col gap-1">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-red-400 to-red-700" />
            <div className="absolute right-2 top-2"><Sparkline data={[0,0,0,0,0,0,statusCounts.failed||0]} color="#ef4444" width={48} height={20} /></div>
            <div className="text-3xl font-bold text-red-600 dark:text-red-400 pr-12">{statusCounts.failed || 0}</div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide uppercase">{t('dashboard.stats.failed')}</div>
          </div>
          {/* Paused */}
          <div className="relative overflow-hidden rounded-xl border border-gray-200/40 dark:border-gray-700/40 bg-gray-50 dark:bg-[#0f1525] p-4 flex flex-col gap-1">
            <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-gradient-to-b from-gray-400 to-gray-600" />
            <div className="absolute right-2 top-2"><Sparkline data={[0,0,0,0,0,0,statusCounts.paused||0]} color="#9ca3af" width={48} height={20} /></div>
            <div className="text-3xl font-bold text-gray-600 dark:text-gray-400 pr-12">{statusCounts.paused || 0}</div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide uppercase">{t('dashboard.stats.paused')}</div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-red-600 dark:text-red-400">{error}</p>
              <button
                onClick={clearError}
                className="text-red-500 dark:text-red-400 hover:text-red-600 dark:hover:text-red-300"
              >
                {t('app.close')}
              </button>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="mb-6 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-500 dark:text-gray-300" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-300">{t('dashboard.filter')}:</span>
          </div>
          <div className="flex items-center gap-2">
            {statusOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setStatusFilter(option.value)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  statusFilter === option.value
                    ? 'bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400 border border-amber-300 dark:border-amber-500/40'
                    : 'bg-gray-200 dark:bg-gray-800 text-gray-600 dark:text-gray-300 border border-gray-300 dark:border-gray-500 hover:bg-gray-300 dark:hover:bg-gray-600'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="flex-1 min-w-[200px] max-w-md ml-auto">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
              <input
                type="text"
                placeholder={t('dashboard.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-500 bg-white dark:bg-gray-800 rounded-lg text-sm text-gray-800 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-amber-500/40 focus:border-amber-500 dark:focus:ring-amber-500/40 dark:focus:border-amber-500"
              />
            </div>
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-gray-200 dark:bg-gray-800 rounded-lg p-0.5 border border-gray-300 dark:border-gray-600">
            <button
              onClick={() => setViewMode('grid')}
              title="Grid view"
              className={`p-1.5 rounded-md transition-all ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-amber-600 dark:text-amber-400'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              title="List view"
              className={`p-1.5 rounded-md transition-all ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-gray-700 shadow-sm text-amber-600 dark:text-amber-400'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Job Grid */}
        {isLoading && jobs.length === 0 ? (
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-800 mb-4">
              <RefreshCw className="w-8 h-8 text-gray-400 dark:text-gray-500 animate-spin" />
            </div>
            <p className="text-gray-500 dark:text-gray-300">{t('app.loading')}</p>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div className="text-center py-16">
            {/* Large biotech helix illustration */}
            <div className="inline-flex items-center justify-center w-24 h-24 rounded-2xl bg-gradient-to-br from-amber-500/10 to-blue-500/10 dark:from-amber-500/5 dark:to-blue-500/5 border border-amber-500/20 dark:border-amber-500/10 mb-6">
              <svg width="48" height="48" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" className="text-amber-500/60">
                <path d="M50 8 C 28 8, 12 28, 12 50 C 12 72, 28 92, 50 92 C 72 92, 88 72, 88 50 C 88 28, 72 8, 50 8Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M25 25 Q 50 40, 75 25" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M75 42 Q 50 57, 25 42" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M25 58 Q 50 73, 75 58" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="50" cy="50" r="6" fill="currentColor" opacity="0.5"/>
                <circle cx="25" cy="25" r="3" fill="currentColor"/>
                <circle cx="75" cy="25" r="3" fill="currentColor"/>
                <circle cx="25" cy="42" r="3" fill="currentColor"/>
                <circle cx="75" cy="42" r="3" fill="currentColor"/>
                <circle cx="25" cy="58" r="3" fill="currentColor"/>
                <circle cx="75" cy="58" r="3" fill="currentColor"/>
                <circle cx="50" cy="92" r="3" fill="currentColor"/>
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-700 dark:text-gray-100 mb-2">{t('dashboard.noJobs')}</h3>
            <p className="text-gray-500 dark:text-gray-400 mb-8 max-w-sm mx-auto leading-relaxed">{t('dashboard.noTasksDescription')}</p>
            <Button size="lg" onClick={() => navigate('/jobs/new')} className="shadow-lg shadow-amber-500/20">
              <Plus className="w-5 h-5 mr-2" />
              {t('dashboard.createFirst')}
            </Button>
          </div>
        ) : (
          viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onClick={handleJobClick}
                  onMenuClick={(job) => {
                    const confirmMsg = language === 'zh'
                      ? `删除任务 "${job.title}"?`
                      : `Delete task "${job.title}"?`;
                    if (window.confirm(confirmMsg)) handleDeleteJob(job);
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden shadow-sm">
              {/* List header */}
              <div className="flex items-center gap-4 px-4 py-2.5 border-b border-gray-100 dark:border-gray-700/60 bg-gray-50 dark:bg-gray-800/80 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
                <div className="w-8 flex-shrink-0" />
                <div className="flex-1 min-w-0">{language === 'zh' ? '任务名称' : 'Task'}</div>
                <div className="hidden sm:block w-24 text-center">{language === 'zh' ? '进度' : 'Progress'}</div>
                <div className="hidden md:flex w-24">{language === 'zh' ? '靶点数' : 'Targets'}</div>
                <div className="hidden sm:flex w-28">{language === 'zh' ? '创建时间' : 'Created'}</div>
                <div className="w-8 flex-shrink-0" />
              </div>
              {filteredJobs.map((job) => (
                <JobRow
                  key={job.id}
                  job={job}
                  onClick={handleJobClick}
                  onMenuClick={(job) => {
                    const confirmMsg = language === 'zh'
                      ? `删除任务 "${job.title}"?`
                      : `Delete task "${job.title}"?`;
                    if (window.confirm(confirmMsg)) handleDeleteJob(job);
                  }}
                />
              ))}
            </div>
          )
        )}

        {/* Show filtered count */}
        {searchQuery && (
          <div className="mt-6 text-center text-sm text-gray-500 dark:text-gray-300">
            {t('dashboard.matchingTasks').replace('{count}', filteredJobs.length.toString())}
          </div>
        )}
      </main>
      </div>
    </div>
  );
};