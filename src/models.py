"""
Database models for Protein Evaluation
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class PromptTemplate(Base):
    """AI 提示模板表"""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # 模板名称
    content = Column(Text, nullable=False)  # 模板内容
    is_default = Column(Boolean, default=False)  # 是否为默认模板
    description = Column(Text)  # 模板描述
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'is_default': self.is_default,
            'description': self.description,
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
    ai_analysis = Column(JSON)  # AI分析结果
    report = Column(Text)  # 最终报告

    # 向量嵌入（RAG用）
    embedding = Column(JSON)

    # 飞书文档
    feishu_doc_url = Column(String(500))

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
            'report': self.report,
            'embedding': self.embedding,
            'feishu_doc_url': self.feishu_doc_url,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.started_at.isoformat() if self.started_at else None
        }
