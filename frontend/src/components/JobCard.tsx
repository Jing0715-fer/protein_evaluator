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

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const progressColor = {
    completed: 'bg-green-500',
    pending: 'bg-gray-400',
    failed: 'bg-red-500',
    running: 'bg-blue-500',
    processing: 'bg-blue-500',
    paused: 'bg-yellow-500',
  }[job.status];

  return (
    <Card
      className="cursor-pointer transition-all duration-200 hover:shadow-md hover:border-blue-300"
      onClick={() => onClick?.(job)}
    >
      <CardHeader className="flex flex-row items-center justify-between py-3">
        <div className="flex items-center gap-3">
          <h3 className="font-semibold text-gray-900 text-base">{job.title}</h3>
          <Badge variant={job.status}>{statusLabels[job.status]}</Badge>
        </div>
        <button
          className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
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
          <p className="text-sm text-gray-500 mb-3 line-clamp-2">{job.description}</p>
        )}

        {/* Progress Bar */}
        <div className="mb-4">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-sm font-medium text-gray-700">{language === 'zh' ? '进度' : 'Progress'}</span>
            <span className="text-sm font-medium text-gray-900">{job.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-500 ${progressColor}`}
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>

        {/* Meta Info */}
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <Target className="w-4 h-4 text-gray-400" />
              <span>{job.targetCount} {language === 'zh' ? '个靶点' : 'targets'}</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Calendar className="w-4 h-4 text-gray-400" />
            <span>{formatDate(job.createdAt)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export type { Job };
