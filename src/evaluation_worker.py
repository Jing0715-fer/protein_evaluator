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
            max_pdb = self.config.get('max_pdb', 100)
            if len(pdb_ids) > max_pdb:
                pdb_ids = pdb_ids[:max_pdb]

            self._log(evaluation_id, f"[步骤2/6] 开始获取PDB数据, 共 {len(pdb_ids)} 个结构...")
            pdb_data = self._fetch_pdb(pdb_ids, evaluation_id)

            if progress_callback:
                progress_callback(50)

            # Step 3: Calculate coverage
            protein_length = uniprot_data.get('sequence_length', 0) if uniprot_data else 0
            if pdb_data and protein_length > 0:
                coverage = self.coverage_calculator.calculate_coverage(
                    pdb_data, protein_length, uniprot_id
                )
                pdb_data['coverage'] = coverage
                coverage_pct = coverage.get('coverage_percent', 0)
                self._log(evaluation_id, f"PDB序列覆盖度: {coverage_pct:.1f}%")

            # Step 4: Run BLAST search if needed
            pdb_count = len(pdb_data.get('structures', []))
            need_blast = coverage.get('coverage_percent', 0) < 50 or pdb_count < 5 if pdb_data else True

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

            # Step 6: Run AI analysis
            self._log(evaluation_id, "[步骤5/6] 开始AI深度分析...")
            ai_analysis = self._run_ai_analysis(uniprot_data, pdb_data, blast_results, evaluation_id)

            if ai_analysis.get('error'):
                self._log(evaluation_id, f"AI分析警告: {ai_analysis['error']}", level='warning')
            else:
                self._log(evaluation_id, "AI分析完成")

            if progress_callback:
                progress_callback(90)

            # Step 7: Generate report
            self._log(evaluation_id, "[步骤6/6] 生成评估报告...")
            report = self.report_generator.generate_evaluation_report(
                uniprot_data, pdb_data, blast_results, ai_analysis
            )

            results.update({
                'success': True,
                'uniprot_data': uniprot_data,
                'pdb_data': pdb_data,
                'blast_results': blast_results,
                'ai_analysis': ai_analysis,
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
        return self.pdb_client.get_structures_batch(pdb_ids)

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
        evaluation_id: int = None
    ) -> Dict[str, Any]:
        """Run AI analysis."""
        try:
            ai_wrapper = get_ai_client_wrapper(self.config)

            if not ai_wrapper.is_available():
                return {'error': 'AI client not available'}

            prompt = ai_wrapper.build_analysis_prompt(uniprot_data, pdb_data, blast_results)

            return ai_wrapper.analyze(
                prompt,
                system_message="你是一个专业的蛋白质结构生物学家。请对给定的蛋白质进行综合分析。"
            )

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {'error': str(e)}

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
