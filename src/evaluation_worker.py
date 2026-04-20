"""
Evaluation worker module for single protein evaluation.
Handles the core evaluation workflow for a single protein.
"""

import logging
from typing import Dict, Any, Optional

import config
from src.api_clients import UniProtClient, PDBClient, BLASTClient, PubMedClient
from src.coverage_calculator import CoverageCalculator
from src.report_generator import ReportGenerator
from src.ai_client_wrapper import get_ai_client_wrapper
from src.database_service import add_log

logger = logging.getLogger(__name__)


class EvaluationWorker:
    """Worker for single protein evaluation."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize evaluation worker.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.uniprot_client = UniProtClient()
        self.pdb_client = PDBClient()
        self.blast_client = BLASTClient()
        self.pubmed_client = PubMedClient()
        self.coverage_calculator = CoverageCalculator()
        self.report_generator = ReportGenerator(self.config)

    def evaluate(
        self,
        evaluation_id: int,
        uniprot_id: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Execute full evaluation workflow for a protein.

        Args:
            evaluation_id: Evaluation ID for logging
            uniprot_id: UniProt ID
            progress_callback: Optional callback for progress updates

        Returns:
            Evaluation results dictionary
        """
        results = {
            'uniprot_id': uniprot_id,
            'evaluation_id': evaluation_id,
            'success': False
        }

        try:
            # Step 1: Fetch UniProt data
            self._log(evaluation_id, f"[步骤1/6] 开始获取UniProt元数据...")
            uniprot_data = self._fetch_uniprot(uniprot_id)
            if uniprot_data:
                self._log(evaluation_id, f"UniProt元数据获取成功: {uniprot_data.get('protein_name', 'N/A')[:50]}")
            else:
                self._log(evaluation_id, "警告: 未能获取UniProt数据", level='warning')

            if progress_callback:
                progress_callback(30)

            # Step 2: Fetch PDB data
            pdb_ids = uniprot_data.get('pdb_ids', []) if uniprot_data else []
            max_pdb = self.config.get('max_pdb', None)  # None means no limit
            if max_pdb is not None and len(pdb_ids) > max_pdb:
                pdb_ids = pdb_ids[:max_pdb]

            self._log(evaluation_id, f"[步骤2/6] 开始获取PDB数据, 共 {len(pdb_ids)} 个结构...")
            pdb_data = self._fetch_pdb(pdb_ids, evaluation_id)

            if progress_callback:
                progress_callback(50)

            # Step 3: Calculate coverage
            protein_length = uniprot_data.get('sequence_length', 0) if uniprot_data else 0
            coverage = None  # 初始化 coverage 变量
            if pdb_data and protein_length > 0:
                coverage = self.coverage_calculator.calculate_coverage(
                    pdb_data, protein_length, uniprot_id
                )
                pdb_data['coverage'] = coverage
                coverage_pct = coverage.get('coverage_percent', 0)
                self._log(evaluation_id, f"PDB序列覆盖度: {coverage_pct:.1f}%")

            # Step 4: Run BLAST search if needed
            pdb_count = len(pdb_data.get('structures', [])) if pdb_data else 0
            if coverage:
                need_blast = coverage.get('coverage_percent', 0) < 50 or pdb_count < 5
            else:
                need_blast = True

            blast_results = {}
            if need_blast:
                self._log(evaluation_id, f"[步骤3/6] 开始执行BLAST同源蛋白搜索...")
                sequence = uniprot_data.get('sequence', '') if uniprot_data else ''
                blast_results = self._run_blast(uniprot_id, sequence, evaluation_id)
            else:
                self._log(evaluation_id, "[步骤3/6] 跳过BLAST搜索 (覆盖度充足)")

            if progress_callback:
                progress_callback(70)

            # Step 5: Fetch PubMed abstracts
            self._log(evaluation_id, "[步骤4/6] 获取PubMed文献摘要...")
            pdb_data = self._fetch_pubmed_abstracts(pdb_data)

            if progress_callback:
                progress_callback(80)

            # Step 6: Run AI analysis (both Chinese and English)
            self._log(evaluation_id, "[步骤5/6] 开始AI深度分析...")
            custom_template = self.config.get('custom_template')
            ai_analysis_zh, ai_analysis_en = self._run_bilingual_ai_analysis(
                uniprot_data, pdb_data, blast_results, evaluation_id,
                custom_template=custom_template
            )

            if progress_callback:
                progress_callback(90)

            # Step 7: Generate report
            self._log(evaluation_id, "[步骤6/6] 生成评估报告...")
            report = self.report_generator.generate_evaluation_report(
                uniprot_data, pdb_data, blast_results, ai_analysis_zh
            )

            results.update({
                'success': True,
                'uniprot_data': uniprot_data,
                'pdb_data': pdb_data,
                'blast_results': blast_results,
                'ai_analysis': ai_analysis_zh,
                'ai_analysis_en': ai_analysis_en,
                'report': report
            })

            self._log(evaluation_id, "评估完成")

        except Exception as e:
            logger.error(f"Evaluation failed for {uniprot_id}: {e}")
            self._log(evaluation_id, f"评估失败: {e}", level='error')
            results['error'] = str(e)

        return results

    def _fetch_uniprot(self, uniprot_id: str) -> Optional[Dict[str, Any]]:
        """Fetch UniProt data."""
        return self.uniprot_client.get_protein(uniprot_id)

    def _fetch_pdb(self, pdb_ids: list, evaluation_id: int = None) -> Dict[str, Any]:
        """Fetch PDB data."""
        max_pdb = self.config.get('max_pdb', None)  # None means no limit
        return self.pdb_client.get_structures_batch(pdb_ids, max_structures=max_pdb, evaluation_id=evaluation_id)

    def _run_blast(
        self,
        uniprot_id: str,
        sequence: str,
        evaluation_id: int = None
    ) -> Dict[str, Any]:
        """Run BLAST search."""
        try:
            return self.blast_client.search(uniprot_id, sequence, evaluation_id)
        except Exception as e:
            logger.warning(f"BLAST search failed: {e}")
            return {'query_id': uniprot_id, 'results': [], 'method': 'failed', 'pdb_data': None}

    def _fetch_pubmed_abstracts(self, pdb_data: Dict) -> Dict:
        """Fetch PubMed abstracts for citations."""
        try:
            return self.pubmed_client.fetch_abstracts_for_structures(pdb_data)
        except Exception as e:
            logger.warning(f"Failed to fetch PubMed abstracts: {e}")
            return pdb_data

    def _run_ai_analysis(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        evaluation_id: int = None,
        language: str = 'zh',
        custom_template: str = None
    ) -> Dict[str, Any]:
        """Run AI analysis in specified language using two-stage generation."""
        try:
            ai_wrapper = get_ai_client_wrapper(self.config)

            if not ai_wrapper.is_available():
                return {'error': 'AI client not available'}

            # Use two-stage analysis (Stage 1: statistical summary, Stage 2: full report)
            result = ai_wrapper.analyze_two_stage(
                uniprot_data=uniprot_data,
                pdb_data=pdb_data,
                blast_results=blast_results,
                custom_template=custom_template,
                language=language,
                config=self.config
            )

            return result

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {'error': str(e)}

    def _run_bilingual_ai_analysis(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        evaluation_id: int = None,
        custom_template: str = None
    ) -> tuple:
        """Run AI analysis in both Chinese and English."""
        # Pre-build prompts for debugging (even if AI fails)
        ai_wrapper = get_ai_client_wrapper(self.config)
        prompt_zh = None
        prompt_en = None

        # Run Chinese analysis
        if evaluation_id:
            self._log(evaluation_id, "[步骤5/6] → 开始中文AI分析...")
            self._log(evaluation_id, "[步骤5/6]   [Stage 1/2] 生成统计摘要...")
        ai_analysis_zh = self._run_ai_analysis(
            uniprot_data, pdb_data, blast_results, evaluation_id, language='zh',
            custom_template=custom_template
        )
        if evaluation_id:
            if ai_analysis_zh.get('error'):
                self._log(evaluation_id, f"[步骤5/6]   AI分析失败: {ai_analysis_zh.get('error')}", level='warning')
                self._log(evaluation_id, "[步骤5/6]   使用备用分析数据继续...", level='warning')
                # 尝试获取失败时的prompt用于调试
                prompt_zh = ai_analysis_zh.get('prompt')
                # 生成备用分析，传入prompt用于调试
                ai_analysis_zh = self._generate_fallback_analysis(uniprot_data, pdb_data, blast_results, 'zh', prompt_zh)
            else:
                self._log(evaluation_id, "[步骤5/6]   [Stage 2/2] 生成最终报告...")
                prompt_zh = ai_analysis_zh.get('prompt')

        # Run English analysis
        if evaluation_id:
            self._log(evaluation_id, "[步骤5/6] → 开始英文AI分析...")
            self._log(evaluation_id, "[步骤5/6]   [Stage 1/2] 生成统计摘要...")
        ai_analysis_en = self._run_ai_analysis(
            uniprot_data, pdb_data, blast_results, evaluation_id, language='en',
            custom_template=custom_template
        )
        if evaluation_id:
            if ai_analysis_en.get('error'):
                self._log(evaluation_id, f"[步骤5/6]   AI分析失败: {ai_analysis_en.get('error')}", level='warning')
                self._log(evaluation_id, "[步骤5/6]   使用备用分析数据继续...", level='warning')
                # 尝试获取失败时的prompt用于调试
                prompt_en = ai_analysis_en.get('prompt')
                # 生成备用分析，传入prompt用于调试
                ai_analysis_en = self._generate_fallback_analysis(uniprot_data, pdb_data, blast_results, 'en', prompt_en)
            else:
                self._log(evaluation_id, "[步骤5/6]   [Stage 2/2] 生成最终报告...")
                prompt_en = ai_analysis_en.get('prompt')

        return ai_analysis_zh, ai_analysis_en

    def _generate_fallback_analysis(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        language: str = 'zh',
        prompt: str = None  # Add prompt parameter for debugging
    ) -> Dict[str, Any]:
        """Generate fallback analysis when AI service is unavailable."""
        from datetime import datetime

        protein_name = uniprot_data.get('protein_name', 'Unknown') if uniprot_data else 'Unknown'
        uniprot_id = uniprot_data.get('uniprot_id', 'N/A') if uniprot_data else 'N/A'
        structures = pdb_data.get('structures', []) if pdb_data else []
        structure_count = len(structures)

        if language == 'zh':
            analysis = f"""## 蛋白质结构评估报告（备用）

**注意**: 由于AI服务暂时不可用，此报告为自动生成的备用版本。

### 蛋白质信息
- **UniProt ID**: {uniprot_id}
- **蛋白质名称**: {protein_name}
- **数据来源**: UniProt, PDB

### 结构数据概览
- **PDB结构数量**: {structure_count}个

### 数据可用性说明
本评估基于以下数据源：
1. **UniProt数据库**: 蛋白质序列和注释信息
2. **PDB数据库**: {structure_count}个实验结构
3. **文献数据**: 相关研究文献

### 评估状态
- **评估时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **评估状态**: 数据收集完成，AI分析不可用

### 建议
请稍后重新运行评估以获取AI生成的深度分析报告。"""
        else:
            analysis = f"""## Protein Structure Evaluation Report (Fallback)

**Note**: This is a fallback report generated automatically due to temporary AI service unavailability.

### Protein Information
- **UniProt ID**: {uniprot_id}
- **Protein Name**: {protein_name}
- **Data Sources**: UniProt, PDB

### Structure Data Overview
- **PDB Structure Count**: {structure_count}

### Data Availability
This evaluation is based on the following data sources:
1. **UniProt Database**: Protein sequence and annotation information
2. **PDB Database**: {structure_count} experimental structures
3. **Literature Data**: Related research publications

### Evaluation Status
- **Evaluation Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Evaluation Status**: Data collection completed, AI analysis unavailable

### Recommendations
Please re-run the evaluation later to obtain the AI-generated in-depth analysis report."""

        return {
            'analysis': analysis,
            'quality_score': 0,
            'success': True,
            'fallback': True,
            'prompt': prompt  # Include prompt for debugging
        }

    def _log(self, evaluation_id: int, message: str, level: str = 'info'):
        """Add log to evaluation."""
        add_log(evaluation_id, message, level)


def run_evaluation(
    evaluation_id: int,
    uniprot_id: str,
    config: Dict[str, Any] = None,
    progress_callback: callable = None
) -> Dict[str, Any]:
    """
    Convenience function to run evaluation.

    Args:
        evaluation_id: Evaluation ID
        uniprot_id: UniProt ID
        config: Configuration dictionary
        progress_callback: Progress callback function

    Returns:
        Evaluation results
    """
    worker = EvaluationWorker(config)
    return worker.evaluate(evaluation_id, uniprot_id, progress_callback)
