import React from 'react';
import { ChevronDown, ChevronRight, Database, CheckCircle, AlertCircle, Loader2, Search } from 'lucide-react';
import { Badge } from './Badge';
import { useLanguage } from '../contexts/LanguageContext';
import type { PdbStructure } from '../types';

interface BlastResult {
  pdb_id: string;
  title?: string;
  identity?: number;
  score?: number;
  evalue?: number;
}

interface TargetCardProps {
  targetId: number;
  uniprotId: string;
  status: string;
  overallScore?: number;
  structureQualityScore?: number;
  pdbData?: {
    pdb_ids: string[];
    structures: PdbStructure[];
    coverage?: {
      coverage_percent: number;
      covered_residues: number;
      total_residues: number;
    };
  };
  uniprotMetadata?: {
    protein_name?: string;
    gene_name?: string;
    organism?: string;
    function?: string;
    domains?: Array<{ name: string; start: number; end: number }>;
    modifications?: string[];
  };
  blastResults?: {
    query_id: string;
    results: BlastResult[];
  };
  isExpanded: boolean;
  isSelected: boolean;
  commonPdbIds?: Set<string>;
  onToggleExpand: () => void;
  onSelect: () => void;
  onPdbSelect: (pdbId: string, source: 'pdb' | 'alphafold') => void;
  onBlastPdbSelect?: (pdbId: string) => void;
}

export const TargetCard: React.FC<TargetCardProps> = ({
  uniprotId,
  status,
  overallScore,
  structureQualityScore,
  pdbData,
  uniprotMetadata,
  blastResults,
  isExpanded,
  isSelected,
  commonPdbIds,
  onToggleExpand,
  onSelect,
  onPdbSelect,
  onBlastPdbSelect,
}) => {
  const { language } = useLanguage();
  const [showCommonOnly, setShowCommonOnly] = React.useState(false);
  const commonPdbCount = commonPdbIds ? pdbData?.structures?.filter(s => commonPdbIds.has(s.pdb_id)).length || 0 : 0;

  // Filter structures based on showCommonOnly
  const filteredStructures = showCommonOnly && commonPdbIds
    ? pdbData?.structures?.filter(s => commonPdbIds.has(s.pdb_id)) || []
    : pdbData?.structures || [];
  const statusVariant = status === 'completed' ? 'success' : status === 'failed' ? 'error' : status === 'processing' ? 'running' : 'default';

  const statusLabels: Record<string, string> = {
    pending: language === 'zh' ? '待处理' : 'Pending',
    processing: language === 'zh' ? '处理中' : 'Processing',
    completed: language === 'zh' ? '已完成' : 'Completed',
    failed: language === 'zh' ? '失败' : 'Failed',
  };

  const pdbCount = pdbData?.structures?.length || 0;
  const alphafoldCount = pdbData?.structures?.filter(s => s.source === 'alphafold').length || 0;

  return (
    <div
      className={`rounded-lg bg-white overflow-hidden transition-all duration-200 border border-gray-200 shadow-sm ${
        isSelected
          ? 'ring-2 ring-blue-100 shadow-md'
          : 'hover:bg-gray-50'
      }`}
    >
      {/* Header - always visible */}
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3 flex-1">
          {/* Expand/Collapse button */}
          <button
            className="p-1 hover:bg-gray-100 rounded transition-colors"
            onClick={(e) => {
              e.stopPropagation();
              onToggleExpand();
            }}
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-500" />
            )}
          </button>

          {/* UniProt ID - clickable for metadata and expand */}
          <div
            className="cursor-pointer flex-1"
            onClick={(e) => {
              e.stopPropagation();
              onSelect();
              if (!isExpanded) {
                onToggleExpand();
              }
            }}
          >
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                <span className="font-mono font-semibold text-gray-900 hover:text-blue-600 transition-colors">
                  {uniprotId}
                </span>
                {/* Status icon */}
                {status === 'completed' && (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                )}
                {status === 'failed' && (
                  <AlertCircle className="w-4 h-4 text-red-500" />
                )}
                {status === 'processing' && (
                  <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                )}
              </div>
              {uniprotMetadata?.protein_name && (
                <span className="text-sm text-gray-600 truncate max-w-[200px]">
                  {uniprotMetadata.protein_name}
                </span>
              )}
            </div>

            {/* Statistics row displayed directly on UniProt entry */}
            <div className="flex items-center gap-3 mt-1.5">
              {/* Overall Score */}
              {overallScore != null && (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-400">{language === 'zh' ? '评分' : 'Score'}</span>
                  <span className={`text-xs font-medium ${
                    overallScore >= 0.8 ? 'text-green-600' :
                    overallScore >= 0.6 ? 'text-blue-600' :
                    overallScore >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {overallScore.toFixed(2)}
                  </span>
                </div>
              )}

              {/* Structure Quality Score */}
              {structureQualityScore != null && (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-400">{language === 'zh' ? '结构' : 'Structure'}</span>
                  <span className={`text-xs font-medium ${
                    structureQualityScore >= 0.8 ? 'text-green-600' :
                    structureQualityScore >= 0.6 ? 'text-blue-600' :
                    structureQualityScore >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {structureQualityScore.toFixed(2)}
                  </span>
                </div>
              )}

              {/* Coverage */}
              {pdbData?.coverage && (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-gray-400">{language === 'zh' ? '覆盖' : 'Coverage'}</span>
                  <span className="text-xs font-medium text-blue-600">
                    {pdbData.coverage.coverage_percent.toFixed(1)}%
                  </span>
                </div>
              )}

              {/* PDB Count */}
              {pdbCount > 0 && (
                <div className="flex items-center gap-1">
                  <Database className="w-3 h-3 text-gray-400" />
                  <span className="text-xs text-gray-500">
                    {pdbCount} {language === 'zh' ? '结构' : 'structures'}
                    {alphafoldCount > 0 && (
                      <span className="text-gray-400 ml-1">
                        ({alphafoldCount} AF)
                      </span>
                    )}
                    {commonPdbCount > 0 && (
                      <span className="text-green-600 font-medium ml-1">
                        · {commonPdbCount} {language === 'zh' ? '共有' : 'common'}
                      </span>
                    )}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Status Badge */}
        <Badge variant={statusVariant}>{statusLabels[status] || status}</Badge>
      </div>

      {/* Expanded PDB List - only shows PDB entries, no statistics */}
      {isExpanded && pdbData && (
        <div className="border-t border-gray-100 bg-gradient-to-b from-gray-50 to-white">
          {/* PDB/AlphaFold Structure List */}
          {pdbData.structures && pdbData.structures.length > 0 && (
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-700 flex items-center gap-2">
                  <Database className="w-4 h-4 text-blue-500" />
                  {language === 'zh' ? '结构列表' : 'Structure List'}
                  <span className="text-xs text-gray-400">
                    ({showCommonOnly ? filteredStructures.length : pdbData.structures.length})
                  </span>
                </span>
                <div className="flex items-center gap-2">
                  {commonPdbCount > 0 && (
                    <button
                      onClick={() => setShowCommonOnly(!showCommonOnly)}
                      className={`px-2 py-1 text-xs rounded border transition-colors ${
                        showCommonOnly
                          ? 'bg-green-100 border-green-300 text-green-700'
                          : 'bg-white border-gray-200 text-gray-600 hover:bg-green-50'
                      }`}
                    >
                      {language === 'zh' ? '只看共有' : 'Common only'} ({commonPdbCount})
                    </button>
                  )}
                  <span className="text-xs text-gray-400">
                    {language === 'zh' ? '点击查看详情' : 'Click to view'}
                  </span>
                </div>
              </div>
              <div className="space-y-1 max-h-80 overflow-y-auto pr-1">
                {filteredStructures.map((structure) => {
                  const isCommon = commonPdbIds?.has(structure.pdb_id);
                  return (
                    <div
                      key={structure.pdb_id}
                      className={`group flex items-center justify-between p-3 hover:bg-blue-50 rounded-lg cursor-pointer transition-all duration-200 border ${
                        isCommon ? 'bg-green-50 border-green-200' : 'bg-white border-gray-100'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onPdbSelect(structure.pdb_id, structure.source);
                      }}
                    >
                      <div className="flex items-center gap-2 flex-1 overflow-hidden">
                        {/* PDB ID */}
                        <span className={`font-mono font-semibold whitespace-nowrap ${isCommon ? 'text-green-700' : 'text-gray-900 group-hover:text-blue-600'} transition-colors`}>
                          {structure.pdb_id}
                        </span>

                        {/* Common Badge */}
                        {isCommon && (
                          <Badge variant="success" className="text-xs">
                            {language === 'zh' ? '共有' : 'Common'}
                          </Badge>
                        )}

                        {/* Source Badge */}
                        <Badge
                          variant={structure.source === 'alphafold' ? 'secondary' : 'primary'}
                          className="text-xs"
                        >
                          {structure.source === 'alphafold' ? 'AF' : 'PDB'}
                        </Badge>

                      {/* Experimental Method */}
                      {structure.source !== 'alphafold' && (
                        (() => {
                          const method = structure.experimental_method || structure.basic_info?.experimental_method;
                          if (!method) return null;
                          return (
                            <span className="text-xs text-gray-500 whitespace-nowrap">
                              {method}
                            </span>
                          );
                        })()
                      )}

                      {/* Resolution */}
                      {structure.source !== 'alphafold' ? (
                        (() => {
                          const res = structure.resolution ?? structure.basic_info?.resolution;
                          if (res != null && res > 0) {
                            return (
                              <span className="text-xs text-blue-600 font-medium whitespace-nowrap">
                                {res.toFixed(2)} Å
                              </span>
                            );
                          }
                          return null;
                        })()
                      ) : (
                        <span className="text-xs text-gray-400 italic whitespace-nowrap">
                          {language === 'zh' ? '预测' : 'Predicted'}
                        </span>
                      )}

                      {/* Entity count */}
                      {(() => {
                        const entityList = structure.entity_list || structure.basic_info?.entity_list;
                        if (entityList && entityList.length > 0) {
                          return (
                            <span className="text-xs text-gray-400 whitespace-nowrap">
                              · {entityList.length} {language === 'zh' ? '实体' : 'entities'}
                            </span>
                          );
                        }
                        return null;
                      })()}
                    </div>

                    <div className="flex items-center gap-2">
                      {/* External link */}
                      <a
                        href={structure.source === 'alphafold'
                          ? `https://alphafold.ebi.ac.uk/entry/${structure.pdb_id}`
                          : `https://www.rcsb.org/structure/${structure.pdb_id}`
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-blue-500"
                        onClick={(e) => e.stopPropagation()}
                      >
                        ↗
                      </a>
                    </div>
                  </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* No structures */}
          {(!pdbData.structures || pdbData.structures.length === 0) && (
            <div className="p-4 text-center py-6 text-gray-500 text-sm bg-gray-50">
              <Database className="w-8 h-8 mx-auto mb-2 text-gray-300" />
              <p>{language === 'zh' ? '暂无结构数据' : 'No structure data'}</p>
            </div>
          )}

          {/* BLAST Search Results */}
          {blastResults && blastResults.results && blastResults.results.length > 0 && (
            <div className="p-4 border-t border-gray-100">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-blue-500" />
                  <span className="text-sm font-medium text-gray-700">
                    {language === 'zh' ? 'BLAST 相似蛋白搜索' : 'BLAST Similar Protein Search'}
                  </span>
                  <Badge variant="secondary" className="text-xs">
                    {blastResults.results.length} {language === 'zh' ? '个结果' : 'results'}
                  </Badge>
                </div>
              </div>
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {blastResults.results.map((result) => (
                  <div
                    key={result.pdb_id}
                    className="bg-white rounded-lg p-2 border border-gray-100 hover:border-blue-200 hover:bg-blue-50 transition-colors cursor-pointer"
                    onClick={() => onBlastPdbSelect?.(result.pdb_id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <span className="font-mono font-semibold text-gray-900 whitespace-nowrap">
                          {result.pdb_id}
                        </span>
                        <Badge variant="outline" className="text-xs whitespace-nowrap">
                          {result.identity?.toFixed(1) || 'N/A'}% {language === 'zh' ? '一致' : 'identity'}
                        </Badge>
                        <span className="text-xs text-gray-500 whitespace-nowrap">
                          E-value: {typeof result.evalue === 'number' && !isNaN(result.evalue) ? result.evalue.toExponential(2) : (result.evalue ?? 'N/A')}
                        </span>
                        {result.score && (
                          <span className="text-xs text-gray-500 whitespace-nowrap">
                            Score: {result.score.toFixed(0)}
                          </span>
                        )}
                      </div>
                      <a
                        href={`https://www.rcsb.org/structure/${result.pdb_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-blue-500"
                        onClick={(e) => e.stopPropagation()}
                      >
                        ↗
                      </a>
                    </div>
                    <p className="text-xs text-gray-600 mt-1 truncate">
                      {result.title?.split('>')[0] || 'N/A'}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
