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
    completed: 'bg-green-100 text-green-800 border-green-200',
    pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    failed: 'bg-red-100 text-red-800 border-red-200',
    running: 'bg-blue-100 text-blue-800 border-blue-200',
    processing: 'bg-blue-100 text-blue-800 border-blue-200',
    paused: 'bg-gray-100 text-gray-800 border-gray-200',
    default: 'bg-gray-100 text-gray-800 border-gray-200',
    success: 'bg-green-100 text-green-800 border-green-200',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    error: 'bg-red-100 text-red-800 border-red-200',
    info: 'bg-cyan-100 text-cyan-800 border-cyan-200',
    primary: 'bg-blue-100 text-blue-800 border-blue-200',
    secondary: 'bg-purple-100 text-purple-800 border-purple-200',
    outline: 'bg-transparent text-gray-600 border-gray-300',
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
