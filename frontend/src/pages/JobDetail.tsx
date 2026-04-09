import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Activity,
  Play,
  Pause,
  RotateCcw,
  X,
  Clock,
  Target,
  CheckCircle,
  AlertCircle,
  Loader2,
  Dna,
  Beaker,
  FileText,
  Globe,
  Microscope,
  Layers,
  Settings,
} from 'lucide-react';
import { parseMarkdown } from '../utils/markdown';
import api from '../services/api';
import { useJobs } from '../contexts/JobContext';
import { useLanguage } from '../contexts/LanguageContext';
import { Button } from '../components/Button';
import { Card, CardContent, CardHeader } from '../components/Card';
import { Badge } from '../components/Badge';
import { TargetCard } from '../components/TargetCard';
import { PdbDetailPanel } from '../components/PdbDetailPanel';
import type { JobStatus, PdbStructure } from '../types';

// Generate HTML for popup window with markdown rendering
function generatePopupHtml(title: string, content: string): string {
  // Simple markdown to HTML (no HTML escaping - for document.write)
  const htmlContent = content
    .replace(/```([\s\S]*?)```/g, '<pre style="background:#1f2937;color:#f9fafb;padding:1rem;border-radius:0.5rem;overflow-x:auto;margin:1rem 0;"><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code style="background:#f3f4f6;padding:0.125rem 0.375rem;border-radius:0.25rem;font-size:0.875rem;">$1</code>')
    .replace(/^### (.+)$/gm, '<h3 style="font-size:1.1rem;font-weight:600;margin:1.25rem 0 0.5rem 0;color:#4b5563;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:1.25rem;font-weight:600;margin:1.5rem 0 0.75rem 0;color:#374151;">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="font-size:1.5rem;font-weight:700;margin:0 0 1rem 0;color:#111827;">$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight:600;color:#111827;">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p style="margin:0 0 0.75rem 0;color:#374151;">')
    .replace(/\n/g, '<br>');

  const safeTitle = title.replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${safeTitle} - Prompt</title><style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; background: #f9fafb; line-height: 1.6; }
    .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .container p { margin: 0 0 0.75rem 0; color: #374151; }
    .container ul, .container ol { margin: 0 0 0.75rem 1.5rem; color: #374151; }
    .container li { margin-bottom: 0.25rem; }
    .container hr { border: none; border-top: 1px solid #e5e7eb; margin: 1.5rem 0; }
  </style></head><body><div class="container"><p style="margin:0 0 0.75rem 0;color:#374151;">${htmlContent}</p></div></body></html>`;
}

// UniProt metadata detail panel component
interface UniProtDetailPanelProps {
  target: any;
  onClose: () => void;
}

const UniProtDetailPanel: React.FC<UniProtDetailPanelProps> = React.memo(({ target, onClose }) => {
  const { language } = useLanguage();
  const uniprotId = target.uniprot_id;
  const metadata = target.uniprot_metadata || {};
  const evaluation = target.evaluation || {};

  return (
    <div className="border border-gray-200 rounded-lg bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-white">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Dna className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <span className="font-mono font-bold text-lg text-gray-900">{uniprotId}</span>
            <p className="text-sm text-gray-500">{language === 'zh' ? 'UniProt 条目' : 'UniProt Entry'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={`https://www.uniprot.org/uniprotkb/${uniprotId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Globe className="w-4 h-4 text-gray-500" />
          </a>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Protein Name */}
        {metadata.protein_name && (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-1">
              <Microscope className="w-4 h-4" />
              {language === 'zh' ? '蛋白质名称' : 'Protein Name'}
            </div>
            <p className="text-gray-900 font-medium">{metadata.protein_name}</p>
          </div>
        )}

        {/* Gene Name */}
        {metadata.gene_name && (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-1">
              <Dna className="w-4 h-4" />
              {language === 'zh' ? '基因名称' : 'Gene Name'}
            </div>
            <p className="text-gray-900 font-mono">{metadata.gene_name}</p>
          </div>
        )}

        {/* Organism */}
        {metadata.organism && (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-1">
              <Globe className="w-4 h-4" />
              {language === 'zh' ? '物种' : 'Organism'}
            </div>
            <p className="text-gray-900">{metadata.organism}</p>
          </div>
        )}

        {/* Function */}
        {metadata.function && (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-1">
              <Beaker className="w-4 h-4" />
              {language === 'zh' ? '功能' : 'Function'}
            </div>
            <p className="text-gray-700 text-sm leading-relaxed">{metadata.function}</p>
          </div>
        )}

        {/* Domains */}
        {metadata.domains && metadata.domains.length > 0 && (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
              <Layers className="w-4 h-4" />
              {language === 'zh' ? '结构域' : 'Domains'}
            </div>
            <div className="space-y-1">
              {metadata.domains.map((domain: any, idx: number) => (
                <div
                  key={idx}
                  className="flex items-center justify-between py-1 px-2 bg-white rounded border border-gray-100"
                >
                  <span className="text-sm text-gray-700">{domain.name}</span>
                  <span className="text-xs font-mono text-gray-500">
                    {domain.start}-{domain.end}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Modifications */}
        {metadata.modifications && metadata.modifications.length > 0 && (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
              <Beaker className="w-4 h-4" />
              {language === 'zh' ? '翻译后修饰' : 'PTMs'}
            </div>
            <div className="flex flex-wrap gap-2">
              {metadata.modifications.map((mod: string, idx: number) => (
                <Badge key={idx} variant="outline" className="text-xs">
                  {mod}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* PDB Coverage */}
        {evaluation.pdb_data?.coverage && (
          <div className="bg-gradient-to-r from-purple-50 to-white p-3 rounded-lg border border-purple-100">
            <div className="flex items-center gap-2 text-sm font-medium text-purple-600 mb-2">
              <FileText className="w-4 h-4" />
              {language === 'zh' ? '结构覆盖' : 'Structure Coverage'}
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-lg font-bold text-purple-600">
                  {evaluation.pdb_data.coverage.coverage_percent.toFixed(1)}%
                </p>
                <span className="text-xs text-gray-500">{language === 'zh' ? '覆盖率' : 'Coverage'}</span>
              </div>
              <div>
                <p className="text-lg font-bold text-green-600">
                  {evaluation.pdb_data.coverage.covered_residues}
                </p>
                <span className="text-xs text-gray-500">{language === 'zh' ? '覆盖残基' : 'Covered'}</span>
              </div>
              <div>
                <p className="text-lg font-bold text-orange-600">
                  {evaluation.pdb_data.coverage.total_residues}
                </p>
                <span className="text-xs text-gray-500">{language === 'zh' ? '总残基' : 'Total'}</span>
              </div>
            </div>
          </div>
        )}

        {/* No metadata message */}
        {!metadata.protein_name && !metadata.function && (
          <div className="text-center py-6 text-gray-500">
            <Dna className="w-10 h-10 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">{language === 'zh' ? '暂无详细元数据' : 'No detailed metadata'}</p>
            <p className="text-xs text-gray-400 mt-1">
              {language === 'zh' ? '访问 UniProt 官网查看更多详情' : 'Visit UniProt website for more details'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
});

export const JobDetail: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const {
    selectedJob,
    jobProgress,
    isLoading,
    error,
    fetchJobDetail,
    fetchJobProgress,
    startPolling,
    stopPolling,
    isPolling,
    startJob,
    pauseJob,
    resumeJob,
    cancelJob,
    restartJob,
    clearError,
  } = useJobs();

  const [activeTab, setActiveTab] = useState<'overview' | 'interactions' | 'report'>('overview');

  // Store targets with evaluation data for overview
  const [targetsWithEval, setTargetsWithEval] = useState<any[]>([]);

  // TargetCard expansion and selection state
  const [expandedTargets, setExpandedTargets] = useState<Set<number>>(new Set());
  const [selectedTargetId, setSelectedTargetId] = useState<number | null>(null);
  const [selectedPdb, setSelectedPdb] = useState<{ targetId: number; structure: PdbStructure } | null>(null);
  // Common PDB IDs state for TargetCard filtering
  const [commonPdbIds, setCommonPdbIds] = useState<Set<string>>(new Set());

  // AI Report expansion state (for per-target collapsible reports)
  const [expandedReports, setExpandedReports] = useState<Set<number>>(new Set());

  // AI Interaction Analysis expansion state
  const [interactionReportExpanded, setInteractionReportExpanded] = useState(false);

  // Restart dialog state
  const [showRestartDialog, setShowRestartDialog] = useState(false);
  const [restartMode, setRestartMode] = useState<'all' | 'failed'>('all');
  const [restartParams, setRestartParams] = useState({
    name: '',
    description: '',
    priority: 5,
    evaluation_mode: 'parallel' as 'parallel' | 'sequential',
    max_pdb: 100,
  });
  const [showAdvancedParams, setShowAdvancedParams] = useState(false);

  // Network visualization state for zoom and pan
  const [networkScale, setNetworkScale] = useState(1);
  const [networkPan, setNetworkPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const networkContainerRef = useRef<HTMLDivElement>(null);

  // Job logs state for status bar
  const [, setJobLogs] = useState<Array<{ timestamp: string; level: string; message: string }>>([]);
  const [latestLog, setLatestLog] = useState<string>('');

  // Print report function - opens new window with just the report content
  const printReport = useCallback((_targetId: number, uniprotId: string, content: string) => {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      alert(language === 'zh' ? '请允许弹出窗口以导出PDF' : 'Please allow popups to export PDF');
      return;
    }

    // Convert markdown to HTML using a simple converter
    const convertMarkdownToHtml = (md: string): string => {
      let html = md;

      // Handle horizontal rules first
      html = html.replace(/^---$/gm, '<hr/>');

      // Handle headers
      html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
      html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
      html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
      html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');

      // Handle bold and italic (must be before other replacements)
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

      // Handle code blocks
      html = html.replace(/```[\s\S]*?```/g, (match) => {
        const code = match.replace(/```\w*\n?/, '').replace(/```$/, '');
        return `<pre><code>${code}</code></pre>`;
      });

      // Handle inline code
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

      // Handle lists
      html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
      html = html.replace(/^- (.+)$/gm, '<li>$1</li>');

      // Wrap consecutive <li> elements
      html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => {
        if (match.includes('1.') || /^\d/.test(match)) {
          return '<ol>' + match + '</ol>';
        }
        return '<ul>' + match + '</ul>';
      });

      // Handle paragraphs (lines that aren't already wrapped)
      const lines = html.split('\n');
      const result: string[] = [];
      let inBlock = false;

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
          if (inBlock) {
            result.push('</p>');
            inBlock = false;
          }
          continue;
        }
        if (trimmed.startsWith('<h') || trimmed.startsWith('<ol') || trimmed.startsWith('<ul') || trimmed.startsWith('<pre') || trimmed.startsWith('<hr') || trimmed.startsWith('</')) {
          if (inBlock) {
            result.push('</p>');
            inBlock = false;
          }
          result.push(line);
        } else {
          if (!inBlock) {
            result.push('<p>');
            inBlock = true;
          }
          result.push(line);
        }
      }
      if (inBlock) {
        result.push('</p>');
      }

      return result.join('\n');
    };

    const htmlContent = convertMarkdownToHtml(content);

    printWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>${uniprotId} - ${language === 'zh' ? '分析报告' : 'Analysis Report'}</title>
        <style>
          body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            padding: 40px;
            max-width: 800px;
            margin: 0 auto;
            line-height: 1.8;
            color: #333;
            font-size: 14px;
          }
          h1, h2, h3, h4 { color: #1a1a1a; margin-top: 24px; margin-bottom: 12px; }
          h1 { font-size: 22px; border-bottom: 2px solid #333; padding-bottom: 8px; }
          h2 { font-size: 18px; border-bottom: 1px solid #ddd; padding-bottom: 6px; }
          h3 { font-size: 16px; }
          h4 { font-size: 14px; }
          p { margin: 12px 0; }
          ul, ol { margin: 12px 0; padding-left: 24px; }
          li { margin: 6px 0; }
          strong { font-weight: 600; }
          em { font-style: italic; }
          blockquote {
            border-left: 4px solid #3b82f6;
            padding-left: 16px;
            margin: 16px 0;
            background: #f0f9ff;
            font-style: italic;
          }
          hr { border: none; border-top: 1px solid #ddd; margin: 24px 0; }
          code {
            background: #f5f5f5;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
          }
          pre {
            background: #1a1a1a;
            color: #f5f5f5;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
          }
          pre code { background: none; padding: 0; }
          table {
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
          }
          th, td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
          }
          th { background: #f5f5f5; }
          @media print {
            body { padding: 20px; font-size: 12px; }
            h1 { font-size: 18px; }
            h2 { font-size: 16px; }
          }
        </style>
      </head>
      <body>
        <h1>${uniprotId}</h1>
        ${htmlContent}
        <script>
          window.onload = function() {
            setTimeout(function() {
              window.print();
            }, 300);
          };
        </script>
      </body>
      </html>
    `);
    printWindow.document.close();
  }, [language]);

  // Add wheel zoom listener for network
  useEffect(() => {
    const container = networkContainerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.deltaY < 0) {
        setNetworkScale(s => Math.min(s * 1.1, 3));
      } else {
        setNetworkScale(s => Math.max(s / 1.1, 0.3));
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, []);

  // Fetch targets with evaluation data when job loads or status changes
  useEffect(() => {
    if (jobId) {
      fetch(`/api/v2/evaluate/multi/${jobId}/targets`)
        .then(res => res.json())
        .then(data => {
          if (data.success && data.targets) {
            setTargetsWithEval(data.targets);
          }
        })
        .catch(err => console.error('Failed to fetch targets:', err));
    }
  }, [jobId, selectedJob?.job?.status]);

  // AI Report - select appropriate language version based on UI language
  const rawReport = language === 'en'
    ? (selectedJob?.job?.report_content_en || selectedJob?.job?.report_content || '')
    : (selectedJob?.job?.report_content || '');

  // Find AI content starting from markers (works for both Chinese and English)
  const getAIContent = (content: string): string => {
    if (!content) return '';
    const markers = language === 'en'
      ? ['## Summary', '# Human', '## AI Analysis', '## AI', '# Summary']
      : ['## 摘要', '# 人', '## AI分析'];
    let aiStartIndex = -1;
    for (const marker of markers) {
      const idx = content.indexOf(marker);
      if (idx !== -1 && (aiStartIndex === -1 || idx < aiStartIndex)) {
        aiStartIndex = idx;
      }
    }
    return aiStartIndex !== -1 ? content.substring(aiStartIndex) : content;
  };

  const aiReport = getAIContent(rawReport);

  // Literature references from PDB citations - with deduplication and grouped PDB IDs
  const literature = React.useMemo(() => {
    const map = new Map<string, any>();
    
    targetsWithEval?.forEach((target: any) => {
      const pdbData = target.evaluation?.pdb_data;
      if (!pdbData?.structures) return;
      
      pdbData.structures.forEach((structure: any) => {
        (structure.citations || []).forEach((cite: any) => {
          const key = cite.title || cite.pmid || JSON.stringify(cite);
          if (!key) return;
          
          if (!map.has(key)) {
            map.set(key, {
              title: cite.title && cite.title !== 'None' ? cite.title : 'Unknown Title',
              authors: structure.authors ? structure.authors.join(', ') : (structure.authors || ''),
              journal: cite.journal && cite.journal !== 'None' ? cite.journal : '',
              year: cite.year && cite.year !== 'None' ? cite.year.toString() : '',
              pmid: cite.pubmed_id ? cite.pubmed_id.toString() : '',
              pdb_ids: new Set<string>([structure.pdb_id])
            });
          } else {
            map.get(key).pdb_ids.add(structure.pdb_id);
          }
        });
      });
    });
    
    return Array.from(map.values()).map((item: any) => ({
      ...item,
      pdb_ids: Array.from(item.pdb_ids)
    }));
  }, [targetsWithEval]);

  const [interactions, setInteractions] = useState<any[]>([]);
  const [interactionsLoading, setInteractionsLoading] = useState(false);
  const [chainInteractions, setChainInteractions] = useState<{
    nodes: Array<{
      id: string;
      label: string;
      gene_name: string;
      protein_name: string;
      is_input: boolean;
      pdb_count: number;
      organism: string;
    }>;
    direct_interactions: any[];
    indirect_interactions: any[];
    all_interactions: any[];
    chain_interactions: any[];
    pdb_structures: string[];
    failed_pdbs?: string[];
  } | null>(null);

  const [failedPdbs, setFailedPdbs] = useState<string[]>([]);
  const [retryingPdbs, setRetryingPdbs] = useState(false);

  // Derive interaction analysis from selectedJob (reactive to language changes)
  const interactionAnalysis = language === 'en'
    ? selectedJob?.job?.interaction_ai_analysis_en
    : selectedJob?.job?.interaction_ai_analysis;

  // Derive interaction prompt from selectedJob (for debugging)
  const interactionPrompt = language === 'en'
    ? selectedJob?.job?.interaction_prompt_en
    : selectedJob?.job?.interaction_prompt;

  // Fetch interactions data when job loads (not just when on interactions tab)
  useEffect(() => {
    if (jobId && selectedJob?.job.status === 'completed') {
      setInteractionsLoading(true);
      fetch(`/api/v2/evaluate/multi/${jobId}/interactions`)
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setInteractions(data.interactions || []);
          }
        })
        .catch(err => console.error('Failed to fetch interactions:', err))
        .finally(() => setInteractionsLoading(false));

      // Always fetch chain-level interactions from the dedicated endpoint
      // This endpoint computes and caches the analysis if not already available
      fetch(`/api/v2/evaluate/multi/${jobId}/interactions/chain`)
        .then(res => res.json())
        .then(data => {
          if (data.success) {
            setChainInteractions(data);
            setFailedPdbs(data.failed_pdbs || []);
          } else {
            console.error('Chain interactions API error:', data.error);
          }
        })
        .catch(err => console.error('Failed to fetch chain interactions:', err));
    }
  }, [jobId, selectedJob?.job.status]);

  // Memoize deduplicated interactions - expensive computation
  const deduplicatedInteractions = useMemo(() => {
    return Object.values(
      interactions.reduce((acc: any, interaction: any) => {
        const pairKey = [interaction.source_uniprot, interaction.target_uniprot].sort().join('-');
        // Deep copy interaction and create new metadata object
        const interactionMetadata = interaction.metadata ? { ...interaction.metadata } : {};

        if (!acc[pairKey]) {
          acc[pairKey] = {
            ...interaction,
            metadata: interactionMetadata,
            sources: []
          };
        } else {
          // Deep copy existing metadata to avoid reference issues
          acc[pairKey].metadata = { ...acc[pairKey].metadata };
        }

        // Check for common structures
        const hasCommonStructures =
          (interactionMetadata?.common_structures && interactionMetadata.common_structures.length > 0) ||
          !!interactionMetadata?.common_pdb ||
          (Array.isArray(interactionMetadata?.common_pdbs) && interactionMetadata.common_pdbs.length > 0);

        if (hasCommonStructures) {
          // If has common structures, this takes priority - set to 100%
          acc[pairKey].score = 1.0;
          acc[pairKey].metadata.experimental = true;
          acc[pairKey].hasCommonPdb = true;
        }

        // Merge common_structures
        if (interactionMetadata?.common_structures?.length > 0) {
          const existing = acc[pairKey].metadata.common_structures || [];
          acc[pairKey].metadata.common_structures = [...new Set([...existing, ...interactionMetadata.common_structures])];
          if (!acc[pairKey].metadata.common_pdb) {
            acc[pairKey].metadata.common_pdb = interactionMetadata.common_structures[0];
          }
        }
        // Merge common_pdb
        if (interactionMetadata?.common_pdb) {
          acc[pairKey].metadata.common_pdb = interactionMetadata.common_pdb;
          const existingPdbs = acc[pairKey].metadata.common_pdbs || [];
          if (!existingPdbs.includes(interactionMetadata.common_pdb)) {
            acc[pairKey].metadata.common_pdbs = [...existingPdbs, interactionMetadata.common_pdb];
          }
        }
        // Merge common_pdbs array
        if (interactionMetadata?.common_pdbs?.length > 0) {
          const existingPdbs = acc[pairKey].metadata.common_pdbs || [];
          acc[pairKey].metadata.common_pdbs = [...new Set([...existingPdbs, ...interactionMetadata.common_pdbs])];
          if (!acc[pairKey].metadata.common_pdb) {
            acc[pairKey].metadata.common_pdb = interactionMetadata.common_pdbs[0];
          }
        }

        // Accumulate sources
        if (interactionMetadata?.sources) {
          acc[pairKey].sources = [...new Set([...acc[pairKey].sources, ...interactionMetadata.sources])];
        }
        // Keep highest score (if not already confirmed)
        if (!acc[pairKey].hasCommonPdb && interaction.score > acc[pairKey].score) {
          acc[pairKey].score = interaction.score;
        }
        return acc;
      }, {})
    );
  }, [interactions]);

  // Compute common PDB IDs from interactions data
  useEffect(() => {
    if (interactions.length > 0) {
      // Find confirmed interactions (those with common PDB structures)
      const confirmedInteractions = interactions.filter((i: any) =>
        !!i.metadata?.common_pdb ||
        i.hasCommonPdb ||
        (Array.isArray(i.metadata?.common_pdbs) && i.metadata.common_pdbs.length > 0) ||
        (Array.isArray(i.metadata?.common_structures) && i.metadata.common_structures.length > 0)
      );

      // Collect ALL unique PDB IDs across all confirmed interactions
      const allPdbIds = new Set<string>();
      confirmedInteractions.forEach((i: any) => {
        if (i.metadata?.common_pdb) allPdbIds.add(i.metadata.common_pdb);
        if (i.metadata?.common_pdbs?.length) {
          i.metadata.common_pdbs.forEach((pdb: string) => allPdbIds.add(pdb));
        }
        if (i.metadata?.common_structures?.length) {
          i.metadata.common_structures.forEach((pdb: string) => allPdbIds.add(pdb));
        }
      });

      setCommonPdbIds(allPdbIds);
    }
  }, [interactions]);

  // Fetch job details on mount
  useEffect(() => {
    if (jobId) {
      fetchJobDetail(jobId, language);
      fetchJobProgress(jobId);
    }
  }, [jobId, fetchJobDetail, fetchJobProgress, language]);

  // Start polling for active jobs
  useEffect(() => {
    const activeStatuses = ['processing', 'pending', 'running', 'paused'];
    if (jobId && selectedJob && activeStatuses.includes(selectedJob.job.status)) {
      startPolling(jobId);
    } else if (isPolling) {
      stopPolling();
    }

    return () => {
      if (isPolling) {
        stopPolling();
      }
    };
  }, [jobId, selectedJob?.job.status, isPolling, startPolling, stopPolling]);

  // Fetch job logs for status bar
  useEffect(() => {
    const fetchLogs = async () => {
      if (!jobId) return;
      try {
        const result = await api.jobControl.getJobLogs(jobId);
        if (result.success && result.logs) {
          setJobLogs(result.logs);
          // Set latest log message (last one in the array)
          if (result.logs.length > 0) {
            setLatestLog(result.logs[result.logs.length - 1].message);
          }
        }
      } catch (err) {
        console.error('Failed to fetch job logs:', err);
      }
    };

    fetchLogs();
    // Poll logs every 5 seconds when job is running
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [jobId, selectedJob?.job.status]);

  // Clear latestLog when job status changes to pending (after restart)
  useEffect(() => {
    if (selectedJob?.job.status === 'pending') {
      setLatestLog('');
    }
  }, [selectedJob?.job.status]);

  // All hooks must be defined before any early returns or conditional logic
  // Memoize statusConfig to prevent recreation on every render
  const statusConfig = useMemo<Record<JobStatus, { label: string; color: string; icon: React.ReactNode }>>(() => ({
    pending: { label: language === 'zh' ? '待处理' : 'Pending', color: 'yellow', icon: <Clock className="w-5 h-5" /> },
    processing: { label: language === 'zh' ? '运行中' : 'Running', color: 'blue', icon: <Loader2 className="w-5 h-5 animate-spin" /> },
    running: { label: language === 'zh' ? '运行中' : 'Running', color: 'blue', icon: <Loader2 className="w-5 h-5 animate-spin" /> },
    completed: { label: language === 'zh' ? '已完成' : 'Completed', color: 'green', icon: <CheckCircle className="w-5 h-5" /> },
    failed: { label: language === 'zh' ? '失败' : 'Failed', color: 'red', icon: <AlertCircle className="w-5 h-5" /> },
    paused: { label: language === 'zh' ? '已暂停' : 'Paused', color: 'gray', icon: <Pause className="w-5 h-5" /> },
  }), [language]);

  // Memoize callbacks for TargetCard to prevent unnecessary re-renders
  const handleToggleExpand = useCallback((targetId: number) => {
    setExpandedTargets(prev => {
      const next = new Set(prev);
      if (next.has(targetId)) {
        next.delete(targetId);
      } else {
        next.add(targetId);
      }
      return next;
    });
  }, []);

  const handleSelectTarget = useCallback((targetId: number) => {
    setSelectedTargetId(targetId);
    setSelectedPdb(null);
  }, []);

  const handlePdbSelect = useCallback((targetId: number, pdbId: string, source: 'pdb' | 'alphafold', structures: PdbStructure[] | undefined) => {
    const structure = structures?.find(
      (s: PdbStructure) => s.pdb_id === pdbId && s.source === source
    );
    if (structure) {
      setSelectedPdb({ targetId, structure });
    }
  }, []);

  const handleBlastPdbSelect = useCallback(async (targetId: number, pdbId: string) => {
    // Find the target and its structures from targetsWithEval
    const targetData = targetsWithEval.find((t: any) => t.target_id === targetId);
    if (!targetData) return;

    const structures = targetData?.evaluation?.pdb_data?.structures || [];
    // Try to find the structure in existing data
    let structure = structures.find((s: PdbStructure) => s.pdb_id === pdbId);

    if (!structure) {
      // Fetch PDB structure details from API
      try {
        const response = await fetch(`/api/v2/evaluate/multi/pdb/${pdbId}`);
        const data = await response.json();
        if (data.success && data.structure) {
          structure = data.structure;
        }
      } catch (err) {
        console.error('Failed to fetch PDB structure:', err);
      }
    }

    if (structure) {
      setSelectedTargetId(targetId);
      setSelectedPdb({ targetId, structure });
    }
  }, [targetsWithEval]);

  const handleStart = useCallback(async () => {
    if (jobId) {
      await startJob(jobId);
      // Refresh job details after starting
      fetchJobDetail(jobId, language);
      fetchJobProgress(jobId);
    }
  }, [jobId, startJob, fetchJobDetail, fetchJobProgress, language]);

  const handlePause = useCallback(async () => {
    if (jobId) await pauseJob(jobId);
  }, [jobId, pauseJob]);

  const handleResume = useCallback(async () => {
    if (jobId) await resumeJob(jobId);
  }, [jobId, resumeJob]);

  const handleCancel = useCallback(async () => {
    const confirmMsg = language === 'zh'
      ? '确定要取消此任务吗？'
      : 'Are you sure you want to cancel this task?';
    if (jobId && window.confirm(confirmMsg)) {
      await cancelJob(jobId);
    }
  }, [jobId, cancelJob, language]);

  const handleRestart = useCallback(async () => {
    if (!jobId) return;

    // Initialize params from current job
    if (selectedJob?.job) {
      const jobConfig = selectedJob.job.config || {};
      setRestartParams({
        name: selectedJob.job.name || '',
        description: selectedJob.job.description || '',
        priority: selectedJob.job.priority || 5,
        evaluation_mode: selectedJob.job.evaluation_mode || 'parallel',
        max_pdb: jobConfig.max_pdb || 100,
      });
    }
    setShowRestartDialog(true);
  }, [jobId, selectedJob]);

  // Retry handler for failed PDBs
  const handleRetryFailedPdbs = useCallback(async () => {
    if (!jobId || failedPdbs.length === 0) return;
    
    setRetryingPdbs(true);
    try {
      const response = await fetch(`/api/v2/evaluate/multi/${jobId}/interactions/chain/retry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ failed_pdbs: failedPdbs }),
      });
      const data = await response.json();
      if (data.success) {
        setChainInteractions(data);
        setFailedPdbs(data.failed_pdbs || []);
        // Refresh job detail to get updated data
        fetchJobDetail(jobId, language);
      }
    } catch (err) {
      console.error('Failed to retry PDBs:', err);
    } finally {
      setRetryingPdbs(false);
    }
  }, [jobId, failedPdbs, fetchJobDetail, language]);

  const confirmRestart = useCallback(async () => {
    if (!jobId) return;

    const resetFailedOnly = restartMode === 'failed';
    setShowRestartDialog(false);
    // Pass params to restartJob
    await restartJob(jobId, resetFailedOnly, restartParams);
    // Refresh job details after restarting
    fetchJobDetail(jobId, language);
    fetchJobProgress(jobId);
  }, [jobId, restartJob, restartMode, restartParams, fetchJobDetail, fetchJobProgress, language]);

  // Early returns must come AFTER all hooks
  if (isLoading && !selectedJob) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-500">{t('app.loading')}</p>
        </div>
      </div>
    );
  }

  if (!selectedJob) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-gray-900 font-medium mb-2">{language === 'zh' ? '任务不存在' : 'Task Not Found'}</p>
          <p className="text-gray-500 mb-6">{language === 'zh' ? '无法找到该任务的详细信息' : 'Cannot find detailed information for this task'}</p>
          <Button onClick={() => navigate('/')}>{t('app.back')}</Button>
        </div>
      </div>
    );
  }

  const { job, statistics } = selectedJob;
  const currentStatus = statusConfig[job.status] || statusConfig.pending;

  // Calculate progress color
  const progressColor =
    job.status === 'completed'
      ? 'bg-green-500'
      : job.status === 'failed'
      ? 'bg-red-500'
      : job.status === 'processing'
      ? 'bg-blue-500'
      : 'bg-gray-400';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600 rounded-lg">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">{job.name}</h1>
                <p className="text-sm text-gray-500">
                  ID: {job.job_id} · {t('templates.createdAt')} {new Date(job.created_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {job.status === 'pending' && (
                <>
                  <Button variant="outline" onClick={() => {
                    if (selectedJob?.job) {
                      const jobConfig = selectedJob.job.config || {};
                      setRestartParams({
                        name: selectedJob.job.name || '',
                        description: selectedJob.job.description || '',
                        priority: selectedJob.job.priority || 5,
                        evaluation_mode: selectedJob.job.evaluation_mode || 'parallel',
                        max_pdb: jobConfig.max_pdb || 100,
                      });
                    }
                    setShowAdvancedParams(true);
                  }}>
                    <Settings className="w-4 h-4 mr-2" />
                    {language === 'zh' ? '编辑参数' : 'Edit Params'}
                  </Button>
                  <Button variant="primary" onClick={handleStart}>
                    <Play className="w-4 h-4 mr-2" />
                    {language === 'zh' ? '开始' : 'Start'}
                  </Button>
                </>
              )}
              {job.status === 'processing' && (
                <Button variant="secondary" onClick={handlePause}>
                  <Pause className="w-4 h-4 mr-2" />
                  {language === 'zh' ? '暂停' : 'Pause'}
                </Button>
              )}
              {job.status === 'paused' && (
                <Button variant="primary" onClick={handleResume}>
                  <Play className="w-4 h-4 mr-2" />
                  {language === 'zh' ? '恢复' : 'Resume'}
                </Button>
              )}
              {(job.status === 'pending' || job.status === 'processing' || job.status === 'paused') && (
                <Button variant="outline" onClick={handleCancel}>
                  <X className="w-4 h-4 mr-2" />
                  {t('app.cancel')}
                </Button>
              )}
              {(job.status === 'completed' || job.status === 'failed') && (
                <Button variant="outline" onClick={handleRestart}>
                  <RotateCcw className="w-4 h-4 mr-2" />
                  {language === 'zh' ? '重启' : 'Restart'}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
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
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center justify-between">
              <p className="text-red-700">{error}</p>
              <button onClick={clearError} className="text-red-500 hover:text-red-700">
                {t('app.close')}
              </button>
            </div>
          </div>
        )}

        {/* Status Banner - hidden when completed */}
        {job.status !== 'completed' && (
          <div
            className={`mb-6 p-4 rounded-lg border ${
              job.status === 'failed'
                ? 'bg-red-50 border-red-200'
                : job.status === 'processing'
                ? 'bg-blue-50 border-blue-200'
                : 'bg-gray-50 border-gray-200'
            }`}
          >
            <div className="flex items-center gap-4">
              <div
                className={`p-3 rounded-full ${
                  job.status === 'failed'
                    ? 'bg-red-100 text-red-600'
                    : job.status === 'processing'
                    ? 'bg-blue-100 text-blue-600'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {currentStatus.icon}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-gray-900">状态:</span>
                  <Badge
                    variant={
                      job.status === 'failed'
                        ? 'error'
                        : job.status === 'processing'
                        ? 'running'
                        : job.status === 'paused'
                        ? 'warning'
                        : 'default'
                    }
                  >
                    {currentStatus.label}
                  </Badge>
                </div>
                {/* Only show progress bar when job is running/processing/pending */}
                {(job.status === 'processing' || job.status === 'pending' || job.status === 'running') && (
                  <>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-500 ${progressColor}`}
                        style={{ width: `${jobProgress?.progress.percentage || 0}%` }}
                      />
                    </div>
                    <div className="flex justify-between items-center mt-1 text-sm text-gray-600">
                      <span>
                        进度: {jobProgress?.progress.completed || 0} / {jobProgress?.progress.total || 0} (
                        {jobProgress?.progress.percentage || 0}%)
                      </span>
                      {jobProgress?.progress?.failed != null && jobProgress.progress.failed > 0 && (
                        <span className="text-red-600">
                          失败: {jobProgress.progress.failed}
                        </span>
                      )}
                    </div>
                    {/* Status log bar - shows current step */}
                    {latestLog && (
                      <div className="mt-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800 truncate">
                        <span className="font-medium">{language === 'zh' ? '当前步骤:' : 'Current step:'} </span>
                        {latestLog}
                      </div>
                    )}
                  </>
                )}
                {/* Show completion summary only for failed jobs - hide for completed */}
                {job.status === 'failed' && (
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span>
                      完成: <span className="font-medium text-green-600">{jobProgress?.progress.completed || 0}</span> / {jobProgress?.progress.total || 0}
                    </span>
                    {jobProgress?.progress?.failed != null && jobProgress.progress.failed > 0 && (
                      <span>
                        失败: <span className="font-medium text-red-600">{jobProgress.progress.failed}</span>
                      </span>
                    )}
                    <span className="text-gray-400">
                      任务已结束
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-6 border-b border-gray-200">
          <div className="flex gap-6">
            {[
              { id: 'overview', label: language === 'zh' ? '概览' : 'Overview' },
              { id: 'report', label: language === 'zh' ? '评估报告' : 'Evaluation Report' },
              ...(targetsWithEval?.length > 1 ? [{ id: 'interactions', label: language === 'zh' ? '相互作用' : 'Interactions' }] : []),
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`pb-3 text-sm font-medium transition-colors relative ${
                  activeTab === tab.id
                    ? 'text-blue-600'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
                {activeTab === tab.id && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600" />
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Task Statistics Section */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {/* Total Targets */}
              <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-100">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-blue-100 rounded-md">
                      <Target className="w-4 h-4 text-blue-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">{language === 'zh' ? '总靶点数' : 'Total Targets'}</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-900">{statistics.total}</div>
                </CardContent>
              </Card>

              {/* Pending */}
              <Card className="bg-gradient-to-br from-gray-50 to-white border-gray-100">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-gray-100 rounded-md">
                      <Clock className="w-4 h-4 text-gray-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">{language === 'zh' ? '待处理' : 'Pending'}</span>
                  </div>
                  <div className="text-2xl font-bold text-gray-700">{statistics.pending}</div>
                </CardContent>
              </Card>

              {/* Processing */}
              <Card className="bg-gradient-to-br from-blue-50 to-white border-blue-100">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-blue-100 rounded-md">
                      <Loader2 className="w-4 h-4 text-blue-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">{language === 'zh' ? '处理中' : 'Processing'}</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-600">{statistics.processing}</div>
                </CardContent>
              </Card>

              {/* Completed */}
              <Card className="bg-gradient-to-br from-green-50 to-white border-green-100">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-green-100 rounded-md">
                      <CheckCircle className="w-4 h-4 text-green-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">{language === 'zh' ? '已完成' : 'Completed'}</span>
                  </div>
                  <div className="text-2xl font-bold text-green-600">{statistics.completed}</div>
                </CardContent>
              </Card>

              {/* Failed */}
              <Card className="bg-gradient-to-br from-red-50 to-white border-red-100">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-red-100 rounded-md">
                      <AlertCircle className="w-4 h-4 text-red-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">{language === 'zh' ? '失败' : 'Failed'}</span>
                  </div>
                  <div className="text-2xl font-bold text-red-600">{statistics.failed}</div>
                </CardContent>
              </Card>

              {/* Success Rate */}
              <Card className="bg-gradient-to-br from-purple-50 to-white border-purple-100">
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="p-1.5 bg-purple-100 rounded-md">
                      <Activity className="w-4 h-4 text-purple-600" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">{language === 'zh' ? '成功率' : 'Success Rate'}</span>
                  </div>
                  <div className="text-2xl font-bold text-purple-600">
                    {statistics.success_rate.toFixed(1)}%
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Status Distribution Bar */}
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-gray-700">{language === 'zh' ? '状态分布' : 'Status Distribution'}</span>
                  <span className="text-sm text-gray-500">
                    {jobProgress?.progress.completed || 0} / {jobProgress?.progress.total || 0}
                  </span>
                </div>
                <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden flex">
                  {statistics.total > 0 && (
                    <>
                      <div
                        className="h-full bg-green-500 transition-all duration-500"
                        style={{ width: `${(statistics.completed / statistics.total) * 100}%` }}
                      />
                      <div
                        className="h-full bg-red-500 transition-all duration-500"
                        style={{ width: `${(statistics.failed / statistics.total) * 100}%` }}
                      />
                      <div
                        className="h-full bg-blue-500 transition-all duration-500"
                        style={{ width: `${(statistics.processing / statistics.total) * 100}%` }}
                      />
                      <div
                        className="h-full bg-gray-400 transition-all duration-500"
                        style={{ width: `${(statistics.pending / statistics.total) * 100}%` }}
                      />
                    </>
                  )}
                </div>
                <div className="flex gap-4 mt-3 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    {language === 'zh' ? '已完成' : 'Completed'} ({statistics.completed})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    {language === 'zh' ? '失败' : 'Failed'} ({statistics.failed})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                    {language === 'zh' ? '处理中' : 'Processing'} ({statistics.processing})
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-gray-400" />
                    {language === 'zh' ? '待处理' : 'Pending'} ({statistics.pending})
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* PDB Stats & Target List */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
              {/* Left Column: TargetCard List */}
              <Card className="border border-gray-200 h-full">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                      <Target className="w-4 h-4 text-blue-600" />
                      {language === 'zh' ? '靶点列表' : 'Target List'}
                    </h3>
                    <Badge variant="outline">{targetsWithEval?.length || 0} {language === 'zh' ? '个靶点' : 'targets'}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 pt-0 flex flex-col">
                  {selectedJob.targets && selectedJob.targets.length > 0 ? (
                    selectedJob.targets.map((target, index) => {
                      const evalData = targetsWithEval.find((t: any) => t.target_id === target.target_id);
                      return (
                        <div key={target.target_id} className={index === 0 ? 'mt-3' : ''}>
                        <TargetCard
                          targetId={target.target_id}
                          uniprotId={target.uniprot_id}
                          status={target.status}
                          overallScore={target.evaluation?.overall_score}
                          structureQualityScore={target.evaluation?.structure_quality_score}
                          pdbData={evalData?.evaluation?.pdb_data}
                          uniprotMetadata={evalData?.uniprot_metadata}
                          blastResults={evalData?.evaluation?.blast_results}
                          isExpanded={expandedTargets.has(target.target_id)}
                          isSelected={selectedTargetId === target.target_id}
                          commonPdbIds={commonPdbIds}
                          onToggleExpand={() => handleToggleExpand(target.target_id)}
                          onSelect={() => handleSelectTarget(target.target_id)}
                          onPdbSelect={(pdbId, source) => handlePdbSelect(target.target_id, pdbId, source, evalData?.evaluation?.pdb_data?.structures)}
                          onBlastPdbSelect={(pdbId) => handleBlastPdbSelect(target.target_id, pdbId)}
                        />
                        </div>
                      );
                    })
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <Target className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">{language === 'zh' ? '暂无靶点数据' : 'No target data'}</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Right Column: Detail Panel */}
              <div>
                {selectedPdb ? (
                  <PdbDetailPanel
                    structure={selectedPdb.structure}
                    onClose={() => setSelectedPdb(null)}
                  />
                ) : selectedTargetId ? (
                  (() => {
                    const target = targetsWithEval.find((t: any) => t.target_id === selectedTargetId);
                    return target ? (
                      <UniProtDetailPanel
                        target={target}
                        onClose={() => setSelectedTargetId(null)}
                      />
                    ) : (
                      <Card>
                        <CardContent>
                          <div className="text-center py-12 text-gray-500">
                            <Dna className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                            <p className="text-sm">{language === 'zh' ? '无法找到靶点数据' : 'Cannot find target data'}</p>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })()
                ) : (
                  <Card className="border border-gray-200 h-full">
                    <CardContent className="flex items-center justify-center min-h-[200px] h-full">
                      <div className="text-center text-gray-500">
                        <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm">{language === 'zh' ? '选择左侧靶点查看详情' : 'Select a target on the left to view details'}</p>
                        <p className="text-xs text-gray-400 mt-1">
                          {language === 'zh' ? '点击 UniProt ID 查看元数据，展开后点击结构查看 PDB 详情' : 'Click UniProt ID to view metadata, expand and click structure to view PDB details'}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>
        )}

                {activeTab === 'interactions' && (
          <div className="space-y-4">
            {selectedJob?.job.status !== 'completed' ? (
              <div className="text-center py-12">
                <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">{language === 'zh' ? '任务完成后将自动分析靶点相互作用' : 'Target interactions will be analyzed automatically after task completion'}</p>
                <p className="text-sm text-gray-400 mt-2">{language === 'zh' ? '当前状态' : 'Current status'}: {selectedJob?.job.status}</p>
              </div>
            ) : interactionsLoading ? (
              <div className="text-center py-12">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
                <p className="text-gray-500">{language === 'zh' ? '加载相互作用数据...' : 'Loading interaction data...'}</p>
              </div>
            ) : !interactionAnalysis && interactions.length === 0 ? (
              <div className="text-center py-12">
                <Activity className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">{language === 'zh' ? '暂未发现靶点间相互作用' : 'No interactions found between targets'}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Key Findings */}
                {(() => {
                  const deduped = deduplicatedInteractions;

                  // Build protein name map (prioritize gene_name for display)
                  const proteinNameMap: Record<string, string> = {};
                  (targetsWithEval || []).forEach((t: any) => {
                    if (t.uniprot_id) {
                      // Prioritize gene_name (shorter, more recognizable in networks)
                      proteinNameMap[t.uniprot_id] =
                        t.uniprot_metadata?.gene_name ||
                        t.uniprot_metadata?.gene ||
                        t.uniprot_metadata?.protein_name ||
                        t.gene_name ||
                        t.gene ||
                        t.protein_name ||
                        '';
                    }
                  });

                  // Collect all interactions with common structures (check all possible fields)
                  // hasCommonPdb is set on the deduplicated object when common_structures was detected
                  const confirmedInteractions = deduped.filter((i: any) =>
                    !!i.metadata?.common_pdb ||
                    i.hasCommonPdb ||
                    (Array.isArray(i.metadata?.common_pdbs) && i.metadata.common_pdbs.length > 0) ||
                    (Array.isArray(i.metadata?.common_structures) && i.metadata.common_structures.length > 0)
                  );

                  // Collect ALL unique PDB IDs across all confirmed interactions
                  const allPdbIds = new Set<string>();
                  confirmedInteractions.forEach((i: any) => {
                    if (i.metadata?.common_pdb) allPdbIds.add(i.metadata.common_pdb);
                    if (i.metadata?.common_pdbs?.length) {
                      i.metadata.common_pdbs.forEach((pdb: string) => allPdbIds.add(pdb));
                    }
                    // Also collect from common_structures (backend field name)
                    if (i.metadata?.common_structures?.length) {
                      i.metadata.common_structures.forEach((pdb: string) => allPdbIds.add(pdb));
                    }
                  });

                  // Debug: log confirmed interactions
                  // console.log('Interactions data:', interactions.length, 'interactions');
                  // console.log('Deduplicated:', deduped.length, deduped);
                  // console.log('First deduped metadata:', deduped[0]?.metadata);
                  // console.log('Confirmed:', confirmedInteractions.length, confirmedInteractions);

                  if (deduped.length === 0) return null;

                  return (
                    <Card className="border border-blue-200 bg-gradient-to-br from-blue-50/50 to-white">
                      <CardHeader>
                        <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                          <span className="w-1.5 h-4 bg-blue-600 rounded-full"></span>
                          {language === 'zh' ? '整体概况' : 'Overview'}
                        </h3>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {/* Overview stats - only 4 boxes */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                          <div className="bg-white rounded-lg p-2 border border-blue-100">
                            <div className="text-xs text-gray-500">{language === 'zh' ? '总靶点数' : 'Total Targets'}</div>
                            <div className="text-lg font-bold text-blue-600">
                              {new Set([...deduped.map((i: any) => i.source_uniprot), ...deduped.map((i: any) => i.target_uniprot)]).size}
                            </div>
                          </div>
                          <div className="bg-white rounded-lg p-2 border border-blue-100">
                            <div className="text-xs text-gray-500">{language === 'zh' ? '相互作用数' : 'Interactions'}</div>
                            <div className="text-lg font-bold text-purple-600">{deduped.length}</div>
                          </div>
                          <div className="bg-white rounded-lg p-2 border border-blue-100">
                            <div className="text-xs text-gray-500">{language === 'zh' ? '直接互作' : 'Direct'}</div>
                            <div className="text-lg font-bold text-green-600">
                              {chainInteractions?.direct_interactions?.length || 0}
                            </div>
                          </div>
                          <div className="bg-white rounded-lg p-2 border border-blue-100">
                            <div className="text-xs text-gray-500">{language === 'zh' ? '高置信度' : 'High Confidence'}</div>
                            <div className="text-lg font-bold text-orange-600">
                              {deduped.filter((i: any) => i.score > 0.5).length}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })()}

                {/* AI Analysis Report - Collapsible */}
                {interactionAnalysis && (
                  <Card className="border border-gray-200">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <h3
                          className="text-base font-semibold text-gray-900 flex items-center gap-2 cursor-pointer"
                          onClick={() => setInteractionReportExpanded(!interactionReportExpanded)}
                        >
                          <span className="w-1.5 h-4 bg-green-500 rounded-full"></span>
                          {language === 'zh' ? 'AI 相互作用分析报告' : 'AI Interaction Analysis Report'}
                        </h3>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7 px-2 text-purple-600"
                            onClick={(e) => {
                              e.stopPropagation();
                              const prompt = interactionPrompt;
                              if (prompt && prompt.trim()) {
                                const promptWindow = window.open('', '_blank');
                                if (promptWindow) {
                                  promptWindow.document.write(generatePopupHtml(job.name || 'Interaction', prompt));
                                  promptWindow.document.close();
                                }
                              } else {
                                alert(language === 'zh' ? '暂无Prompt记录' : 'No prompt record');
                              }
                            }}
                          >
                            {language === 'zh' ? '查看Prompt' : 'View Prompt'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7 px-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              const blob = new Blob([interactionAnalysis], { type: 'text/markdown' });
                              const url = URL.createObjectURL(blob);
                              const a = document.createElement('a');
                              a.href = url;
                              a.download = `interaction_report_${job.job_id}.md`;
                              a.click();
                              URL.revokeObjectURL(url);
                            }}
                          >
                            {language === 'zh' ? '导出MD' : 'Export MD'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-xs h-7 px-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              printReport(0, `${job.name || 'Interaction'}`, interactionAnalysis);
                            }}
                          >
                            {language === 'zh' ? '导出PDF' : 'Export PDF'}
                          </Button>
                          <span className="text-gray-400 text-sm cursor-pointer" onClick={() => setInteractionReportExpanded(!interactionReportExpanded)}>
                            {interactionReportExpanded ? '▼' : '▶'}
                          </span>
                        </div>
                      </div>
                    </CardHeader>
                    {interactionReportExpanded && (
                      <CardContent>
                        <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                          <div
                            className="prose prose-sm max-w-none"
                            dangerouslySetInnerHTML={{ __html: parseMarkdown(interactionAnalysis || '') }}
                          />
                        </div>
                      </CardContent>
                    )}
                  </Card>
                )}

                {/* Chain-Level Interaction Analysis Summary */}
                {chainInteractions && (() => {
                  // Build protein name map (same as in network visualization)
                  const localProteinNameMap: Record<string, string> = {};
                  (targetsWithEval || []).forEach((t: any) => {
                    if (t.uniprot_id) {
                      localProteinNameMap[t.uniprot_id] =
                        t.uniprot_metadata?.gene_name ||
                        t.uniprot_metadata?.gene ||
                        t.uniprot_metadata?.protein_name ||
                        t.gene_name ||
                        t.gene ||
                        t.protein_name ||
                        '';
                    }
                  });
                  return (
                    <Card className="border border-gray-200">
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                            <span className="w-1.5 h-4 bg-blue-500 rounded-full"></span>
                            {language === 'zh' ? '相互作用详情' : 'Interaction Details'}
                          </h3>
                          {failedPdbs.length > 0 && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={handleRetryFailedPdbs}
                              disabled={retryingPdbs}
                              className="text-orange-600 border-orange-300 hover:bg-orange-50"
                            >
                              {retryingPdbs ? (
                                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                              ) : (
                                <RotateCcw className="w-4 h-4 mr-1" />
                              )}
                              {language === 'zh' 
                                ? `重试失败PDB (${failedPdbs.length})` 
                                : `Retry Failed PDBs (${failedPdbs.length})`}
                            </Button>
                          )}
                        </div>
                        {failedPdbs.length > 0 && (
                          <div className="mt-2 text-sm text-orange-600 flex items-center gap-2">
                            <AlertCircle className="w-4 h-4" />
                            {language === 'zh' 
                              ? `以下PDB获取失败: ${failedPdbs.slice(0, 5).join(', ')}${failedPdbs.length > 5 ? '...' : ''}` 
                              : `Failed PDBs: ${failedPdbs.slice(0, 5).join(', ')}${failedPdbs.length > 5 ? '...' : ''}`}
                          </div>
                        )}
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-4">
                          {/* Direct Interactions */}
                          {chainInteractions.direct_interactions?.length > 0 && (
                            <div>
                              <h4 className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-2">
                                <span className="w-3 h-0.5 bg-green-500 rounded"></span>
                                {language === 'zh' ? '直接互作（同一PDB结构中链级相互作用）' : 'Direct Interactions (chain-level in same PDB)'}
                              </h4>
                              <div className="grid gap-2">
                                {chainInteractions.direct_interactions.map((interaction: any, idx: number) => {
                                  return (
                                    <div key={idx} className="bg-white rounded-lg p-3 border border-green-100">
                                      <div className="flex items-center justify-between flex-wrap gap-2">
                                        <div className="flex items-center gap-2">
                                          <Badge variant="success" className="font-mono">{interaction.source_uniprot}</Badge>
                                          <span className="text-gray-400">—</span>
                                          <Badge variant="success" className="font-mono">{interaction.target_uniprot}</Badge>
                                        </div>
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <Badge variant="success" className="text-xs">
                                            {interaction.pdb_ids?.length || 0} PDBs
                                          </Badge>
                                          <Badge variant="outline" className="text-xs">
                                            {language === 'zh' ? '直接' : 'Direct'}
                                          </Badge>
                                        </div>
                                      </div>
                                      {interaction.pdb_ids?.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                          {interaction.pdb_ids.map((pdb: string, i: number) => (
                                            <span key={i} className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded text-xs font-mono">
                                              {pdb}
                                            </span>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Indirect Interactions */}
                          {chainInteractions.indirect_interactions?.length > 0 && (
                            <div>
                              <h4 className="text-sm font-semibold text-orange-700 mb-2 flex items-center gap-2">
                                <span className="w-3 h-0.5 bg-orange-400 border-t-2 border-dashed border-orange-400"></span>
                                {language === 'zh' ? '间接互作（通过介导蛋白连接）' : 'Indirect Interactions (mediated by other proteins)'}
                              </h4>
                              <div className="grid gap-2">
                                {chainInteractions.indirect_interactions.map((interaction: any, idx: number) => {
                                  const sourceName = localProteinNameMap[interaction.source_uniprot] || interaction.source_uniprot;
                                  const targetName = localProteinNameMap[interaction.target_uniprot] || interaction.target_uniprot;
                                  const mediatorName = localProteinNameMap[interaction.mediator_uniprot] || interaction.mediator_uniprot;
                                  return (
                                    <div key={idx} className="bg-white rounded-lg p-3 border border-orange-100">
                                      <div className="flex items-center justify-between flex-wrap gap-2">
                                        <div className="flex items-center gap-2">
                                          <Badge variant="outline" className="font-mono">{interaction.source_uniprot}</Badge>
                                          <span className="text-gray-400">--</span>
                                          <Badge variant="outline" className="font-mono text-orange-600 border-orange-200">{mediatorName}</Badge>
                                          <span className="text-gray-400">--</span>
                                          <Badge variant="outline" className="font-mono">{interaction.target_uniprot}</Badge>
                                        </div>
                                        <Badge variant="outline" className="text-xs text-orange-600 border-orange-200">
                                          {language === 'zh' ? '间接' : 'Indirect'}
                                        </Badge>
                                      </div>
                                      <p className="text-xs text-gray-500 mt-2">
                                        {language === 'zh'
                                          ? `${sourceName} 与 ${targetName} 通过 ${mediatorName} 介导形成间接相互作用`
                                          : `${sourceName} connected to ${targetName} via ${mediatorName} (indirect)`}
                                      </p>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Chain Interaction Summary */}
                          <div className="text-sm text-gray-600 bg-white/50 rounded-lg p-3">
                            <p>
                              {language === 'zh'
                                ? `基于 ${chainInteractions.pdb_structures?.length || 0} 个PDB结构分析，发现 ${(chainInteractions.direct_interactions?.length || 0) + (chainInteractions.indirect_interactions?.length || 0)} 个链级互作对`
                                : `Analyzed ${chainInteractions.pdb_structures?.length || 0} PDB structures with ${(chainInteractions.direct_interactions?.length || 0) + (chainInteractions.indirect_interactions?.length || 0)} chain-level interaction pairs`}
                            </p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })()}

                {/* Network Visualization */}
                <Card className="border border-gray-200">
                  <CardHeader>
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                        <span className="w-1.5 h-4 bg-purple-500 rounded-full"></span>
                        {language === 'zh' ? '相互作用网络图' : 'Interaction Network'}
                      </h3>
                      <div className="flex items-center gap-2 flex-wrap">
                        <Button variant="outline" size="sm" onClick={() => { setNetworkScale(s => Math.min(s * 1.2, 3)); }}>
                          {language === 'zh' ? '放大' : 'Zoom In'}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => { setNetworkScale(s => Math.max(s / 1.2, 0.3)); }}>
                          {language === 'zh' ? '缩小' : 'Zoom Out'}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => { setNetworkScale(1); setNetworkPan({ x: 0, y: 0 }); }}>
                          {t('app.reset')}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      // Build protein name map from targetsWithEval (prioritize gene_name)
                      const proteinNameMap: Record<string, string> = {};
                      (targetsWithEval || []).forEach((t: any) => {
                        if (t.uniprot_id) {
                          // Prioritize gene_name (shorter, more recognizable in networks)
                          proteinNameMap[t.uniprot_id] =
                            t.uniprot_metadata?.gene_name ||
                            t.uniprot_metadata?.gene ||
                            t.uniprot_metadata?.protein_name ||
                            t.gene_name ||
                            t.gene ||
                            t.protein_name ||
                            '';
                        }
                      });

                      // Always use chain interactions for display
                      const displayInteractions = chainInteractions?.all_interactions || chainInteractions?.direct_interactions || [];
                      const nodeSet = new Set<string>();
                      displayInteractions.forEach((i: any) => {
                        nodeSet.add(i.source_uniprot);
                        nodeSet.add(i.target_uniprot);
                      });

                      // Add nodes from chain analysis data
                      if (chainInteractions?.nodes) {
                        chainInteractions.nodes.forEach((n: any) => {
                          if (n.id) nodeSet.add(n.id);
                        });
                      }

                      const nodes = Array.from(nodeSet);
                      const nodeCount = nodes.length;

                      if (nodeCount === 0) return <div className="text-center py-8 text-gray-500">{language === 'zh' ? '无数据' : 'No data'}</div>;

                      const centerX = 250, centerY = 150, radius = Math.min(120, 80 + nodeCount * 15);
                      const nodePositions: Record<string, {x: number, y: number}> = {};
                      nodes.forEach((node, i) => {
                        const angle = (2 * Math.PI * i) / nodeCount - Math.PI / 2;
                        nodePositions[node] = {
                          x: centerX + radius * Math.cos(angle),
                          y: centerY + radius * Math.sin(angle)
                        };
                      });

                      const handleMouseDown = (e: React.MouseEvent) => {
                        setIsDragging(true);
                        setDragStart({ x: e.clientX - networkPan.x, y: e.clientY - networkPan.y });
                      };
                      const handleMouseMove = (e: React.MouseEvent) => {
                        if (isDragging) {
                          setNetworkPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
                        }
                      };
                      const handleMouseUp = () => {
                        setIsDragging(false);
                      };

                      return (
                        <div
                          className="overflow-hidden border border-gray-100 rounded-lg bg-gray-50 touch-none"
                          ref={networkContainerRef}
                          style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
                          onMouseDown={handleMouseDown}
                          onMouseMove={handleMouseMove}
                          onMouseUp={handleMouseUp}
                          onMouseLeave={handleMouseUp}
                        >
                          {chainInteractions && (
                            <div className="p-2 bg-blue-50 border-b border-blue-100 flex flex-wrap gap-3 text-xs">
                              <span className="flex items-center gap-1">
                                <span className="w-4 h-0.5 bg-green-500 rounded"></span>
                                {language === 'zh' ? '直接互作' : 'Direct'}: {chainInteractions.direct_interactions?.length || 0}
                              </span>
                              <span className="text-gray-500">
                                {language === 'zh' ? '涉及结构数' : 'PDB structures'}: {chainInteractions.pdb_structures?.length || 0}
                              </span>
                            </div>
                          )}
                          <svg width="100%" height="400" viewBox="0 0 500 300" className="mx-auto">
                            <g transform={`translate(${networkPan.x}, ${networkPan.y}) scale(${networkScale})`}>
                              {/* Draw direct interactions (solid green lines) */}
                              {displayInteractions.map((interaction: any, idx: number) => {
                                // Skip indirect interactions
                                if (interaction.interaction_type === 'indirect') return null;

                                const source = nodePositions[interaction.source_uniprot];
                                const target = nodePositions[interaction.target_uniprot];
                                if (!source || !target) return null;

                                return (
                                  <line
                                    key={`line-${idx}`}
                                    x1={source.x} y1={source.y}
                                    x2={target.x} y2={target.y}
                                    stroke="#22c55e"
                                    strokeWidth="2.5"
                                    strokeOpacity={0.8}
                                  />
                                );
                              })}
                              {nodes.map((node) => {
                                const proteinName = proteinNameMap[node] || '';
                                const showGene = proteinName && proteinName.length <= 8;
                                const nodeRadius = showGene ? 26 : 20;
                                const cx = nodePositions[node].x;
                                const cy = nodePositions[node].y;
                                return (
                                  <g key={node}>
                                    <circle
                                      cx={cx}
                                      cy={cy}
                                      r={nodeRadius}
                                      fill="#fff"
                                      stroke="#3b82f6"
                                      strokeWidth="1.5"
                                    />
                                    <text
                                      x={cx}
                                      y={cy}
                                      textAnchor="middle"
                                      dominantBaseline="middle"
                                      fontSize="7"
                                      fontWeight="600"
                                      fill="#1e40af"
                                    >
                                      {node.length > 8 ? node.substring(0, 6) + '..' : node}
                                    </text>
                                    {showGene && (
                                      <text
                                        x={cx}
                                        y={cy + 10}
                                        textAnchor="middle"
                                        dominantBaseline="middle"
                                        fontSize="5"
                                        fill="#64748b"
                                      >
                                        {proteinName}
                                      </text>
                                    )}
                                  </g>
                                );
                              })}
                            </g>
                          </svg>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}

        {activeTab === 'report' && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="font-medium">{language === 'zh' ? '评估报告' : 'Evaluation Report'}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {selectedJob?.job.report_generated_at && (
                      <span className="text-sm text-gray-500">
                        {language === 'zh' ? '生成于' : 'Generated at'}: {new Date(selectedJob.job.report_generated_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}
                      </span>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* 任务统计 */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                      <div className="text-2xl font-bold text-purple-600">{job.job_id}</div>
                      <div className="text-xs text-gray-500">{language === 'zh' ? '任务ID' : 'Task ID'}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                      <div className="text-2xl font-bold text-blue-600">{targetsWithEval?.length || 0}</div>
                      <div className="text-xs text-gray-500">{language === 'zh' ? '靶点数量' : 'Targets'}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                      <div className="text-2xl font-bold text-green-600">
                        {targetsWithEval?.filter((t: any) => t.status === 'completed').length || 0}
                      </div>
                      <div className="text-xs text-gray-500">{language === 'zh' ? '已完成' : 'Completed'}</div>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-gray-200">
                      <div className="text-2xl font-bold text-orange-600">
                        {targetsWithEval?.filter((t: any) => t.status === 'failed').length || 0}
                      </div>
                      <div className="text-xs text-gray-500">{language === 'zh' ? '失败' : 'Failed'}</div>
                    </div>
                  </div>

                  {/* AI 分析报告 */}
                  {aiReport ? (
                    <div className="space-y-4">

                      {/* Per-target AI Analysis Reports */}
                      {targetsWithEval && targetsWithEval.length > 0 && (
                        <div className="space-y-3">
                          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                            <span className="w-1.5 h-4 bg-blue-500 rounded-full"></span>
                            {language === 'zh' ? '各靶点 AI 分析报告' : 'Per-Target AI Analysis Reports'}
                          </h3>
                          {targetsWithEval.map((target: any, index: number) => {
                            // Select appropriate language version for AI analysis
                            const aiAnalysis = language === 'en'
                              ? (target?.evaluation?.ai_analysis_en || target?.evaluation?.ai_analysis)
                              : (target?.evaluation?.ai_analysis);
                            const reportContent = aiAnalysis?.analysis || aiAnalysis?.summary || '';
                            const aiError = aiAnalysis?.error || target?.evaluation?.error_message || '';

                            // Get literature for this specific target (by matching PDB IDs)
                            const targetPdbIds = target?.evaluation?.pdb_data?.structures?.map((s: any) => s.pdb_id) || [];
                            const targetLiterature = literature.filter((lit: any) =>
                              lit.pdb_ids?.some((pid: string) => targetPdbIds.includes(pid))
                            );
                            
                            return (
                              <Card key={target.target_id} className="border border-gray-200">
                                {/* Target Header */}
                                <CardHeader
                                  className="cursor-pointer hover:bg-gray-50 transition-colors py-3 px-4"
                                  onClick={() => {
                                    setExpandedReports(prev => {
                                      const next = new Set(prev);
                                      if (next.has(index)) {
                                        next.delete(index);
                                      } else {
                                        next.add(index);
                                      }
                                      return next;
                                    });
                                  }}
                                >
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                      <span className="font-mono font-medium text-gray-900">{target.uniprot_id}</span>
                                      <span className="text-lg">
                                        {target.status === 'completed' ? '✅' :
                                         target.status === 'failed' ? '❌' :
                                         target.status === 'processing' ? '🔄' : '⏳'}
                                      </span>
                                      <Badge variant={
                                        target.status === 'completed' ? 'success' :
                                        target.status === 'failed' ? 'error' :
                                        target.status === 'processing' ? 'running' : 'default'
                                      } className="text-xs">
                                        {target.status === 'completed' ? 'completed' :
                                         target.status === 'failed' ? 'failed' :
                                         target.status === 'processing' ? 'processing' :
                                         target.status === 'pending' ? 'pending' : target.status}
                                      </Badge>
                                      {target.evaluation?.overall_score != null && (
                                        <span className="text-xs text-gray-500">
                                          {language === 'zh' ? '质量' : 'Quality'}: <span className="font-medium text-blue-600">{target.evaluation.overall_score.toFixed(2)}</span>
                                        </span>
                                      )}
                                      <span className="text-xs text-gray-500">
                                        {language === 'zh' ? '结构' : 'Structures'}: <span className="font-medium text-purple-600">{target?.evaluation?.pdb_data?.structures?.length || 0}</span>
                                      </span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-xs h-7 px-2 text-purple-600"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const prompt = target?.evaluation?.ai_prompt;
                                          if (prompt && prompt.trim()) {
                                            const promptWindow = window.open('', '_blank');
                                            if (promptWindow) {
                                              promptWindow.document.write(generatePopupHtml(target.uniprot_id, prompt));
                                              promptWindow.document.close();
                                            }
                                          } else {
                                            alert(language === 'zh' ? '该靶点暂无Prompt记录' : 'No prompt record for this target');
                                          }
                                        }}
                                      >
                                        {language === 'zh' ? '查看Prompt' : 'View Prompt'}
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-xs h-7 px-2"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const blob = new Blob([reportContent], { type: 'text/markdown' });
                                          const url = URL.createObjectURL(blob);
                                          const a = document.createElement('a');
                                          a.href = url;
                                          a.download = `${target.uniprot_id}_report.md`;
                                          a.click();
                                          URL.revokeObjectURL(url);
                                        }}
                                      >
                                        {language === 'zh' ? '导出MD' : 'Export MD'}
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        className="text-xs h-7 px-2"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          printReport(target.target_id, target.uniprot_id, reportContent);
                                        }}
                                      >
                                        {language === 'zh' ? '导出PDF' : 'Export PDF'}
                                      </Button>
                                      <span className="text-gray-400 text-sm">
                                        {expandedReports.has(index) ? '▼' : '▶'}
                                      </span>
                                    </div>
                                  </div>
                                </CardHeader>
                                
                                {expandedReports.has(index) && (
                                  <CardContent className="py-3">
                                    {/* AI Report Content or Error Display */}
                                    {aiError ? (
                                      /* Error Display */
                                      <div className="bg-red-50 rounded-lg p-4 border border-red-200">
                                        <div className="flex items-start gap-3">
                                          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                                          <div className="flex-1">
                                            <h4 className="text-sm font-semibold text-red-800 mb-1">
                                              {language === 'zh' ? 'AI 分析失败' : 'AI Analysis Failed'}
                                            </h4>
                                            <p className="text-sm text-red-700">{aiError}</p>
                                            {target.status === 'failed' && (
                                              <p className="text-xs text-red-600 mt-2">
                                                {language === 'zh' ? '任务执行失败，请重试' : 'Task execution failed, please retry'}
                                              </p>
                                            )}
                                          </div>
                                        </div>
                                      </div>
                                    ) : reportContent ? (
                                      /* Normal Report Content */
                                      <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                                        <div
                                          className="prose prose-sm max-w-none"
                                          dangerouslySetInnerHTML={{ __html: parseMarkdown(reportContent) }}
                                        />
                                      </div>
                                    ) : (
                                      /* No Content Yet */
                                      <div className="bg-gray-50 rounded-lg p-4 border border-gray-100 text-center text-gray-500 text-sm">
                                        {language === 'zh' ? '暂无报告内容' : 'No report content yet'}
                                      </div>
                                    )}
                                    
                                    {/* Literature for this target */}
                                    {targetLiterature.length > 0 && (
                                      <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                                        <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1">
                                          <span className="w-1 h-3 bg-green-500 rounded-full"></span>
                                          {language === 'zh' ? '参考文献' : 'References'} ({targetLiterature.length})
                                        </h4>
                                        <div className="space-y-1.5">
                                          {targetLiterature.map((lit: any, litIdx: number) => (
                                            <div key={litIdx} className="bg-white rounded p-2 border border-gray-100">
                                              <p className="text-xs font-medium text-gray-900 mb-0.5 line-clamp-1">
                                                {lit.title}
                                              </p>
                                              <p className="text-xs text-gray-500">
                                                {lit.authors?.substring(0, 50)}{lit.authors?.length > 50 ? '...' : ''}
                                                {lit.journal && ` - ${lit.journal}`}
                                                {lit.year && ` (${lit.year})`}
                                                {lit.pmid && ` - PMID: ${lit.pmid}`}
                                              </p>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </CardContent>
                                )}
                              </Card>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ) : selectedJob?.job.status === 'completed' ? (
                    <div className="text-center py-8">
                      <p className="text-gray-500">{language === 'zh' ? '暂无 AI 分析报告' : 'No AI analysis report available'}</p>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <p className="text-gray-500">{language === 'zh' ? '任务完成后将自动生成 AI 分析报告' : 'AI analysis report will be generated automatically after task completion'}</p>
                      <p className="text-sm text-gray-400 mt-2">
                        {language === 'zh' ? '当前状态' : 'Current status'}: {selectedJob?.job.status}
                      </p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Restart Confirmation Dialog */}
        {showRestartDialog && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowRestartDialog(false)}>
            <div className="bg-white rounded-xl shadow-lg border border-gray-200 w-full max-w-md mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                    <RotateCcw className="w-4 h-4 text-blue-600" />
                    {language === 'zh' ? '重新运行任务' : 'Restart Task'}
                  </h3>
                  <button
                    onClick={() => setShowRestartDialog(false)}
                    className="p-1 hover:bg-gray-200 rounded transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-500" />
                  </button>
                </div>
              </div>
              <div className="p-6">
                <p className="text-gray-600 mb-3 text-sm">
                  {language === 'zh' ? '选择重置模式：' : 'Select reset mode:'}
                </p>
                <div className="space-y-2 mb-6">
                  <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${restartMode === 'all' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}>
                    <input
                      type="radio"
                      name="restartMode"
                      value="all"
                      checked={restartMode === 'all'}
                      onChange={() => setRestartMode('all')}
                      className="mt-0.5 w-4 h-4 text-blue-600"
                    />
                    <div>
                      <div className="font-medium text-gray-900 text-sm">
                        {language === 'zh' ? '重置所有靶点' : 'Reset All Targets'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {language === 'zh' ? '清除所有靶点的评估数据和AI分析报告' : 'Clear all evaluation data and AI analysis reports'}
                      </div>
                    </div>
                  </label>
                  <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${restartMode === 'failed' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}>
                    <input
                      type="radio"
                      name="restartMode"
                      value="failed"
                      checked={restartMode === 'failed'}
                      onChange={() => setRestartMode('failed')}
                      className="mt-0.5 w-4 h-4 text-blue-600"
                    />
                    <div>
                      <div className="font-medium text-gray-900 text-sm">
                        {language === 'zh' ? '只重置失败的靶点' : 'Only Reset Failed Targets'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {language === 'zh' ? '保留已完成靶点的数据' : 'Keep completed targets data'}
                      </div>
                    </div>
                  </label>
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => setShowRestartDialog(false)}
                  >
                    {language === 'zh' ? '取消' : 'Cancel'}
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1"
                    onClick={confirmRestart}
                  >
                    {language === 'zh' ? '确认重启' : 'Confirm Restart'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Edit Parameters Dialog */}
        {showAdvancedParams && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAdvancedParams(false)}>
            <div className="bg-white rounded-xl shadow-lg border border-gray-200 w-full max-w-md mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
              <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
                    <Settings className="w-4 h-4 text-blue-600" />
                    {language === 'zh' ? '编辑任务参数' : 'Edit Job Parameters'}
                  </h3>
                  <button
                    onClick={() => setShowAdvancedParams(false)}
                    className="p-1 hover:bg-gray-200 rounded transition-colors"
                  >
                    <X className="w-4 h-4 text-gray-500" />
                  </button>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-4">
                  {/* Job Name */}
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      {language === 'zh' ? '任务名称' : 'Job Name'}
                    </label>
                    <input
                      type="text"
                      value={restartParams.name}
                      onChange={(e) => setRestartParams({ ...restartParams, name: e.target.value })}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>

                  {/* Priority */}
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      {language === 'zh' ? '优先级' : 'Priority'} (1-10)
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={restartParams.priority}
                        onChange={(e) => setRestartParams({ ...restartParams, priority: parseInt(e.target.value) })}
                        className="flex-1"
                      />
                      <span className="text-sm font-medium text-gray-700 w-6 text-center">{restartParams.priority}</span>
                    </div>
                  </div>

                  {/* Evaluation Mode */}
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      {language === 'zh' ? '评估模式' : 'Evaluation Mode'}
                    </label>
                    <select
                      value={restartParams.evaluation_mode}
                      onChange={(e) => setRestartParams({ ...restartParams, evaluation_mode: e.target.value as 'parallel' | 'sequential' })}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="parallel">{language === 'zh' ? '并行' : 'Parallel'}</option>
                      <option value="sequential">{language === 'zh' ? '顺序' : 'Sequential'}</option>
                    </select>
                  </div>

                  {/* Max PDB */}
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      {language === 'zh' ? '最大PDB数量上限' : 'Max PDB Count'}
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="500"
                      value={restartParams.max_pdb || ''}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '') {
                          setRestartParams({ ...restartParams, max_pdb: undefined as any });
                        } else {
                          const num = parseInt(val);
                          if (!isNaN(num) && num >= 1 && num <= 500) {
                            setRestartParams({ ...restartParams, max_pdb: num });
                          }
                        }
                      }}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      {language === 'zh' ? '每个靶点最多获取的PDB结构数量' : 'Maximum number of PDB structures per target'}
                    </p>
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      {language === 'zh' ? '描述' : 'Description'}
                    </label>
                    <textarea
                      value={restartParams.description}
                      onChange={(e) => setRestartParams({ ...restartParams, description: e.target.value })}
                      rows={2}
                      className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                    />
                  </div>
                </div>
                <div className="flex gap-3 mt-6">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => setShowAdvancedParams(false)}
                  >
                    {language === 'zh' ? '取消' : 'Cancel'}
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1"
                    onClick={async () => {
                      try {
                        const response = await fetch(`/api/v2/evaluate/multi/${jobId}/params`, {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            name: restartParams.name,
                            description: restartParams.description,
                            priority: restartParams.priority,
                            evaluation_mode: restartParams.evaluation_mode,
                            max_pdb: restartParams.max_pdb || 100,
                          }),
                        });
                        const result = await response.json();
                        if (result.success) {
                          setShowAdvancedParams(false);
                          // Refresh job details to get updated values
                          if (jobId) {
                            fetchJobDetail(jobId, language);
                          }
                        } else {
                          alert(result.error || (language === 'zh' ? '保存失败' : 'Save failed'));
                        }
                      } catch (error) {
                        console.error('Failed to update params:', error);
                        alert(language === 'zh' ? '保存失败' : 'Save failed');
                      }
                    }}
                  >
                    {language === 'zh' ? '保存' : 'Save'}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
