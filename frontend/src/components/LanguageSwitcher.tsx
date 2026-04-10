import React from 'react';
import { Globe } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';

export const LanguageSwitcher: React.FC = () => {
  const { language, setLanguage } = useLanguage();

  const toggleLanguage = () => {
    setLanguage(language === 'zh' ? 'en' : 'zh');
  };

  // Amber text shows current language
  const currentLabel = language === 'zh' ? '中文' : 'EN';
  const switchToLabel = language === 'zh' ? 'EN' : '中文';

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-sm hover:shadow-md hover:border-amber-500/40 transition-all duration-200 group"
      title={language === 'zh' ? 'Switch to English' : '切换到中文'}
    >
      <Globe className="w-4 h-4 text-gray-500 dark:text-gray-400 group-hover:text-amber-400 transition-colors" />
      <div className="flex items-center gap-1">
        <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 group-hover:text-amber-500 dark:group-hover:text-amber-300">{currentLabel}</span>
        <span className="text-xs text-gray-400 dark:text-gray-600">/</span>
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{switchToLabel}</span>
      </div>
    </button>
  );
};