"""
Batch processing module for protein evaluation.
Handles batch evaluation workflows.
"""

import logging
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

import config
from src.database_service import (
    create_batch_evaluation,
    update_batch_evaluation,
    add_batch_log,
    DatabaseService
)
from src.report_generator import ReportGenerator
from src.evaluation_worker import EvaluationWorker

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Processor for batch protein evaluations."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize batch processor.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.db_service = DatabaseService()
        self.report_generator = ReportGenerator(self.config)
        self.evaluation_worker = EvaluationWorker(self.config)

    def process_batch(
        self,
        batch_id: int,
        uniprot_ids: List[str],
        config: Dict[str, Any] = None
    ) -> None:
        """
        Process a batch evaluation.

        Args:
            batch_id: Batch evaluation ID
            uniprot_ids: List of UniProt IDs
            config: Configuration dictionary
        """
        if config is None:
            config = {}

        try:
            logger.info(f"Starting batch evaluation: ID={batch_id}, proteins={len(uniprot_ids)}")
            add_batch_log(batch_id, f"开始批量评估: {len(uniprot_ids)} 个蛋白")

            # Update status
            update_batch_evaluation(batch_id, {
                'status': 'processing',
                'progress': 10
            })

            # Step 1: Get individual evaluations
            individual_reports = {}
            successful_evaluations = []
            failed_evaluations = []

            for idx, uniprot_id in enumerate(uniprot_ids):
                progress = 10 + int((idx / len(uniprot_ids)) * 40)
                update_batch_evaluation(batch_id, {'progress': progress})

                add_batch_log(batch_id, f"[{idx + 1}/{len(uniprot_ids)}] 评估 {uniprot_id}...")

                # 实际调用单个评估
                try:
                    # 创建单个评估记录
                    from src.database_service import create_protein_evaluation
                    evaluation = create_protein_evaluation(uniprot_id=uniprot_id)
                    
                    if evaluation:
                        # 运行评估
                        results = self.evaluation_worker.evaluate(
                            evaluation.id, 
                            uniprot_id,
                            progress_callback=None
                        )
                        
                        if results.get('success'):
                            report = results.get('report', '')
                            individual_reports[uniprot_id] = report
                            successful_evaluations.append(uniprot_id)
                            add_batch_log(batch_id, f"✅ {uniprot_id} 评估完成")
                        else:
                            error = results.get('error', '未知错误')
                            individual_reports[uniprot_id] = f"评估失败: {error}"
                            failed_evaluations.append(uniprot_id)
                            add_batch_log(batch_id, f"❌ {uniprot_id} 评估失败: {error}", level='error')
                    else:
                        individual_reports[uniprot_id] = "创建评估记录失败"
                        failed_evaluations.append(uniprot_id)
                        add_batch_log(batch_id, f"❌ {uniprot_id} 创建记录失败", level='error')
                        
                except Exception as e:
                    logger.error(f"评估 {uniprot_id} 失败: {e}")
                    individual_reports[uniprot_id] = f"评估异常: {str(e)}"
                    failed_evaluations.append(uniprot_id)
                    add_batch_log(batch_id, f"❌ {uniprot_id} 异常: {e}", level='error')

            update_batch_evaluation(batch_id, {'progress': 50})

            # Step 2: Fetch interaction data
            add_batch_log(batch_id, "获取蛋白质相互作用数据...")
            interaction_data = self._fetch_interactions(uniprot_ids)

            update_batch_evaluation(batch_id, {'progress': 60})

            # Step 3: Run batch AI analysis
            add_batch_log(batch_id, "运行批量AI分析...")
            batch_analysis = self._run_batch_analysis(
                successful_evaluations,
                interaction_data,
                individual_reports
            )

            update_batch_evaluation(batch_id, {'progress': 80})

            # Step 4: Generate batch report
            add_batch_log(batch_id, "生成批量报告...")
            batch_report = self.report_generator.generate_batch_report(
                successful_evaluations,
                interaction_data,
                individual_reports,
                batch_analysis
            )

            # Save report
            update_batch_evaluation(batch_id, {
                'report': batch_report,
                'status': 'completed',
                'progress': 100,
                'completed_at': datetime.now()
            })

            add_batch_log(batch_id, "批量评估完成")
            logger.info(f"Batch evaluation completed: ID={batch_id}")

        except Exception as e:
            logger.error(f"Batch evaluation failed: ID={batch_id}, error={e}")
            add_batch_log(batch_id, f"批量评估失败: {e}", level='error')
            update_batch_evaluation(batch_id, {
                'status': 'failed',
                'error': str(e)
            })

    def _fetch_interactions(self, uniprot_ids: List[str]) -> Dict[str, Any]:
        """Fetch protein interactions."""
        from src.interaction_service import fetch_protein_interactions
        return fetch_protein_interactions(uniprot_ids)

    def _run_batch_analysis(
        self,
        uniprot_ids: List[str],
        interaction_data: Dict,
        individual_reports: Dict[str, str]
    ) -> Dict[str, Any]:
        """Run AI analysis for batch."""
        # This would call the AI client wrapper
        # For now, return placeholder
        return {
            'analysis': f"Batch analysis for {len(uniprot_ids)} proteins",
            'model': self.config.get('ai_model', 'default')
        }


def process_batch_evaluation(
    batch_id: int,
    uniprot_ids: List[str],
    config: Dict[str, Any] = None
) -> None:
    """
    Convenience function to process batch evaluation.

    Args:
        batch_id: Batch evaluation ID
        uniprot_ids: List of UniProt IDs
        config: Configuration dictionary
    """
    processor = BatchProcessor(config)
    processor.process_batch(batch_id, uniprot_ids, config)
