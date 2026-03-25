import React from 'react';
import { Globe } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';

export const LanguageSwitcher: React.FC = () => {
  const { language, setLanguage } = useLanguage();

  const toggleLanguage = () => {
    setLanguage(language === 'zh' ? 'en' : 'zh');
  };

  // Blue text shows current language
  const currentLabel = language === 'zh' ? '中文' : 'EN';
  const switchToLabel = language === 'zh' ? 'EN' : '中文';

  return (
    <button
      onClick={toggleLanguage}
      className="flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md hover:border-blue-300 transition-all duration-200 group"
      title={language === 'zh' ? 'Switch to English' : '切换到中文'}
    >
      <Globe className="w-4 h-4 text-gray-400 group-hover:text-blue-500 transition-colors" />
      <div className="flex items-center gap-1">
        <span className="text-xs font-semibold text-blue-600 group-hover:text-blue-700">{currentLabel}</span>
        <span className="text-xs text-gray-300">/</span>
        <span className="text-xs font-medium text-gray-500">{switchToLabel}</span>
      </div>
    </button>
  );
};
