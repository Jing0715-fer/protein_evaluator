"""
Database operations for Protein Evaluation
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base, ProteinEvaluation, PromptTemplate, BatchEvaluation, ProteinInteraction
import config

logger = logging.getLogger(__name__)

# Database path
DATABASE_PATH = config.DATABASE_PATH

# Ensure data directory exists
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

# Create engine
engine = create_engine(f'sqlite:///{DATABASE_PATH}', echo=False)

# Create tables
Base.metadata.create_all(engine)

# Create session factory
Session = sessionmaker(bind=engine)


def get_session():
    """获取数据库会话"""
    return Session()


def create_protein_evaluation(uniprot_id: str, gene_name: str = None, protein_name: str = None) -> Optional[ProteinEvaluation]:
    """创建蛋白质评估记录"""
    session = get_session()
    try:
        evaluation = ProteinEvaluation(
            uniprot_id=uniprot_id.upper(),
            gene_name=gene_name,
            protein_name=protein_name,
            evaluation_status='pending',
            progress=0,
            started_at=datetime.now()
        )
        session.add(evaluation)
        session.commit()
        session.refresh(evaluation)
        logger.info(f"创建蛋白质评估成功: ID={evaluation.id}, UniProt={uniprot_id}")
        return evaluation
    except Exception as e:
        logger.error(f"创建蛋白质评估失败: {e}")
        session.rollback()
        return None
    finally:
        session.close()


def get_protein_evaluation(evaluation_id: int) -> Optional[ProteinEvaluation]:
    """获取蛋白质评估记录"""
    session = get_session()
    try:
        evaluation = session.query(ProteinEvaluation).filter_by(id=evaluation_id).first()
        return evaluation
    except Exception as e:
        logger.error(f"获取蛋白质评估失败: {e}")
        return None
    finally:
        session.close()


def get_protein_evaluation_by_uniprot(uniprot_id: str) -> Optional[ProteinEvaluation]:
    """通过UniProt ID获取评估记录"""
    session = get_session()
    try:
        evaluation = session.query(ProteinEvaluation).filter_by(
            uniprot_id=uniprot_id.upper()
        ).order_by(ProteinEvaluation.started_at.desc()).first()
        return evaluation
    except Exception as e:
        logger.error(f"获取蛋白质评估失败: {e}")
        return None
    finally:
        session.close()


def get_all_protein_evaluations(limit: int = 50, offset: int = 0) -> List[ProteinEvaluation]:
    """获取所有蛋白质评估记录"""
    session = get_session()
    try:
        evaluations = session.query(ProteinEvaluation).order_by(
            ProteinEvaluation.started_at.desc()
        ).offset(offset).limit(limit).all()
        return evaluations
    except Exception as e:
        logger.error(f"获取蛋白质评估列表失败: {e}")
        return []
    finally:
        session.close()


def update_protein_evaluation(evaluation_id: int, updates: dict) -> bool:
    """更新蛋白质评估记录"""
    session = get_session()
    try:
        evaluation = session.query(ProteinEvaluation).filter_by(id=evaluation_id).first()
        if not evaluation:
            return False

        for key, value in updates.items():
            if hasattr(evaluation, key):
                setattr(evaluation, key, value)

        # 自动更新完成时间
        if updates.get('evaluation_status') == 'completed':
            evaluation.completed_at = datetime.now()

        session.commit()
        logger.info(f"更新蛋白质评估成功: ID={evaluation_id}")
        return True
    except Exception as e:
        logger.error(f"更新蛋白质评估失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def delete_protein_evaluation(evaluation_id: int) -> bool:
    """删除蛋白质评估记录"""
    session = get_session()
    try:
        evaluation = session.query(ProteinEvaluation).filter_by(id=evaluation_id).first()
        if not evaluation:
            return False
        session.delete(evaluation)
        session.commit()
        logger.info(f"删除蛋白质评估成功: ID={evaluation_id}")
        return True
    except Exception as e:
        logger.error(f"删除蛋白质评估失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def search_protein_evaluations(query: str) -> List[ProteinEvaluation]:
    """搜索蛋白质评估记录"""
    session = get_session()
    try:
        evaluations = session.query(ProteinEvaluation).filter(
            (ProteinEvaluation.uniprot_id.like(f'%{query}%')) |
            (ProteinEvaluation.gene_name.like(f'%{query}%')) |
            (ProteinEvaluation.protein_name.like(f'%{query}%'))
        ).order_by(ProteinEvaluation.started_at.desc()).all()
        return evaluations
    except Exception as e:
        logger.error(f"搜索蛋白质评估失败: {e}")
        return []
    finally:
        session.close()


# ========== Prompt Template CRUD ==========

def create_prompt_template(name: str, content: str, description: str = '', is_default: bool = False) -> Optional[PromptTemplate]:
    """创建提示模板"""
    session = get_session()
    try:
        # 如果设为默认模板，先取消其他默认
        if is_default:
            session.query(PromptTemplate).filter_by(is_default=True).update({'is_default': False})

        template = PromptTemplate(
            name=name,
            content=content,
            description=description,
            is_default=is_default
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        logger.info(f"创建提示模板成功: ID={template.id}, name={name}")
        return template
    except Exception as e:
        logger.error(f"创建提示模板失败: {e}")
        session.rollback()
        return None
    finally:
        session.close()


def get_prompt_template(template_id: int) -> Optional[PromptTemplate]:
    """获取提示模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id).first()
        return template
    except Exception as e:
        logger.error(f"获取提示模板失败: {e}")
        return None
    finally:
        session.close()


def get_all_prompt_templates() -> List[PromptTemplate]:
    """获取所有提示模板"""
    session = get_session()
    try:
        templates = session.query(PromptTemplate).order_by(PromptTemplate.is_default.desc(), PromptTemplate.name).all()
        return templates
    except Exception as e:
        logger.error(f"获取提示模板列表失败: {e}")
        return []
    finally:
        session.close()


def get_default_prompt_template() -> Optional[PromptTemplate]:
    """获取默认提示模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(is_default=True).first()
        # 如果没有默认模板，返回第一个
        if not template:
            template = session.query(PromptTemplate).first()
        return template
    except Exception as e:
        logger.error(f"获取默认提示模板失败: {e}")
        return None
    finally:
        session.close()


def update_prompt_template(template_id: int, updates: dict) -> bool:
    """更新提示模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id).first()
        if not template:
            return False

        # 如果设为默认模板，先取消其他默认
        if updates.get('is_default'):
            session.query(PromptTemplate).filter_by(is_default=True).update({'is_default': False})

        for key, value in updates.items():
            if hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = datetime.now()
        session.commit()
        logger.info(f"更新提示模板成功: ID={template_id}")
        return True
    except Exception as e:
        logger.error(f"更新提示模板失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def delete_prompt_template(template_id: int) -> bool:
    """删除提示模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id).first()
        if not template:
            return False
        session.delete(template)
        session.commit()
        logger.info(f"删除提示模板成功: ID={template_id}")
        return True
    except Exception as e:
        logger.error(f"删除提示模板失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def set_default_prompt_template(template_id: int) -> bool:
    """设置默认模板"""
    session = get_session()
    try:
        # 先取消所有默认
        session.query(PromptTemplate).filter_by(is_default=True).update({'is_default': False})
        # 设置新的默认
        template = session.query(PromptTemplate).filter_by(id=template_id).first()
        if not template:
            return False
        template.is_default = True
        session.commit()
        logger.info(f"设置默认提示模板成功: ID={template_id}")
        return True
    except Exception as e:
        logger.error(f"设置默认提示模板失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


# ========== Batch Evaluation CRUD ==========

def create_batch_evaluation(name: str, uniprot_ids: List[str], config: Dict = None) -> Optional[BatchEvaluation]:
    """创建批量评估记录"""
    session = get_session()
    try:
        batch = BatchEvaluation(
            name=name,
            uniprot_ids=uniprot_ids,
            config=config or {},
            status='pending',
            progress=0,
            created_at=datetime.now()
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)
        logger.info(f"创建批量评估成功: ID={batch.id}, UniProt IDs={len(uniprot_ids)}")
        return batch
    except Exception as e:
        logger.error(f"创建批量评估失败: {e}")
        session.rollback()
        return None
    finally:
        session.close()


def get_batch_evaluation(batch_id: int) -> Optional[BatchEvaluation]:
    """获取批量评估记录"""
    session = get_session()
    try:
        batch = session.query(BatchEvaluation).filter_by(id=batch_id).first()
        return batch
    except Exception as e:
        logger.error(f"获取批量评估失败: {e}")
        return None
    finally:
        session.close()


def get_all_batch_evaluations(limit: int = 50, offset: int = 0) -> List[BatchEvaluation]:
    """获取所有批量评估记录"""
    session = get_session()
    try:
        batches = session.query(BatchEvaluation).order_by(
            BatchEvaluation.created_at.desc()
        ).offset(offset).limit(limit).all()
        return batches
    except Exception as e:
        logger.error(f"获取批量评估列表失败: {e}")
        return []
    finally:
        session.close()


def update_batch_evaluation(batch_id: int, updates: dict) -> bool:
    """更新批量评估记录"""
    session = get_session()
    try:
        batch = session.query(BatchEvaluation).filter_by(id=batch_id).first()
        if not batch:
            return False

        for key, value in updates.items():
            if hasattr(batch, key):
                setattr(batch, key, value)

        # 自动更新完成时间
        if updates.get('status') == 'completed':
            batch.completed_at = datetime.now()

        session.commit()
        logger.info(f"更新批量评估成功: ID={batch_id}")
        return True
    except Exception as e:
        logger.error(f"更新批量评估失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def delete_batch_evaluation(batch_id: int) -> bool:
    """删除批量评估记录"""
    session = get_session()
    try:
        batch = session.query(BatchEvaluation).filter_by(id=batch_id).first()
        if not batch:
            return False
        session.delete(batch)
        session.commit()
        logger.info(f"删除批量评估成功: ID={batch_id}")
        return True
    except Exception as e:
        logger.error(f"删除批量评估失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def create_protein_interaction(batch_id: int, protein_a: str, protein_b: str,
                                interaction_type: str = None, score: float = None,
                                source: str = None, data_json: Dict = None) -> Optional[ProteinInteraction]:
    """创建蛋白相互作用记录"""
    session = get_session()
    try:
        interaction = ProteinInteraction(
            batch_id=batch_id,
            protein_a=protein_a.upper(),
            protein_b=protein_b.upper(),
            interaction_type=interaction_type,
            score=score,
            source=source,
            data_json=data_json
        )
        session.add(interaction)
        session.commit()
        session.refresh(interaction)
        return interaction
    except Exception as e:
        logger.error(f"创建蛋白相互作用失败: {e}")
        session.rollback()
        return None
    finally:
        session.close()


def get_protein_interactions(batch_id: int) -> List[ProteinInteraction]:
    """获取批量评估的蛋白相互作用列表"""
    session = get_session()
    try:
        interactions = session.query(ProteinInteraction).filter_by(batch_id=batch_id).all()
        return interactions
    except Exception as e:
        logger.error(f"获取蛋白相互作用失败: {e}")
        return []
    finally:
        session.close()


def delete_protein_interactions(batch_id: int) -> bool:
    """删除批量评估的所有蛋白相互作用记录"""
    session = get_session()
    try:
        session.query(ProteinInteraction).filter_by(batch_id=batch_id).delete()
        session.commit()
        return True
    except Exception as e:
        logger.error(f"删除蛋白相互作用失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()
