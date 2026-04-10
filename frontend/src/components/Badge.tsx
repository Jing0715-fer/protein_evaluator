import React from 'react';

type BadgeVariant = 'completed' | 'pending' | 'failed' | 'running' | 'processing' | 'paused' | 'default' | 'success' | 'warning' | 'error' | 'info' | 'primary' | 'secondary' | 'outline';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  children,
  className = '',
}) => {
  const variants: Record<BadgeVariant, string> = {
    completed: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 border-green-200 dark:border-green-800',
    pending: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800',
    failed: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 border-red-200 dark:border-red-800',
    running: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    processing: 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400 border-blue-200 dark:border-blue-800',
    paused: 'bg-gray-200 dark:bg-gray-700/50 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600',
    default: 'bg-gray-200 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600',
    success: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400 border-green-200 dark:border-green-800',
    warning: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800',
    error: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 border-red-200 dark:border-red-800',
    info: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-800 dark:text-cyan-400 border-cyan-200 dark:border-cyan-800',
    primary: 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-400 border-amber-200 dark:border-amber-800',
    secondary: 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-400 border-purple-200 dark:border-purple-800',
    outline: 'bg-transparent text-gray-500 dark:text-gray-400 border-gray-400 dark:border-gray-600',
  };

  return (
    <span
      className={`
        inline-flex items-center px-2.5 py-0.5
        text-xs font-medium
        border rounded-full
        ${variants[variant]}
        ${className}
      `}
    >
      {children}
    </span>
  );
};