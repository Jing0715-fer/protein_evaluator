"""
多靶点评估调度器
支持并行和串行两种评估模式，提供进度追踪和任务管理
"""

import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

from src.multi_target_models import MultiTargetJob, Target, TargetRelationship
from src.models import ProteinEvaluation
from src.database import get_session
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


class EvaluationMode(Enum):
    """评估模式"""
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


class MultiTargetScheduler:
    """多靶点评估调度器
    
    负责管理多靶点任务的执行流程，支持：
    - 并行评估：多个靶点同时评估
    - 串行评估：按顺序逐个评估
    - 进度实时追踪
    - 失败处理和重试
    - 任务暂停/恢复/取消
    """
    
    def __init__(self, max_workers: int = 5, config: Dict[str, Any] = None):
        """
        初始化调度器
        
        Args:
            max_workers: 并行模式下的最大工作线程数
            config: 配置字典
        """
        self.max_workers = max_workers
        self.config = config or {}
        self._active_jobs: Dict[int, threading.Event] = {}  # job_id -> cancel_event
        self._progress_callbacks: Dict[int, Callable] = {}  # job_id -> callback
        # 线程锁 - 保护 _active_jobs 和 _progress_callbacks 的并发访问
        self._jobs_lock = threading.Lock()
        self._callbacks_lock = threading.Lock()
    
    def submit_job(
        self,
        name: str,
        targets: List[Dict[str, Any]],
        mode: EvaluationMode = EvaluationMode.PARALLEL,
        priority: int = 5,
        config: Dict[str, Any] = None
    ) -> int:
        """
        提交多靶点评估任务
        
        Args:
            name: 任务名称
            targets: 靶点列表，每个靶点为字典包含 uniprot_id, weight 等
            mode: 评估模式（并行/串行）
            priority: 优先级（1-10）
            config: 任务配置
            
        Returns:
            job_id: 任务ID
        """
        config = config or {}
        
        with get_session() as session:
            # 创建任务
            job = MultiTargetJob(
                name=name,
                target_count=len(targets),
                evaluation_mode=mode.value,
                priority=priority,
                config=config,
                status='pending'
            )
            session.add(job)
            session.flush()
            job_id = job.job_id
            
            # 创建靶点记录
            for idx, target_data in enumerate(targets):
                target = Target(
                    job_id=job_id,
                    target_index=idx,
                    uniprot_id=target_data['uniprot_id'],
                    protein_name=target_data.get('protein_name'),
                    gene_name=target_data.get('gene_name'),
                    structure_source=target_data.get('structure_source', 'alphafold'),
                    structure_id=target_data.get('structure_id'),
                    weight=target_data.get('weight', 1.0),
                    status='pending'
                )
                session.add(target)
            
            session.commit()
        
        logger.info(f"多靶点任务已提交: job_id={job_id}, targets={len(targets)}, mode={mode.value}")
        return job_id
    
    def start_job(self, job_id: int, progress_callback: Callable = None) -> bool:
        """
        启动多靶点评估任务
        
        Args:
            job_id: 任务ID
            progress_callback: 进度回调函数，接收 (job_id, progress, status) 参数
            
        Returns:
            bool: 是否成功启动
        """
        # 检查是否已有相同任务在运行
        with self._jobs_lock:
            logger.info(f"尝试启动任务 {job_id}, 当前活动任务: {list(self._active_jobs.keys())}")
            if job_id in self._active_jobs:
                logger.warning(f"任务 {job_id} 已在运行中")
                return False

            # 注册取消事件和回调
            cancel_event = threading.Event()
            self._active_jobs[job_id] = cancel_event
            logger.info(f"任务 {job_id} 已注册到活动任务列表")
        
        if progress_callback:
            with self._callbacks_lock:
                self._progress_callbacks[job_id] = progress_callback
        
        # 在后台线程启动任务
        thread = threading.Thread(
            target=self._execute_job,
            args=(job_id, cancel_event),
            daemon=True
        )
        thread.start()
        
        logger.info(f"任务 {job_id} 已启动")
        return True
    
    def _execute_job(self, job_id: int, cancel_event: threading.Event):
        """执行任务的主逻辑"""
        try:
            with get_session() as session:
                job = session.get(MultiTargetJob, job_id)
                if not job:
                    logger.error(f"任务 {job_id} 不存在")
                    return
                
                # 更新状态
                job.status = 'processing'
                job.started_at = datetime.now()
                session.commit()
                
                # 获取所有靶点
                targets = session.query(Target).filter_by(job_id=job_id).all()
                
                # 根据模式选择执行策略
                if job.evaluation_mode == EvaluationMode.PARALLEL.value:
                    self._execute_parallel(job_id, targets, cancel_event)
                else:
                    self._execute_sequential(job_id, targets, cancel_event, session)
                
                # 检查是否有取消请求
                if cancel_event.is_set():
                    job.status = 'paused' if job.status == 'processing' else 'failed'
                    logger.info(f"任务 {job_id} 已取消")
                else:
                    # 所有靶点评估完成，开始后处理
                    self._update_progress(job_id, 95, f"靶点评估完成，正在分析相互作用...")
                    logger.info(f"任务 {job_id} 靶点评估完成，开始后处理")

                    # 自动生成报告
                    try:
                        self._generate_report(job_id, session=session)
                    except Exception as report_err:
                        logger.error(f"生成报告失败: {report_err}")

                    # 自动分析靶点相互作用
                    try:
                        self._analyze_interactions(job_id)
                    except Exception as interaction_err:
                        logger.error(f"分析相互作用失败: {interaction_err}")

                    # 完成
                    job.status = 'completed'
                    job.completed_at = datetime.now()
                    logger.info(f"任务 {job_id} 已完成")
                    self._update_progress(job_id, 100, f"已完成 {len(targets)}/{len(targets)}")
                
                session.commit()
                
        except Exception as e:
            logger.error(f"任务 {job_id} 执行失败: {e}")
            with get_session() as session:
                job = session.get(MultiTargetJob, job_id)
                if job:
                    job.status = 'failed'
                    job.completed_at = datetime.now()
                    session.commit()
        finally:
            # 清理 - 使用锁保护
            with self._jobs_lock:
                self._active_jobs.pop(job_id, None)
            with self._callbacks_lock:
                self._progress_callbacks.pop(job_id, None)
    
    def _execute_parallel(
        self,
        job_id: int,
        targets: List[Target],
        cancel_event: threading.Event
    ):
        """并行执行模式 - 每个工作线程使用独立的 session"""
        logger.info(f"任务 {job_id} 使用并行模式，max_workers={self.max_workers}")
        
        completed = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_target = {
                executor.submit(self._evaluate_single_target, target.target_id, cancel_event): target
                for target in targets
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_target):
                if cancel_event.is_set():
                    executor.shutdown(wait=False)
                    break
                
                target = future_to_target[future]
                try:
                    success = future.result()
                    if success:
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"靶点 {target.target_id} 评估失败: {e}")
                    failed += 1
                
                # 更新进度
                progress = int(((completed + failed) / len(targets)) * 100)
                self._update_progress(job_id, progress, f"已完成 {completed}/{len(targets)}")
    
    def _execute_sequential(
        self,
        job_id: int,
        targets: List[Target],
        cancel_event: threading.Event,
        session
    ):
        """串行执行模式"""
        logger.info(f"任务 {job_id} 使用串行模式")
        
        for idx, target in enumerate(targets):
            if cancel_event.is_set():
                break
            
            # 更新靶点状态
            target.status = 'processing'
            target.started_at = datetime.now()
            session.commit()
            
            # 执行评估
            try:
                success = self._evaluate_single_target(target.target_id, cancel_event)
                target.status = 'completed' if success else 'failed'
            except Exception as e:
                logger.error(f"靶点 {target.target_id} 评估异常: {e}")
                target.status = 'failed'
                target.error_message = str(e)
            
            target.completed_at = datetime.now()
            session.commit()
            
            # 更新进度
            progress = int(((idx + 1) / len(targets)) * 100)
            self._update_progress(job_id, progress, f"进度 {idx + 1}/{len(targets)}")
    
    def _evaluate_single_target(
        self,
        target_id: int,
        cancel_event: threading.Event
    ) -> bool:
        """
        评估单个靶点
        
        Args:
            target_id: 靶点ID
            cancel_event: 取消事件
            
        Returns:
            bool: 是否成功
        """
        if cancel_event.is_set():
            return False

        try:
            with get_session() as session:
                target = session.query(Target).options(joinedload(Target.job)).filter_by(target_id=target_id).first()
                if not target:
                    return False

                # Get job config and merge with default config
                job_config = {}
                if target.job and target.job.config:
                    job_config = target.job.config

                # Merge configs - job config takes precedence
                worker_config = {**self.config, **job_config}

                # Priority: single_template (per-protein eval) takes precedence over template (batch/interaction)
                # single_template contains the template content for individual protein evaluation
                if 'single_template' in worker_config:
                    template_value = worker_config['single_template']
                    if '\n' in template_value:
                        # Content is directly in single_template
                        worker_config['custom_template'] = template_value
                        logger.info(f"Using single_template content for per-protein eval (length: {len(template_value)})")
                    else:
                        # It's a template name - look up in database
                        try:
                            from src.database import get_single_templates
                            all_templates = get_single_templates()
                            template_obj = next((t for t in all_templates if t.name == template_value or t.name_en == template_value), None)
                            if template_obj:
                                worker_config['custom_template'] = template_obj.content
                                logger.info(f"Using single_template from database: {template_value}")
                            else:
                                logger.info(f"Single template '{template_value}' not found")
                        except Exception as e:
                            logger.warning(f"Failed to get single_template: {e}")

                # template is used for batch/interaction analysis (if not already set by single_template)
                if 'template' in worker_config and 'custom_template' not in worker_config:
                    template_value = worker_config['template']
                    if '\n' in template_value:
                        worker_config['custom_template'] = template_value
                        worker_config['batch_template'] = template_value
                        logger.info(f"Using template content (length: {len(template_value)})")
                    else:
                        # Template name - look up in database
                        try:
                            from src.database import get_all_prompt_templates
                            all_templates = get_all_prompt_templates()
                            template_obj = next((t for t in all_templates if t.name == template_value or t.name_en == template_value), None)
                            if template_obj:
                                worker_config['custom_template'] = template_obj.content
                                worker_config['batch_template'] = template_obj.content
                                logger.info(f"Using template from database: {template_value}")
                        except Exception as e:
                            logger.warning(f"Failed to get template from database: {e}")
                elif 'template' in worker_config:
                    # template exists but custom_template already set from single_template
                    # Store template as batch_template for interaction analysis
                    template_value = worker_config['template']
                    if '\n' in template_value:
                        worker_config['batch_template'] = template_value
                        logger.info(f"Storing template as batch_template (length: {len(template_value)})")

                # 这里调用实际的评估逻辑
                from src.evaluation_worker import EvaluationWorker
                worker = EvaluationWorker(worker_config)
                
                # 创建单靶点评估记录
                eval_record = ProteinEvaluation(
                    uniprot_id=target.uniprot_id,
                    evaluation_status='processing'
                )
                session.add(eval_record)
                session.flush()
                
                # 关联到多靶点记录
                target.evaluation_id = eval_record.id
                target.status = 'processing'
                target.started_at = datetime.now()
                session.commit()
                
                # 执行评估
                results = worker.evaluate(
                    eval_record.id,
                    target.uniprot_id,
                    progress_callback=None
                )
                
                # 保存评估结果到数据库
                if results.get('success'):
                    target.status = 'completed'
                    eval_record.evaluation_status = 'completed'
                    
                    # 保存 PDB 数据
                    if results.get('pdb_data'):
                        eval_record.pdb_data = results['pdb_data']

                    # 保存 AI 分析结果（中文）
                    if results.get('ai_analysis'):
                        eval_record.ai_analysis = results['ai_analysis']
                        # 保存 AI prompt
                        if results['ai_analysis'].get('prompt'):
                            eval_record.ai_prompt = results['ai_analysis']['prompt']

                    # 保存 AI 分析结果（英文）
                    if results.get('ai_analysis_en'):
                        eval_record.ai_analysis_en = results['ai_analysis_en']

                    # 保存 BLAST 结果
                    if results.get('blast_results'):
                        eval_record.blast_results = results['blast_results']
                    
                    # 保存 UniProt 数据
                    if results.get('uniprot_data'):
                        eval_record.uniprot_data = results['uniprot_data']
                else:
                    target.status = 'failed'
                    target.error_message = results.get('error', '未知错误')
                    eval_record.evaluation_status = 'failed'
                    if results.get('error'):
                        eval_record.error_message = results['error']
                
                target.completed_at = datetime.now()
                eval_record.completed_at = datetime.now()
                session.commit()
                
                return results.get('success', False)
                
        except Exception as e:
            logger.error(f"评估靶点 {target_id} 失败: {e}")
            with get_session() as session:
                target = session.get(Target, target_id)
                if target:
                    target.status = 'failed'
                    target.error_message = str(e)
                    target.completed_at = datetime.now()
                    session.commit()
            return False
    
    def _update_progress(self, job_id: int, progress: int, message: str):
        """更新进度"""
        # 更新数据库
        with get_session() as session:
            job = session.get(MultiTargetJob, job_id)
            if job:
                job.config = {**(job.config or {}), 'progress': progress, 'message': message}
                session.commit()
        
        # 调用回调 - 使用锁保护
        with self._callbacks_lock:
            callback = self._progress_callbacks.get(job_id)
        if callback:
            try:
                callback(job_id, progress, message)
            except Exception as e:
                logger.error(f"进度回调失败: {e}")
        
        logger.debug(f"任务 {job_id} 进度: {progress}% - {message}")
    
    def _analyze_interactions(self, job_id: int):
        """
        自动分析靶点间的相互作用

        Args:
            job_id: 任务ID
        """
        try:
            from src.target_interaction_analyzer import TargetInteractionAnalyzer

            logger.info(f"开始分析任务 {job_id} 的靶点相互作用")

            analyzer = TargetInteractionAnalyzer()
            relationships = analyzer.analyze_job(job_id)

            logger.info(f"任务 {job_id} 相互作用分析完成，共 {len(relationships)} 条关系")

        except Exception as e:
            logger.error(f"分析相互作用失败: {e}")
            import traceback
            traceback.print_exc()

        # Also run chain-level interaction analysis and store in job
        try:
            from src.chain_interaction_analyzer import analyze_chain_interactions
            from src.database import get_session

            logger.info(f"开始分析任务 {job_id} 的链级相互作用")

            # Get input_uniprot_ids from targets and collect PDB IDs for progress
            input_uniprot_ids = []
            pdb_ids = []  # Collect PDB IDs for progress reporting
            with get_session() as session:
                from src.multi_target_models import MultiTargetJob, Target
                from sqlalchemy.orm import joinedload

                job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
                if job:
                    # Use eager loading for evaluation relationship
                    targets = session.query(Target).options(joinedload(Target.evaluation)).filter_by(job_id=job_id).all()
                    input_uniprot_ids = [t.uniprot_id for t in targets if t.uniprot_id]
                    # Collect all PDB IDs for progress display
                    for target in targets:
                        if target.evaluation and target.evaluation.pdb_data:
                            structures = target.evaluation.pdb_data.get('structures', [])
                            for struct in structures:
                                pdb_id = struct.get('pdb_id', '')
                                if pdb_id and pdb_id not in pdb_ids:
                                    pdb_ids.append(pdb_id)
                else:
                    logger.warning(f"任务 {job_id} 不存在，无法进行链级相互作用分析")

            # Create progress callback for scrolling PDB status
            total_pdbs = len(pdb_ids)
            animation_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']  # Spinning chars
            frame_idx = [0]  # Use list to allow modification in closure

            def progress_callback(current_pdb, total, idx):
                frame = animation_frames[frame_idx[0] % len(animation_frames)]
                frame_idx[0] += 1
                progress_pct = int(((idx + 1) / total) * 100) if total > 0 else 100
                # Scroll through PDB IDs for effect - show current one
                display_pdb = current_pdb[:8] if len(current_pdb) > 8 else current_pdb
                message = f"分析PDB {frame} {progress_pct}% ({idx + 1}/{total}) - {display_pdb}..."
                self._update_progress(job_id, 95, message)

            # Run chain interaction analysis (creates its own session internally)
            if input_uniprot_ids:
                analyze_chain_interactions(job_id, input_uniprot_ids, progress_callback)
                logger.info(f"任务 {job_id} 链级相互作用分析完成，共 {len(input_uniprot_ids)} 个靶点")
            else:
                logger.warning(f"任务 {job_id} 没有有效的靶点，跳过链级相互作用分析")

        except Exception as e:
            logger.error(f"链级相互作用分析失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_report(self, job_id: int, session=None):
        """自动生成任务报告"""
        try:
            from src.multi_target_report_generator import MultiTargetReportGenerator
            from datetime import datetime

            generator = MultiTargetReportGenerator()

            close_session = False
            if session is None:
                session = get_session()
                close_session = True

            try:
                job = session.get(MultiTargetJob, job_id)
                if not job:
                    logger.warning(f"任务 {job_id} 不存在，无法生成报告")
                    return
                
                # 获取所有靶点数据
                targets = session.query(Target).filter_by(job_id=job_id).all()

                # 构建靶点数据列表
                targets_data = []
                for target in targets:
                    # 优先使用 Target 表中的基本信息（来自 submit_job 时传入的数据）
                    target_info = {
                        'target_id': target.target_id,
                        'uniprot_id': target.uniprot_id,
                        'protein_name': target.protein_name,
                        'gene_name': target.gene_name,
                        'structure_source': target.structure_source,
                        'structure_id': target.structure_id,
                        'weight': target.weight,
                        'status': target.status,
                        'error_message': target.error_message,
                        'started_at': target.started_at.isoformat() if target.started_at else None,
                        'completed_at': target.completed_at.isoformat() if target.completed_at else None,
                    }

                    # 如果有评估记录，获取完整评估详情
                    if target.evaluation_id:
                        eval_record = session.get(ProteinEvaluation, target.evaluation_id)
                        if eval_record:
                            # 使用 eval_record 中的数据覆盖/补充 Target 表数据
                            # 确保 protein_name 和 gene_name 有值
                            if not target_info['protein_name'] and eval_record.protein_name:
                                target_info['protein_name'] = eval_record.protein_name
                            if not target_info['gene_name'] and eval_record.gene_name:
                                target_info['gene_name'] = eval_record.gene_name

                            # 从 JSON 字段提取完整数据
                            pdb_data = eval_record.pdb_data or {}
                            ai_analysis = eval_record.ai_analysis or {}
                            uniprot_data = eval_record.uniprot_data or {}

                            # 构建完整的评估数据
                            target_info['evaluation'] = {
                                # 基本状态
                                'id': eval_record.id,
                                'status': eval_record.evaluation_status,
                                'progress': eval_record.progress,

                                # PDB 数据（完整）
                                'pdb_data': pdb_data,
                                'pdb_structures': pdb_data.get('structures', []) if isinstance(pdb_data, dict) else [],
                                'pdb_count': len(pdb_data.get('structures', [])) if isinstance(pdb_data, dict) else 0,

                                # AI 分析（完整）
                                'ai_analysis': ai_analysis,
                                'ai_prompt': eval_record.ai_prompt,
                                'quality_score': ai_analysis.get('quality_score', 0) if isinstance(ai_analysis, dict) else 0,
                                'sequence_coverage': ai_analysis.get('sequence_coverage', 0) if isinstance(ai_analysis, dict) else 0,
                                'quality_assessment': ai_analysis.get('quality_assessment', {}) if isinstance(ai_analysis, dict) else {},
                                'functional_sites': ai_analysis.get('functional_sites', []) if isinstance(ai_analysis, dict) else [],
                                'drug_target_potential': ai_analysis.get('drug_target_potential', {}) if isinstance(ai_analysis, dict) else {},

                                # UniProt 数据
                                'uniprot_data': uniprot_data,
                                'sequence_length': uniprot_data.get('sequence_length', 0) if isinstance(uniprot_data, dict) else 0,
                                'organism': uniprot_data.get('organism', '') if isinstance(uniprot_data, dict) else '',

                                # 其他评估数据
                                'blast_results': eval_record.blast_results,
                                'logs': eval_record.logs,
                                'error_message': eval_record.error_message,
                                'started_at': eval_record.started_at.isoformat() if eval_record.started_at else None,
                                'completed_at': eval_record.completed_at.isoformat() if eval_record.completed_at else None,
                            }

                            # 添加评估分数（用于统计）
                            if isinstance(ai_analysis, dict) and ai_analysis.get('quality_score'):
                                target_info['evaluation_score'] = ai_analysis['quality_score']

                    targets_data.append(target_info)
                
                # 生成 Markdown 报告
                job_data = {
                    'job_id': job.job_id,
                    'name': job.name,
                    'status': job.status,
                    'target_count': job.target_count,
                    'evaluation_mode': job.evaluation_mode,
                    'created_at': job.created_at.isoformat() if job.created_at else None,
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                }
                
                # 生成报告内容 - 使用完善的报告生成器
                try:
                    from src.multi_target_report_generator import MultiTargetReportGenerator
                    report_gen = MultiTargetReportGenerator()
                    template = job.config.get('template', 'full') if job.config else 'full'
                    result = report_gen.generate_multi_target_report(
                        job_data=job_data,
                        targets_data=targets_data,
                        template=template,
                        format='markdown'
                    )
                    report_content = result.get('content', '')
                    if not report_content:
                        # 如果生成器返回空内容，使用简单方法
                        report_content = self._build_report_markdown(job_data, targets_data)
                except Exception as gen_err:
                    logger.warning(f"使用报告生成器失败: {gen_err}，使用简单方法")
                    report_content = self._build_report_markdown(job_data, targets_data)

                # 翻译报告为英文
                report_content_en = self._translate_report(report_content)

                # 保存报告到数据库
                job.report_content = report_content
                job.report_content_en = report_content_en
                job.report_format = 'markdown'
                job.report_generated_at = datetime.now()
                session.commit()

                logger.info(f"任务 {job_id} 报告已生成，中文长度: {len(report_content)} 字符，英文长度: {len(report_content_en)} 字符")
            finally:
                if close_session:
                    session.close()

        except Exception as e:
            logger.error(f"生成报告失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _build_report_markdown(self, job_data: Dict, targets_data: List[Dict]) -> str:
        """构建 Markdown 格式报告"""
        from datetime import datetime
        
        lines = []
        lines.append(f"# {job_data['name']} - 评估报告\n")
        
        # 基本信息
        lines.append("## 基本信息\n")
        lines.append(f"- **任务ID**: {job_data['job_id']}")
        lines.append(f"- **任务名称**: {job_data['name']}")
        lines.append(f"- **状态**: {job_data['status']}")
        lines.append(f"- **靶点数量**: {job_data['target_count']}")
        lines.append(f"- **评估模式**: {job_data['evaluation_mode']}")
        
        if job_data.get('created_at'):
            lines.append(f"- **创建时间**: {job_data['created_at']}")
        if job_data.get('completed_at'):
            lines.append(f"- **完成时间**: {job_data['completed_at']}")
        
        lines.append("")
        
        # 统计信息
        completed = sum(1 for t in targets_data if t.get('status') == 'completed')
        failed = sum(1 for t in targets_data if t.get('status') == 'failed')
        pending = sum(1 for t in targets_data if t.get('status') in ['pending', 'processing'])
        
        lines.append("## 统计信息\n")
        lines.append(f"| 状态 | 数量 |")
        lines.append(f"|------|------|")
        lines.append(f"| ✅ 完成 | {completed} |")
        lines.append(f"| ❌ 失败 | {failed} |")
        lines.append(f"| ⏳ 进行中 | {pending} |")
        lines.append("")
        
        # 靶点详情
        lines.append("## 靶点详情\n")
        lines.append("| UniProt ID | 状态 | 质量分数 | 结构数 |")
        lines.append(f"|------------|------|----------|--------|")
        
        for target in targets_data:
            status = target.get('status', 'unknown')
            status_emoji = {
                'completed': '✅',
                'failed': '❌',
                'processing': '⏳',
                'pending': '⏳'
            }.get(status, '❓')
            
            eval_data = target.get('evaluation', {})
            quality = eval_data.get('quality_score', 'N/A')
            pdb_count = eval_data.get('pdb_count', 0)
            
            lines.append(f"| {target['uniprot_id']} | {status_emoji} {status} | {quality} | {pdb_count} |")
        
        lines.append("")
        lines.append("---\n")
        lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")

        return "\n".join(lines)

    def _translate_report(self, content: str) -> str:
        """Translate report content from Chinese to English.

        Args:
            content: Chinese report content

        Returns:
            English report content
        """
        if not content:
            return ''

        # 检查是否主要是中文内容
        chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
        total_chars = len(content.replace(' ', '').replace('\n', ''))
        chinese_ratio = chinese_chars / max(total_chars, 1)

        # 如果中文字符比例低于10%，认为已经是英文
        if chinese_ratio < 0.1:
            return content

        try:
            # 使用 AI 进行翻译
            from src.ai_client_wrapper import get_ai_client_wrapper

            ai_wrapper = get_ai_client_wrapper()
            if not ai_wrapper or not ai_wrapper.is_available():
                logger.warning("AI client not available for translation, returning original content")
                return content

            # 构建翻译提示
            system_message = """You are a professional scientific translator specializing in bioinformatics and protein science.
Translate the following report from Chinese to English. Maintain the markdown formatting, including headers, lists, tables, and code blocks.
Keep scientific terminology accurate and consistent. Use British/American English spelling consistently.
Do not add, omit, or paraphrase any content - translate accurately."""

            result = ai_wrapper.analyze(
                prompt=f"Translate the following Chinese report to English:\n\n{content}",
                system_message=system_message,
                max_tokens=16000,
                temperature=0.3
            )

            if result.get('success') and result.get('analysis'):
                translated = result['analysis']
                logger.info(f"Report translated successfully, length: {len(translated)} characters")
                return translated
            else:
                logger.warning(f"Translation failed: {result.get('error', 'Unknown error')}")
                return content

        except Exception as e:
            logger.error(f"Translation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return content
    
    def pause_job(self, job_id: int) -> bool:
        """暂停任务"""
        with self._jobs_lock:
            if job_id in self._active_jobs:
                self._active_jobs[job_id].set()
                logger.info(f"任务 {job_id} 暂停请求已发送")
                return True
        return False
    
    def resume_job(self, job_id: int) -> bool:
        """恢复任务"""
        with get_session() as session:
            job = session.get(MultiTargetJob, job_id)
            if not job:
                logger.warning(f"任务 {job_id} 不存在，无法恢复")
                return False
            
            if job.status != 'paused':
                logger.warning(f"任务 {job_id} 状态为 {job.status}，不是暂停状态")
                return False
            
            # 清除取消事件 - 使用锁保护
            with self._jobs_lock:
                if job_id in self._active_jobs:
                    del self._active_jobs[job_id]
            
            # 启动任务执行
            return self.start_job(job_id)
    
    def cancel_job(self, job_id: int) -> bool:
        """取消任务"""
        with get_session() as session:
            job = session.get(MultiTargetJob, job_id)
            if not job:
                return False
            
            # 设置取消事件 - 使用锁保护
            with self._jobs_lock:
                if job_id in self._active_jobs:
                    self._active_jobs[job_id].set()
            
            # 更新任务状态
            job.status = 'failed'
            session.commit()
            
            logger.info(f"任务 {job_id} 已取消")
            return True
    
    def restart_job(self, job_id: int, reset_failed_only: bool = False, clear_evaluations: bool = True) -> bool:
        """重启任务

        Args:
            job_id: 任务ID
            reset_failed_only: 是否只重置失败的靶点
            clear_evaluations: 是否清除旧的 evaluation 数据（默认 True）
        """
        with get_session() as session:
            job = session.get(MultiTargetJob, job_id)
            if not job:
                logger.warning(f"任务 {job_id} 不存在")
                return False

            if job.status not in ['completed', 'failed']:
                logger.warning(f"任务 {job_id} 状态为 {job.status}，不能重启")
                return False

            # 获取所有靶点
            targets = session.query(Target).filter_by(job_id=job_id).all()

            # 收集要删除的旧 evaluation IDs
            old_eval_ids = []
            for target in targets:
                if target.evaluation_id:
                    old_eval_ids.append(target.evaluation_id)

            # 清除旧的 evaluation 数据
            if clear_evaluations and old_eval_ids:
                deleted_count = session.query(ProteinEvaluation).filter(
                    ProteinEvaluation.id.in_(old_eval_ids)
                ).delete(synchronize_session=False)
                logger.info(f"已删除 {deleted_count} 个旧的 evaluation 记录")

            # 重置靶点状态
            for target in targets:
                if reset_failed_only:
                    # 只重置失败的靶点
                    if target.status == 'failed':
                        target.status = 'pending'
                        target.error_message = None
                        if clear_evaluations:
                            target.evaluation_id = None
                else:
                    # 重置所有靶点
                    target.status = 'pending'
                    target.error_message = None
                    target.started_at = None
                    target.completed_at = None
                    target.evaluation_id = None

            # 清除任务的 AI 分析和报告（因为会重新生成）
            job.interaction_ai_analysis = None
            job.interaction_ai_analysis_en = None
            job.report_content = None
            job.report_content_en = None
            job.report_generated_at = None

            # 重置任务状态
            job.status = 'pending'
            job.started_at = None
            job.completed_at = None

            session.commit()

            logger.info(f"任务 {job_id} 已重启 (reset_failed_only={reset_failed_only}, clear_evaluations={clear_evaluations})")
            return True
    
    def get_job_status(self, job_id: int) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with get_session() as session:
            job = session.get(MultiTargetJob, job_id)
            if not job:
                return None
            
            # 获取靶点统计
            targets = session.query(Target).filter_by(job_id=job_id).all()
            status_count = {}
            for t in targets:
                status_count[t.status] = status_count.get(t.status, 0) + 1
            
            return {
                'job_id': job.job_id,
                'name': job.name,
                'status': job.status,
                'target_count': job.target_count,
                'evaluation_mode': job.evaluation_mode,
                'progress': job.config.get('progress', 0) if job.config else 0,
                'message': job.config.get('message', '') if job.config else '',
                'status_summary': status_count,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None
            }
    
    def get_job_progress(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        获取任务进度详情
        
        Args:
            job_id: 任务ID
            
        Returns:
            进度信息字典
        """
        with get_session() as session:
            job = session.get(MultiTargetJob, job_id)
            if not job:
                return None

            # 获取所有靶点状态
            targets = session.query(Target).filter_by(job_id=job_id).all()
            
            total = len(targets)
            completed = sum(1 for t in targets if t.status == 'completed')
            failed = sum(1 for t in targets if t.status == 'failed')
            processing = sum(1 for t in targets if t.status == 'processing')
            pending = sum(1 for t in targets if t.status == 'pending')
            
            progress_percent = (completed / total * 100) if total > 0 else 0
            
            return {
                'job_id': job_id,
                'status': job.status,
                'total': total,
                'total_targets': total,
                'completed': completed,
                'failed': failed,
                'processing': processing,
                'pending': pending,
                'progress': round(progress_percent, 1),
                'message': job.config.get('message', '') if job.config else '',
            }
    
    def get_pending_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取待处理的任务列表"""
        with get_session() as session:
            jobs = session.query(MultiTargetJob)\
                .filter_by(status='pending')\
                .order_by(MultiTargetJob.priority.desc(), MultiTargetJob.created_at.asc())\
                .limit(limit)\
                .all()
            return [job.to_dict() for job in jobs]


# 全局调度器实例（线程安全单例）
_scheduler_lock = threading.Lock()
_scheduler: Optional[MultiTargetScheduler] = None


def get_scheduler(max_workers: int = 5, config: Dict[str, Any] = None) -> MultiTargetScheduler:
    """获取全局调度器实例（线程安全单例模式）"""
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            # Double-check inside lock to avoid race on second-plus entrant
            if _scheduler is None:
                _scheduler = MultiTargetScheduler(max_workers=max_workers, config=config)
    return _scheduler


def reset_scheduler() -> None:
    """重置调度器（仅用于测试隔离）"""
    global _scheduler
    with _scheduler_lock:
        _scheduler = None


def submit_multi_target_job(
    name: str,
    targets: List[Dict[str, Any]],
    mode: str = "parallel",
    priority: int = 5,
    config: Dict[str, Any] = None
) -> int:
    """
    便捷函数：提交多靶点任务
    
    Args:
        name: 任务名称
        targets: 靶点列表
        mode: "parallel" 或 "sequential"
        priority: 优先级
        config: 配置
        
    Returns:
        job_id
    """
    scheduler = get_scheduler()
    mode_enum = EvaluationMode.PARALLEL if mode == "parallel" else EvaluationMode.SEQUENTIAL
    job_id = scheduler.submit_job(name, targets, mode_enum, priority, config)
    scheduler.start_job(job_id)
    return job_id


def get_job_progress(job_id: int) -> Optional[Dict[str, Any]]:
    """便捷函数：获取任务进度"""
    scheduler = get_scheduler()
    return scheduler.get_job_status(job_id)
