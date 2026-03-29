"""
多靶点报告服务

提供报告生成的高级接口，集成数据库查询和报告生成逻辑。
"""

import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.multi_target_report_generator import MultiTargetReportGenerator
from src.database import get_session, MultiTargetJob, Target, TargetRelationship
from src.target_interaction_analyzer import TargetInteractionAnalyzer

logger = logging.getLogger(__name__)


class MultiTargetReportService:
    """多靶点报告服务
    
    封装报告生成的业务逻辑，提供简洁的接口供 API 层调用。
    """
    
    def __init__(self, output_dir: str = 'reports'):
        """
        初始化报告服务
        
        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir
        self.generator = MultiTargetReportGenerator(config={'output_dir': output_dir})
        self.analyzer = TargetInteractionAnalyzer()
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_report(
        self,
        job_id: int,
        template: str = 'full',
        format_type: str = 'markdown',
        include_interactions: bool = True
    ) -> Dict[str, Any]:
        """
        为指定任务生成报告
        
        Args:
            job_id: 多靶点任务ID
            template: 报告模板 (full/summary/detailed/minimal)
            format_type: 导出格式 (markdown/json/excel)
            include_interactions: 是否包含相互作用分析
            
        Returns:
            Dict: 包含报告元数据和下载信息的字典
        """
        session = get_session()
        try:
            # 获取任务数据
            job = self._get_job_data(session, job_id)
            if not job:
                raise ValueError(f'任务 {job_id} 不存在')
            
            # 获取靶点数据
            targets_data = self._get_targets_data(session, job_id)
            if not targets_data:
                raise ValueError(f'任务 {job_id} 没有靶点数据')
            
            # 获取相互作用数据
            interactions_data = None
            if include_interactions:
                interactions_data = self._get_interactions_data(session, job_id)
            
            # 生成报告
            report_result = self.generator.generate_multi_target_report(
                job_data=job,
                targets_data=targets_data,
                interactions_data=interactions_data,
                template=template,
                format=format_type
            )
            
            # 导出报告
            output_path = self._export_report(report_result, format_type)
            
            # 构建结果
            file_size = os.path.getsize(output_path)
            filename = os.path.basename(output_path)
            
            return {
                'success': True,
                'report_id': report_result['metadata']['report_id'],
                'job_id': job_id,
                'format': format_type,
                'template': template,
                'download_url': f'/api/evaluation/reports/{filename}',
                'file_path': output_path,
                'file_size': file_size,
                'statistics': report_result['statistics'],
                'created_at': datetime.now().isoformat()
            }
            
        finally:
            session.close()
    
    def generate_preview(
        self,
        job_id: int,
        template: str = 'summary',
        max_targets: int = 5
    ) -> Dict[str, Any]:
        """
        生成报告预览
        
        Args:
            job_id: 多靶点任务ID
            template: 报告模板
            max_targets: 预览的最大靶点数
            
        Returns:
            Dict: 包含预览内容的字典
        """
        session = get_session()
        try:
            job = self._get_job_data(session, job_id)
            if not job:
                raise ValueError(f'任务 {job_id} 不存在')
            
            # 只获取部分靶点用于预览
            targets = session.query(Target).filter_by(job_id=job_id).limit(max_targets).all()
            targets_data = [self._target_to_dict(t, session) for t in targets]
            
            # 生成预览报告
            report_result = self.generator.generate_multi_target_report(
                job_data=job,
                targets_data=targets_data,
                template=template,
                format='markdown'
            )
            
            content = report_result['content']
            preview_content = content[:2000] + '...' if len(content) > 2000 else content
            
            return {
                'success': True,
                'job_id': job_id,
                'preview_content': preview_content,
                'total_targets': job.get('target_count', 0),
                'preview_targets': len(targets_data),
                'template': template
            }
            
        finally:
            session.close()
    
    def _get_job_data(self, session, job_id: int) -> Optional[Dict[str, Any]]:
        """获取任务数据"""
        job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
        if not job:
            return None
        
        return {
            'job_id': job.job_id,
            'name': job.name,
            'description': job.description,
            'status': job.status,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'target_count': job.target_count,
            'evaluation_mode': job.evaluation_mode,
            'priority': job.priority,
            'tags': job.tags
        }
    
    def _get_targets_data(self, session, job_id: int) -> List[Dict[str, Any]]:
        """获取所有靶点数据"""
        targets = session.query(Target).filter_by(job_id=job_id).all()
        return [self._target_to_dict(t, session) for t in targets]
    
    def _target_to_dict(self, target: Target, session) -> Dict[str, Any]:
        """将 Target 对象转换为字典"""
        target_dict = target.to_dict()

        # 添加评估数据
        if target.evaluation:
            eval_obj = target.evaluation
            # 构建完整的 evaluation 字典
            evaluation_data = {
                'id': eval_obj.id,
                'quality_score': getattr(eval_obj, 'overall_score', None),
                'summary': getattr(eval_obj, 'summary', None),
                'ai_analysis': eval_obj.ai_analysis if eval_obj.ai_analysis else {},
                'pdb_data': eval_obj.pdb_data if eval_obj.pdb_data else {},
                'uniprot_data': eval_obj.uniprot_data if eval_obj.uniprot_data else {},
                'logs': eval_obj.logs if eval_obj.logs else [],
            }

            # 从 ai_analysis 中提取 quality_score（如果 available）
            if eval_obj.ai_analysis and isinstance(eval_obj.ai_analysis, dict):
                ai_quality_score = eval_obj.ai_analysis.get('quality_score')
                if ai_quality_score is not None:
                    evaluation_data['quality_score'] = ai_quality_score

                # 提取 PDB 结构信息
                pdb_structures = []
                pdb_count = 0
                if eval_obj.pdb_data and isinstance(eval_obj.pdb_data, dict):
                    pdb_ids = eval_obj.pdb_data.get('pdb_ids', [])
                    if pdb_ids:
                        pdb_structures = pdb_ids[:10]  # 限制前10个
                        pdb_count = len(pdb_ids)

                evaluation_data['pdb_structures'] = pdb_structures
                evaluation_data['pdb_count'] = pdb_count

                # 从 ai_analysis 提取更多信息
                ai_analysis = eval_obj.ai_analysis
                evaluation_data['quality_assessment'] = ai_analysis.get('quality_assessment', {})
                evaluation_data['functional_sites'] = ai_analysis.get('functional_sites', [])
                evaluation_data['drug_target_potential'] = ai_analysis.get('drug_target_potential', {})
                evaluation_data['analysis_summary'] = ai_analysis.get('summary', '')

            target_dict['evaluation'] = evaluation_data
            target_dict['evaluation_score'] = evaluation_data.get('quality_score')

        return target_dict
    
    def _get_interactions_data(self, session, job_id: int) -> Optional[Dict[str, Any]]:
        """获取相互作用数据"""
        relationships = session.query(TargetRelationship).filter_by(job_id=job_id).all()
        
        if not relationships:
            return None
        
        interactions = []
        for rel in relationships:
            source_target = session.get(Target, rel.source_target_id)
            target_target = session.get(Target, rel.target_target_id)
            
            interactions.append({
                'source_target_id': rel.source_target_id,
                'target_target_id': rel.target_target_id,
                'source_uniprot': source_target.uniprot_id if source_target else None,
                'target_uniprot': target_target.uniprot_id if target_target else None,
                'relationship_type': rel.relationship_type,
                'score': rel.score,
                'metadata': rel.relationship_metadata
            })
        
        # 构建聚类信息
        targets_data = self._get_targets_data(session, job_id)
        clusters = self.analyzer.cluster_targets_by_similarity(targets_data, relationships)
        
        return {
            'interactions': interactions,
            'clusters': clusters,
            'total_interactions': len(interactions),
            'total_clusters': len(clusters)
        }
    
    def _export_report(self, report_result: Dict[str, Any], format_type: str) -> str:
        """导出报告到文件"""
        if format_type == 'json':
            return self.generator.export_to_json(report_result)
        elif format_type == 'excel':
            return self.generator.export_to_excel(report_result)
        else:
            return self.generator.export_to_markdown(report_result)
    
    def list_reports(self, job_id: int) -> List[Dict[str, Any]]:
        """
        列出任务的所有报告
        
        Args:
            job_id: 多靶点任务ID
            
        Returns:
            List: 报告信息列表
        """
        import glob
        
        if not os.path.exists(self.output_dir):
            return []
        
        # 查找与该任务相关的报告文件
        # 文件名格式: batch_report_YYYYMMDD_HHMMSS_<job_id>.<ext>
        pattern = os.path.join(self.output_dir, f'*_{job_id}.*')
        report_files = glob.glob(pattern)
        
        reports = []
        for filepath in sorted(report_files, key=os.path.getmtime, reverse=True):
            filename = os.path.basename(filepath)
            stat = os.stat(filepath)
            
            # 从扩展名判断格式
            ext = filename.split('.')[-1].lower()
            format_map = {
                'md': 'markdown',
                'json': 'json',
                'xlsx': 'excel',
                'zip': 'zip'
            }
            format_type = format_map.get(ext, 'unknown')
            
            reports.append({
                'filename': filename,
                'job_id': job_id,
                'format': format_type,
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'download_url': f'/api/evaluation/reports/{filename}'
            })
        
        return reports
    
    def delete_report(self, filename: str) -> bool:
        """
        删除报告文件
        
        Args:
            filename: 报告文件名
            
        Returns:
            bool: 是否成功删除
        """
        # 安全检查
        if '..' in filename or filename.startswith('/'):
            logger.warning(f'非法文件名: {filename}')
            return False
        
        filepath = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(filepath):
            return False
        
        try:
            os.remove(filepath)
            logger.info(f'已删除报告: {filename}')
            return True
        except Exception as e:
            logger.error(f'删除报告失败: {e}')
            return False


# 单例模式
_report_service = None


def get_report_service(output_dir: str = 'reports') -> MultiTargetReportService:
    """
    获取报告服务单例
    
    Args:
        output_dir: 报告输出目录
        
    Returns:
        MultiTargetReportService: 报告服务实例
    """
    global _report_service
    if _report_service is None:
        _report_service = MultiTargetReportService(output_dir)
    return _report_service


def reset_report_service():
    """重置报告服务（主要用于测试）"""
    global _report_service
    _report_service = None
