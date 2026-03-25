"""
Database models for Protein Evaluation
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean, Float, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class PromptTemplate(Base):
    """AI 提示模板表"""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 模板名称
    name_en = Column(String(100))  # 模板名称（英文）
    content = Column(Text, nullable=False)  # 模板内容（中文）
    content_en = Column(Text)  # 模板内容（英文）
    is_default = Column(Boolean, default=False)  # 是否为默认模板
    description = Column(Text)  # 模板描述（中文）
    description_en = Column(Text)  # 模板描述（英文）
    template_type = Column(String(20), default='single')  # 模板类型: single 或 batch
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'name_en': self.name_en,
            'content': self.content,
            'content_en': self.content_en,
            'is_default': self.is_default,
            'description': self.description,
            'description_en': self.description_en,
            'template_type': self.template_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ProteinEvaluation(Base):
    """蛋白质评估主表"""
    __tablename__ = "protein_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 基本信息
    uniprot_id = Column(String(20), nullable=False, index=True)
    gene_name = Column(String(100))
    protein_name = Column(Text)

    # 评估状态
    evaluation_status = Column(String(20), default='pending')  # pending, processing, completed, failed

    # 进度跟踪
    progress = Column(Integer, default=0)  # 0-100
    current_step = Column(String(50))  # 当前执行步骤
    error_message = Column(Text)  # 错误信息（如有）
    logs = Column(JSON)  # 运行日志列表
    ai_prompt = Column(Text)  # 提交给 AI 的 prompt

    # 关联数据（JSON存储）
    pdb_data = Column(JSON)  # PDB元数据
    uniprot_data = Column(JSON)  # Uniprot元数据
    blast_results = Column(JSON)  # Blast结果
    ai_analysis = Column(JSON)  # AI分析结果（中文）
    ai_analysis_en = Column(JSON)  # AI分析结果（英文）
    report = Column(Text)  # 最终报告

    # 向量嵌入（RAG用）
    embedding = Column(JSON)

    # 飞书文档
    feishu_doc_url = Column(String(500))

    # 批量评估关联
    batch_id = Column(Integer, ForeignKey('batch_evaluations.id'), nullable=True)

    # 时间戳
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'uniprot_id': self.uniprot_id,
            'gene_name': self.gene_name,
            'protein_name': self.protein_name,
            'evaluation_status': self.evaluation_status,
            'progress': self.progress,
            'current_step': self.current_step,
            'error_message': self.error_message,
            'logs': self.logs,
            'ai_prompt': self.ai_prompt,
            'pdb_data': self.pdb_data,
            'uniprot_data': self.uniprot_data,
            'blast_results': self.blast_results,
            'ai_analysis': self.ai_analysis,
            'ai_analysis_en': self.ai_analysis_en,
            'report': self.report,
            'embedding': self.embedding,
            'feishu_doc_url': self.feishu_doc_url,
            'batch_id': self.batch_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.started_at.isoformat() if self.started_at else None
        }


class BatchEvaluation(Base):
    """批量评估任务"""
    __tablename__ = "batch_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200))  # 批量评估名称
    uniprot_ids = Column(JSON)  # UniProt ID 列表
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100

    # 评估结果
    interaction_data = Column(JSON)  # 蛋白互作数据
    batch_ai_analysis = Column(JSON)  # 批量AI分析结果
    batch_report = Column(Text)  # 综合分析报告
    
    # 日志
    logs = Column(JSON, default=list)  # 批量评估日志

    # 配置
    config = Column(JSON)

    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'uniprot_ids': self.uniprot_ids,
            'status': self.status,
            'progress': self.progress,
            'interaction_data': self.interaction_data,
            'batch_ai_analysis': self.batch_ai_analysis,
            'batch_report': self.batch_report,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class ProteinInteraction(Base):
    """蛋白相互作用数据"""
    __tablename__ = "protein_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey('batch_evaluations.id'), nullable=False)
    protein_a = Column(String(20), nullable=False)  # UniProt ID A
    protein_b = Column(String(20), nullable=False)  # UniProt ID B
    interaction_type = Column(String(50))  # 相互作用类型
    score = Column(Float)  # 相互作用置信度分数
    source = Column(String(50))  # 数据来源 (String, BioGRID, etc.)
    data_json = Column(JSON)  # 原始数据

    def to_dict(self):
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'protein_a': self.protein_a,
            'protein_b': self.protein_b,
            'interaction_type': self.interaction_type,
            'score': self.score,
            'source': self.source,
            'data_json': self.data_json
        }


class DataCache(Base):
    """API 数据缓存表 - 避免重复 API 调用"""
    __tablename__ = "data_cache"
    __table_args__ = (
        # 复合索引：缓存类型 + 缓存键
        {'sqlite_with_rowid': False}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 缓存标识
    cache_type = Column(String(50), nullable=False, index=True)  # 缓存类型: uniprot, pdb, alphafold, emdb, blast, pubmed
    cache_key = Column(String(100), nullable=False)  # 缓存键 (如 UniProt ID, PDB ID)
    
    # 缓存数据
    data = Column(JSON, nullable=False)  # 缓存的 API 响应数据
    data_hash = Column(String(64))  # 数据哈希，用于检测变化
    
    # 缓存元数据
    source_api = Column(String(50))  # 数据来源 API 名称
    api_version = Column(String(20))  # API 版本 (用于版本控制)
    
    # 过期控制
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)  # 过期时间
    last_accessed_at = Column(DateTime, default=datetime.now)  # 最后访问时间
    access_count = Column(Integer, default=1)  # 访问次数
    
    # 状态
    is_valid = Column(Boolean, default=True)  # 缓存是否有效 (可手动标记失效)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'cache_type': self.cache_type,
            'cache_key': self.cache_key,
            'data': self.data,
            'data_hash': self.data_hash,
            'source_api': self.source_api,
            'api_version': self.api_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_accessed_at': self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            'access_count': self.access_count,
            'is_valid': self.is_valid
        }
    
    def is_expired(self):
        """检查缓存是否过期"""
        if not self.is_valid:
            return True
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        return False
    
    def touch(self):
        """更新访问时间和计数"""
        self.last_accessed_at = datetime.now()
        self.access_count += 1

