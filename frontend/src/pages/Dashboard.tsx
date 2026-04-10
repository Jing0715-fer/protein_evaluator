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
import { Card, CardContent } from '../components/Card';
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-800">
      {/* Header */}
      <header className="bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-500 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
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
        {/* Stats Cards with Sparklines */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <Card className="border-l-4 border-l-gray-500 dark:border-l-gray-500">
            <CardContent className="p-4 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">{totalJobs}</div>
                <Sparkline data={sparklineData.total} color="#64748b" width={56} height={24} />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-300">{t('dashboard.stats.total')}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-blue-500 dark:border-l-blue-500">
            <CardContent className="p-4 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div className="text-2xl font-bold text-blue-500 dark:text-blue-400">{statusCounts.processing || 0}</div>
                <Sparkline data={sparklineData.running} color="#3b82f6" width={56} height={24} />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-300">{t('dashboard.stats.running')}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-yellow-500 dark:border-l-yellow-500">
            <CardContent className="p-4 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div className="text-2xl font-bold text-yellow-500 dark:text-yellow-400">{statusCounts.pending || 0}</div>
                <Sparkline data={[0,0,0,0,0,0,statusCounts.pending||0]} color="#f59e0b" width={56} height={24} />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-300">{t('dashboard.stats.pending')}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-green-500 dark:border-l-green-500">
            <CardContent className="p-4 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div className="text-2xl font-bold text-green-500 dark:text-green-400">{statusCounts.completed || 0}</div>
                <Sparkline data={sparklineData.completed} color="#22c55e" width={56} height={24} />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-300">{t('dashboard.stats.completed')}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-red-500 dark:border-l-red-500">
            <CardContent className="p-4 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div className="text-2xl font-bold text-red-500 dark:text-red-400">{statusCounts.failed || 0}</div>
                <Sparkline data={[0,0,0,0,0,0,statusCounts.failed||0]} color="#ef4444" width={56} height={24} />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-300">{t('dashboard.stats.failed')}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-gray-400 dark:border-l-gray-500">
            <CardContent className="p-4 flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <div className="text-2xl font-bold text-gray-500 dark:text-gray-300">{statusCounts.paused || 0}</div>
                <Sparkline data={[0,0,0,0,0,0,statusCounts.paused||0]} color="#9ca3af" width={56} height={24} />
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-300">{t('dashboard.stats.paused')}</div>
            </CardContent>
          </Card>
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
          <div className="text-center py-12">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-200 dark:bg-gray-800 mb-4">
              <svg className="w-8 h-8 text-gray-400 dark:text-gray-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M12 3 C 7 3, 4 6.5, 4 12 C 4 17.5, 7 21, 12 21 C 17 21, 20 17.5, 20 12 C 20 6.5, 17 3, 12 3Z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                <path d="M8 8 Q 12 10.5, 16 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                <path d="M16 12 Q 12 14.5, 8 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                <path d="M8 16 Q 12 18.5, 16 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                <circle cx="12" cy="12" r="1.5" fill="currentColor"/>
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-800 dark:text-gray-100 mb-2">{t('dashboard.noJobs')}</h3>
            <p className="text-gray-500 dark:text-gray-300 mb-6">{t('dashboard.noTasksDescription')}</p>
            <Button onClick={() => navigate('/jobs/new')}>
              <Plus className="w-4 h-4 mr-2" />
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
  );
};