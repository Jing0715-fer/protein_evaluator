import React from 'react';
import { Calendar, Target, Trash2 } from 'lucide-react';
import { Badge } from './Badge';
import { useLanguage } from '../contexts/LanguageContext';
import type { Job } from '../types';

interface JobRowProps {
  job: Job;
  onClick?: (job: Job) => void;
  onMenuClick?: (job: Job) => void;
}

export const JobRow: React.FC<JobRowProps> = ({ job, onClick, onMenuClick }) => {
  const { language } = useLanguage();

  const statusLabels: Record<Job['status'], string> = {
    completed: language === 'zh' ? '已完成' : 'Completed',
    pending: language === 'zh' ? '待处理' : 'Pending',
    failed: language === 'zh' ? '失败' : 'Failed',
    running: language === 'zh' ? '运行中' : 'Running',
    processing: language === 'zh' ? '运行中' : 'Running',
    paused: language === 'zh' ? '已暂停' : 'Paused',
  };

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return '—';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '—';
    return date.toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  const ringColor = {
    completed: '#22c55e',
    pending: '#9ca3af',
    failed: '#ef4444',
    running: '#3b82f6',
    processing: '#3b82f6',
    paused: '#f59e0b',
  }[job.status] as string;

  const circumference = 2 * Math.PI * 12;

  return (
    <div
      className="flex items-center gap-4 px-4 py-3 border-b border-gray-100 dark:border-gray-700/50 last:border-0 hover:bg-gray-50 dark:hover:bg-gray-800/60 cursor-pointer transition-colors rounded-lg"
      onClick={() => onClick?.(job)}
    >
      {/* Circular progress ring */}
      <div className="relative flex-shrink-0">
        <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="12" fill="none" stroke="currentColor" strokeWidth="3"
            className="text-gray-200 dark:text-gray-700" />
          <circle cx="16" cy="16" r="12" fill="none"
            strokeWidth="3" strokeLinecap="round"
            strokeDasharray={`${circumference}`}
            strokeDashoffset={`${circumference * (1 - job.progress / 100)}`}
            transform="rotate(-90 16 16)"
            style={{ stroke: ringColor }}
            className="transition-all duration-500" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[9px] font-bold text-gray-600 dark:text-gray-100">{job.progress}%</span>
        </div>
      </div>

      {/* Title + badge */}
      <div className="flex items-center gap-2 min-w-0 flex-1">
        <span className="font-medium text-gray-800 dark:text-gray-100 truncate text-sm">{job.title}</span>
        <Badge variant={job.status}>{statusLabels[job.status]}</Badge>
      </div>

      {/* Mini progress bar (only when running/processing) */}
      {job.status === 'running' || job.status === 'processing' ? (
        <div className="hidden sm:block w-24">
          <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${job.progress}%` }} />
          </div>
        </div>
      ) : (
        <div className="hidden sm:block w-24" />
      )}

      {/* Target count */}
      <div className="hidden md:flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 w-24">
        <Target className="w-3.5 h-3.5 text-amber-500" />
        <span>{job.targetCount} {language === 'zh' ? '靶点' : 'targets'}</span>
      </div>

      {/* Date */}
      <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500 w-28">
        <Calendar className="w-3.5 h-3.5" />
        <span>{formatDate(job.createdAt)}</span>
      </div>

      {/* Delete */}
      <button
        className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors flex-shrink-0"
        onClick={(e) => { e.stopPropagation(); onMenuClick?.(job); }}
        title={language === 'zh' ? '删除' : 'Delete'}
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
