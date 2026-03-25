import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Plus,
  Edit2,
  Trash2,
  Star,
  FileText,
  RefreshCw,
  AlertCircle,
  Eye,
  X,
} from 'lucide-react';
import { Button } from '../components/Button';
import { Card, CardContent } from '../components/Card';
import { Badge } from '../components/Badge';
import { templatesApi, batchTemplatesApi } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import type { PromptTemplate } from '../types';

type TemplateType = 'single' | 'batch';

// Markdown parser for preview
const parseMarkdown = (text: string): string => {
  if (!text) return '';

  let processed = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Highlight template variables
  processed = processed.replace(
    /\[([^\]]+)\]/g,
    '<span class="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-mono text-sm border border-blue-300">[$1]</span>'
  );
  processed = processed.replace(
    /\{([^}]+)\}/g,
    '<span class="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-mono text-sm border border-purple-300">{$1}</span>'
  );

  const lines = processed.split('\n');
  const result: string[] = [];
  let inCodeBlock = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        result.push('<pre class="bg-gray-800 text-gray-100 p-4 rounded-lg overflow-x-auto my-4"><code>');
      } else {
        inCodeBlock = false;
        result.push('</code></pre>');
      }
      continue;
    }
    if (inCodeBlock) {
      result.push(line);
      continue;
    }

    if (line.startsWith('### ')) {
      result.push(`<h3 class="text-lg font-semibold text-gray-900 mt-4 mb-2">${line.substring(4)}</h3>`);
      continue;
    }
    if (line.startsWith('## ')) {
      result.push(`<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">${line.substring(3)}</h2>`);
      continue;
    }
    if (line.startsWith('# ')) {
      result.push(`<h1 class="text-2xl font-bold text-gray-900 mt-6 mb-4">${line.substring(2)}</h1>`);
      continue;
    }

    if (line.match(/^---+$/)) {
      result.push('<hr class="my-6 border-gray-300" />');
      continue;
    }

    if (line.match(/^[\s]*[-*]\s/)) {
      const content = line.replace(/^[\s]*[-*]\s/, '');
      result.push(`<li class="ml-4 text-gray-700 list-disc">${content}</li>`);
      continue;
    }

    if (line.match(/^[\s]*\d+\.\s/)) {
      const content = line.replace(/^[\s]*\d+\.\s/, '');
      result.push(`<li class="ml-4 text-gray-700 list-decimal">${content}</li>`);
      continue;
    }

    let formatted = line
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>');

    if (formatted.trim()) {
      result.push(`<p class="text-gray-700 mb-2">${formatted}</p>`);
    } else {
      result.push('');
    }
  }

  return result.join('\n');
};

export const Templates: React.FC = () => {
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const [activeTab, setActiveTab] = useState<TemplateType>('single');
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [defaultId, setDefaultId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewTemplate, setPreviewTemplate] = useState<PromptTemplate | null>(null);

  // Fetch templates function
  const fetchTemplates = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const api = activeTab === 'single' ? templatesApi : batchTemplatesApi;
      const response = await api.listTemplates();
      if (response.success) {
        setTemplates(response.templates);
        setDefaultId(response.default_id);
      } else {
        setError('无法加载模板');
      }
    } catch {
      setError('加载模板失败');
    } finally {
      setIsLoading(false);
    }
  }, [activeTab]);

  // Fetch templates on mount and when tab changes
  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleCreateTemplate = () => {
    navigate(`/templates/new?type=${activeTab}`);
  };

  const handleEditTemplate = (template: PromptTemplate) => {
    navigate(`/templates/${template.id}?type=${activeTab}`);
  };

  const handleDeleteTemplate = async (template: PromptTemplate) => {
    const confirmMsg = language === 'zh'
      ? `确定要删除模板 "${template.name}" 吗？`
      : `Are you sure you want to delete template "${template.name}"?`;
    if (!window.confirm(confirmMsg)) {
      return;
    }

    try {
      const api = activeTab === 'single' ? templatesApi : batchTemplatesApi;
      const result = await api.deleteTemplate(template.id);
      if (result.success) {
        fetchTemplates();
      } else {
        setError(result.error || (language === 'zh' ? '删除失败' : 'Delete failed'));
      }
    } catch {
      setError(language === 'zh' ? '删除模板失败' : 'Failed to delete template');
    }
  };

  const handleSetDefault = async (template: PromptTemplate) => {
    try {
      const api = activeTab === 'single' ? templatesApi : batchTemplatesApi;
      const result = await api.setDefaultTemplate(template.id);
      if (result.success) {
        setDefaultId(template.id);
        fetchTemplates();
      } else {
        setError(result.error || '设置默认模板失败');
      }
    } catch {
      setError('设置默认模板失败');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-gray-600" />
                <h1 className="text-lg font-semibold text-gray-900">{t('templates.title')}</h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" onClick={fetchTemplates} disabled={isLoading}>
                <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                {t('templates.refresh')}
              </Button>
              <Button onClick={handleCreateTemplate}>
                <Plus className="w-4 h-4 mr-2" />
                {t('templates.newTemplate')}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                {t('templates.return')}
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('single')}
                className={`py-4 px-6 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'single'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {t('templates.singleTab')}
              </button>
              <button
                onClick={() => setActiveTab('batch')}
                className={`py-4 px-6 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'batch'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {t('templates.batchTab')}
              </button>
            </nav>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-red-700">{error}</p>
            <button
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              {t('app.close')}
            </button>
          </div>
        )}

        {/* Templates List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
            <span className="ml-3 text-gray-500">{t('templates.loading')}</span>
          </div>
        ) : templates.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 mb-4">
                <FileText className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">{t('templates.noTemplates')}</h3>
              <p className="text-gray-500 mb-6">
                {activeTab === 'single'
                  ? t('templates.noSingleTemplates')
                  : t('templates.noBatchTemplates')}
              </p>
              <Button onClick={handleCreateTemplate}>
                <Plus className="w-4 h-4 mr-2" />
                {t('templates.createFirst')}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {templates.map((template) => (
              <Card key={template.id} className="relative">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-gray-900 truncate">
                          {language === 'zh' ? template.name : (template.name_en || template.name)}
                        </h3>
                        {template.id === defaultId && (
                          <Badge variant="success">
                            <Star className="w-3 h-3 mr-1" />
                            {t('templates.default')}
                          </Badge>
                        )}
                      </div>
                      {(language === 'zh' ? template.description : template.description_en) && (
                        <p className="text-sm text-gray-500 mb-3">
                          {language === 'zh' ? template.description : template.description_en}
                        </p>
                      )}
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span>{t('templates.createdAt')} {formatDate(template.created_at)}</span>
                        {template.updated_at && (
                          <span>{t('templates.updatedAt')} {formatDate(template.updated_at)}</span>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPreviewTemplate(template)}
                      >
                        <Eye className="w-4 h-4 mr-1" />
                        {t('app.preview')}
                      </Button>
                      {template.id !== defaultId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleSetDefault(template)}
                          title={t('templates.setDefault')}
                        >
                          <Star className="w-4 h-4" />
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleEditTemplate(template)}
                      >
                        <Edit2 className="w-4 h-4 mr-1" />
                        {t('app.edit')}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDeleteTemplate(template)}
                        className="text-red-600 hover:text-red-700 hover:border-red-300"
                      >
                        <Trash2 className="w-4 h-4 mr-1" />
                        {t('app.delete')}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Info Box */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">{t('templates.about')}</h3>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>{t('templates.singleDesc')}</li>
            <li>{t('templates.batchDesc')}</li>
            <li>{t('templates.defaultDesc')}</li>
            <li>{t('templates.markdownDesc')}</li>
          </ul>
        </div>
      </main>

      {/* Preview Modal */}
      {previewTemplate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {language === 'zh' ? previewTemplate.name : (previewTemplate.name_en || previewTemplate.name)}
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  {language === 'zh' ? '模板预览' : 'Template Preview'}
                  <span className="ml-2 text-xs">
                    ({language === 'zh' ? '中文' : 'English'})
                  </span>
                </p>
              </div>
              <button
                onClick={() => setPreviewTemplate(null)}
                className="p-1 hover:bg-gray-100 rounded-full transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            {/* Modal Content */}
            <div className="p-6 overflow-y-auto max-h-[70vh]">
              <div
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{
                  __html: parseMarkdown(language === 'zh' ? previewTemplate.content : (previewTemplate.content_en || previewTemplate.content)),
                }}
              />
            </div>
            {/* Modal Footer */}
            <div className="flex justify-end p-4 border-t border-gray-200">
              <Button variant="outline" onClick={() => setPreviewTemplate(null)}>
                {t('templates.close')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
