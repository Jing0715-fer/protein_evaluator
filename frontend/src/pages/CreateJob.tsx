import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useJobs } from '../contexts/JobContext';
import { useLanguage } from '../contexts/LanguageContext';
import { MultiTargetInput, type MultiTargetFormData } from '../components/MultiTargetInput';
import { Button } from '../components/Button';
import api from '../services/api';

export const CreateJob: React.FC = () => {
  const navigate = useNavigate();
  const { language, t } = useLanguage();
  const { createJob, isLoading, error, clearError } = useJobs();

  const handleSubmit = async (data: MultiTargetFormData) => {
    // Build config, looking up template content for both templates
    let config: Record<string, string> = {};

    // Fetch single template and store as single_template (for per-protein evaluation)
    if (data.singleTemplate) {
      const singleResult = await api.templates.listTemplates();
      if (singleResult.success && singleResult.templates) {
        const matchedTemplate = singleResult.templates.find(
          (tmpl: any) => tmpl.name === data.singleTemplate
        );
        if (matchedTemplate) {
          const templateContent = language === 'en'
            ? (matchedTemplate.content_en || matchedTemplate.content)
            : matchedTemplate.content;
          if (templateContent) {
            config.single_template = templateContent;
          }
        }
      }
    }

    // Fetch batch template and store as template (for interaction analysis)
    if (data.batchTemplate) {
      const batchResult = await api.batchTemplates.listTemplates();
      if (batchResult.success && batchResult.templates) {
        const matchedTemplate = batchResult.templates.find(
          (tmpl: any) => tmpl.name === data.batchTemplate
        );
        if (matchedTemplate) {
          const templateContent = language === 'en'
            ? (matchedTemplate.content_en || matchedTemplate.content)
            : matchedTemplate.content;
          if (templateContent) {
            config.template = templateContent;
          }
        }
      }
    }

    // If only singleTemplate is selected (no batchTemplate),
    // use single_template for template (for backward compatibility)
    if (data.singleTemplate && !data.batchTemplate) {
      if (config.single_template) {
        config.template = config.single_template;
      }
    }

    const result = await createJob({
      name: data.taskName,
      description: data.description,
      uniprot_ids: data.targetIds,
      evaluation_mode: data.mode,
      config: Object.keys(config).length > 0 ? config : undefined,
    });

    if (result.success && result.jobId) {
      navigate(`/jobs/${result.jobId}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-800">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-500 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500 dark:bg-amber-600 rounded-lg flex items-center justify-center">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M12 3 C 7 3, 4 6.5, 4 12 C 4 17.5, 7 21, 12 21 C 17 21, 20 17.5, 20 12 C 20 6.5, 17 3, 12 3Z" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M8 8 Q 12 10.5, 16 8" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <path d="M16 12 Q 12 14.5, 8 12" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <path d="M8 16 Q 12 18.5, 16 16" stroke="white" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <circle cx="12" cy="12" r="1.5" fill="white"/>
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">{t('dashboard.newJob')}</h1>
                <p className="text-sm text-gray-500 dark:text-gray-300">{t('createJob.configMulti')}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/')}
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                {t('app.back')}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-red-700">{error}</p>
              <button
                onClick={clearError}
                className="text-red-500 hover:text-red-700"
              >
                {t('app.close')}
              </button>
            </div>
          </div>
        )}

        <div className="max-w-3xl mx-auto">
          <MultiTargetInput
            onSubmit={handleSubmit}
            isLoading={isLoading}
          />

          {/* Tips */}
          <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">
              {t('createJob.tips')}
            </h3>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>• {t('createJob.tip1')}</li>
              <li>• {t('createJob.tip2')}</li>
              <li>• {t('createJob.tip3')}</li>
              <li>• {t('createJob.tip4')}</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
};
