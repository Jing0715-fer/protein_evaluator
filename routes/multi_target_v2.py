"""
多靶点评估 API 路由 (v2 API)

提供多靶点评估相关的 REST API 端点，支持：
- 多靶点任务 CRUD 操作
- 任务进度和状态查询
- 任务控制（暂停、恢复、取消）
- 向后兼容 v1 API

API 版本: v2
基础路径: /api/v2/evaluate/multi
"""

import logging
from flask import Blueprint, jsonify, request, Response
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from src.multi_target_scheduler import MultiTargetScheduler, EvaluationMode
from src.api_clients import UniProtClient, PDBClient
from src.multi_target_models import MultiTargetJob, Target, TargetRelationship
from src.database import get_session, get_prompt_template
from src.report_service import get_report_service
from src.ai_client_wrapper import get_ai_client_wrapper
from core.uniprot_client import UniProtAPIClient

logger = logging.getLogger(__name__)

# 创建蓝图 - v2 API
bp = Blueprint('multi_target_v2', __name__, url_prefix='/api/v2/evaluate/multi')

# 全局调度器实例
_scheduler = None


def get_scheduler() -> MultiTargetScheduler:
    """获取调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = MultiTargetScheduler()
    return _scheduler


# ========== 多靶点任务管理 API ==========

@bp.route('', methods=['POST'])
def create_multi_target_job():
    """
    创建多靶点评估任务
    
    Request Body:
        - name: 任务名称（可选）
        - description: 任务描述（可选）
        - uniprot_ids: UniProt ID 列表（必需）
        - evaluation_mode: 评估模式（parallel/sequential，默认 parallel）
        - priority: 优先级 1-10（默认 5）
        - tags: 标签字典（可选）
        - config: 配置参数（可选）
    
    Returns:
        - job_id: 任务ID
        - name: 任务名称
        - status: 任务状态
        - target_count: 靶点数量
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400
        
        # 验证必需参数
        uniprot_ids = data.get('uniprot_ids', [])
        if not uniprot_ids:
            # 尝试从文本解析
            uniprot_input = data.get('uniprot_ids_text', '')
            if uniprot_input:
                import re
                uniprot_ids = re.split(r'[,;\s\n]+', uniprot_input)
                uniprot_ids = [uid.strip().upper() for uid in uniprot_ids if uid.strip()]
        
        if not uniprot_ids or len(uniprot_ids) < 1:
            return jsonify({
                'success': False, 
                'error': '请提供至少1个UniProt ID'
            }), 400
        
        if len(uniprot_ids) > 50:
            return jsonify({
                'success': False,
                'error': f'最多支持50个靶点，当前{len(uniprot_ids)}个'
            }), 400
        
        # 获取其他参数
        name = data.get('name', f"批量评估任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        description = data.get('description', '')
        
        # 评估模式
        mode_str = data.get('evaluation_mode', 'parallel')
        try:
            evaluation_mode = EvaluationMode(mode_str)
        except ValueError:
            return jsonify({
                'success': False,
                'error': f'无效的评估模式: {mode_str}。有效选项: parallel, sequential'
            }), 400
        
        # 优先级
        priority = data.get('priority', 5)
        if not isinstance(priority, int) or priority < 1 or priority > 10:
            return jsonify({
                'success': False,
                'error': '优先级必须是1-10之间的整数'
            }), 400
        
        # 标签和配置
        tags = data.get('tags', {})
        config = data.get('config', {})
        
        # 创建任务 - 直接使用数据库模型
        from src.database import get_session, MultiTargetJob, Target
        
        with get_session() as session:
            # 创建任务
            job = MultiTargetJob(
                name=name,
                description=description,
                target_count=len(uniprot_ids),
                evaluation_mode=mode_str,
                priority=priority,
                config=config,
                tags=tags,
                status='pending'
            )
            session.add(job)
            session.flush()
            job_id = job.job_id
            
            # 创建靶点记录，同时获取 UniProt 信息
            uniprot_client = UniProtClient()
            for idx, uniprot_id in enumerate(uniprot_ids):
                # 尝试获取 UniProt 信息
                protein_name = None
                gene_name = None
                try:
                    protein_info = uniprot_client.get_protein(uniprot_id)
                    if protein_info:
                        protein_name = protein_info.get('protein_name')
                        gene_name = protein_info.get('gene_names', [None])[0] if protein_info.get('gene_names') else None
                except Exception as e:
                    logger.warning(f"Failed to fetch UniProt info for {uniprot_id}: {e}")
                
                target = Target(
                    job_id=job_id,
                    target_index=idx,
                    uniprot_id=uniprot_id,
                    protein_name=protein_name,
                    gene_name=gene_name,
                    status='pending'
                )
                session.add(target)
            
            session.commit()
            
            # 获取完整的 job 对象（已提交到数据库）
            job_data = {
                'job_id': job_id,
                'name': name,
                'status': 'pending',
                'target_count': len(uniprot_ids),
                'evaluation_mode': mode_str,
                'priority': priority,
            }
        
        logger.info(f"创建多靶点任务: job_id={job_data['job_id']}, name={name}, targets={len(uniprot_ids)}")
        
        # 自动启动任务
        try:
            scheduler = get_scheduler()
            if scheduler.start_job(job_id):
                logger.info(f"任务已自动启动: job_id={job_id}")
                job_data['status'] = 'processing'
            else:
                logger.warning(f"任务自动启动失败: job_id={job_id}")
        except Exception as e:
            logger.error(f"自动启动任务异常: {e}")
            # 不影响创建成功，可以手动启动
        
        return jsonify({
            'success': True,
            'job_id': job_data['job_id'],
            'name': job_data['name'],
            'status': job_data['status'],
            'target_count': job_data['target_count'],
            'evaluation_mode': job_data['evaluation_mode'],
            'priority': job_data['priority'],
            'message': f'成功创建任务，包含 {len(uniprot_ids)} 个靶点'
        }), 201
        
    except Exception as e:
        logger.error(f"创建多靶点任务失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('', methods=['GET'])
def list_multi_target_jobs():
    """
    获取多靶点任务列表
    
    Query Parameters:
        - status: 状态过滤（pending/processing/completed/failed/paused）
        - limit: 返回数量限制（默认50，最大100）
        - offset: 偏移量（默认0）
        - sort_by: 排序字段（created_at/priority/status）
        - sort_order: 排序方向（asc/desc，默认desc）
    
    Returns:
        - jobs: 任务列表
        - total: 总数
        - offset: 当前偏移量
        - limit: 当前限制
    """
    try:
        # 解析查询参数
        status_filter = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # 验证排序字段
        valid_sort_fields = ['created_at', 'updated_at', 'priority', 'status', 'job_id']
        if sort_by not in valid_sort_fields:
            return jsonify({
                'success': False,
                'error': f'无效的排序字段。有效选项: {valid_sort_fields}'
            }), 400
        
        # 查询数据库
        session = get_session()
        try:
            query = session.query(MultiTargetJob)
            
            # 应用状态过滤
            if status_filter:
                query = query.filter(MultiTargetJob.status == status_filter)
            
            # 应用排序
            sort_column = getattr(MultiTargetJob, sort_by)
            if sort_order == 'desc':
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())
            
            # 获取总数
            total = query.count()
            
            # 应用分页
            jobs = query.offset(offset).limit(limit).all()
            
            # 构建响应
            jobs_data = []
            for job in jobs:
                job_dict = job.to_dict()
                # 添加进度信息
                job_dict['progress'] = {
                    'completed': job.get_completed_count(),
                    'total': job.target_count,
                    'percentage': job.get_progress_percentage()
                }
                jobs_data.append(job_dict)
            
            return jsonify({
                'success': True,
                'jobs': jobs_data,
                'total': total,
                'offset': offset,
                'limit': limit
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>', methods=['GET'])
def get_multi_target_job(job_id: int):
    """
    获取多靶点任务详情

    Query Parameters:
        - lang: 语言选择 ('zh' for Chinese, 'en' for English)
        - force_refresh: 是否强制刷新 AI 分析 ('true' to force regeneration)

    Returns:
        - job: 任务详细信息
        - targets: 靶点列表
        - progress: 进度信息
        - statistics: 统计信息
    """
    try:
        # Get language preference from query param
        lang = request.args.get('lang', 'zh')
        if lang not in ('zh', 'en'):
            lang = 'zh'

        # Check if we should force refresh AI analysis
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'

        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404

            # Check if job is completed and we have targets with interactions
            targets = session.query(Target).options(joinedload(Target.evaluation)).filter_by(job_id=job_id).order_by(Target.target_index).all()

            # Regenerate AI interaction analysis if job is completed and force_refresh or AI not available in cache
            if job.status == 'completed' and targets:
                relationships = session.query(TargetRelationship).filter_by(job_id=job_id).all()
                if relationships and (force_refresh or not job.interaction_ai_analysis or not job.interaction_ai_analysis_en):
                    _ensure_interaction_analysis(job, targets, relationships, session)

            # 获取任务详情
            job_data = job.to_dict()

            # 获取靶点列表

            # Build targets data with evaluation details
            targets_data = []
            for target in targets:
                target_dict = target.to_dict()

                # Add evaluation details with language-aware ai_analysis
                if target.evaluation:
                    eval_dict = {
                        'id': target.evaluation.id,
                        'overall_score': getattr(target.evaluation, 'overall_score', None),
                        'status': target.evaluation.evaluation_status
                    }
                    if target.evaluation.pdb_data:
                        eval_dict['pdb_data'] = target.evaluation.pdb_data
                    # Return analysis based on language
                    if lang == 'en' and target.evaluation.ai_analysis_en:
                        eval_dict['ai_analysis'] = target.evaluation.ai_analysis_en
                    elif target.evaluation.ai_analysis:
                        eval_dict['ai_analysis'] = target.evaluation.ai_analysis
                    # Always include both versions for frontend flexibility
                    eval_dict['ai_analysis_zh'] = target.evaluation.ai_analysis
                    eval_dict['ai_analysis_en'] = target.evaluation.ai_analysis_en
                    # Include AI prompt for debugging
                    eval_dict['ai_prompt'] = getattr(target.evaluation, 'ai_prompt', None)
                    target_dict['evaluation'] = eval_dict

                targets_data.append(target_dict)

            # 计算统计信息
            completed = sum(1 for t in targets if t.status == 'completed')
            failed = sum(1 for t in targets if t.status == 'failed')
            processing = sum(1 for t in targets if t.status == 'processing')
            pending = sum(1 for t in targets if t.status == 'pending')

            statistics = {
                'total': len(targets),
                'completed': completed,
                'failed': failed,
                'processing': processing,
                'pending': pending,
                'success_rate': (completed / len(targets) * 100) if targets else 0
            }

            # 进度信息
            progress = {
                'completed': completed,
                'total': len(targets),
                'percentage': job.get_progress_percentage()
            }

            return jsonify({
                'success': True,
                'job': job_data,
                'targets': targets_data,
                'progress': progress,
                'statistics': statistics,
                'lang': lang
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"获取任务详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>', methods=['PUT'])
def update_multi_target_job(job_id: int):
    """
    更新多靶点任务

    Request Body:
        - name: 任务名称
        - description: 任务描述
        - priority: 优先级 (1-10)
        - evaluation_mode: 评估模式 ('parallel' 或 'sequential')
        - tags: 标签

    Note:
        - 只能更新 pending 或 paused 状态的任务
        - 不能修改靶点列表
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404

            # 检查状态
            if job.status not in ['pending', 'paused']:
                return jsonify({
                    'success': False,
                    'error': f'任务状态为 {job.status}，无法更新。只能更新 pending 或 paused 状态的任务'
                }), 400

            # 更新字段
            updates = {}
            if 'name' in data:
                updates['name'] = data['name']
            if 'description' in data:
                updates['description'] = data['description']
            if 'priority' in data:
                priority = data['priority']
                if not isinstance(priority, int) or priority < 1 or priority > 10:
                    return jsonify({
                        'success': False,
                        'error': '优先级必须是1-10之间的整数'
                    }), 400
                updates['priority'] = priority
            if 'evaluation_mode' in data:
                mode = data['evaluation_mode']
                if mode not in ['parallel', 'sequential']:
                    return jsonify({
                        'success': False,
                        'error': '评估模式必须是 parallel 或 sequential'
                    }), 400
                updates['evaluation_mode'] = mode
            if 'tags' in data:
                updates['tags'] = data['tags']

            if not updates:
                return jsonify({
                    'success': False,
                    'error': '没有要更新的字段'
                }), 400

            # 应用更新
            for key, value in updates.items():
                setattr(job, key, value)

            session.commit()
            
            logger.info(f"更新任务 {job_id}: {updates}")
            
            return jsonify({
                'success': True,
                'job': job.to_dict(),
                'message': '任务已更新'
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"更新任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>', methods=['DELETE'])
def delete_multi_target_job(job_id: int):
    """
    删除多靶点任务
    
    Note:
        - 会同时删除关联的靶点和关系数据
        - 无法删除 processing 状态的任务
    """
    try:
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404
            
            # 检查状态
            if job.status == 'processing':
                return jsonify({
                    'success': False,
                    'error': '无法删除正在执行中的任务，请先停止任务'
                }), 400
            
            # 删除任务（级联删除靶点和关系）
            session.delete(job)
            session.commit()
            
            logger.info(f"删除任务 {job_id}")
            
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已删除'
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 任务进度和控制 API ==========

@bp.route('/<int:job_id>/progress', methods=['GET'])
def get_job_progress(job_id: int):
    """
    获取任务进度
    
    Returns:
        - job_id: 任务ID
        - status: 任务状态
        - progress: 进度百分比
        - completed: 已完成数量
        - total: 总数量
        - targets_status: 各靶点状态
        - estimated_remaining: 预估剩余时间（秒，如果有）
    """
    try:
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404
            
            # 获取靶点状态
            targets = session.query(Target).filter_by(job_id=job_id).order_by(Target.target_index).all()
            
            targets_status = []
            for target in targets:
                target_info = {
                    'target_id': target.target_id,
                    'uniprot_id': target.uniprot_id,
                    'status': target.status,
                    'target_index': target.target_index
                }
                if target.started_at:
                    target_info['started_at'] = target.started_at.isoformat()
                if target.completed_at:
                    target_info['completed_at'] = target.completed_at.isoformat()
                targets_status.append(target_info)
            
            # 计算进度
            completed = sum(1 for t in targets if t.status == 'completed')
            total = len(targets)
            percentage = int((completed / total * 100) if total > 0 else 0)
            
            # 预估剩余时间（简化计算）
            estimated_remaining = None
            if job.started_at and completed > 0 and job.status == 'processing':
                elapsed = (datetime.now() - job.started_at).total_seconds()
                avg_time_per_target = elapsed / completed
                remaining_targets = total - completed
                estimated_remaining = int(avg_time_per_target * remaining_targets)
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'status': job.status,
                'progress': {
                    'percentage': percentage,
                    'completed': completed,
                    'total': total,
                    'failed': sum(1 for t in targets if t.status == 'failed')
                },
                'targets_status': targets_status,
                'estimated_remaining_seconds': estimated_remaining
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"获取任务进度失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/progress/stream', methods=['GET'])
def stream_job_progress(job_id: int):
    """
    SSE endpoint for real-time job progress updates.

    Uses Server-Sent Events to push progress updates to the frontend,
    replacing the previous 2-second polling approach.

    Returns:
        Server-Sent Events stream with job progress data
    """
    def generate():
        session = get_session()
        try:
            last_progress = None
            check_count = 0

            while True:
                job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                targets = session.query(Target).filter_by(job_id=job_id).order_by(Target.target_index).all()

                completed = sum(1 for t in targets if t.status == 'completed')
                total = len(targets)
                percentage = int((completed / total * 100) if total > 0 else 0)

                progress_data = {
                    'success': True,
                    'job_id': job_id,
                    'status': job.status,
                    'progress': {
                        'percentage': percentage,
                        'completed': completed,
                        'total': total,
                        'failed': sum(1 for t in targets if t.status == 'failed')
                    }
                }

                # Only send if progress changed
                if progress_data != last_progress:
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    last_progress = progress_data.copy()

                # Send heartbeat every 10 seconds to keep connection alive
                check_count += 1
                if check_count % 20 == 0:  # Every 10 seconds
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

                # Stop when job is complete or failed
                if job.status in ('completed', 'failed', 'cancelled'):
                    yield f"data: {json.dumps({**progress_data, 'done': True})}\n\n"
                    break

                time.sleep(0.5)  # Check every 500ms

        finally:
            session.close()

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*'
        }
    )


@bp.route('/<int:job_id>/start', methods=['POST'])
def start_job(job_id: int):
    """
    开始执行任务
    
    Note:
        - 只能启动 pending 或 paused 状态的任务
    """
    try:
        scheduler = get_scheduler()
        success = scheduler.start_job(job_id)
        
        if success:
            logger.info(f"启动任务 {job_id}")
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已开始执行',
                'job_id': job_id
            })
        else:
            return jsonify({
                'success': False,
                'error': '启动任务失败，任务可能不存在或状态不正确'
            }), 400
            
    except Exception as e:
        logger.error(f"启动任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/pause', methods=['POST'])
def pause_job(job_id: int):
    """
    暂停任务
    
    Note:
        - 只能暂停 processing 状态的任务
    """
    try:
        scheduler = get_scheduler()
        success = scheduler.pause_job(job_id)
        
        if success:
            logger.info(f"暂停任务 {job_id}")
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已暂停',
                'job_id': job_id
            })
        else:
            return jsonify({
                'success': False,
                'error': '暂停任务失败，任务可能不存在或状态不正确'
            }), 400
            
    except Exception as e:
        logger.error(f"暂停任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/resume', methods=['POST'])
def resume_job(job_id: int):
    """
    恢复任务
    
    Note:
        - 只能恢复 paused 状态的任务
    """
    try:
        scheduler = get_scheduler()
        success = scheduler.resume_job(job_id)
        
        if success:
            logger.info(f"恢复任务 {job_id}")
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已恢复',
                'job_id': job_id
            })
        else:
            return jsonify({
                'success': False,
                'error': '恢复任务失败，任务可能不存在或状态不正确'
            }), 400
            
    except Exception as e:
        logger.error(f"恢复任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/cancel', methods=['POST'])
def cancel_job(job_id: int):
    """
    取消任务
    
    Note:
        - 可以取消 pending、processing 或 paused 状态的任务
        - 取消后任务状态变为 failed
    """
    try:
        scheduler = get_scheduler()
        success = scheduler.cancel_job(job_id)
        
        if success:
            logger.info(f"取消任务 {job_id}")
            return jsonify({
                'success': True,
                'message': f'任务 {job_id} 已取消',
                'job_id': job_id
            })
        else:
            return jsonify({
                'success': False,
                'error': '取消任务失败，任务可能不存在或已完成'
            }), 400
            
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/restart', methods=['POST'])
def restart_job(job_id: int):
    """
    重启任务

    Request Body:
        - reset_failed_only: 只重置失败的靶点（默认 false）
        - evaluation_mode: 评估模式 ('parallel' 或 'sequential')，可选
        - priority: 优先级 (1-10)，可选
        - name: 任务名称，可选
        - description: 任务描述，可选
        - tags: 标签，可选

    Note:
        - 可以重启 completed 或 failed 状态的任务
        - 会重置靶点状态并重新开始执行
        - 会清除旧的 evaluation 数据和 AI 分析
        - 支持在重启时同时更新任务参数
    """
    try:
        data = request.get_json() or {}
        reset_failed_only = data.get('reset_failed_only', False)

        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404

            if job.status not in ['completed', 'failed']:
                return jsonify({
                    'success': False,
                    'error': f'任务状态为 {job.status}，不能重启'
                }), 400

            # 更新任务参数（如果提供）
            param_updates = {}
            if 'name' in data:
                param_updates['name'] = data['name']
            if 'description' in data:
                param_updates['description'] = data['description']
            if 'priority' in data:
                priority = data['priority']
                if isinstance(priority, int) and 1 <= priority <= 10:
                    param_updates['priority'] = priority
            if 'evaluation_mode' in data:
                mode = data['evaluation_mode']
                if mode in ['parallel', 'sequential']:
                    param_updates['evaluation_mode'] = mode
            if 'tags' in data:
                param_updates['tags'] = data['tags']

            # 更新配置参数（config）
            if 'max_pdb' in data:
                max_pdb = data['max_pdb']
                if isinstance(max_pdb, int) and max_pdb > 0:
                    # Merge with existing config
                    current_config = dict(job.config) if job.config else {}
                    current_config['max_pdb'] = max_pdb
                    job.config = current_config
                    flag_modified(job, 'config')
                    param_updates['config'] = {'max_pdb': max_pdb}

            for key, value in param_updates.items():
                if key != 'config':
                    setattr(job, key, value)

            session.commit()
            logger.info(f"更新任务参数 {job_id}: {param_updates}")

        finally:
            session.close()

        scheduler = get_scheduler()
        success = scheduler.restart_job(job_id, reset_failed_only=reset_failed_only, clear_evaluations=True)

        if success:
            message_parts = ['任务已重启']
            if reset_failed_only:
                message_parts.append('（只重置失败的靶点）')
            if param_updates:
                message_parts.append(f'，已更新: {", ".join(param_updates.keys())}')
            message = ''.join(message_parts)
            logger.info(f"重启任务 {job_id}, reset_failed_only={reset_failed_only}")
            return jsonify({
                'success': True,
                'message': message,
                'job_id': job_id,
                'updated_params': param_updates
            })
        else:
            return jsonify({
                'success': False,
                'error': '重启任务失败，任务可能不存在或状态不正确'
            }), 400

    except Exception as e:
        logger.error(f"重启任务失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/params', methods=['PUT'])
def update_job_params(job_id: int):
    """更新任务参数（不重启任务）

    Body Parameters:
        - name: 任务名称（可选）
        - description: 任务描述（可选）
        - priority: 优先级 1-10（可选）
        - evaluation_mode: 评估模式 parallel/sequential（可选）
        - max_pdb: 最大PDB数量（可选）
    """
    try:
        data = request.get_json() or {}

        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404

            # 更新任务参数
            param_updates = {}
            if 'name' in data:
                param_updates['name'] = data['name']
                job.name = data['name']
            if 'description' in data:
                param_updates['description'] = data['description']
                job.description = data['description']
            if 'priority' in data:
                priority = data['priority']
                if isinstance(priority, int) and 1 <= priority <= 10:
                    param_updates['priority'] = priority
                    job.priority = priority
            if 'evaluation_mode' in data:
                mode = data['evaluation_mode']
                if mode in ['parallel', 'sequential']:
                    param_updates['evaluation_mode'] = mode
                    job.evaluation_mode = mode
            if 'max_pdb' in data:
                max_pdb = data['max_pdb']
                if isinstance(max_pdb, int) and max_pdb > 0:
                    current_config = dict(job.config) if job.config else {}
                    current_config['max_pdb'] = max_pdb
                    job.config = current_config
                    flag_modified(job, 'config')  # Tell SQLAlchemy the JSON field was modified
                    param_updates['max_pdb'] = max_pdb

            session.commit()
            logger.info(f"更新任务参数 {job_id}: {param_updates}")

            return jsonify({
                'success': True,
                'message': '参数已更新',
                'job_id': job_id,
                'updated_params': param_updates
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"更新任务参数失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 靶点操作 API ==========

@bp.route('/<int:job_id>/targets', methods=['GET'])
def get_job_targets(job_id: int):
    """
    获取任务的所有靶点
    
    Query Parameters:
        - status: 状态过滤
        - limit: 数量限制
        - offset: 偏移量
    """
    try:
        status_filter = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        lang = request.args.get('lang', 'zh')

        # Initialize UniProt client
        uniprot_client = UniProtAPIClient()

        session = get_session()
        try:
            # 验证任务存在
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({
                    'success': False,
                    'error': f'任务 {job_id} 不存在'
                }), 404

            # 查询靶点
            query = session.query(Target).filter_by(job_id=job_id)

            if status_filter:
                query = query.filter(Target.status == status_filter)

            total = query.count()

            targets = query.options(joinedload(Target.evaluation)).order_by(Target.target_index).offset(offset).limit(limit).all()

            targets_data = []
            for target in targets:
                target_dict = target.to_dict()

                # Fetch UniProt metadata
                try:
                    uniprot_entry = uniprot_client.get_by_uniprot_id(target.uniprot_id)
                    if uniprot_entry:
                        # Structure as uniprot_metadata for frontend
                        target_dict['uniprot_metadata'] = {
                            'protein_name': getattr(uniprot_entry, 'protein_name', None),
                            'gene_name': uniprot_entry.gene_names[0] if hasattr(uniprot_entry, 'gene_names') and uniprot_entry.gene_names else None,
                            'organism': uniprot_entry.organism,
                            'function': uniprot_entry.function,
                            'keywords': uniprot_entry.keywords,
                            'subcellular_location': uniprot_entry.subcellular_location,
                            'sequence_length': uniprot_entry.sequence_length,
                            'domains': getattr(uniprot_entry, 'domains', []),
                            'modifications': getattr(uniprot_entry, 'modifications', []),
                        }
                except Exception as e:
                    logger.warning(f"Failed to fetch UniProt metadata for {target.uniprot_id}: {e}")

                # Add evaluation result (if exists)
                if target.evaluation:
                    eval_dict = {
                        'id': target.evaluation.id,
                        'overall_score': getattr(target.evaluation, 'overall_score', None),
                        'status': target.evaluation.evaluation_status
                    }
                    # Add PDB data
                    if target.evaluation.pdb_data:
                        pdb_data = target.evaluation.pdb_data
                        eval_dict['pdb_data'] = pdb_data
                    # Add BLAST results
                    if target.evaluation.blast_results:
                        eval_dict['blast_results'] = target.evaluation.blast_results
                    # Return analysis based on language
                    if lang == 'en' and target.evaluation.ai_analysis_en:
                        eval_dict['ai_analysis'] = target.evaluation.ai_analysis_en
                    elif target.evaluation.ai_analysis:
                        eval_dict['ai_analysis'] = target.evaluation.ai_analysis
                    # Always include both versions for frontend flexibility
                    eval_dict['ai_analysis_zh'] = target.evaluation.ai_analysis
                    eval_dict['ai_analysis_en'] = target.evaluation.ai_analysis_en
                    # Include AI prompt for debugging
                    eval_dict['ai_prompt'] = getattr(target.evaluation, 'ai_prompt', None)
                    target_dict['evaluation'] = eval_dict
                targets_data.append(target_dict)

            return jsonify({
                'success': True,
                'job_id': job_id,
                'targets': targets_data,
                'total': total,
                'offset': offset,
                'limit': limit,
                'lang': lang
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"获取靶点列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/targets/<int:target_id>', methods=['GET'])
def get_target_detail(job_id: int, target_id: int):
    """
    获取单个靶点详情
    """
    try:
        session = get_session()
        try:
            target = session.query(Target).filter_by(
                target_id=target_id,
                job_id=job_id
            ).first()
            
            if not target:
                return jsonify({
                    'success': False,
                    'error': f'靶点 {target_id} 不存在'
                }), 404
            
            target_dict = target.to_dict()
            
            # 添加完整评估结果
            if target.evaluation:
                eval_data = {
                    'id': target.evaluation.id,
                    'status': target.evaluation.evaluation_status,
                    'created_at': target.evaluation.created_at.isoformat() if target.evaluation.created_at else None
                }
                
                # 添加评分详情
                if hasattr(target.evaluation, 'structure_quality_score'):
                    eval_data['structure_quality_score'] = target.evaluation.structure_quality_score
                if hasattr(target.evaluation, 'function_score'):
                    eval_data['function_score'] = target.evaluation.function_score
                if hasattr(target.evaluation, 'overall_score'):
                    eval_data['overall_score'] = target.evaluation.overall_score
                
                target_dict['evaluation'] = eval_data
            
            # 添加关系信息
            relationships = []
            for rel in target.outgoing_relationships:
                rel_dict = rel.to_dict()
                rel_dict['direction'] = 'outgoing'
                relationships.append(rel_dict)
            for rel in target.incoming_relationships:
                rel_dict = rel.to_dict()
                rel_dict['direction'] = 'incoming'
                relationships.append(rel_dict)
            
            if relationships:
                target_dict['relationships'] = relationships
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'target': target_dict
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"获取靶点详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== 相互作用分析 API ==========

@bp.route('/<int:job_id>/interactions', methods=['GET'])
def get_job_interactions(job_id: int):
    """
    获取任务的靶点间相互作用

    Query Parameters:
        - relationship_type: 关系类型过滤
        - min_score: 最小分数阈值
        - limit: 数量限制
    """
    try:
        rel_type = request.args.get('relationship_type')
        min_score = request.args.get('min_score')
        limit = int(request.args.get('limit', 100))

        session = get_session()
        try:
            # Get all targets for this job to build PDB map
            targets = session.query(Target).filter_by(job_id=job_id).all()
            target_pdb_map = {}
            for t in targets:
                # Get PDB IDs from evaluation
                if t.evaluation and t.evaluation.pdb_data:
                    pdb_ids = [s.get('pdb_id') for s in t.evaluation.pdb_data.get('structures', []) if s.get('pdb_id')]
                    target_pdb_map[t.uniprot_id] = pdb_ids
                else:
                    target_pdb_map[t.uniprot_id] = []

            query = session.query(TargetRelationship).filter_by(job_id=job_id)

            if rel_type:
                query = query.filter(TargetRelationship.relationship_type == rel_type)

            if min_score is not None:
                query = query.filter(TargetRelationship.score >= float(min_score))

            query = query.order_by(TargetRelationship.score.desc())
            relationships = query.limit(limit).all()

            interactions = []
            for rel in relationships:
                source = session.query(Target).get(rel.source_target_id)
                target = session.query(Target).get(rel.target_target_id)

                # Calculate common PDB structures between source and target
                source_pdb = target_pdb_map.get(source.uniprot_id, []) if source else []
                target_pdb = target_pdb_map.get(target.uniprot_id, []) if target else []
                common_pdb = list(set(source_pdb) & set(target_pdb))

                # Build metadata with common_structures
                metadata = dict(rel.relationship_metadata) if rel.relationship_metadata else {}
                if common_pdb:
                    metadata['common_structures'] = common_pdb
                    metadata['common_pdb'] = common_pdb[0] if common_pdb else None
                    metadata['common_pdbs'] = common_pdb

                interactions.append({
                    'relationship_id': rel.relationship_id,
                    'source_target_id': rel.source_target_id,
                    'target_target_id': rel.target_target_id,
                    'source_uniprot': source.uniprot_id if source else None,
                    'target_uniprot': target.uniprot_id if target else None,
                    'relationship_type': rel.relationship_type,
                    'score': rel.score,
                    'metadata': metadata
                })

            return jsonify({
                'success': True,
                'job_id': job_id,
                'interactions': interactions,
                'total': len(interactions)
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"获取相互作用失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/interactions/chain', methods=['GET'])
def get_chain_interactions(job_id: int):
    """
    获取增强的链级别互作分析（包含直接/间接互作）

    优先返回数据库中已存储的分析结果，如果不存在则计算并存入数据库。
    返回所有在PDB结构中发现的蛋白质互作，区分：
    - 直接互作：两个蛋白的链在PDB结构中直接相互作用
    - 间接互作：通过第三个蛋白介导的互作
    """
    try:
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404

            # Return stored data if available
            if job.chain_interaction_analysis:
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    **job.chain_interaction_analysis,
                    'from_cache': True
                })

            # If not stored, compute and save
            from src.chain_interaction_analyzer import analyze_chain_interactions
            targets = session.query(Target).filter_by(job_id=job_id).all()
            input_uniprot_ids = [t.uniprot_id for t in targets]

            result = analyze_chain_interactions(job_id, input_uniprot_ids)

            return jsonify({
                'success': True,
                'job_id': job_id,
                **result,
                'from_cache': False
            })

        finally:
            session.close()

    except Exception as e:
        logger.error(f"获取链级相互作用失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/interactions/chain/retry', methods=['POST'])
def retry_chain_interactions(job_id: int):
    """重试获取失败的 PDB 的链级相互作用分析"""
    from src.chain_interaction_analyzer import retry_chain_interactions
    from src.multi_target_models import MultiTargetJob
    
    try:
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            
            data = request.get_json() or {}
            failed_pdbs = data.get('failed_pdbs', [])
            
            if not failed_pdbs:
                return jsonify({'success': False, 'error': '未指定需要重试的PDB'}), 400
            
            input_uniprot_ids = [t.uniprot_id for t in job.targets if t.uniprot_id]
            
            result = retry_chain_interactions(job_id, input_uniprot_ids, failed_pdbs)
            
            return jsonify({
                'success': True,
                **result
            })
        finally:
            session.close()
    except Exception as e:
        logger.error(f"重试链级相互作用失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:job_id>/interactions/analysis', methods=['GET'])
def get_interaction_analysis(job_id: int):
    """获取靶点相互作用的 AI 分析（支持中英文）

    Query Parameters:
        - lang: 语言选择 ('zh' for Chinese, 'en' for English, defaults to 'zh')
    """
    try:
        from src.multi_target_models import MultiTargetJob

        # Get language preference from query param, default to Chinese
        lang = request.args.get('lang', 'zh')
        if lang not in ('zh', 'en'):
            lang = 'zh'

        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404

            # Return cached analysis based on language
            if lang == 'en' and job.interaction_ai_analysis_en:
                return jsonify({'success': True, 'analysis': job.interaction_ai_analysis_en, 'lang': 'en'})
            elif lang == 'zh' and job.interaction_ai_analysis:
                return jsonify({'success': True, 'analysis': job.interaction_ai_analysis, 'lang': 'zh'})

            # Get all interactions
            relationships = session.query(TargetRelationship).filter_by(job_id=job_id).order_by(TargetRelationship.score.desc()).all()
            if not relationships:
                return jsonify({'success': True, 'analysis': '暂无相互作用数据'})

            # Get target info - use target_id as key
            targets = session.query(Target).filter_by(job_id=job_id).all()
            target_map = {t.target_id: t for t in targets}

            # Get PDB data for each target from targets table directly
            target_pdb_map = {}
            for t in targets:
                # Get pdb_ids from target's evaluation
                if t.evaluation and t.evaluation.pdb_data:
                    pdb_data = t.evaluation.pdb_data
                    pdb_ids = pdb_data.get('pdb_ids', []) if isinstance(pdb_data, dict) else []
                    target_pdb_map[t.uniprot_id] = pdb_ids

            # Build interaction summary with final confidence score
            interaction_summary = []
            seen_pairs = set()

            for rel in relationships:
                key = tuple(sorted([rel.source_target_id, rel.target_target_id]))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)

                source = target_map.get(rel.source_target_id)
                target = target_map.get(rel.target_target_id)

                if not source or not target:
                    continue

                src_pdb = target_pdb_map.get(source.uniprot_id, [])
                tgt_pdb = target_pdb_map.get(target.uniprot_id, [])
                common_pdb = set(src_pdb) & set(tgt_pdb)

                # Final score: 100% if have common structures, else use raw score
                final_score = 1.0 if common_pdb else rel.score

                interaction_summary.append({
                    'source': source.uniprot_id,
                    'source_name': source.protein_name or source.gene_name or '',
                    'target': target.uniprot_id,
                    'target_name': target.protein_name or target.gene_name or '',
                    'common_structures': list(common_pdb) if common_pdb else [],
                    'raw_score': rel.score,
                    'final_score': final_score,
                    'source_db': rel.relationship_metadata.get('source_db', []) if rel.relationship_metadata else []
                })

            # Generate both Chinese and English analysis
            job_name = job.name or '多靶点评估'
            ai_wrapper = get_ai_client_wrapper()
            ai_available = ai_wrapper.is_available()

            # Generate Chinese analysis - always try AI if available (overwrite template-only cache)
            if ai_available:
                # Always try AI first to ensure AI-generated content
                analysis_zh = _generate_ai_interaction_analysis(
                    job, targets, interaction_summary, job_name, lang='zh'
                )
                if analysis_zh:
                    job.interaction_ai_analysis = analysis_zh
                else:
                    # AI failed, use template
                    job.interaction_ai_analysis = _generate_template_interaction_analysis(
                        targets, interaction_summary, lang='zh'
                    )
            elif not job.interaction_ai_analysis:
                # AI not available and no cache, use template
                job.interaction_ai_analysis = _generate_template_interaction_analysis(
                    targets, interaction_summary, lang='zh'
                )
            # If AI available and we have AI result, use it (overwrites template cache)

            # Generate English analysis - always try AI if available (overwrite template-only cache)
            if ai_available:
                analysis_en = _generate_ai_interaction_analysis(
                    job, targets, interaction_summary, job_name, lang='en'
                )
                if analysis_en:
                    job.interaction_ai_analysis_en = analysis_en
                else:
                    job.interaction_ai_analysis_en = _generate_template_interaction_analysis(
                        targets, interaction_summary, lang='en'
                    )
            elif not job.interaction_ai_analysis_en:
                job.interaction_ai_analysis_en = _generate_template_interaction_analysis(
                    targets, interaction_summary, lang='en'
                )

            session.commit()

            # Return the requested language version
            if lang == 'en':
                return jsonify({'success': True, 'analysis': job.interaction_ai_analysis_en, 'lang': 'en'})
            else:
                return jsonify({'success': True, 'analysis': job.interaction_ai_analysis, 'lang': 'zh'})

        finally:
            session.close()

    except Exception as e:
        logger.error(f"获取相互作用分析失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _ensure_interaction_analysis(job, targets, relationships, session):
    """Ensure interaction analysis exists in both languages (called from get_multi_target_job).

    This function generates AI analysis if:
    1. AI is available
    2. Existing cache is template-based (detected by presence of template markers)
    3. force_refresh is requested
    """
    try:
        # Build interaction summary
        target_map = {t.target_id: t for t in targets}
        target_pdb_map = {}
        for t in targets:
            if t.evaluation and t.evaluation.pdb_data:
                pdb_data = t.evaluation.pdb_data
                pdb_ids = pdb_data.get('pdb_ids', []) if isinstance(pdb_data, dict) else []
                target_pdb_map[t.uniprot_id] = pdb_ids

        interaction_summary = []
        seen_pairs = set()

        for rel in relationships:
            key = tuple(sorted([rel.source_target_id, rel.target_target_id]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            source = target_map.get(rel.source_target_id)
            target = target_map.get(rel.target_target_id)

            if not source or not target:
                continue

            src_pdb = target_pdb_map.get(source.uniprot_id, [])
            tgt_pdb = target_pdb_map.get(target.uniprot_id, [])
            common_pdb = set(src_pdb) & set(tgt_pdb)
            final_score = 1.0 if common_pdb else rel.score

            interaction_summary.append({
                'source': source.uniprot_id,
                'source_name': source.protein_name or source.gene_name or '',
                'target': target.uniprot_id,
                'target_name': target.protein_name or target.gene_name or '',
                'common_structures': list(common_pdb) if common_pdb else [],
                'raw_score': rel.score,
                'final_score': final_score,
                'source_db': rel.relationship_metadata.get('source_db', []) if rel.relationship_metadata else []
            })

        job_name = job.name or '多靶点评估'
        ai_wrapper = get_ai_client_wrapper()
        ai_available = ai_wrapper.is_available()

        # Check if existing content is template-based (simple heuristic)
        def is_template_based(content):
            if not content:
                return True
            template_markers = ['Overall Overview', '整体概况', 'Overall overview']
            return any(marker in content for marker in template_markers[:1])

        # Generate Chinese analysis - always try AI if available
        needs_zh = not job.interaction_ai_analysis or (ai_available and is_template_based(job.interaction_ai_analysis))
        if ai_available and needs_zh:
            result_zh = _generate_ai_interaction_analysis(
                job, targets, interaction_summary, job_name, lang='zh'
            )
            if result_zh:
                job.interaction_ai_analysis, job.interaction_prompt = result_zh
            else:
                job.interaction_ai_analysis = _generate_template_interaction_analysis(
                    targets, interaction_summary, lang='zh'
                )
        elif needs_zh:
            job.interaction_ai_analysis = _generate_template_interaction_analysis(
                targets, interaction_summary, lang='zh'
            )

        # Generate English analysis - always try AI if available
        needs_en = not job.interaction_ai_analysis_en or (ai_available and is_template_based(job.interaction_ai_analysis_en))
        if ai_available and needs_en:
            result_en = _generate_ai_interaction_analysis(
                job, targets, interaction_summary, job_name, lang='en'
            )
            if result_en:
                job.interaction_ai_analysis_en, job.interaction_prompt_en = result_en
            else:
                job.interaction_ai_analysis_en = _generate_template_interaction_analysis(
                    targets, interaction_summary, lang='en'
                )
        elif needs_en:
            job.interaction_ai_analysis_en = _generate_template_interaction_analysis(
                targets, interaction_summary, lang='en'
            )

        session.commit()
        logger.info(f"Interaction analysis ensured for job {job.job_id}")

    except Exception as e:
        logger.error(f"Failed to ensure interaction analysis: {e}")
        # Don't raise - we don't want to fail the whole request


def _generate_ai_interaction_analysis(
    job,
    targets: List[Target],
    interaction_summary: List[Dict],
    job_name: str,
    lang: str = 'zh'
) -> Optional[str]:
    """Generate interaction analysis using AI in the specified language.

    Args:
        job: MultiTargetJob object (to access config.template and chain_interaction_analysis)
        targets: List of Target objects
        interaction_summary: List of interaction data dictionaries
        job_name: Name of the job
        lang: Language code ('zh' for Chinese, 'en' for English)

    Returns:
        Generated analysis text or None if AI generation failed
    """
    try:
        ai_wrapper = get_ai_client_wrapper()

        if not ai_wrapper.is_available():
            logger.warning("AI client not available, using template fallback")
            return None

        # Get frontend template from job config if available
        frontend_template = None
        if job and job.config and job.config.get('template'):
            template_value = job.config['template']
            # If the value contains newlines, it's the actual template content (sent by new frontend)
            # Otherwise it's a template name that needs to be looked up
            if '\n' in template_value:
                frontend_template = template_value
                logger.info(f"Using frontend template content (length: {len(frontend_template)})")
            else:
                # Legacy: template name - look up in database
                from src.database import get_all_prompt_templates
                all_templates = get_all_prompt_templates()
                matched_template = next((t for t in all_templates if t.name == template_value or t.name_en == template_value), None)
                if matched_template:
                    frontend_template = matched_template.content_en if lang == 'en' else matched_template.content
                    logger.info(f"Using template '{template_value}' from database (content length: {len(frontend_template) if frontend_template else 0})")
                else:
                    logger.warning(f"Template '{template_value}' not found in database")

        # Get chain-level interaction data
        chain_data = None
        if job and job.chain_interaction_analysis:
            chain_data = job.chain_interaction_analysis
            logger.info(f"Using chain interaction data: {len(chain_data.get('direct_interactions', []))} direct, {len(chain_data.get('indirect_interactions', []))} indirect")

        # Build interaction data for prompt
        pairs_with_common = sum(1 for i in interaction_summary if i['common_structures'])
        high_conf = sum(1 for i in interaction_summary if i['final_score'] > 0.5)

        # Format interaction details
        interaction_details = []
        for i in interaction_summary:
            src_name = i['source_name'] or i['source']
            tgt_name = i['target_name'] or i['target']
            has_common = bool(i['common_structures'])
            confidence = "100%" if has_common else f"{i['final_score'] * 100:.0f}%"
            source_db = ', '.join(i['source_db']) if i['source_db'] else 'unknown'
            common_structs = ', '.join(i['common_structures'][:5]) if i['common_structures'] else 'None'

            interaction_details.append({
                'pair': f"{i['source']} ({src_name}) ↔ {i['target']} ({tgt_name})",
                'confidence': confidence,
                'source_db': source_db,
                'common_structures': common_structs,
                'raw_score': f"{i['raw_score'] * 100:.0f}%"
            })

        # Format chain-level interaction details
        chain_details = []
        if chain_data:
            for di in chain_data.get('direct_interactions', []):
                chain_details.append({
                    'type': '直接互作',
                    'source': di.get('source_uniprot', ''),
                    'target': di.get('target_uniprot', ''),
                    'pdb': di.get('pdb_id', ''),
                    'chains': f"{di.get('source_chain', '')}-{di.get('target_chain', '')}",
                    'residues': di.get('interface_residues', '')
                })
            for ii in chain_data.get('indirect_interactions', []):
                chain_details.append({
                    'type': '间接互作',
                    'source': ii.get('source_uniprot', ''),
                    'target': ii.get('target_uniprot', ''),
                    'via': ii.get('intermediate_uniprot', ''),
                    'common_pdb': ii.get('common_pdb', '')
                })

        # Build prompt based on language
        if lang == 'en':
            prompt = ""
            prompt += "## Task Description\n"
            prompt += "Please analyze the protein-protein interaction data for the following multi-target project and generate a comprehensive, professional interaction analysis report.\n\n"
            prompt += "## Project Information\n"
            prompt += f"- Project Name: {job_name}\n"
            prompt += f"- Total Targets: {len(targets)}\n"
            prompt += f"- Number of Target Pair Interactions: {len(interaction_summary)}\n"
            prompt += f"- Confirmed Interactions (Shared PDB Structures): {pairs_with_common} pairs\n"
            prompt += f"- High-Confidence Interactions: {high_conf} pairs\n\n"
            prompt += "## Interaction Data\n\n"
            prompt += "### Key Findings\n"

            if pairs_with_common > 0:
                prompt += f"**{pairs_with_common} pairs of targets share PDB structures**, confirming physical interactions.\n\n"
            else:
                prompt += "No target pairs currently share PDB structures. Interactions are based on computational predictions.\n\n"

            prompt += "### Detailed Interaction List\n\n"
            for idx, detail in enumerate(interaction_details, 1):
                prompt += f"""**{idx}. {detail['pair']}**
   - Confidence: {detail['confidence']}
   - Data Source: {detail['source_db']}
   - Raw Score: {detail['raw_score']}
   - Shared Structures: {detail['common_structures']}

"""

            # Add chain-level interaction data if available
            if chain_details:
                prompt += "### Chain-Level Interaction Details (from PDB structures)\n\n"
                for idx, cd in enumerate(chain_details[:20], 1):  # Limit to first 20
                    src = cd.get('source', '')
                    tgt = cd.get('target', '')
                    if cd.get('type') == '直接互作':
                        prompt += f"**{idx}. Direct Interaction: {src} <-> {tgt}**\n"
                        prompt += f"   - PDB: {cd.get('pdb', 'N/A')}\n"
                        prompt += f"   - Chains: {cd.get('chains', 'N/A')}\n"
                        prompt += f"   - Interface Residues: {cd.get('residues', 'N/A')}\n\n"
                    else:
                        prompt += f"**{idx}. Indirect Interaction: {src} <-> {tgt}**\n"
                        prompt += f"   - Via: {cd.get('via', 'N/A')}\n"
                        prompt += f"   - Common PDB: {cd.get('common_pdb', 'N/A')}\n\n"

            if frontend_template:
                prompt = frontend_template + "\n\n" + prompt
                # Even with frontend template, add instruction to remove placeholder dates
                prompt += "## Important Reminder\n"
                prompt += "Please remove all placeholder dates (such as 'YYYY-MM', '202X', 'Month YYYY', etc.) from the template. Do not include any date placeholders in the final report. If dates are needed, use the actual analysis date.\n"
            else:
                prompt += "## Output Requirements\n\n"
                prompt += "Please generate a **professional English** protein-protein interaction analysis report, containing:\n\n"
                prompt += "1. **Overall Overview** - Summarize the scale and characteristics of the interaction network\n"
                prompt += "2. **Key Findings** - Identify the most important interaction pairs and their biological significance\n"
                prompt += "3. **Structural Basis** - Analyze interactions confirmed by shared PDB structures (include chain-level details if available)\n"
                prompt += "4. **Predicted Interactions** - Discuss high-confidence interactions lacking structural evidence\n"
                prompt += "5. **Biological Interpretation** - Analyze the significance of interactions from a protein function perspective\n\n"
                prompt += "Please output the report in Markdown format, maintaining a professional, scientific English expression style.\n"
            system_message = "You are a professional protein structural biologist and bioinformatics expert, specializing in protein-protein interaction network analysis. Please provide professional and rigorous scientific analysis."
        else:
            # Chinese prompt
            if frontend_template:
                prompt = frontend_template + "\n\n"
            else:
                prompt = ""

            prompt += f"""## 项目信息
- 项目名称: {job_name}
- 总靶点数: {len(targets)}
- 靶点对相互作用数: {len(interaction_summary)}
- 确定互作(共有PDB结构): {pairs_with_common} 对
- 高置信度相互作用: {high_conf} 个

## 相互作用数据

### 关键发现
"""

            if pairs_with_common > 0:
                prompt += f"**{pairs_with_common} 对靶点共享PDB结构**，确认存在物理相互作用。\n\n"
            else:
                prompt += "目前没有靶点对共享PDB结构，相互作用基于计算预测。\n\n"

            prompt += "### 相互作用详情列表\n\n"
            for idx, detail in enumerate(interaction_details, 1):
                prompt += f"""**{idx}. {detail['pair']}**
   - 置信度: {detail['confidence']}
   - 数据来源: {detail['source_db']}
   - 原始评分: {detail['raw_score']}
   - 共有结构: {detail['common_structures']}

"""

            # Add chain-level interaction data if available
            if chain_details:
                prompt += "### 链级相互作用详细信息（来自PDB结构）\n\n"
                for idx, cd in enumerate(chain_details[:20], 1):  # Limit to first 20
                    src = cd.get('source', '')
                    tgt = cd.get('target', '')
                    if cd.get('type') == '直接互作':
                        prompt += f"**{idx}. 直接互作: {src} <-> {tgt}**\n"
                        prompt += f"   - PDB: {cd.get('pdb', 'N/A')}\n"
                        prompt += f"   - 链: {cd.get('chains', 'N/A')}\n"
                        prompt += f"   - 界面残基: {cd.get('residues', 'N/A')}\n\n"
                    else:
                        prompt += f"**{idx}. 间接互作: {src} <-> {tgt}**\n"
                        prompt += f"   - 途经: {cd.get('via', 'N/A')}\n"
                        prompt += f"   - 共同PDB: {cd.get('common_pdb', 'N/A')}\n\n"

            if not frontend_template:
                prompt += """## 输出要求\n\n"""
                prompt += "请生成一份**专业的中文**靶点相互作用分析报告，包含：\n\n"
                prompt += "1. **整体概况** - 总结相互作用网络的规模和特点\n"
                prompt += "2. **关键概况** - 识别最重要的相互作用对及其生物学意义\n"
                prompt += "3. **结构基础** - 分析共有PDB结构证实的相互作用（包含链级详细信息）\n"
                prompt += "4. **预测相互作用** - 讨论高置信度但缺乏结构证据的相互作用\n"
                prompt += "5. **生物学解读** - 从蛋白质功能角度分析相互作用的意义\n\n"
                prompt += "请用Markdown格式输出报告，保持专业、科学的中文表达风格。\n"
            else:
                # Even with frontend template, add instruction to remove placeholder dates
                prompt += "\n\n## 重要提醒\n"
                prompt += "请删除模板中所有占位符日期（如'XXXX年XX月'、'202X年'等），不要在最终报告中保留任何日期占位符。如果需要日期，请使用实际分析日期。\n"
            system_message = "你是一个专业的蛋白质结构生物学家和生物信息学专家，擅长分析蛋白质-蛋白质相互作用网络。请提供专业、严谨的科学分析。"

        # Call AI
        result = ai_wrapper.analyze(
            prompt,
            system_message=system_message
        )

        if result.get('success') and result.get('analysis'):
            logger.info(f"AI interaction analysis generated successfully ({lang})")
            # Return tuple of (analysis, prompt)
            return result['analysis'], prompt
        else:
            error = result.get('error', 'Unknown error')
            logger.warning(f"AI interaction analysis failed: {error}, using template fallback")
            return None, prompt  # Still return prompt even if AI fails

    except Exception as e:
        logger.error(f"AI interaction analysis error: {e}")
        return None


def _generate_template_interaction_analysis(
    targets: List[Target],
    interaction_summary: List[Dict],
    lang: str = 'zh'
) -> str:
    """Generate template-based interaction analysis (fallback).

    Args:
        targets: List of Target objects
        interaction_summary: List of interaction data dictionaries
        lang: Language code ('zh' for Chinese, 'en' for English)
    """
    pairs_with_common = sum(1 for i in interaction_summary if i['common_structures'])
    high_conf = sum(1 for i in interaction_summary if i['final_score'] > 0.5)

    if lang == 'en':
        analysis_text = f"""## Protein-Protein Interaction Analysis

### Overall Overview
- Total Targets: {len(targets)}
- Number of Target Pair Interactions: {len(interaction_summary)}
- Confirmed Interactions (Shared PDB Structures): {pairs_with_common} pairs
- High-Confidence Interactions: {high_conf} pairs

### Key Findings
"""

        if pairs_with_common > 0:
            analysis_text += f"**{pairs_with_common} pairs of targets share PDB structures**, confirming physical interactions:\n\n"
            for i in interaction_summary:
                if i['common_structures']:
                    pdb_list = ', '.join(i['common_structures'][:10])
                    if len(i['common_structures']) > 10:
                        pdb_list += f' ... (+{len(i["common_structures"]) - 10} more)'
                    analysis_text += f"- **{i['source']}** ↔ **{i['target']}**: {pdb_list}\n"

        analysis_text += "\n### Detailed Interactions\n\n"
        for i in interaction_summary:
            src_name = f" ({i['source_name']})" if i['source_name'] else ""
            tgt_name = f" ({i['target_name']})" if i['target_name'] else ""

            if i['common_structures']:
                confidence = "✅ **Confirmed Interaction** (100%)"
            else:
                confidence = f"{i['final_score']*100:.0f}% confidence"

            source_db = ', '.join(i['source_db']) if i['source_db'] else 'unknown'

            analysis_text += f"#### {i['source']}{src_name} ↔ {i['target']}{tgt_name}\n"
            analysis_text += f"- Confidence: {confidence}\n"
            analysis_text += f"- Data Source: {source_db}\n"
            analysis_text += f"- Raw Score: {i['raw_score']*100:.0f}%\n"
            if i['common_structures']:
                analysis_text += f"- Shared Structures: {', '.join(i['common_structures'][:5])}...\n"
            analysis_text += "\n"
    else:
        # Chinese template
        analysis_text = f"""## 靶点相互作用 AI 分析

### 整体概况
- 总靶点数: {len(targets)}
- 靶点对相互作用数: {len(interaction_summary)}
- 确定互作（共有PDB结构）: {pairs_with_common} 对
- 高置信度相互作用: {high_conf} 个

### 关键发现
"""

        if pairs_with_common > 0:
            analysis_text += f"**{pairs_with_common} 对靶点共享PDB结构**，确认存在物理相互作用：\n\n"
            for i in interaction_summary:
                if i['common_structures']:
                    pdb_list = ', '.join(i['common_structures'][:10])
                    if len(i['common_structures']) > 10:
                        pdb_list += f' ... (+{len(i["common_structures"]) - 10} more)'
                    analysis_text += f"- **{i['source']}** ↔ **{i['target']}**: {pdb_list}\n"

        analysis_text += "\n### 相互作用详情\n\n"
        for i in interaction_summary:
            src_name = f" ({i['source_name']})" if i['source_name'] else ""
            tgt_name = f" ({i['target_name']})" if i['target_name'] else ""

            if i['common_structures']:
                confidence = "✅ **确定互作** (100%)"
            else:
                confidence = f"{i['final_score']*100:.0f}% 置信度"

            source_db = ', '.join(i['source_db']) if i['source_db'] else 'unknown'

            analysis_text += f"#### {i['source']}{src_name} ↔ {i['target']}{tgt_name}\n"
            analysis_text += f"- 置信度: {confidence}\n"
            analysis_text += f"- 数据来源: {source_db}\n"
            analysis_text += f"- 原始评分: {i['raw_score']*100:.0f}%\n"
            if i['common_structures']:
                analysis_text += f"- 共有结构: {', '.join(i['common_structures'][:5])}...\n"
            analysis_text += "\n"

    return analysis_text


# ========== 报告生成 API (重定向到 evaluation.py) ==========

@bp.route('/<int:job_id>/report', methods=['POST'])
def generate_report(job_id: int):
    """
    生成任务报告
    
    代理到 evaluation.py 中的报告生成端点
    """
    from flask import redirect, url_for
    # 重定向到 evaluation.py 中的端点
    return redirect(f'/api/evaluation/multi-target/{job_id}/report', code=307)


# ========== API 信息和文档 ==========

@bp.route('/info', methods=['GET'])
def get_api_info():
    """
    获取 API 信息和版本
    """
    return jsonify({
        'success': True,
        'api_version': 'v2',
        'base_path': '/api/v2/evaluate/multi',
        'endpoints': {
            'jobs': {
                'list': 'GET /',
                'create': 'POST /',
                'get': 'GET /<job_id>',
                'update': 'PUT /<job_id>',
                'delete': 'DELETE /<job_id>'
            },
            'control': {
                'start': 'POST /<job_id>/start',
                'pause': 'POST /<job_id>/pause',
                'resume': 'POST /<job_id>/resume',
                'cancel': 'POST /<job_id>/cancel',
                'restart': 'POST /<job_id>/restart'
            },
            'progress': {
                'get': 'GET /<job_id>/progress'
            },
            'targets': {
                'list': 'GET /<job_id>/targets',
                'get': 'GET /<job_id>/targets/<target_id>'
            },
            'interactions': {
                'get': 'GET /<job_id>/interactions'
            },
            'reports': {
                'generate': 'POST /<job_id>/report',
                'preview': 'GET /<job_id>/report-preview'
            }
        },
        'supported_formats': ['markdown', 'json', 'excel'],
        'supported_templates': ['full', 'summary', 'detailed', 'minimal'],
        'max_targets': 50
    })


# ========== 向后兼容 v1 API ==========

@bp.route('/v1-compat/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def v1_compat(path):
    """
    v1 API 兼容层
    
    将 v1 API 请求重定向到 v2 端点
    """
    # v1 到 v2 的映射
    compat_routes = {
        'batch-start': '',  # POST / -> POST /
        'batch': '',  # GET /batch -> GET /
        'batch/<id>': '<id>',  # GET /batch/<id> -> GET /<id>
        'batch/<id>/status': '<id>/progress'  # GET /batch/<id>/status -> GET /<id>/progress
    }
    
    # 返回兼容性说明
    return jsonify({
        'success': False,
        'error': 'v1 API compatibility not yet implemented',
        'message': 'Please use v2 API at /api/v2/evaluate/multi',
        'v1_path': path,
        'documentation': '/api/v2/evaluate/multi/info'
    }), 501


@bp.route('/<int:job_id>/logs', methods=['GET'])
def get_job_logs(job_id: int):
    """获取任务的运行日志

    Returns:
        - logs: 结构化日志列表，每个日志包含 timestamp, level, message
    """
    try:
        with get_session() as session:
            from src.models import ProteinEvaluation

            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({'success': False, 'error': f'任务 {job_id} 不存在'}), 404

            # 获取所有靶点的日志
            targets = session.query(Target).filter_by(job_id=job_id).order_by(Target.target_index).all()

            logs = []

            # 添加任务信息日志
            logs.append({
                'timestamp': job.created_at.strftime('%H:%M:%S') if job.created_at else '--:--:--',
                'level': 'info',
                'message': f"========== 任务信息 =========="
            })
            logs.append({
                'timestamp': job.created_at.strftime('%H:%M:%S') if job.created_at else '--:--:--',
                'level': 'info',
                'message': f"任务名称: {job.name}"
            })
            logs.append({
                'timestamp': job.created_at.strftime('%H:%M:%S') if job.created_at else '--:--:--',
                'level': 'info',
                'message': f"任务ID: {job.job_id}"
            })

            if job.started_at:
                logs.append({
                    'timestamp': job.started_at.strftime('%H:%M:%S'),
                    'level': 'info',
                    'message': f"开始时间: {job.started_at.isoformat()}"
                })

            # 添加靶点评估详情
            logs.append({
                'timestamp': job.created_at.strftime('%H:%M:%S') if job.created_at else '--:--:--',
                'level': 'info',
                'message': f"========== 靶点评估详情 =========="
            })

            for idx, target in enumerate(targets, 1):
                target_time = target.started_at.strftime('%H:%M:%S') if target.started_at else (
                    job.created_at.strftime('%H:%M:%S') if job.created_at else '--:--:--'
                )

                logs.append({
                    'timestamp': target_time,
                    'level': 'info',
                    'message': f"--- 靶点 {idx}: {target.uniprot_id} ---"
                })
                logs.append({
                    'timestamp': target_time,
                    'level': 'info' if target.status == 'completed' else ('error' if target.status == 'failed' else 'warning'),
                    'message': f"状态: {target.status}"
                })

                # 获取评估详情
                if target.evaluation_id:
                    eval_record = session.query(ProteinEvaluation).filter_by(id=target.evaluation_id).first()
                    if eval_record:
                        # 评估时间
                        eval_time = target.completed_at.strftime('%H:%M:%S') if target.completed_at else target_time
                        
                        # 添加评估状态
                        logs.append({
                            'timestamp': target_time,
                            'level': 'info',
                            'message': f"评估状态: {eval_record.evaluation_status}"
                        })

                        # PDB 数据
                        pdb_data = eval_record.pdb_data or {}
                        if pdb_data:
                            structures = pdb_data.get('structures', [])
                            pdb_ids = pdb_data.get('pdb_ids', [])
                            chains = pdb_data.get('chains', [])
                            resolution = pdb_data.get('resolution')
                            coverage = pdb_data.get('coverage', 0)
                            
                            logs.append({
                                'timestamp': eval_time,
                                'level': 'info',
                                'message': f"📦 PDB结构数: {len(structures)}"
                            })
                            # 提取 PDB ID 字符串
                            if pdb_ids:
                                pdb_id_strs = [pid if isinstance(pid, str) else pid.get('pdb_id', 'N/A') for pid in pdb_ids[:5]]
                                logs.append({
                                    'timestamp': eval_time,
                                    'level': 'info',
                                    'message': f"   PDB IDs: {', '.join(pdb_id_strs)}"
                                })
                            elif structures:
                                # structures 可能是字典列表
                                struct_ids = [s['pdb_id'] if isinstance(s, dict) else str(s) for s in structures[:5]]
                                logs.append({
                                    'timestamp': eval_time,
                                    'level': 'info',
                                    'message': f"   PDB IDs: {', '.join(struct_ids)}"
                                })
                            if chains:
                                logs.append({
                                    'timestamp': eval_time,
                                    'level': 'info',
                                    'message': f"   链数: {len(chains)}"
                                })
                            if resolution:
                                logs.append({
                                    'timestamp': eval_time,
                                    'level': 'info',
                                    'message': f"   分辨率: {resolution}Å"
                                })

                        # AI 分析 - 支持新旧两种格式
                        ai_analysis = eval_record.ai_analysis or {}
                        
                        # 新格式：有 structured 分析
                        quality_score = ai_analysis.get('quality_score', 'N/A')
                        coverage = ai_analysis.get('sequence_coverage', 'N/A')
                        
                        # 旧格式：分析文本在 'analysis' 字段
                        analysis_text = ai_analysis.get('analysis', '')
                        
                        logs.append({
                            'timestamp': eval_time,
                            'level': 'info',
                            'message': f"🧠 AI分析结果:"
                        })
                        
                        if analysis_text:
                            # 显示摘要（前 300 字）
                            logs.append({
                                'timestamp': eval_time,
                                'level': 'info',
                                'message': f"   分析文本长度: {len(analysis_text)} 字符"
                            })
                            logs.append({
                                'timestamp': eval_time,
                                'level': 'info',
                                'message': f"   摘要: {analysis_text[:300]}..."
                            })
                        
                        if quality_score != 'N/A':
                            logs.append({
                                'timestamp': eval_time,
                                'level': 'info',
                                'message': f"   质量评分: {quality_score}"
                            })
                        if coverage != 'N/A':
                            logs.append({
                                'timestamp': eval_time,
                                'level': 'info',
                                'message': f"   序列覆盖率: {coverage}%"
                            })

                if target.error_message:
                    logs.append({
                        'timestamp': target_time,
                        'level': 'error',
                        'message': f"错误信息: {target.error_message}"
                    })

            if job.completed_at:
                logs.append({
                    'timestamp': job.completed_at.strftime('%H:%M:%S'),
                    'level': 'success',
                    'message': f"========== 任务完成 =========="
                })
                logs.append({
                    'timestamp': job.completed_at.strftime('%H:%M:%S'),
                    'level': 'success',
                    'message': f"任务状态: {job.status}"
                })
                if job.report_content:
                    logs.append({
                        'timestamp': job.completed_at.strftime('%H:%M:%S'),
                        'level': 'success',
                        'message': f"报告已生成，长度: {len(job.report_content)} 字符"
                    })

            return jsonify({
                'success': True,
                'job_id': job_id,
                'logs': logs
            })

    except Exception as e:
        logger.error(f"获取任务日志失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/pdb/<pdb_id>', methods=['GET'])
def get_pdb_structure(pdb_id: str):
    """
    获取单个 PDB 结构详情

    用于 BLAST 结果中 PDB 的详情展示
    """
    try:
        pdb_client = PDBClient()
        structure = pdb_client.get_structure(pdb_id.upper())

        if structure:
            # Format as PdbStructure type
            formatted_structure = {
                'pdb_id': pdb_id.upper(),
                'source': 'pdb',
                'basic_info': {
                    'title': structure.get('title', ''),
                    'experimental_method': structure.get('experimental_method', ''),
                    'resolution': structure.get('resolution'),
                    'deposition_date': structure.get('deposition_date', ''),
                    'authors': structure.get('authors', []),
                },
                'resolution': structure.get('resolution'),
                'experimental_method': structure.get('experimental_method'),
                'entity_list': structure.get('entity_list', []),
                'citations': structure.get('citations', []),
            }
            return jsonify({
                'success': True,
                'structure': formatted_structure
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to fetch structure for {pdb_id}'
            }), 404

    except Exception as e:
        logger.error(f"获取 PDB 结构详情失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
