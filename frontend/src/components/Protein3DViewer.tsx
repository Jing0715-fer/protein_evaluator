import React, { useEffect, useRef, useState } from 'react';
import { Loader2, AlertCircle } from 'lucide-react';
import { useLanguage } from '../contexts/LanguageContext';

interface Protein3DViewerProps {
  pdbId: string;
  source: 'pdb' | 'alphafold';
}

// @ts-ignore
import * as $3Dmol from '3dmol';

export const Protein3DViewer: React.FC<Protein3DViewerProps> = ({
  pdbId,
  source,
}) => {
  const { language } = useLanguage();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const colorMode = 'chain';

  useEffect(() => {
    if (!containerRef.current || !pdbId) return;

    const initViewer = async () => {
      try {
        setLoading(true);
        setError(null);

        // Clear container
        containerRef.current!.innerHTML = '';

        // Create viewer element
        const viewerElement = document.createElement('div');
        viewerElement.style.width = '100%';
        viewerElement.style.height = '100%';
        containerRef.current!.appendChild(viewerElement);

        // Initialize 3Dmol viewer
        viewerRef.current = $3Dmol.createViewer(viewerElement, {
          backgroundColor: 'white',
        });

        if (!viewerRef.current) {
          throw new Error('Failed to initialize 3D viewer');
        }

        // Get PDB data URL
        let pdbUrl: string;
        if (source === 'alphafold') {
          pdbUrl = `https://alphafold.ebi.ac.uk/files/AF-${pdbId}-F1-model_v4.pdb`;
        } else {
          // Standard PDB structures
          pdbUrl = `https://files.rcsb.org/download/${pdbId}.pdb`;
        }

        // Fetch PDB data
        const response = await fetch(pdbUrl);
        if (!response.ok) {
          throw new Error(`Failed to fetch structure: ${response.statusText}`);
        }

        const pdbData = await response.text();

        // Load the structure with selected coloring
        viewerRef.current.addModel(pdbData, 'pdb');
        viewerRef.current.setStyle({}, { cartoon: { colorscheme: colorMode } });

        // Zoom to fit
        viewerRef.current.zoomTo();

        // Render
        viewerRef.current.render();

        setLoading(false);
      } catch (err: any) {
        console.error('Error loading 3D structure:', err);
        setError(err.message || 'Failed to load 3D structure');
        setLoading(false);
      }
    };

    initViewer();

    // Cleanup
    return () => {
      if (viewerRef.current) {
        viewerRef.current = null;
      }
    };
  }, [pdbId, source, colorMode]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => {
      if (viewerRef.current) {
        viewerRef.current.resize();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  if (error) {
    return (
      <div className="w-full h-full min-h-[450px] bg-gray-50 rounded-lg flex flex-col items-center justify-center p-6">
        <AlertCircle className="w-12 h-12 text-amber-500 mb-3" />
        <p className="text-gray-700 font-medium mb-2">
          {language === 'zh' ? '无法加载 3D 结构' : 'Failed to load 3D structure'}
        </p>
        <p className="text-gray-500 text-sm text-center mb-4">{error}</p>
        <a
          href={source === 'alphafold'
            ? `https://alphafold.ebi.ac.uk/entry/${pdbId}`
            : `https://www.rcsb.org/structure/${pdbId}`
          }
          target="_blank"
          rel="noopener noreferrer"
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
        >
          {language === 'zh' ? '在官网查看' : 'View on website'}
        </a>
      </div>
    );
  }

  return (
    <div className="w-full h-full min-h-[450px] bg-white rounded-lg overflow-hidden border border-gray-200 relative">
      {loading && (
        <div className="absolute inset-0 bg-white z-10 flex flex-col items-center justify-center">
          <Loader2 className="w-10 h-10 text-blue-600 animate-spin mb-3" />
          <p className="text-gray-600 text-sm">{language === 'zh' ? '正在加载 3D 结构...' : 'Loading 3D structure...'}</p>
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" />
      {!loading && (
        <div className="absolute bottom-3 left-3 right-3 bg-white/90 backdrop-blur-sm rounded-lg p-2 text-xs text-gray-500 flex items-center justify-between border border-gray-200">
          <span>{language === 'zh' ? '💡 拖拽旋转 • 滚轮缩放 • 右键平移' : '💡 Drag to rotate • Scroll to zoom • Right-click to pan'}</span>
          <span className="font-mono text-blue-600">{pdbId}</span>
        </div>
      )}
    </div>
  );
};
