import React, { useState } from 'react';
import { X, ExternalLink, Loader2, Ruler, Beaker, Calendar, Users, FileText } from 'lucide-react';
import { Badge } from './Badge';
import { Protein3DViewer } from './Protein3DViewer';
import { useLanguage } from '../contexts/LanguageContext';
import type { PdbStructure } from '../types';

interface PdbDetailPanelProps {
  structure: PdbStructure;
  onClose: () => void;
}

type TabId = 'details' | 'entities' | '3d';

export const PdbDetailPanel: React.FC<PdbDetailPanelProps> = ({ structure, onClose }) => {
  const { language } = useLanguage();
  const [activeTab, setActiveTab] = useState<TabId>('details');

  const tabs: { id: TabId; label: string }[] = [
    { id: 'details', label: language === 'zh' ? '详情' : 'Details' },
    { id: 'entities', label: language === 'zh' ? '实体' : 'Entities' },
    { id: '3d', label: language === 'zh' ? '3D视图' : '3D View' },
  ];

  // RCSB preview image URL - uses CDN images from og:image meta tag
  // AlphaFold doesn't provide direct preview images, so only show for PDB source
  const previewImageUrl = structure.source !== 'alphafold'
    ? `https://cdn.rcsb.org/images/structures/${structure.pdb_id.toLowerCase()}_assembly-1.jpeg`
    : null;

  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between p-5 border-b border-gray-200 bg-gradient-to-r from-blue-50 via-white to-blue-50">
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <div className="p-2.5 bg-blue-100 rounded-xl">
            <Beaker className="w-6 h-6 text-blue-600" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3">
              <span className="font-mono font-bold text-xl text-gray-900">{structure.pdb_id}</span>
              <Badge variant={structure.source === 'alphafold' ? 'secondary' : 'primary'} className="text-xs">
                {structure.source === 'alphafold' ? 'AlphaFold' : 'PDB'}
              </Badge>
            </div>
            {structure.resolution !== undefined && structure.resolution !== null && (
              <div className="flex items-center gap-1.5 mt-1 text-sm text-gray-500">
                <Ruler className="w-3.5 h-3.5" />
                <span>{language === 'zh' ? '分辨率' : 'Resolution'}: {structure.resolution > 0 ? `${structure.resolution.toFixed(2)} Å` : (language === 'zh' ? '计算预测' : 'Computational')}</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={structure.source === 'alphafold'
              ? `https://alphafold.ebi.ac.uk/entry/${structure.pdb_id}`
              : `https://www.rcsb.org/structure/${structure.pdb_id}`
            }
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
            {language === 'zh' ? '访问官网' : 'View Website'}
          </a>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400 hover:text-gray-600" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 bg-gray-50/50">
        <div className="flex px-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-3.5 text-sm font-medium transition-all relative ${
                activeTab === tab.id
                  ? 'text-blue-600'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100/50'
              }`}
            >
              {tab.label}
              {activeTab === tab.id && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {activeTab === 'details' && (
          <div className="space-y-4">
            {/* Support both new format (top-level) and legacy format (nested in basic_info) */}
            {(() => {
              const title = structure.title || structure.basic_info?.title || '';
              const resolution = structure.resolution ?? structure.basic_info?.resolution ?? null;
              const experimentalMethod = structure.experimental_method || structure.basic_info?.experimental_method || '';
              const depositionDate = structure.deposition_date || structure.basic_info?.deposition_date || '';
              const authors = structure.authors || structure.basic_info?.authors || [];
              
              return (
                <>
                  {/* Preview Image - displayed at top of details content */}
                  {previewImageUrl && (
                    <div className="flex justify-center p-2 bg-white rounded-lg border border-gray-100">
                      <img
                        src={previewImageUrl}
                        alt={`${structure.pdb_id} preview`}
                        className="max-h-80 object-contain"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                        }}
                      />
                    </div>
                  )}

                  {title ? (
                    <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
                        <FileText className="w-4 h-4" />
                        {language === 'zh' ? '标题' : 'Title'}
                      </div>
                      <p className="text-gray-900 text-sm leading-relaxed">{title}</p>
                    </div>
                  ) : (
                    <div className="text-center py-4 text-gray-400 text-sm">
                      <p>{language === 'zh' ? '暂无标题信息' : 'No title available'}</p>
                    </div>
                  )}

                  {depositionDate ? (
                    <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-1">
                        <Calendar className="w-4 h-4" />
                        {language === 'zh' ? '沉积日期' : 'Deposition Date'}
                      </div>
                      <p className="text-gray-900 text-sm">{depositionDate}</p>
                    </div>
                  ) : null}

                  {authors && authors.length > 0 ? (
                    <div className="bg-gradient-to-r from-gray-50 to-white p-3 rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2 text-sm font-medium text-gray-500 mb-2">
                        <Users className="w-4 h-4" />
                        {language === 'zh' ? '作者' : 'Authors'}
                      </div>
                      <p className="text-gray-900 text-sm leading-relaxed">{authors.join(', ')}</p>
                    </div>
                  ) : null}

                  {experimentalMethod || resolution !== null ? (
                    <div className="bg-gradient-to-r from-blue-50 to-white p-3 rounded-lg border border-blue-100">
                      <div className="flex items-center gap-2 text-sm font-medium text-blue-600 mb-2">
                        <Beaker className="w-4 h-4" />
                        {language === 'zh' ? '实验方法 / 分辨率' : 'Method / Resolution'}
                      </div>
                      <p className="text-gray-900 text-sm">
                        {experimentalMethod && <span className="mr-2">{experimentalMethod}</span>}
                        {resolution !== null && resolution !== undefined && (
                          <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${
                            resolution > 0 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                          }`}>
                            {resolution > 0 ? `${resolution.toFixed(2)} Å` : (language === 'zh' ? '计算预测' : 'Computational')}
                          </span>
                        )}
                      </p>
                    </div>
                  ) : null}
                </>
              );
            })()}

            {/* Citations */}
            {structure.citations && structure.citations.length > 0 && (
              <div>
                <span className="text-sm font-medium text-gray-500">{language === 'zh' ? '引用' : 'Citations'}</span>
                <div className="mt-2 space-y-2">
                  {structure.citations.slice(0, 3).map((cite, idx) => (
                    <div key={idx} className="text-sm text-gray-700">
                      <p className="font-medium">{cite.title || 'Unknown Title'}</p>
                      <p className="text-gray-500 text-xs">
                        {cite.journal && `${cite.journal}`}
                        {cite.year && ` (${cite.year})`}
                        {cite.pubmed_id && ` - PMID: ${cite.pubmed_id}`}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Show placeholder if no details */}
            {!structure.title && !structure.deposition_date &&
             (!structure.authors || structure.authors.length === 0) &&
             structure.resolution === undefined && (!structure.citations || structure.citations.length === 0) && (
              <div className="text-center py-8 text-gray-500">
                <p className="text-sm">{language === 'zh' ? '暂无详细信息' : 'No detailed information'}</p>
                <p className="text-xs text-gray-400 mt-1">
                  PDB ID: {structure.pdb_id} - {language === 'zh' ? '请访问 RCSB 获取完整信息' : 'Please visit RCSB for complete information'}
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'entities' && (
          <div>
            {/* Support both new format (entity_list) and legacy format */}
            {(() => {
              const entities = structure.entity_list || structure.basic_info?.entity_list || [];
              if (entities.length === 0) {
                return (
                  <div className="text-center py-8 text-gray-500">
                    <div className="mb-2">
                      <Loader2 className="w-8 h-8 mx-auto text-gray-300" />
                    </div>
                    <p className="text-sm">{language === 'zh' ? '暂无实体数据' : 'No entity data'}</p>
                    <p className="text-xs text-gray-400 mt-1">{language === 'zh' ? '结构实体信息不可用' : 'Structure entity information not available'}</p>
                  </div>
                );
              }

              return (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 px-3 font-medium text-gray-600">{language === 'zh' ? '链' : 'Chain'}</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">{language === 'zh' ? '分子名称' : 'Molecule Name'}</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">{language === 'zh' ? '类型' : 'Type'}</th>
                        <th className="text-left py-2 px-3 font-medium text-gray-600">{language === 'zh' ? '序列预览' : 'Sequence Preview'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entities.map((entity: any, idx: number) => (
                        <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                          <td className="py-2 px-3 font-mono text-gray-900">{entity.chain || entity.chains?.[0] || 'N/A'}</td>
                          <td className="py-2 px-3 text-gray-700">{entity.description || entity.name || entity.molecule_name || '-'}</td>
                          <td className="py-2 px-3 text-gray-700">{entity.polymer_type || entity.molecule_type || 'N/A'}</td>
                          <td className="py-2 px-3 font-mono text-xs text-gray-500 max-w-xs truncate">
                            {entity.sequence && entity.sequence.length > 0
                              ? `${entity.sequence.substring(0, 60)}${entity.sequence.length > 60 ? '...' : ''}`
                              : entity.length ? `${language === 'zh' ? '长度' : 'Length'}: ${entity.length}` : 'N/A'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </div>
        )}

        {activeTab === '3d' && (
          <div className="h-[450px]">
            <Protein3DViewer pdbId={structure.pdb_id} source={structure.source} />
          </div>
        )}
      </div>
    </div>
  );
};
