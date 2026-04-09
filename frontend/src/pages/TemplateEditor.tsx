import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Save,
  Eye,
  RefreshCw,
  AlertCircle,
  FileText,
} from 'lucide-react';
import { Button } from '../components/Button';
import { Card, CardContent, CardHeader } from '../components/Card';
import { Input } from '../components/Input';
import { templatesApi, batchTemplatesApi } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import type { PromptTemplate } from '../types';
import { applyInlineFormatting } from '../utils/markdown';

// Simple markdown parser for preview with variable highlighting
const parseMarkdown = (text: string): string => {
  if (!text) return '';

  // Process in order: escape HTML first, then handle variables, then markdown
  let processed = text
    // Escape HTML to prevent XSS but preserve newlines
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Highlight template variables FIRST (before markdown processing)
  // Square bracket variables like [蛋白质名称], [UniProt ID]
  processed = processed.replace(
    /\[([^\]]+)\]/g,
    '<span class="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-mono text-sm border border-blue-300">[$1]</span>'
  );
  // Curly brace variables like {target_id}, {uniprot_id}
  processed = processed.replace(
    /\{([^}]+)\}/g,
    '<span class="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-mono text-sm border border-purple-300">{$1}</span>'
  );

  // Split into lines for processing
  const lines = processed.split('\n');
  const result: string[] = [];
  let inCodeBlock = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks (must be processed before other regex)
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

    // Headers - apply inline formatting
    if (line.startsWith('### ')) {
      const headerText = applyInlineFormatting(line.substring(4));
      result.push(`<h3 class="text-lg font-semibold text-gray-900 mt-4 mb-2">${headerText}</h3>`);
      continue;
    }
    if (line.startsWith('## ')) {
      const headerText = applyInlineFormatting(line.substring(3));
      result.push(`<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">${headerText}</h2>`);
      continue;
    }
    if (line.startsWith('# ')) {
      const headerText = applyInlineFormatting(line.substring(2));
      result.push(`<h1 class="text-2xl font-bold text-gray-900 mt-6 mb-4">${headerText}</h1>`);
      continue;
    }

    // Horizontal rule
    if (line.match(/^---+$/)) {
      result.push('<hr class="my-6 border-gray-300" />');
      continue;
    }

    // Table detection - markdown table structure: header, separator, then data rows
    if (line.startsWith('|')) {
      // Check if the next line is a table separator
      if (i + 1 < lines.length && lines[i + 1].match(/^\|[\s\-:]+\|([\s\-:]+\|)*[\s\-:]*$/)) {
        // It's a table - collect header (current line)
        const tableLines: string[] = [line];
        let rowIndex = i + 1; // separator index
        tableLines.push(lines[rowIndex]); // add separator

        // Collect all data rows (consecutive lines starting with | after separator)
        rowIndex++;
        while (rowIndex < lines.length && lines[rowIndex].startsWith('|')) {
          tableLines.push(lines[rowIndex]);
          rowIndex++;
        }

        // Process the table
        const tableHtml = processTable(tableLines);
        result.push(tableHtml);
        i = rowIndex - 1; // Set i to last data row index, for loop will increment
      } else {
        // Not a table, output as raw text
        result.push(line);
      }
      continue;
    }

    // Unordered lists
    if (line.match(/^[\s]*[-*]\s/)) {
      const content = applyInlineFormatting(line.replace(/^[\s]*[-*]\s/, ''));
      result.push(`<li class="ml-4 text-gray-700 list-disc">${content}</li>`);
      continue;
    }

    // Ordered lists
    if (line.match(/^[\s]*\d+\.\s/)) {
      const content = applyInlineFormatting(line.replace(/^[\s]*\d+\.\s/, ''));
      result.push(`<li class="ml-4 text-gray-700 list-decimal">${content}</li>`);
      continue;
    }

    // Regular paragraph - apply inline formatting
    let formatted = line
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
      // Italic
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>');

    if (formatted.trim()) {
      result.push(`<p class="text-gray-700 mb-2">${formatted}</p>`);
    } else {
      result.push(''); // Empty line for spacing
    }
  }

  return result.join('\n');
};

// Helper to process markdown tables
function processTable(rows: string[]): string {
  if (rows.length < 2) return rows.join('\n');

  const headerRow = rows[0];
  const bodyRows = rows.slice(2); // Skip header and separator

  // Parse header cells - apply inline formatting
  const headers = headerRow.split('|').filter(c => c.trim()).map(c =>
    `<th class="border border-gray-200 px-4 py-3 bg-gradient-to-b from-gray-50 to-gray-100 text-left font-semibold text-gray-700 text-sm">${applyInlineFormatting(c.trim())}</th>`
  ).join('');

  // Parse body cells - apply inline formatting with alternating row colors
  const body = bodyRows.map((row, rowIndex) => {
    const bgClass = rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50';
    const cells = row.split('|').filter(c => c.trim()).map(c =>
      `<td class="border border-gray-200 px-4 py-3 text-gray-600 text-sm ${bgClass}">${applyInlineFormatting(c.trim())}</td>`
    ).join('');
    return `<tr class="hover:bg-blue-50 transition-colors duration-150">${cells}</tr>`;
  }).join('');

  return `<table class="w-full border-collapse my-4 text-sm rounded-lg overflow-hidden shadow-sm border border-gray-200">
    <thead>
      <tr class="bg-gradient-to-r from-gray-100 to-gray-50">${headers}</tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;
}

export const TemplateEditor: React.FC = () => {
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const { templateId } = useParams<{ templateId: string }>();
  const [searchParams] = useSearchParams();
  const templateType = searchParams.get('type') as 'single' | 'batch' || 'single';
  const isNew = templateId === 'new';

  const [template, setTemplate] = useState<Partial<PromptTemplate>>({
    name: '',
    content: '',
    content_en: '',
    description: '',
    description_en: '',
    is_default: false,
    template_type: templateType,
  });
  const [isLoading, setIsLoading] = useState(isNew ? false : true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'edit' | 'preview'>('edit');

  // Fetch template if editing
  useEffect(() => {
    const fetchTemplate = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const api = templateType === 'single' ? templatesApi : batchTemplatesApi;
        const data = await api.getTemplate(parseInt(templateId!));
        if (data) {
          setTemplate(data);
        } else {
          setError(language === 'zh' ? '模板不存在' : 'Template not found');
        }
      } catch {
        setError(language === 'zh' ? '加载模板失败' : 'Failed to load template');
      } finally {
        setIsLoading(false);
      }
    };

    if (!isNew && templateId) {
      fetchTemplate();
    }
  }, [templateId, templateType, isNew]);

  const handleSave = async () => {
    if (!template.name?.trim()) {
      setError(language === 'zh' ? '模板名称不能为空' : 'Template name is required');
      return;
    }
    if (!template.content?.trim()) {
      setError(language === 'zh' ? '模板内容不能为空' : 'Template content is required');
      return;
    }

    setIsSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const api = templateType === 'single' ? templatesApi : batchTemplatesApi;

      if (isNew) {
        const result = await api.createTemplate({
          name: template.name,
          content: template.content,
          content_en: template.content_en,
          description: template.description,
          description_en: template.description_en,
          is_default: template.is_default,
        });
        if (result.success) {
          setSuccessMessage(language === 'zh' ? '模板创建成功' : 'Template created successfully');
          setTimeout(() => {
            navigate('/templates');
          }, 1500);
        } else {
          setError(result.error || (language === 'zh' ? '创建失败' : 'Create failed'));
        }
      } else {
        const result = await api.updateTemplate(parseInt(templateId!), {
          name: template.name,
          content: template.content,
          content_en: template.content_en,
          description: template.description,
          description_en: template.description_en,
          is_default: template.is_default,
        });
        if (result.success) {
          setSuccessMessage(language === 'zh' ? '模板更新成功' : 'Template updated successfully');
          setTimeout(() => setSuccessMessage(null), 3000);
        } else {
          setError(result.error || (language === 'zh' ? '更新失败' : 'Update failed'));
        }
      }
    } catch (err: any) {
      console.error('Save template error:', err);
      setError(isNew ? (language === 'zh' ? '创建模板失败' : 'Failed to create template') : (language === 'zh' ? '更新模板失败' : 'Failed to update template'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    if (isNew) {
      setTemplate({
        name: '',
        content: '',
        content_en: '',
        description: '',
        description_en: '',
        is_default: false,
        template_type: templateType,
      });
    } else {
      // Reload the page to re-fetch template data
      window.location.reload();
    }
    setError(null);
    setSuccessMessage(null);
  };

  const insertVariable = (variable: string) => {
    // Check which textarea is focused
    const contentTextarea = document.getElementById('content') as HTMLTextAreaElement;
    const contentEnTextarea = document.getElementById('content_en') as HTMLTextAreaElement;

    const activeTextarea = document.activeElement;
    let targetField: 'content' | 'content_en' = 'content';
    let textarea = contentTextarea;

    if (activeTextarea === contentEnTextarea) {
      targetField = 'content_en';
      textarea = contentEnTextarea;
    }

    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const currentContent = (targetField === 'content' ? template.content : template.content_en) || '';
    const newContent =
      currentContent.substring(0, start) +
      variable +
      currentContent.substring(end);

    setTemplate({ ...template, [targetField]: newContent });

    // Restore focus and set cursor position
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + variable.length, start + variable.length);
    }, 0);
  };

  const commonVariables = language === 'zh' ? [
    { name: t('templates.variable.proteinName'), variable: '[蛋白质名称]' },
    { name: t('templates.variable.uniprotId'), variable: '[UniProt ID]' },
    { name: t('templates.variable.geneName'), variable: '[基因名]' },
    { name: t('templates.variable.pdbId'), variable: '[PDB ID]' },
    { name: t('templates.variable.resolution'), variable: '[分辨率]' },
    { name: t('templates.variable.method'), variable: '[实验方法]' },
    { name: t('templates.variable.sequenceLength'), variable: '[序列长度]' },
    { name: t('templates.variable.molecularWeight'), variable: '[分子量]' },
    { name: 'PDB实体详情', variable: '[PDB_ENTITIES]' },
    { name: '配体/药物信息', variable: '[PDB_LIGANDS]' },
    { name: 'PDB统计摘要', variable: '[PDB_STATISTICS]' },
    { name: '文献统计', variable: '[LITERATURE_STATS]' },
    { name: '同源结构统计', variable: '[HOMOLOGY_STATS]' },
    { name: '完整文献摘要(AI)', variable: '[LITERATURE_FOR_AI]' },
  ] : [
    { name: t('templates.variable.proteinName'), variable: '[Protein Name]' },
    { name: t('templates.variable.uniprotId'), variable: '[UniProt ID]' },
    { name: t('templates.variable.geneName'), variable: '[Gene Name]' },
    { name: t('templates.variable.pdbId'), variable: '[PDB ID]' },
    { name: t('templates.variable.resolution'), variable: '[Resolution]' },
    { name: t('templates.variable.method'), variable: '[Method]' },
    { name: t('templates.variable.sequenceLength'), variable: '[Sequence Length]' },
    { name: t('templates.variable.molecularWeight'), variable: '[Molecular Weight]' },
    { name: 'PDB Entity Details', variable: '[PDB_ENTITIES]' },
    { name: 'Ligand/Drug Info', variable: '[PDB_LIGANDS]' },
    { name: 'PDB Statistics', variable: '[PDB_STATISTICS]' },
    { name: 'Literature Stats', variable: '[LITERATURE_STATS]' },
    { name: 'Homology Stats', variable: '[HOMOLOGY_STATS]' },
    { name: 'Full Abstracts (AI)', variable: '[LITERATURE_FOR_AI]' },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-gray-600" />
                <h1 className="text-lg font-semibold text-gray-900">
                  {isNew ? t('templates.newTemplate') : t('templates.edit')}
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center border border-gray-300 rounded-lg overflow-hidden">
                <button
                  onClick={() => setActiveTab('edit')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === 'edit'
                      ? 'bg-blue-50 text-blue-600 border-r border-gray-300'
                      : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Edit2Icon className="w-4 h-4 inline mr-1" />
                  {t('editor.edit') || '编辑'}
                </button>
                <button
                  onClick={() => setActiveTab('preview')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === 'preview'
                      ? 'bg-blue-50 text-blue-600'
                      : 'bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Eye className="w-4 h-4 inline mr-1" />
                  {t('app.preview')}
                </button>
              </div>
              <Button variant="outline" onClick={handleReset} disabled={isLoading}>
                <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                {t('app.reset')}
              </Button>
              <Button onClick={handleSave} disabled={isSaving || isLoading}>
                <Save className="w-4 h-4 mr-2" />
                {isSaving ? (language === 'zh' ? '保存中...' : 'Saving...') : t('app.save')}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => navigate('/templates')}>
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

        {/* Success Message */}
        {successMessage && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3">
            <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
              <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            </div>
            <p className="text-green-700">{successMessage}</p>
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
            <span className="ml-3 text-gray-500">{t('app.loading')}</span>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto">
            {/* Tab Content */}
            {activeTab === 'edit' ? (
            /* Editor */
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Edit2Icon className="w-5 h-5 text-blue-600" />
                  <h2 className="text-lg font-semibold text-gray-900">{t('editor.title')}</h2>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Template Name */}
                <Input
                  label={t('editor.name')}
                  value={template.name}
                  onChange={(e) => setTemplate({ ...template, name: e.target.value })}
                  placeholder={t('editor.namePlaceholder')}
                />

                {/* Template Description - Chinese */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('editor.description')} (中文)
                  </label>
                  <textarea
                    value={template.description || ''}
                    onChange={(e) => setTemplate({ ...template, description: e.target.value })}
                    placeholder={language === 'zh' ? '输入中文描述' : 'Enter Chinese description'}
                    rows={2}
                    className="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none"
                  />
                </div>

                {/* Template Description - English */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('editor.description')} (English)
                  </label>
                  <textarea
                    value={template.description_en || ''}
                    onChange={(e) => setTemplate({ ...template, description_en: e.target.value })}
                    placeholder={language === 'zh' ? '输入英文描述' : 'Enter English description'}
                    rows={2}
                    className="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none"
                  />
                </div>

                {/* Variable Shortcuts */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('editor.variables')}
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {commonVariables.map((v) => (
                      <button
                        key={v.variable}
                        onClick={() => insertVariable(v.variable)}
                        className="px-3 py-1.5 bg-blue-50 text-blue-700 text-sm rounded-lg border border-blue-200 hover:bg-blue-100 transition-colors"
                      >
                        {v.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Template Content - Chinese */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('editor.content')} (中文)
                  </label>
                  <textarea
                    id="content"
                    value={template.content || ''}
                    onChange={(e) => setTemplate({ ...template, content: e.target.value })}
                    placeholder={language === 'zh' ? '输入中文模板内容' : 'Enter Chinese template content'}
                    rows={15}
                    className="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono text-sm resize-y"
                  />
                </div>

                {/* Template Content - English */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('editor.content')} (English)
                  </label>
                  <textarea
                    id="content_en"
                    value={template.content_en || ''}
                    onChange={(e) => setTemplate({ ...template, content_en: e.target.value })}
                    placeholder={language === 'zh' ? '输入英文模板内容' : 'Enter English template content'}
                    rows={15}
                    className="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-mono text-sm resize-y"
                  />
                </div>

                {/* Is Default Checkbox */}
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="is-default"
                    checked={template.is_default}
                    onChange={(e) => setTemplate({ ...template, is_default: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="is-default" className="text-sm text-gray-700">
                    {t('templates.setDefault')}
                  </label>
                </div>

              </CardContent>
            </Card>
            ) : (
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Eye className="w-5 h-5 text-blue-600" />
                  <h2 className="text-lg font-semibold text-gray-900">
                    {template.name || t('editor.untitled')}
                  </h2>
                </div>
              </CardHeader>
              <CardContent>
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 min-h-[400px]">
                  <div className="prose prose-sm max-w-none">
                    <div
                      className="markdown-preview"
                      dangerouslySetInnerHTML={{
                        __html: parseMarkdown(template.content || ''),
                      }}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
            )}
          </div>
        )}

        {/* Tips */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">{t('editor.supportedMarkdown')}</h3>
            <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
              <li># {language === 'zh' ? '标题 - 一级标题' : 'Title - Level 1 Heading'}</li>
              <li>## {language === 'zh' ? '标题 - 二级标题' : 'Title - Level 2 Heading'}</li>
              <li>**{language === 'zh' ? '粗体' : 'Bold'}** - {language === 'zh' ? '粗体文本' : 'Bold text'}</li>
              <li>*{language === 'zh' ? '斜体' : 'Italic'}* - {language === 'zh' ? '斜体文本' : 'Italic text'}</li>
              <li>`{language === 'zh' ? '代码' : 'Code'}` - {language === 'zh' ? '行内代码' : 'Inline code'}</li>
              <li>```{language === 'zh' ? '代码块' : 'Code block'}``` - {language === 'zh' ? '多行代码块' : 'Multi-line code block'}</li>
              <li>- {language === 'zh' ? '列表项 - 无序列表' : 'List item - Unordered list'}</li>
            </ul>
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-green-900 mb-2">{t('editor.availableVars')}</h3>
            <ul className="text-sm text-green-800 space-y-1 list-disc list-inside">
              {language === 'zh' ? (
                <>
                  <li>[蛋白质名称] - 蛋白质标准全称</li>
                  <li>[UniProt ID] - UniProt 编号</li>
                  <li>[基因名] - 基因名称</li>
                  <li>[PDB ID] - PDB 结构编号</li>
                  <li>[分辨率] - 结构分辨率</li>
                  <li>[实验方法] - 结构解析方法</li>
                  <li>[序列长度] - 氨基酸数目</li>
                  <li>[分子量] - 分子量(Da)</li>
                </>
              ) : (
                <>
                  <li>[Protein Name] - Full protein name</li>
                  <li>[UniProt ID] - UniProt identifier</li>
                  <li>[Gene Name] - Gene name</li>
                  <li>[PDB ID] - PDB structure ID</li>
                  <li>[Resolution] - Structure resolution</li>
                  <li>[Method] - Structure method</li>
                  <li>[Sequence Length] - Amino acid count</li>
                  <li>[Molecular Weight] - Molecular weight (Da)</li>
                </>
              )}
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
};

// Simple edit icon component
function Edit2Icon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </svg>
  );
}
