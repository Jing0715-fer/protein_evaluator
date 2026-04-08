"""
service.py - 蛋白质评估服务 (Refactored)
主要入口文件，使用模块化组件处理蛋白质评估流程。
"""

import os
import sys
import logging
import threading
import traceback
from typing import Dict, List, Optional, Any
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from src.database_service import (
    DatabaseService,
    create_protein_evaluation,
    get_protein_evaluation,
    get_protein_evaluation_by_uniprot,
    get_all_protein_evaluations,
    update_protein_evaluation,
    delete_protein_evaluation,
    search_protein_evaluations,
    create_batch_evaluation,
    get_batch_evaluation,
    get_all_batch_evaluations,
    update_batch_evaluation,
    delete_batch_evaluation,
)
from src.evaluation_worker import EvaluationWorker
from src.batch_processor import BatchProcessor
from src.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

# Evaluation steps definition
EVALUATION_STEPS = {
    'pending': {'progress': 0, 'message': '等待开始'},
    'fetching_pdb': {'progress': 10, 'message': '获取PDB数据'},
    'fetching_uniprot': {'progress': 30, 'message': '获取UniProt数据'},
    'blasting': {'progress': 50, 'message': '执行BLAST搜索'},
    'analyzing': {'progress': 70, 'message': 'AI分析中'},
    'generating_report': {'progress': 90, 'message': '生成报告'},
    'completed': {'progress': 100, 'message': '评估完成'},
    'failed': {'progress': 0, 'message': '评估失败'}
}


class ProteinEvaluationService:
    """蛋白质评估服务 - 主入口类"""

    def __init__(self):
        self.config = {
            'max_pdb': None,  # No limit - fetch all available PDBs
            'max_literature': 20,
            'ai_temperature': 0.3,
            'ai_max_tokens': 6000,
            'ai_prompt': ''
        }
        self.db_service = DatabaseService()
        self.evaluation_worker = EvaluationWorker(self.config)
        self.batch_processor = BatchProcessor(self.config)
        self.report_generator = ReportGenerator(self.config)

    def start_evaluation(
        self,
        uniprot_id: str,
        gene_name: str = None,
        protein_name: str = None,
        config: Dict = None
    ) -> Dict[str, Any]:
        """
        开始蛋白质评估（异步执行）

        Args:
            uniprot_id: UniProt蛋白质ID
            gene_name: 基因名称（可选）
            protein_name: 蛋白质名称（可选）
            config: 配置选项（可选）

        Returns:
            评估任务信息
        """
        # Update config
        if config:
            self.config.update(config)
            self.evaluation_worker = EvaluationWorker(self.config)

        try:
            # Create evaluation record
            evaluation = create_protein_evaluation(
                uniprot_id=uniprot_id,
                gene_name=gene_name,
                protein_name=protein_name
            )

            if not evaluation:
                return {'success': False, 'error': '创建评估记录失败'}

            # Start background thread
            thread = threading.Thread(
                target=self._run_evaluation_task,
                args=(evaluation.id, uniprot_id)
            )
            thread.daemon = True
            thread.start()

            return {
                'success': True,
                'evaluation_id': evaluation.id,
                'uniprot_id': uniprot_id,
                'message': '评估任务已启动'
            }

        except Exception as e:
            logger.error(f"启动评估失败: {e}")
            return {'success': False, 'error': str(e)}

    def _run_evaluation_task(self, evaluation_id: int, uniprot_id: str):
        """在后台线程中执行评估任务"""
        try:
            logger.info(f"========== 开始评估任务 [ID={evaluation_id}, UniProt={uniprot_id}] ==========")

            # Update status to processing
            update_protein_evaluation(evaluation_id, {
                'evaluation_status': 'processing',
                'current_step': 'fetching_pdb',
                'progress': 10
            })

            # Run evaluation using worker
            def progress_callback(progress):
                update_protein_evaluation(evaluation_id, {'progress': progress})

            results = self.evaluation_worker.evaluate(
                evaluation_id, uniprot_id, progress_callback
            )

            if results.get('success'):
                # Update with results
                update_protein_evaluation(evaluation_id, {
                    'evaluation_status': 'completed',
                    'current_step': 'completed',
                    'progress': 100,
                    'completed_at': datetime.now(),
                    'uniprot_data': results.get('uniprot_data'),
                    'pdb_data': results.get('pdb_data'),
                    'blast_results': results.get('blast_results'),
                    'ai_analysis': results.get('ai_analysis'),
                    'report': results.get('report')
                })
                logger.info(f"评估任务完成 [ID={evaluation_id}]")
            else:
                # Mark as failed
                update_protein_evaluation(evaluation_id, {
                    'evaluation_status': 'failed',
                    'current_step': 'failed',
                    'error': results.get('error', 'Unknown error')
                })
                logger.error(f"评估任务失败 [ID={evaluation_id}]: {results.get('error')}")

        except Exception as e:
            tb = traceback.format_exc()
            logger.exception("评估任务异常 [ID=%s]: %s", evaluation_id, e)
            try:
                update_protein_evaluation(evaluation_id, {
                    'evaluation_status': 'failed',
                    'current_step': 'failed',
                    'error': tb
                })
            except Exception:
                logger.error("评估任务异常 [ID=%s]: also failed to update DB: %s", evaluation_id, traceback.format_exc())

    def get_evaluation_status(self, evaluation_id: int) -> Dict[str, Any]:
        """获取评估状态"""
        evaluation = get_protein_evaluation(evaluation_id)
        if not evaluation:
            return {'success': False, 'error': '评估记录不存在'}

        return {
            'success': True,
            'evaluation': evaluation.to_dict()
        }

    def get_evaluation_latest_log(self, evaluation_id: int) -> Dict[str, Any]:
        """获取评估的最新一条日志（用于实时显示进度）"""
        evaluation = get_protein_evaluation(evaluation_id)
        if not evaluation:
            return {'success': False, 'error': '评估记录不存在'}

        logs = evaluation.logs or []
        latest_log = logs[-1] if logs else None

        return {
            'success': True,
            'evaluation_id': evaluation_id,
            'status': evaluation.evaluation_status,
            'progress': evaluation.progress,
            'current_step': evaluation.current_step,
            'latest_log': latest_log
        }

    def get_evaluation_detail(self, evaluation_id: int) -> Dict[str, Any]:
        """获取评估详情"""
        evaluation = get_protein_evaluation(evaluation_id)
        if not evaluation:
            return None
        return evaluation.to_dict()

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """列出所有评估"""
        evaluations = get_all_protein_evaluations(limit, offset)
        return {
            'success': True,
            'evaluations': [e.to_dict() for e in evaluations],
            'total': len(evaluations)
        }

    def delete_evaluation(self, evaluation_id: int) -> Dict[str, Any]:
        """删除评估"""
        success = delete_protein_evaluation(evaluation_id)
        return {'success': success}

    def batch_delete_evaluations(self, evaluation_ids: List[int]) -> Dict[str, Any]:
        """批量删除评估"""
        deleted_count = 0
        failed_ids = []
        for eval_id in evaluation_ids:
            success = delete_protein_evaluation(eval_id)
            if success:
                deleted_count += 1
            else:
                failed_ids.append(eval_id)

        return {
            'success': True,
            'deleted': deleted_count,
            'failed': failed_ids,
            'total': len(evaluation_ids)
        }

    def search_evaluations(self, query: str) -> Dict[str, Any]:
        """搜索评估"""
        evaluations = search_protein_evaluations(query)
        return {
            'success': True,
            'evaluations': [e.to_dict() for e in evaluations]
        }

    # ========== Batch Evaluation Methods ==========

    def start_batch_evaluation(
        self,
        uniprot_ids: List[str],
        name: str = None,
        config: Dict = None
    ) -> Dict[str, Any]:
        """
        开始批量蛋白质评估

        Args:
            uniprot_ids: UniProt蛋白质ID列表
            name: 批量评估名称（可选）
            config: 配置选项（可选）

        Returns:
            批量评估任务信息
        """
        # Parse and validate UniProt IDs
        parsed_ids = []
        for uniprot_id in uniprot_ids:
            clean_id = uniprot_id.strip().upper()
            if clean_id and clean_id not in parsed_ids:
                parsed_ids.append(clean_id)

        if not parsed_ids:
            return {'success': False, 'error': '请提供有效的UniProt ID列表'}

        if len(parsed_ids) < 2:
            return {'success': False, 'error': '批量评估至少需要2个UniProt ID'}

        try:
            # Create batch evaluation record
            batch_name = name or f"批量评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            batch = create_batch_evaluation(
                name=batch_name,
                uniprot_ids=parsed_ids,
                config=config or {}
            )

            if not batch:
                return {'success': False, 'error': '创建批量评估记录失败'}

            # Start background thread
            thread = threading.Thread(
                target=self._run_batch_evaluation_task,
                args=(batch.id, parsed_ids)
            )
            thread.daemon = True
            thread.start()

            return {
                'success': True,
                'batch_id': batch.id,
                'uniprot_ids': parsed_ids,
                'name': batch_name,
                'message': '批量评估任务已启动'
            }

        except Exception as e:
            logger.error(f"启动批量评估失败: {e}")
            return {'success': False, 'error': str(e)}

    def _run_batch_evaluation_task(self, batch_id: int, uniprot_ids: List[str]):
        """在后台线程中执行批量评估任务"""
        self.batch_processor.process_batch(batch_id, uniprot_ids, self.config)

    def get_batch_evaluation_status(self, batch_id: int) -> Dict[str, Any]:
        """获取批量评估状态"""
        batch = get_batch_evaluation(batch_id)
        if not batch:
            return {'success': False, 'error': '批量评估记录不存在'}

        return {
            'success': True,
            'batch': batch.to_dict()
        }

    def list_batch_evaluations(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """列出所有批量评估"""
        batches = get_all_batch_evaluations(limit, offset)
        return {
            'success': True,
            'batches': [b.to_dict() for b in batches],
            'total': len(batches)
        }


    def stop_batch_evaluation(self, batch_id: int) -> Dict[str, Any]:
        """
        停止批量评估
        
        Args:
            batch_id: 批量评估 ID
        
        Returns:
            操作结果
        """
        try:
            # Update batch status to stopped
            from src.database_service import update_batch_evaluation
            update_batch_evaluation(batch_id, {
                'status': 'stopped',
                'progress': 0
            })
            return {'success': True, 'message': '批量评估已停止'}
        except Exception as e:
            logger.error(f"停止批量评估失败：{e}")
            return {'success': False, 'error': str(e)}
    def delete_batch_evaluation(self, batch_id: int) -> Dict[str, Any]:
        """删除批量评估"""
        success = delete_batch_evaluation(batch_id)
        return {'success': success}

    def run_evaluation_sync(
        self,
        uniprot_id: str,
        gene_name: str = None,
        protein_name: str = None,
        config: Dict = None
    ) -> Dict[str, Any]:
        """
        同步运行蛋白质评估（阻塞调用）

        Args:
            uniprot_id: UniProt蛋白质ID
            gene_name: 基因名称（可选）
            protein_name: 蛋白质名称（可选）
            config: 配置选项（可选）

        Returns:
            评估结果
        """
        if config:
            self.config.update(config)
            self.evaluation_worker = EvaluationWorker(self.config)

        try:
            # Create evaluation record
            evaluation = create_protein_evaluation(
                uniprot_id=uniprot_id,
                gene_name=gene_name,
                protein_name=protein_name
            )

            if not evaluation:
                return {'success': False, 'error': '创建评估记录失败'}

            # Run evaluation synchronously
            results = self.evaluation_worker.evaluate(evaluation.id, uniprot_id)

            if results.get('success'):
                # Update record with results
                update_protein_evaluation(evaluation.id, {
                    'evaluation_status': 'completed',
                    'current_step': 'completed',
                    'progress': 100,
                    'completed_at': datetime.now(),
                    'uniprot_data': results.get('uniprot_data'),
                    'pdb_data': results.get('pdb_data'),
                    'blast_results': results.get('blast_results'),
                    'ai_analysis': results.get('ai_analysis'),
                    'report': results.get('report')
                })

            return {
                'success': results.get('success', False),
                'evaluation_id': evaluation.id,
                'results': results
            }

        except Exception as e:
            logger.error(f"同步评估失败: {e}")
            return {'success': False, 'error': str(e)}


# Singleton instance
_evaluation_service: Optional[ProteinEvaluationService] = None


def get_evaluation_service() -> ProteinEvaluationService:
    """Get singleton evaluation service instance."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = ProteinEvaluationService()
    return _evaluation_service
