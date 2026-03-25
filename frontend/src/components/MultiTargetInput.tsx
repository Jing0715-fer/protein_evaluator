import React, { useState, useCallback, useEffect } from 'react';
import { Upload, FileText, AlertCircle } from 'lucide-react';
import { Button } from './Button';
import { Card, CardContent, CardHeader } from './Card';
import { Input } from './Input';
import { useLanguage } from '../contexts/LanguageContext';
import api from '../services/api';
import type { PromptTemplate } from '../types';

export interface MultiTargetFormData {
  taskName: string;
  description: string;
  targetIds: string[];
  mode: 'parallel' | 'sequential';
  singleTemplate: string;
  batchTemplate: string;
  config?: { max_pdb?: number; template?: string; single_template?: string };
}

interface MultiTargetInputProps {
  onSubmit: (data: MultiTargetFormData) => void;
  isLoading?: boolean;
}

export const MultiTargetInput: React.FC<MultiTargetInputProps> = ({
  onSubmit,
  isLoading = false,
}) => {
  const { language } = useLanguage();
  const [taskName, setTaskName] = useState('');
  const [description, setDescription] = useState('');
  const [targetInput, setTargetInput] = useState('');
  const [mode, setMode] = useState<'parallel' | 'sequential'>('parallel');
  const [singleTemplate, setSingleTemplate] = useState<string>('');
  const [batchTemplate, setBatchTemplate] = useState<string>('');
  const [singleTemplates, setSingleTemplates] = useState<PromptTemplate[]>([]);
  const [batchTemplates, setBatchTemplates] = useState<PromptTemplate[]>([]);
  const [maxPdb, setMaxPdb] = useState<number | undefined>(undefined);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch both single and batch templates on mount
  useEffect(() => {
    const fetchTemplates = async () => {
      // Fetch single templates
      const singleResult = await api.templates.listTemplates();
      if (singleResult.success && singleResult.templates) {
        setSingleTemplates(singleResult.templates);
        const defaultSingle = singleResult.templates.find((t: PromptTemplate) => t.is_default) || singleResult.templates[0];
        if (defaultSingle) {
          setSingleTemplate(defaultSingle.name);
        }
      }

      // Fetch batch templates
      const batchResult = await api.batchTemplates.listTemplates();
      if (batchResult.success && batchResult.templates) {
        setBatchTemplates(batchResult.templates);
        const defaultBatch = batchResult.templates.find((t: PromptTemplate) => t.is_default) || batchResult.templates[0];
        if (defaultBatch) {
          setBatchTemplate(defaultBatch.name);
        }
      }
    };
    fetchTemplates();
  }, []);

  const parseTargetIds = useCallback((input: string): string[] => {
    return input
      .split(/[\n,]+/)
      .map(id => id.trim())
      .filter(id => id.length > 0);
  }, []);

  const handleFileUpload = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (content) {
        setTargetInput(content);
      }
    };
    reader.readAsText(file);
  }, []);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!taskName.trim()) {
      newErrors.taskName = language === 'zh' ? '请输入任务名称' : 'Please enter task name';
    }

    const targetIds = parseTargetIds(targetInput);
    if (targetIds.length === 0) {
      newErrors.targets = language === 'zh' ? '请输入至少一个靶点ID' : 'Please enter at least one target ID';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const config: { max_pdb?: number; template?: string; single_template?: string } = {};
    if (maxPdb && maxPdb > 0) {
      config.max_pdb = maxPdb;
    }
    // Pass template names to config
    if (singleTemplate) {
      config.single_template = singleTemplate;
    }
    if (batchTemplate) {
      config.template = batchTemplate;
    }

    onSubmit({
      taskName,
      description,
      targetIds: parseTargetIds(targetInput),
      mode,
      singleTemplate,
      batchTemplate,
      config: Object.keys(config).length > 0 ? config : undefined,
    });
  };

  const targetCount = parseTargetIds(targetInput).length;

  return (
    <Card className="w-full max-w-3xl mx-auto">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <FileText className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{language === 'zh' ? '创建多靶点评估任务' : 'Create Multi-Target Evaluation Task'}</h2>
            <p className="text-sm text-gray-500">{language === 'zh' ? '输入靶点信息以开始蛋白质结构评估' : 'Enter target information to start protein structure evaluation'}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Task Name */}
          <Input
            label={language === 'zh' ? '任务名称' : 'Task Name'}
            placeholder={language === 'zh' ? '输入任务名称' : 'Enter task name'}
            value={taskName}
            onChange={(e) => setTaskName(e.target.value)}
            error={errors.taskName}
          />

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {language === 'zh' ? '任务描述' : 'Task Description'}
            </label>
            <textarea
              className="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none"
              rows={3}
              placeholder={language === 'zh' ? '输入任务描述（可选）' : 'Enter task description (optional)'}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Target IDs */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {language === 'zh' ? '靶点ID' : 'Target IDs'}
              <span className="text-gray-400 font-normal ml-1">({language === 'zh' ? '支持逗号或换行分隔' : 'Comma or newline separated'})</span>
            </label>
            <textarea
              className={`
                w-full px-3 py-2.5 bg-white border rounded-lg
                text-gray-900 placeholder-gray-400 font-mono text-sm
                transition-all duration-200 resize-none
                focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500
                ${errors.targets ? 'border-red-300 focus:border-red-500 focus:ring-red-500/20' : 'border-gray-300 hover:border-gray-400'}
              `}
              rows={5}
              placeholder={language === 'zh' ? '例如：P12345, P67890, Q11111' : 'e.g., P12345, P67890, Q11111'}
              value={targetInput}
              onChange={(e) => setTargetInput(e.target.value)}
            />
            {errors.targets && (
              <div className="flex items-center gap-1.5 mt-1.5">
                <AlertCircle className="w-4 h-4 text-red-500" />
                <p className="text-sm text-red-600">{errors.targets}</p>
              </div>
            )}
            {targetCount > 0 && (
              <p className="mt-1.5 text-sm text-green-600">
                {language === 'zh' ? `已识别 ${targetCount} 个靶点` : `${targetCount} targets identified`}
              </p>
            )}
          </div>

          {/* File Upload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {language === 'zh' ? '或从文件导入' : 'Or import from file'}
            </label>
            <label className="flex items-center justify-center gap-2 w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-all">
              <Upload className="w-5 h-5 text-gray-400" />
              <span className="text-sm text-gray-600">{language === 'zh' ? '点击上传文件' : 'Click to upload file'}</span>
              <input
                type="file"
                accept=".txt,.csv"
                className="hidden"
                onChange={handleFileUpload}
              />
            </label>
            <p className="mt-1 text-xs text-gray-500">{language === 'zh' ? '支持 .txt 和 .csv 格式' : 'Supports .txt and .csv formats'}</p>
          </div>

          {/* Mode Selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {language === 'zh' ? '执行模式' : 'Execution Mode'}
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                className={`
                  flex-1 px-4 py-3 border-2 rounded-lg text-sm font-medium transition-all
                  ${mode === 'parallel'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
                  }
                `}
                onClick={() => setMode('parallel')}
              >
                <span className="block text-base mb-0.5">{language === 'zh' ? '并行' : 'Parallel'}</span>
                <span className="block text-xs opacity-75">{language === 'zh' ? '同时处理所有靶点' : 'Process all targets simultaneously'}</span>
              </button>
              <button
                type="button"
                className={`
                  flex-1 px-4 py-3 border-2 rounded-lg text-sm font-medium transition-all
                  ${mode === 'sequential'
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50'
                  }
                `}
                onClick={() => setMode('sequential')}
              >
                <span className="block text-base mb-0.5">{language === 'zh' ? '串行' : 'Sequential'}</span>
                <span className="block text-xs opacity-75">{language === 'zh' ? '按顺序逐个处理' : 'Process one by one in order'}</span>
              </button>
            </div>
          </div>

          {/* Max PDB Input */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm font-medium text-gray-700">
                {language === 'zh' ? '最大PDB数量' : 'Max PDB Count'}
              </label>
              <span className="text-sm font-semibold text-blue-600">
                {maxPdb || (language === 'zh' ? '无限制' : 'Unlimited')}
              </span>
            </div>
            <input
              type="number"
              min="1"
              max="500"
              value={maxPdb || ''}
              onChange={(e) => {
                const val = e.target.value;
                if (val === '') {
                  setMaxPdb(undefined);
                } else {
                  const num = parseInt(val);
                  if (!isNaN(num) && num >= 1 && num <= 500) {
                    setMaxPdb(num);
                  }
                }
              }}
              placeholder={language === 'zh' ? '留空表示无限制' : 'Leave empty for unlimited'}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              {language === 'zh' ? '每个靶点最多获取的PDB结构数量（1-500），留空则无限制' : 'Maximum number of PDB structures per target (1-500), leave empty for unlimited'}
            </p>
          </div>

          {/* Single Template Selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {language === 'zh' ? '单独分析模板' : 'Single Analysis Template'}
            </label>
            <select
              value={singleTemplate}
              onChange={(e) => setSingleTemplate(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-gray-900 bg-white transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              {singleTemplates.map((tmpl) => (
                <option key={tmpl.id} value={tmpl.name}>
                  {language === 'zh' ? tmpl.name : (tmpl.name_en || tmpl.name)}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              {language === 'zh' ? '用于生成单个靶点的分析报告' : 'Template for individual protein evaluation reports'}
            </p>
          </div>

          {/* Batch Template Selector */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {language === 'zh' ? '互作分析模板' : 'Interaction Analysis Template'}
            </label>
            <select
              value={batchTemplate}
              onChange={(e) => setBatchTemplate(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-gray-900 bg-white transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            >
              {batchTemplates.map((tmpl) => (
                <option key={tmpl.id} value={tmpl.name}>
                  {language === 'zh' ? tmpl.name : (tmpl.name_en || tmpl.name)}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">
              {language === 'zh' ? '用于生成多靶点互作分析报告' : 'Template for multi-target interaction analysis reports'}
            </p>
          </div>

          {/* Submit Button */}
          <div className="pt-2">
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={isLoading}
            >
              {isLoading ? (language === 'zh' ? '创建中...' : 'Creating...') : (language === 'zh' ? '创建任务' : 'Create Task')}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
};
