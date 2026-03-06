"""
Database operations for Protein Evaluation
"""
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base, ProteinEvaluation
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
