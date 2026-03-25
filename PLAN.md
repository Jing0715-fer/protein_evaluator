# Protein Evaluator 后续开发方案

## 当前问题总结

1. **任务不自动启动** - 创建任务后停留在 pending 状态
2. **评估报告缺失** - 任务完成后没有生成报告
3. **相互作用分析未完成** - API 存在但无实际计算逻辑
4. **前端结果查看不完善** - JobDetail 页面缺少结果展示

---

## Phase 1: 任务自动启动 (优先级: 🔴 高)

### 目标
创建任务后自动开始运行评估流程

### 实现方案

#### 1.1 修改创建任务 API
文件: `routes/multi_target_v2.py`

```python
@bp.route('', methods=['POST'])
def create_multi_target_job():
    # ... 现有创建逻辑 ...
    
    # 创建成功后自动启动任务
    try:
        scheduler = get_scheduler()
        scheduler.start_job(job_id)
        logger.info(f"任务已自动启动: job_id={job_id}")
    except Exception as e:
        logger.warning(f"自动启动任务失败: {e}")
        # 不影响创建成功，可以手动启动
    
    return jsonify({...}), 201
```

#### 1.2 或添加后台任务调度器
文件: 新建 `src/job_scheduler_daemon.py`

```python
"""
后台任务调度守护进程
自动执行 pending 状态的任务
"""
import threading
import time
from src.database import get_session, MultiTargetJob
from src.multi_target_scheduler import get_scheduler

class JobSchedulerDaemon:
    def __init__(self, check_interval=5):
        self.check_interval = check_interval
        self.running = False
        self.thread = None
    
    def start(self):
        """启动守护进程"""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("任务调度守护进程已启动")
    
    def _run(self):
        """主循环"""
        while self.running:
            try:
                self._check_and_start_pending_jobs()
            except Exception as e:
                logger.error(f"调度循环错误: {e}")
            time.sleep(self.check_interval)
    
    def _check_and_start_pending_jobs(self):
        """检查并启动 pending 任务"""
        with get_session() as session:
            pending_jobs = session.query(MultiTargetJob).filter_by(
                status='pending'
            ).order_by(MultiTargetJob.priority.desc()).all()
            
            for job in pending_jobs:
                try:
                    scheduler = get_scheduler()
                    if scheduler.start_job(job.job_id):
                        logger.info(f"自动启动任务: job_id={job.job_id}")
                except Exception as e:
                    logger.error(f"启动任务失败: job_id={job.job_id}, error={e}")
    
    def stop(self):
        """停止守护进程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

# 全局守护进程实例
_daemon = None

def start_scheduler_daemon():
    """启动调度守护进程"""
    global _daemon
    if _daemon is None:
        _daemon = JobSchedulerDaemon()
        _daemon.start()

def stop_scheduler_daemon():
    """停止调度守护进程"""
    global _daemon
    if _daemon:
        _daemon.stop()
        _daemon = None
```

### 工作量
- 修改创建任务 API: 30 分钟
- 或开发后台调度器: 2-3 小时
- 测试验证: 30 分钟

---

## Phase 2: 评估报告生成 (优先级: 🔴 高)

### 目标
任务完成后自动生成并展示评估报告

### 实现方案

#### 2.1 报告生成服务
文件: `src/report_service.py`

已存在，需要完善以下功能：

1. **单靶点报告** - 蛋白质结构质量分析
2. **多靶点综合报告** - 相互作用分析汇总
3. **报告格式** - Markdown + PDF 导出

#### 2.2 任务完成时自动触发报告生成
修改: `src/multi_target_scheduler.py`

```python
def _execute_job(self, job_id: int, cancel_event: threading.Event):
    """执行任务，完成后生成报告"""
    # ... 现有执行逻辑 ...
    
    # 所有靶点评估完成后生成报告
    try:
        from src.multi_target_report_generator import MultiTargetReportGenerator
        generator = MultiTargetReportGenerator()
        
        report_result = generator.generate_multi_target_report(
            job_data=job_data,
            targets_data=targets_data,
            template='summary',
            format='markdown'
        )
        
        # 保存报告到数据库或文件
        self._save_report(job_id, report_result)
        
    except Exception as e:
        logger.error(f"生成报告失败: job_id={job_id}, error={e}")

def _save_report(self, job_id: int, report_result: dict):
    """保存报告"""
    from src.database import get_session, MultiTargetJob
    
    with get_session() as session:
        job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
        if job:
            job.report_content = report_result['content']
            job.report_format = report_result['format']
            session.commit()
```

#### 2.3 前端报告展示
修改: `frontend/src/pages/JobDetail.tsx`

添加报告查看区域：
- Markdown 渲染报告内容
- PDF 导出按钮
- 报告下载功能

### 工作量
- 完善报告生成逻辑: 2-3 小时
- 数据库添加报告字段: 30 分钟
- 前端报告展示: 2 小时
- 测试验证: 1 小时

---

## Phase 3: 相互作用分析 (优先级: 🟡 中)

### 目标
实现真正的靶点间相互作用计算

### 实现方案

#### 3.1 相互作用分析服务
文件: 新建 `src/interaction_analyzer.py`

```python
"""
靶点间相互作用分析器
计算结构相似度、序列同源性、功能关联性
"""

from typing import List, Dict, Any
import numpy as np
from Bio import pairwise2
from Bio.Seq import Seq

class InteractionAnalyzer:
    """相互作用分析器"""
    
    def analyze_interactions(
        self,
        targets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        分析所有靶点间的相互作用
        
        Args:
            targets: 靶点列表，包含 evaluation 数据
            
        Returns:
            interactions: 相互作用列表
        """
        interactions = []
        
        for i, source in enumerate(targets):
            for j, target in enumerate(targets):
                if i >= j:  # 避免重复计算
                    continue
                
                interaction = self._calculate_interaction(source, target)
                if interaction['score'] > 0.5:  # 只保留显著的相互作用
                    interactions.append(interaction)
        
        return interactions
    
    def _calculate_interaction(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> Dict[str, Any]:
        """计算两个靶点间的相互作用"""
        
        # 1. 结构相似度 (如果有 PDB 结构)
        structure_score = self._calculate_structure_similarity(source, target)
        
        # 2. 序列同源性
        sequence_score = self._calculate_sequence_similarity(source, target)
        
        # 3. 功能关联性 (基于 GO terms 或功能描述)
        function_score = self._calculate_function_similarity(source, target)
        
        # 4. 综合得分
        weights = {'structure': 0.4, 'sequence': 0.4, 'function': 0.2}
        total_score = (
            structure_score * weights['structure'] +
            sequence_score * weights['sequence'] +
            function_score * weights['function']
        )
        
        return {
            'source_uniprot': source['uniprot_id'],
            'target_uniprot': target['uniprot_id'],
            'relationship_type': self._classify_relationship(
                structure_score, sequence_score, function_score
            ),
            'score': round(total_score, 3),
            'details': {
                'structure_similarity': round(structure_score, 3),
                'sequence_similarity': round(sequence_score, 3),
                'function_similarity': round(function_score, 3),
            }
        }
    
    def _calculate_structure_similarity(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> float:
        """计算结构相似度 (使用 TM-score 或 RMSD)"""
        # 简化实现：基于 structure_quality_score 估算
        source_score = source.get('evaluation', {}).get('structure_quality_score', 0)
        target_score = target.get('evaluation', {}).get('structure_quality_score', 0)
        
        # 如果都有高质量结构，认为可能相似
        if source_score > 0.8 and target_score > 0.8:
            return 0.7  # 高相似度
        elif source_score > 0.5 and target_score > 0.5:
            return 0.4  # 中等相似度
        else:
            return 0.1  # 低相似度
    
    def _calculate_sequence_similarity(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> float:
        """计算序列相似度"""
        source_seq = source.get('sequence', '')
        target_seq = target.get('sequence', '')
        
        if not source_seq or not target_seq:
            return 0.0
        
        # 使用 Biopython 进行序列比对
        alignments = pairwise2.align.globalxx(source_seq, target_seq)
        if not alignments:
            return 0.0
        
        best_alignment = alignments[0]
        score = best_alignment[2]
        max_length = max(len(source_seq), len(target_seq))
        
        return score / max_length if max_length > 0 else 0.0
    
    def _calculate_function_similarity(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> float:
        """计算功能相似度"""
        # 基于功能描述的文本相似度
        source_func = source.get('function', '')
        target_func = target.get('function', '')
        
        if not source_func or not target_func:
            return 0.0
        
        # 简化的 Jaccard 相似度
        source_words = set(source_func.lower().split())
        target_words = set(target_func.lower().split())
        
        intersection = source_words & target_words
        union = source_words | target_words
        
        return len(intersection) / len(union) if union else 0.0
    
    def _classify_relationship(
        self,
        structure_score: float,
        sequence_score: float,
        function_score: float
    ) -> str:
        """分类相互作用类型"""
        if structure_score > 0.7 and sequence_score > 0.7:
            return 'homologous'  # 同源蛋白
        elif structure_score > 0.7:
            return 'structural_similar'  # 结构相似
        elif sequence_score > 0.7:
            return 'sequence_similar'  # 序列相似
        elif function_score > 0.5:
            return 'functional_related'  # 功能相关
        else:
            return 'weak_association'  # 弱关联
```

#### 3.2 在任务执行后自动分析
修改: `src/multi_target_scheduler.py`

```python
def _execute_job(self, job_id: int, cancel_event: threading.Event):
    # ... 执行评估 ...
    
    # 生成报告后分析相互作用
    try:
        from src.interaction_analyzer import InteractionAnalyzer
        analyzer = InteractionAnalyzer()
        
        interactions = analyzer.analyze_interactions(targets_data)
        self._save_interactions(job_id, interactions)
        
    except Exception as e:
        logger.error(f"分析相互作用失败: {e}")

def _save_interactions(self, job_id: int, interactions: List[Dict]):
    """保存相互作用到数据库"""
    from src.database import get_session, TargetRelationship
    
    with get_session() as session:
        for interaction in interactions:
            relationship = TargetRelationship(
                job_id=job_id,
                source_target_id=interaction['source_target_id'],
                target_target_id=interaction['target_target_id'],
                relationship_type=interaction['relationship_type'],
                score=interaction['score'],
                metadata=interaction['details']
            )
            session.add(relationship)
        session.commit()
```

#### 3.3 前端相互作用展示
修改: `frontend/src/pages/JobDetail.tsx`

添加相互作用可视化：
- 网络图展示靶点关系
- 表格列出相互作用详情
- 筛选和排序功能

### 工作量
- 开发相互作用分析器: 4-5 小时
- 数据库添加关系表: 1 小时
- 前端可视化: 3-4 小时
- 测试验证: 2 小时

---

## Phase 4: 前端结果查看优化 (优先级: 🟡 中)

### 目标
完善 JobDetail 页面的结果展示

### 实现内容

1. **评估结果卡片**
   - 每个靶点的评估得分
   - PDB 结构质量
   - 功能分析结果

2. **报告预览/下载**
   - Markdown 报告渲染
   - PDF 导出按钮
   - 报告分享功能

3. **相互作用可视化**
   - 靶点关系网络图
   - 相互作用强度热力图
   - 详情弹窗

### 工作量
- 结果卡片: 2 小时
- 报告展示: 2 小时
- 相互作用可视化: 3 小时
- 测试: 1 小时

---

## 总体时间估算

| Phase | 功能 | 工作量 | 优先级 |
|-------|------|--------|--------|
| Phase 1 | 任务自动启动 | 3-4 小时 | 🔴 高 |
| Phase 2 | 评估报告生成 | 5-6 小时 | 🔴 高 |
| Phase 3 | 相互作用分析 | 10-12 小时 | 🟡 中 |
| Phase 4 | 前端结果展示 | 8 小时 | 🟡 中 |
| **总计** | | **26-30 小时** | |

---

## 建议执行顺序

1. **立即执行**: Phase 1 (任务自动启动) - 解决当前阻塞问题
2. **本周完成**: Phase 2 (评估报告) - 核心功能闭环
3. **下周开发**: Phase 3 (相互作用分析) - 增值功能
4. **后续优化**: Phase 4 (前端展示) - 体验提升

需要我立即开始 Phase 1 的开发吗？