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
    # Dispose the old engine to release any open SQLite connections / file locks
    # before clearing the cache so the next _get_engine() call gets a fresh engine.
    try:
        old_engine = _get_engine()
        old_engine.dispose()
    except Exception:
        pass  # No engine created yet
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
    """Run database migrations for schema updates.

    Uses a schema_migrations tracking table to skip already-run migrations.
    Each ALTER TABLE is wrapped in try/except so concurrent process restarts
    (where another process already added the column) do not crash startup.
    """
    with engine.connect() as conn:
        # Ensure the migrations tracking table exists (idempotent).
        try:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)"
            ))
            conn.commit()
        except Exception as e:
            logger.debug(f"schema_migrations table check: {e}")

        # Helper: record and skip if already recorded.
        def run_migration(version: str, sql: str, log_msg: str):
            try:
                result = conn.execute(text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": version})
                if result.fetchone():
                    logger.debug(f"Migration {version} already applied, skipping")
                    return
            except Exception as e:
                logger.warning(f"Could not check migration {version}: {e}")

            try:
                conn.execute(text(sql))
                conn.commit()
                conn.execute(text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": version})
                conn.commit()
                logger.info(f"Migration: {log_msg}")
            except Exception as e:
                # OperationalError "duplicate column name" means another process
                # already ran this migration — treat as success.
                err_str = str(e).lower()
                if "duplicate column name" in err_str or "already exists" in err_str:
                    logger.debug(f"Migration {version} column already exists (concurrent run), treating as applied")
                    try:
                        conn.execute(text(
                            "INSERT OR IGNORE INTO schema_migrations (version) VALUES (:v)"
                        ), {"v": version})
                        conn.commit()
                    except Exception:
                        pass
                else:
                    logger.warning(f"Migration {version} failed: {e}")

        # v1: add *_en columns to prompt_templates
        run_migration(
            "v1_description_en",
            "ALTER TABLE prompt_templates ADD COLUMN description_en TEXT",
            "Added description_en column to prompt_templates"
        )
        run_migration(
            "v1_content_en",
            "ALTER TABLE prompt_templates ADD COLUMN content_en TEXT",
            "Added content_en column to prompt_templates"
        )
        run_migration(
            "v1_name_en",
            "ALTER TABLE prompt_templates ADD COLUMN name_en TEXT",
            "Added name_en column to prompt_templates"
        )

        # v2: add ai_analysis_en to protein_evaluations
        run_migration(
            "v2_ai_analysis_en",
            "ALTER TABLE protein_evaluations ADD COLUMN ai_analysis_en JSON",
            "Added ai_analysis_en column to protein_evaluations"
        )


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
        # Escape LIKE metacharacters to prevent injection into the LIKE pattern.
        # % and _ have special meaning in LIKE; backslash escapes them.
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        evaluations = session.query(ProteinEvaluation).filter(
            (ProteinEvaluation.uniprot_id.like(f'%{escaped}%')) |
            (ProteinEvaluation.gene_name.like(f'%{escaped}%')) |
            (ProteinEvaluation.protein_name.like(f'%{escaped}%'))
        ).order_by(ProteinEvaluation.started_at.desc()).all()
        return evaluations
    except Exception as e:
        logger.error(f"搜索蛋白质评估失败: {e}")
        return []
    finally:
        session.close()


# ========== Prompt Template CRUD ==========

def create_prompt_template(
    name: str,
    content: str,
    description: str = '',
    description_en: str = '',
    is_default: bool = False,
    content_en: str = '',
    name_en: str = '',
    experimental_method: str = None
) -> Optional[PromptTemplate]:
    """创建提示模板

    Args:
        experimental_method: 实验方法类型 (xray, cryoem, nmr, alphafold) 或 None 表示通用默认
    """
    session = get_session()
    try:
        # 如果设为默认模板，先取消其他同类型默认
        if is_default:
            session.query(PromptTemplate).filter(
                PromptTemplate.is_default == True,
                PromptTemplate.template_type == 'single',
                PromptTemplate.experimental_method == experimental_method
            ).update({'is_default': False})

        template = PromptTemplate(
            name=name,
            name_en=name_en,
            content=content,
            content_en=content_en,
            description=description,
            description_en=description_en,
            is_default=is_default,
            experimental_method=experimental_method
        )
        session.add(template)
        session.commit()
        session.refresh(template)
        logger.info(f"创建提示模板成功: ID={template.id}, name={name}, method={experimental_method}")
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
    """设置默认模板（只取消同类型模板的默认状态）"""
    session = get_session()
    try:
        template = session.query(PromptTemplate).filter_by(id=template_id).first()
        if not template:
            return False

        # 只取消同类型、同实验方法的默认
        session.query(PromptTemplate).filter(
            PromptTemplate.is_default == True,
            PromptTemplate.template_type == template.template_type,
            PromptTemplate.experimental_method == template.experimental_method
        ).update({'is_default': False})

        template.is_default = True
        session.commit()
        logger.info(f"设置默认提示模板成功: ID={template_id}, method={template.experimental_method}")
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
