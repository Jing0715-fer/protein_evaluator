import React from 'react';
import { Calendar, Target, Trash2 } from 'lucide-react';
import { Badge } from './Badge';
import { Card, CardContent, CardHeader } from './Card';
import { useLanguage } from '../contexts/LanguageContext';
import type { Job } from '../types';

interface JobCardProps {
  job: Job;
  onClick?: (job: Job) => void;
  onMenuClick?: (job: Job) => void;
}

export const JobCard: React.FC<JobCardProps> = ({ job, onClick, onMenuClick }) => {
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
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const progressColor = {
    completed: 'bg-green-500',
    pending: 'bg-gray-500',
    failed: 'bg-red-500',
    running: 'bg-blue-500',
    processing: 'bg-blue-500',
    paused: 'bg-yellow-500',
  }[job.status];

  const ringColor: string = {
    completed: '#22c55e',
    pending: '#9ca3af',
    failed: '#ef4444',
    running: '#3b82f6',
    processing: '#3b82f6',
    paused: '#f59e0b',
  }[job.status] as string;

  return (
    <Card
      className="cursor-pointer transition-all duration-200 hover:shadow-amber-500/10 hover:border-amber-600/40"
      onClick={() => onClick?.(job)}
    >
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-base">{job.title}</h3>
          <Badge variant={job.status}>{statusLabels[job.status]}</Badge>
        </div>
        <button
          className="p-1.5 text-gray-400 dark:text-gray-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            onMenuClick?.(job);
          }}
          title={language === 'zh' ? '删除' : 'Delete'}
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </CardHeader>
      <CardContent className="py-3">
        {job.description && (
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3 line-clamp-2">{job.description}</p>
        )}

        {/* Circular Progress + Meta Row */}
        <div className="flex items-center gap-4 mb-4">
          {/* Circular Progress Ring */}
          <div className="relative flex-shrink-0">
            <svg width="56" height="56" viewBox="0 0 56 56" aria-hidden="true">
              {/* Background ring */}
              <circle cx="28" cy="28" r="22" fill="none" stroke="currentColor" strokeWidth="4"
                className="text-gray-200 dark:text-gray-700" />
              {/* Progress ring */}
              <circle cx="28" cy="28" r="22" fill="none" stroke={progressColor.replace('bg-','')}
                strokeWidth="4" strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 22}`}
                strokeDashoffset={`${2 * Math.PI * 22 * (1 - job.progress / 100)}`}
                transform="rotate(-90 28 28)"
                style={{ stroke: ringColor }}
                className="transition-all duration-500" />
            </svg>
            {/* Center text */}
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs font-bold text-gray-700 dark:text-gray-100">{job.progress}%</span>
            </div>
          </div>

          {/* Meta info stacked */}
          <div className="flex flex-col gap-1.5 min-w-0">
            <div className="flex items-center gap-2">
              <Target className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
              <span className="text-sm text-gray-600 dark:text-gray-300">
                {job.targetCount} {language === 'zh' ? '个靶点' : 'targets'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Calendar className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
              <span className="text-xs text-gray-500 dark:text-gray-400">{formatDate(job.createdAt)}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export type { Job };