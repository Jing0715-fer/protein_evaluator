"""
多靶点评估数据模型

本模块定义了多靶点蛋白质评估系统的核心数据模型，支持：
- 多靶点任务管理 (MultiTargetJob)
- 单个靶点跟踪 (Target)
- 靶点间关系分析 (TargetRelationship)

设计原则：
1. 支持并行和串行两种评估模式
2. 完整的任务生命周期管理
3. 灵活的权重配置支持结果加权
4. 靶点间关系追踪（序列相似性、结构相似性、相互作用）
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.models import Base


class MultiTargetJob(Base):
    """多靶点评估任务主表

    表示一个多靶点评估任务的完整生命周期，支持并行和串行两种评估模式。
    一个任务包含多个 Target 记录，通过 target_count 跟踪总数。

    Attributes:
        job_id: 任务唯一标识
        name: 任务名称（用于展示）
        description: 任务描述
        status: 任务状态（pending/processing/completed/failed/paused）
        target_count: 关联的靶点数量
        evaluation_mode: 评估模式（parallel-并行/sequential-串行）
        priority: 任务优先级（1-10，数值越大优先级越高）
        tags: 标签（JSON格式，支持自定义标签）
        config: 配置参数（JSON格式，存储评估相关配置）
        created_by: 创建者
        created_at: 创建时间
        started_at: 开始执行时间
        completed_at: 完成时间

    Relationships:
        targets: 关联的 Target 对象列表
        relationships: 关联的 TargetRelationship 对象列表
    """
    __tablename__ = "multi_target_jobs"
    __table_args__ = (
        # 状态索引，用于快速查询特定状态的任务
        Index('idx_mtj_status', 'status'),
        # 优先级+状态复合索引，用于优先级队列查询
        Index('idx_mtj_priority_status', 'priority', 'status'),
        # 创建者索引
        Index('idx_mtj_created_by', 'created_by'),
        # 创建时间索引，用于排序
        Index('idx_mtj_created_at', 'created_at'),
    )

    job_id = Column(Integer, primary_key=True, autoincrement=True)

    # 基本信息
    name = Column(String(200), nullable=False)
    description = Column(Text)

    # 任务状态: pending-等待中, processing-执行中, completed-已完成, failed-失败, paused-已暂停
    status = Column(String(20), default='pending', nullable=False)

    # 任务配置
    target_count = Column(Integer, default=0, nullable=False)  # 靶点数量
    evaluation_mode = Column(String(20), default='parallel')  # parallel-并行, sequential-串行
    priority = Column(Integer, default=5)  # 优先级 1-10，数值越大优先级越高

    # JSON 字段
    tags = Column(JSON, default=dict)  # 标签，如 {"project": "cancer", "batch": "2024-03"}
    config = Column(JSON, default=dict)  # 配置参数，如 {"timeout": 3600, "max_retries": 3}

    # 创建者和时间戳
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # AI 分析结果（双语支持）
    interaction_ai_analysis = Column(Text)  # 相互作用 AI 分析结果（中文）
    interaction_ai_analysis_en = Column(Text)  # 相互作用 AI 分析结果（英文）
    interaction_prompt = Column(Text)  # 相互作用 AI 分析使用的 Prompt（中文）
    interaction_prompt_en = Column(Text)  # 相互作用 AI 分析使用的 Prompt（英文）

    # 链级相互作用分析结果（JSON格式，存储直接/间接互作分析）
    chain_interaction_analysis = Column(JSON, default=dict)

    # 报告相关字段
    report_content = Column(Text)  # 报告内容（Markdown格式，中文）
    report_content_en = Column(Text)  # 报告内容（英文）
    report_format = Column(String(20), default='markdown')  # 报告格式
    report_generated_at = Column(DateTime)  # 报告生成时间

    # 关系定义
    targets = relationship(
        "Target",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Target.target_index"
    )
    relationships = relationship(
        "TargetRelationship",
        back_populates="job",
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        """将模型实例转换为字典

        Returns:
            dict: 包含所有字段值的字典，日期时间格式化为 ISO 8601 字符串
        """
        return {
            'job_id': self.job_id,
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'target_count': self.target_count,
            'evaluation_mode': self.evaluation_mode,
            'priority': self.priority,
            'tags': self.tags,
            'config': self.config,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            # 报告相关字段
            'report_content': self.report_content,
            'report_content_en': self.report_content_en,
            'report_format': self.report_format,
            'report_generated_at': self.report_generated_at.isoformat() if self.report_generated_at else None,
            # AI 分析双语字段
            'interaction_ai_analysis': self.interaction_ai_analysis,
            'interaction_ai_analysis_en': self.interaction_ai_analysis_en,
            'interaction_prompt': self.interaction_prompt,
            'interaction_prompt_en': self.interaction_prompt_en,
            # 链级相互作用分析
            'chain_interaction_analysis': self.chain_interaction_analysis,
        }

    def update_target_count(self):
        """更新靶点数量（基于关联的 targets）"""
        self.target_count = len(self.targets) if self.targets else 0

    def get_completed_count(self):
        """获取已完成的靶点数量"""
        if not self.targets:
            return 0
        return sum(1 for t in self.targets if t.status == 'completed')

    def get_progress_percentage(self):
        """获取任务进度百分比"""
        if self.target_count == 0:
            return 0
        completed = self.get_completed_count()
        return int((completed / self.target_count) * 100)


class Target(Base):
    """单个靶点表

    表示多靶点评估任务中的一个靶点。每个 Target 关联到一个 MultiTargetJob，
    并可选关联到一个 ProteinEvaluation（单靶点评估记录）。

    Attributes:
        target_id: 靶点唯一标识
        job_id: 关联的多靶点任务ID
        target_index: 靶点在任务中的序号（用于排序）
        uniprot_id: UniProt ID
        protein_name: 蛋白质名称
        gene_name: 基因名称
        structure_source: 结构数据来源（alphafold/pdb/emdb）
        structure_id: 结构ID（PDB ID 或 AlphaFold 版本）
        weight: 权重（用于结果加权计算，默认1.0）
        status: 靶点状态（pending/processing/completed/failed/skipped）
        evaluation_id: 关联的单靶点评估ID
        sequence_data: 序列数据缓存
        structure_data: 结构数据缓存
        error_message: 错误信息
        started_at: 开始评估时间
        completed_at: 完成时间

    Relationships:
        job: 关联的 MultiTargetJob
        evaluation: 关联的 ProteinEvaluation（单靶点评估）
        outgoing_relationships: 作为源靶点的关系列表
        incoming_relationships: 作为目标靶点的关系列表
    """
    __tablename__ = "targets"
    __table_args__ = (
        # 任务ID + 状态索引，用于快速查询特定任务中特定状态的靶点
        Index('idx_tgt_job_status', 'job_id', 'status'),
        # 任务ID + 靶点序号索引，用于排序查询
        Index('idx_tgt_job_index', 'job_id', 'target_index'),
        # UniProt ID 索引
        Index('idx_tgt_uniprot', 'uniprot_id'),
        # 评估ID 索引
        Index('idx_tgt_evaluation', 'evaluation_id'),
        # 状态 + 创建时间索引，用于队列处理
        Index('idx_tgt_status_started', 'status', 'started_at'),
    )

    target_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('multi_target_jobs.job_id', ondelete='CASCADE'), nullable=False)

    # 靶点序号（用于在同一任务内排序）
    target_index = Column(Integer, default=0, nullable=False)

    # 蛋白质基本信息
    uniprot_id = Column(String(20), nullable=False, index=True)
    protein_name = Column(Text)
    gene_name = Column(String(100))

    # 结构信息
    structure_source = Column(String(20))  # alphafold, pdb, emdb
    structure_id = Column(String(50))  # PDB ID 或 AlphaFold 版本

    # 权重（用于结果加权，默认1.0）
    weight = Column(Float, default=1.0)

    # 状态: pending-等待中, processing-执行中, completed-已完成, failed-失败, skipped-已跳过
    status = Column(String(20), default='pending', nullable=False)

    # 关联单靶点评估
    evaluation_id = Column(Integer, ForeignKey('protein_evaluations.id'), nullable=True)

    # 数据缓存
    sequence_data = Column(JSON)  # 序列数据
    structure_data = Column(JSON)  # 结构数据（如坐标、质量等）

    # 错误信息
    error_message = Column(Text)

    # 时间戳
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # 关系定义
    job = relationship("MultiTargetJob", back_populates="targets")
    evaluation = relationship("ProteinEvaluation")
    outgoing_relationships = relationship(
        "TargetRelationship",
        foreign_keys="TargetRelationship.source_target_id",
        back_populates="source_target",
        cascade="all, delete-orphan"
    )
    incoming_relationships = relationship(
        "TargetRelationship",
        foreign_keys="TargetRelationship.target_target_id",
        back_populates="target_target",
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        """将模型实例转换为字典

        Returns:
            dict: 包含所有字段值的字典，日期时间格式化为 ISO 8601 字符串
        """
        return {
            'target_id': self.target_id,
            'job_id': self.job_id,
            'target_index': self.target_index,
            'uniprot_id': self.uniprot_id,
            'protein_name': self.protein_name,
            'gene_name': self.gene_name,
            'structure_source': self.structure_source,
            'structure_id': self.structure_id,
            'weight': self.weight,
            'status': self.status,
            'evaluation_id': self.evaluation_id,
            'sequence_data': self.sequence_data,
            'structure_data': self.structure_data,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    def get_all_relationships(self):
        """获取该靶点的所有关系（包括出边和入边）"""
        outgoing = self.outgoing_relationships if self.outgoing_relationships else []
        incoming = self.incoming_relationships if self.incoming_relationships else []
        return outgoing + incoming

    def get_related_targets(self):
        """获取与该靶点相关的所有其他靶点ID"""
        related = set()
        for rel in self.outgoing_relationships:
            related.add(rel.target_target_id)
        for rel in self.incoming_relationships:
            related.add(rel.source_target_id)
        return list(related)


class TargetRelationship(Base):
    """靶点间关系表

    存储多靶点评估中各个靶点之间的关系，包括序列相似性、
    结构相似性和蛋白质相互作用等。

    Attributes:
        relationship_id: 关系唯一标识
        job_id: 关联的多靶点任务ID
        source_target_id: 源靶点ID
        target_target_id: 目标靶点ID
        relationship_type: 关系类型（sequence_similarity/structural_similarity/interaction）
        score: 相似度/相互作用分数（0.0-1.0或其他范围）
        metadata: 详细数据（JSON格式，存储额外信息）

    Relationships:
        job: 关联的 MultiTargetJob
        source_target: 源 Target 对象
        target_target: 目标 Target 对象

    Note:
        - 序列相似性：存储序列比对分数（如 BLAST 结果）
        - 结构相似性：存储结构比对分数（如 RMSD、TM-score）
        - 相互作用：存储蛋白质相互作用置信度分数
    """
    __tablename__ = "target_relationships"
    __table_args__ = (
        # 任务ID + 关系类型索引，用于查询特定任务的特定类型关系
        Index('idx_rel_job_type', 'job_id', 'relationship_type'),
        # 源靶点 + 关系类型索引
        Index('idx_rel_source_type', 'source_target_id', 'relationship_type'),
        # 目标靶点 + 关系类型索引
        Index('idx_rel_target_type', 'target_target_id', 'relationship_type'),
        # 分数索引，用于查找高分关系
        Index('idx_rel_score', 'score'),
        # 唯一约束：同一对靶点之间同一类型的关系只能有一条
        # Index('idx_rel_unique_pair', 'source_target_id', 'target_target_id', 'relationship_type', unique=True),
    )

    relationship_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('multi_target_jobs.job_id', ondelete='CASCADE'), nullable=False)

    # 关系两端靶点
    source_target_id = Column(Integer, ForeignKey('targets.target_id', ondelete='CASCADE'), nullable=False)
    target_target_id = Column(Integer, ForeignKey('targets.target_id', ondelete='CASCADE'), nullable=False)

    # 关系类型
    # sequence_similarity-序列相似性
    # structural_similarity-结构相似性
    # interaction-蛋白质相互作用
    relationship_type = Column(String(50), nullable=False)

    # 分数（0.0-1.0或其他范围，根据关系类型而定）
    score = Column(Float)

    # 详细数据（JSON格式）
    # sequence_similarity: {"identity": 0.85, "evalue": 1e-50, "alignment_length": 300}
    # structural_similarity: {"rmsd": 2.5, "tm_score": 0.85}
    # interaction: {"confidence": 0.9, "experimental": true, "source": "STRING"}
    relationship_metadata = Column(JSON, default=dict)

    # 关系定义
    job = relationship("MultiTargetJob", back_populates="relationships")
    source_target = relationship(
        "Target",
        foreign_keys=[source_target_id],
        back_populates="outgoing_relationships"
    )
    target_target = relationship(
        "Target",
        foreign_keys=[target_target_id],
        back_populates="incoming_relationships"
    )

    def to_dict(self):
        """将模型实例转换为字典

        Returns:
            dict: 包含所有字段值的字典
        """
        return {
            'relationship_id': self.relationship_id,
            'job_id': self.job_id,
            'source_target_id': self.source_target_id,
            'target_target_id': self.target_target_id,
            'relationship_type': self.relationship_type,
            'score': self.score,
            'metadata': self.relationship_metadata,
        }

    def is_bidirectional(self):
        """判断关系是否为双向（如某些相互作用可能是双向的）"""
        return self.relationship_type == 'interaction'

    @staticmethod
    def create_symmetric_pair(job_id, target_a_id, target_b_id, rel_type, score, metadata=None):
        """创建对称关系对（用于双向关系）

        Args:
            job_id: 任务ID
            target_a_id: 第一个靶点ID
            target_b_id: 第二个靶点ID
            rel_type: 关系类型
            score: 分数
            metadata: 元数据字典（可选）

        Returns:
            tuple: (relationship_a_to_b, relationship_b_to_a)
        """
        meta = metadata or {}
        rel1 = TargetRelationship(
            job_id=job_id,
            source_target_id=target_a_id,
            target_target_id=target_b_id,
            relationship_type=rel_type,
            score=score,
            metadata=meta
        )
        rel2 = TargetRelationship(
            job_id=job_id,
            source_target_id=target_b_id,
            target_target_id=target_a_id,
            relationship_type=rel_type,
            score=score,
            metadata=meta
        )
        return rel1, rel2


# 便捷查询函数（可选，用于常见查询场景）
def get_pending_jobs(session, limit=None):
    """获取等待中的任务，按优先级排序

    Args:
        session: SQLAlchemy session
        limit: 返回数量限制

    Returns:
        list: MultiTargetJob 对象列表
    """
    query = session.query(MultiTargetJob).filter(
        MultiTargetJob.status == 'pending'
    ).order_by(MultiTargetJob.priority.desc(), MultiTargetJob.created_at.asc())
    if limit:
        query = query.limit(limit)
    return query.all()


def get_targets_by_status(session, job_id, status):
    """获取特定任务中特定状态的靶点

    Args:
        session: SQLAlchemy session
        job_id: 任务ID
        status: 状态字符串

    Returns:
        list: Target 对象列表
    """
    return session.query(Target).filter(
        Target.job_id == job_id,
        Target.status == status
    ).order_by(Target.target_index).all()


def get_relationships_for_target(session, target_id, rel_type=None):
    """获取靶点的所有关系

    Args:
        session: SQLAlchemy session
        target_id: 靶点ID
        rel_type: 关系类型过滤（可选）

    Returns:
        list: TargetRelationship 对象列表
    """
    from sqlalchemy import or_
    query = session.query(TargetRelationship).filter(
        or_(
            TargetRelationship.source_target_id == target_id,
            TargetRelationship.target_target_id == target_id
        )
    )
    if rel_type:
        query = query.filter(TargetRelationship.relationship_type == rel_type)
    return query.all()


def get_high_score_relationships(session, job_id, min_score=0.8, rel_type=None):
    """获取高分关系（用于识别紧密相关的靶点）

    Args:
        session: SQLAlchemy session
        job_id: 任务ID
        min_score: 最小分数阈值
        rel_type: 关系类型过滤（可选）

    Returns:
        list: TargetRelationship 对象列表
    """
    query = session.query(TargetRelationship).filter(
        TargetRelationship.job_id == job_id,
        TargetRelationship.score >= min_score
    )
    if rel_type:
        query = query.filter(TargetRelationship.relationship_type == rel_type)
    return query.order_by(TargetRelationship.score.desc()).all()
