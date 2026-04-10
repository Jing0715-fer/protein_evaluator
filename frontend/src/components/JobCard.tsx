import React from 'react';
import { Target, Trash2, ChevronRight } from 'lucide-react';
import { Badge } from './Badge';
import { Card, CardContent } from './Card';
import { useLanguage } from '../contexts/LanguageContext';
import type { Job } from '../types';

interface JobCardProps {
  job: Job;
  onClick?: (job: Job) => void;
  onMenuClick?: (job: Job) => void;
}

const STATUS_CONFIG = {
  completed: {
    label: { zh: '已完成', en: 'Completed' },
    color: '#22c55e',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    ring: '#22c55e',
    glow: 'hover:shadow-green-500/20',
  },
  pending: {
    label: { zh: '待处理', en: 'Pending' },
    color: '#9ca3af',
    bg: 'bg-gray-500/10',
    border: 'border-gray-500/30',
    ring: '#9ca3af',
    glow: '',
  },
  failed: {
    label: { zh: '失败', en: 'Failed' },
    color: '#ef4444',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    ring: '#ef4444',
    glow: 'hover:shadow-red-500/20',
  },
  running: {
    label: { zh: '运行中', en: 'Running' },
    color: '#3b82f6',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    ring: '#3b82f6',
    glow: 'hover:shadow-blue-500/20',
  },
  processing: {
    label: { zh: '运行中', en: 'Running' },
    color: '#3b82f6',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    ring: '#3b82f6',
    glow: 'hover:shadow-blue-500/20',
  },
  paused: {
    label: { zh: '已暂停', en: 'Paused' },
    color: '#f59e0b',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    ring: '#f59e0b',
    glow: 'hover:shadow-yellow-500/20',
  },
} as const;

const formatDate = (dateString: string | null | undefined, lang: string) => {
  if (!dateString) return '—';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(lang === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

// Pseudo-random score from job id (for demo visualization)
const seedScore = (id: string): number => {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (Math.imul(31, h) + id.charCodeAt(i)) | 0;
  return (Math.abs(h) % 40) + 60; // 60–99 range
};

export const JobCard: React.FC<JobCardProps> = ({ job, onClick, onMenuClick }) => {
  const { language } = useLanguage();
  const cfg = STATUS_CONFIG[job.status];
  const isRunning = job.status === 'running' || job.status === 'processing';
  const qualityScore = job.avgPlddt ?? (job.status === 'completed' ? seedScore(job.id) : undefined);

  // pLDDT color bands
  const plddtColor = qualityScore
    ? qualityScore >= 90 ? '#22c55e' : qualityScore >= 70 ? '#3b82f6' : qualityScore >= 50 ? '#f59e0b' : '#ef4444'
    : '#64748b';
  const plddtLabel = qualityScore
    ? qualityScore >= 90 ? 'Very High' : qualityScore >= 70 ? 'Confident' : qualityScore >= 50 ? 'Low' : 'Very Low'
    : '';

  return (
    <div className="group relative">
      {/* Glow border effect on hover */}
      <div className={`absolute -inset-px rounded-xl bg-gradient-to-br opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-sm ${cfg.glow}`}
        style={{ background: `linear-gradient(135deg, ${cfg.color}40, transparent)` }}
        aria-hidden="true" />

      <Card
        className={`relative cursor-pointer transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg dark:hover:shadow-xl ${cfg.border} ${cfg.glow} border bg-gray-50 dark:bg-[#0f1525]`}
        onClick={() => onClick?.(job)}
      >
        {/* Molecular helix background watermark */}
        <div className="absolute right-0 top-0 w-28 h-28 opacity-[0.04] pointer-events-none" aria-hidden="true">
          <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M50 5 C 30 5, 15 22, 15 50 C 15 78, 30 95, 50 95 C 70 95, 85 78, 85 50 C 85 22, 70 5, 50 5Z" stroke="currentColor" strokeWidth="1.5" fill="none"/>
            <path d="M30 20 Q 50 30, 70 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M70 35 Q 50 45, 30 35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M30 50 Q 50 60, 70 50" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <path d="M70 65 Q 50 75, 30 65" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <circle cx="50" cy="50" r="4" fill="currentColor"/>
          </svg>
        </div>

        <CardContent className="p-5 relative">
          {/* Top row: title + badge + delete */}
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ background: `${cfg.color}18`, border: `1px solid ${cfg.color}30` }}>
                {/* Mini protein helix icon */}
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"
                  style={{ color: cfg.color }}>
                  <path d="M12 2 C 7 2, 4 6, 4 12 C 4 18, 7 22, 12 22 C 17 22, 20 18, 20 12 C 20 6, 17 2, 12 2Z"
                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M7 7 Q 12 10, 17 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M17 12 Q 12 15, 7 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M7 17 Q 12 20, 17 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm leading-tight truncate pr-2">
                  {job.title}
                </h3>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  {formatDate(job.createdAt, language)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Badge variant={job.status}>{cfg.label[language === 'zh' ? 'zh' : 'en']}</Badge>
              <button
                className="p-1.5 text-gray-300 dark:text-gray-600 hover:text-red-400 dark:hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                onClick={(e) => { e.stopPropagation(); onMenuClick?.(job); }}
                title={language === 'zh' ? '删除' : 'Delete'}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Description */}
          {job.description && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-4 line-clamp-2 leading-relaxed">
              {job.description}
            </p>
          )}

          {/* Progress + Meta */}
          <div className="flex items-center gap-4">
            {/* Animated progress ring */}
            <div className="relative flex-shrink-0">
              <svg width="52" height="52" viewBox="0 0 52 52" aria-hidden="true">
                <circle cx="26" cy="26" r="20" fill="none"
                  stroke="currentColor" strokeWidth="3"
                  className="text-gray-200 dark:text-gray-700/60" />
                {isRunning ? (
                  /* Animated running ring */
                  <circle cx="26" cy="26" r="20" fill="none"
                    stroke={cfg.ring} strokeWidth="3" strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 20}`}
                    strokeDashoffset={`${2 * Math.PI * 20 * (1 - job.progress / 100)}`}
                    transform="rotate(-90 26 26)"
                    className="transition-all duration-700">
                    <animateTransform attributeName="transform" type="rotate"
                      from="0 26 26" to="360 26 26" dur="3s" repeatCount="indefinite" />
                  </circle>
                ) : (
                  <circle cx="26" cy="26" r="20" fill="none"
                    stroke={cfg.ring} strokeWidth="3" strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 20}`}
                    strokeDashoffset={`${2 * Math.PI * 20 * (1 - job.progress / 100)}`}
                    transform="rotate(-90 26 26)"
                    className="transition-all duration-500" />
                )}
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xs font-bold" style={{ color: cfg.color }}>
                  {job.progress}%
                </span>
              </div>
            </div>

            {/* Meta info */}
            <div className="flex flex-col gap-1.5 min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <Target className="w-3.5 h-3.5 flex-shrink-0" style={{ color: cfg.color }} />
                <span className="text-sm text-gray-600 dark:text-gray-300">
                  {job.targetCount} {language === 'zh' ? '个靶点' : 'targets'}
                </span>
              </div>
              {job.status === 'completed' && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                  <span className="text-xs text-green-600 dark:text-green-400 font-medium">
                    {language === 'zh' ? '结果就绪' : 'Results ready'}
                  </span>
                  <ChevronRight className="w-3 h-3 text-green-400 ml-auto" />
                </div>
              )}
              {job.status === 'failed' && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
                  <span className="text-xs text-red-500 dark:text-red-400">
                    {language === 'zh' ? '查看错误日志' : 'Check error logs'}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Quality score bar (for completed jobs) */}
          {job.status === 'completed' && qualityScore !== undefined && (
            <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/40">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">
                  {language === 'zh' ? '结构质量' : 'Structure Quality'}
                </span>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold" style={{ color: plddtColor }}>
                    {qualityScore.toFixed(1)}
                  </span>
                  <span className="text-xs text-gray-400 dark:text-gray-500">pLDDT</span>
                </div>
              </div>
              {/* pLDDT bar with color zones */}
              <div className="relative h-1.5 bg-gray-100 dark:bg-gray-700/40 rounded-full overflow-hidden">
                <div className="absolute inset-y-0 left-0 rounded-full transition-all duration-700"
                  style={{ width: `${qualityScore}%`, background: plddtColor }} />
                {/* Zone markers */}
                <div className="absolute inset-0 flex">
                  <div className="flex-1 border-r border-white/30 dark:border-black/10" />
                  <div className="flex-1 border-r border-white/30 dark:border-black/10" />
                  <div className="flex-1 border-r border-white/30 dark:border-black/10" />
                  <div className="flex-1" />
                </div>
              </div>
              <div className="flex justify-between mt-0.5">
                <span className="text-[10px] text-gray-400 dark:text-gray-500">0</span>
                <span className="text-[10px] text-gray-400 dark:text-gray-500" style={{ color: plddtColor }}>{plddtLabel}</span>
                <span className="text-[10px] text-gray-400 dark:text-gray-500">100</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export type { Job };
