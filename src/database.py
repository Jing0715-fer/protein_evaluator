"""
Database operations for Protein Evaluation
"""
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from .models import Base, ProteinEvaluation, PromptTemplate, BatchEvaluation, ProteinInteraction
from .multi_target_models import MultiTargetJob, Target, TargetRelationship
import config

logger = logging.getLogger(__name__)


def reset_engine():
    """Reset the cached engine. Call this in tests before patching DATABASE_PATH."""
    _get_engine.cache_clear()


def get_engine():
    """Public entry point for the engine. Delegates to the cached _get_engine()."""
    return _get_engine()


@lru_cache(maxsize=1)
def _get_engine():
    """Lazily create and return the SQLAlchemy engine. Deferred until first call."""
    import importlib
    # Re-import config inside the lazy function so any test-level patches
    # to config.DATABASE_PATH take effect before we read it.
    importlib.reload(config)
    DATABASE_PATH = config.DATABASE_PATH

    # Ensure data directory exists
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f'sqlite:///{DATABASE_PATH}',
        echo=False,
        poolclass=NullPool,
        connect_args={'check_same_thread': False}
    )

    # Create tables
    Base.metadata.create_all(engine)

    # Run migrations for new columns
    _run_migrations(engine)

    return engine


# Backwards-compatibility: module-level 'engine' proxy that delegates lazily
class _EngineProxy:
    """Proxy object that resolves the real engine on first use."""
    def __getattr__(self, name):
        return getattr(_get_engine(), name)

    def __repr__(self):
        return repr(_get_engine())

    def __bool__(self):
        return True


engine = _EngineProxy()


def _run_migrations(engine):
    """Run database migrations for schema updates"""
    with engine.connect() as conn:
        # Check if description_en column exists in prompt_templates
        result = conn.execute(text("PRAGMA table_info(prompt_templates)"))
        columns = [row[1] for row in result.fetchall()]
        if 'description_en' not in columns:
            conn.execute(text("ALTER TABLE prompt_templates ADD COLUMN description_en TEXT"))
            conn.commit()
            logger.info("Migration: Added description_en column to prompt_templates")
        if 'content_en' not in columns:
            conn.execute(text("ALTER TABLE prompt_templates ADD COLUMN content_en TEXT"))
            conn.commit()
            logger.info("Migration: Added content_en column to prompt_templates")
        if 'name_en' not in columns:
            conn.execute(text("ALTER TABLE prompt_templates ADD COLUMN name_en TEXT"))
            conn.commit()
            logger.info("Migration: Added name_en column to prompt_templates")

        # Check if ai_analysis_en column exists in protein_evaluations
        result = conn.execute(text("PRAGMA table_info(protein_evaluations)"))
        eval_columns = [row[1] for row in result.fetchall()]
        if 'ai_analysis_en' not in eval_columns:
            conn.execute(text("ALTER TABLE protein_evaluations ADD COLUMN ai_analysis_en JSON"))
            conn.commit()
            logger.info("Migration: Added ai_analysis_en column to protein_evaluations")


# Create session factory — bind=engine is a _EngineProxy that defers to _get_engine()
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

def create_prompt_template(name: str, content: str, description: str = '', description_en: str = '', is_default: bool = False, content_en: str = '', name_en: str = '') -> Optional[PromptTemplate]:
    """创建提示模板"""
    session = get_session()
    try:
        # 如果设为默认模板，先取消其他默认
        if is_default:
            session.query(PromptTemplate).filter_by(is_default=True).update({'is_default': False})

        template = PromptTemplate(
            name=name,
            name_en=name_en,
            content=content,
            content_en=content_en,
            description=description,
            description_en=description_en,
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


def get_single_templates() -> List[PromptTemplate]:
    """获取单个蛋白评估模板"""
    session = get_session()
    try:
        templates = session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'single'
        ).order_by(PromptTemplate.is_default.desc(), PromptTemplate.name).all()
        return templates
    except Exception as e:
        logger.error(f"获取单个模板列表失败: {e}")
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


# ========== Batch Template CRUD ==========

def create_batch_template(name: str, content: str, description: str = '', description_en: str = '', is_default: bool = False, template_type: str = 'batch', content_en: str = '', name_en: str = '') -> Optional[PromptTemplate]:
    """创建批量分析模板"""
    session = get_session()
    try:
        # 如果设为默认模板，先取消其他默认
        if is_default:
            session.query(PromptTemplate).filter_by(is_default=True, template_type='batch').update({'is_default': False})

        template = PromptTemplate(
            name=name,
            name_en=name_en,
            content=content,
            content_en=content_en,
            description=description,
            description_en=description_en,
            is_default=is_default,
            template_type=template_type
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        logger.info(f"创建批量模板成功: ID={template.id}, name={name}")
        return template
    except Exception as e:
        logger.error(f"创建批量模板失败: {e}")
        session.rollback()
        return None
    finally:
        session.close()


def get_batch_template(template_id: int) -> Optional[PromptTemplate]:
    """获取批量分析模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id, template_type='batch').first()
        return template
    except Exception as e:
        logger.error(f"获取批量模板失败: {e}")
        return None
    finally:
        session.close()


def get_all_batch_templates() -> List[PromptTemplate]:
    """获取所有批量分析模板"""
    session = get_session()
    try:
        templates = session.query(PromptTemplate).filter_by(template_type='batch').order_by(PromptTemplate.is_default.desc(), PromptTemplate.name).all()
        return templates
    except Exception as e:
        logger.error(f"获取批量模板列表失败: {e}")
        return []
    finally:
        session.close()


def get_default_batch_template() -> Optional[PromptTemplate]:
    """获取默认批量分析模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(is_default=True, template_type='batch').first()
        # 如果没有默认模板，返回第一个
        if not template:
            template = session.query(PromptTemplate).filter_by(template_type='batch').first()
        return template
    except Exception as e:
        logger.error(f"获取默认批量模板失败: {e}")
        return None
    finally:
        session.close()


def update_batch_template(template_id: int, updates: dict) -> bool:
    """更新批量分析模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id, template_type='batch').first()
        if not template:
            return False

        # 如果设为默认模板，先取消其他默认
        if updates.get('is_default'):
            session.query(PromptTemplate).filter_by(is_default=True, template_type='batch').update({'is_default': False})

        for key, value in updates.items():
            if hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = datetime.now()
        session.commit()
        logger.info(f"更新批量模板成功: ID={template_id}")
        return True
    except Exception as e:
        logger.error(f"更新批量模板失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def delete_batch_template(template_id: int) -> bool:
    """删除批量分析模板"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id, template_type='batch').first()
        if not template:
            return False
        session.delete(template)
        session.commit()
        logger.info(f"删除批量模板成功: ID={template_id}")
        return True
    except Exception as e:
        logger.error(f"删除批量模板失败: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def set_default_batch_template(template_id: int) -> bool:
    """设置默认批量模板"""
    session = get_session()
    try:
        # 先取消所有默认
        session.query(PromptTemplate).filter_by(is_default=True, template_type='batch').update({'is_default': False})
        # 设置新的默认
        template = session.query(PromptTemplate).filter_by(id=template_id, template_type='batch').first()
        if not template:
            return False
        template.is_default = True
        session.commit()
        logger.info(f"设置默认批量模板成功: ID={template_id}")
        return True
    except Exception as e:
        logger.error(f"设置默认批量模板失败: {e}")
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
