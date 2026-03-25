"""
多靶点功能数据库迁移脚本
创建多靶点评估相关表结构

迁移版本: 002_add_multi_target_tables
创建时间: 2026-03-14
"""

from sqlalchemy import create_engine, text
from src.database import get_engine
from src.multi_target_models import Base

def migrate():
    """执行迁移"""
    print("开始多靶点功能数据库迁移...")
    
    engine = get_engine()
    
    # 创建新表
    Base.metadata.create_all(engine, tables=[
        Base.metadata.tables['multi_target_jobs'],
        Base.metadata.tables['targets'],
        Base.metadata.tables['target_relationships']
    ])
    
    print("✅ 多靶点表创建成功")
    
    # 验证表是否创建
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('multi_target_jobs', 'targets', 'target_relationships')
        """))
        tables = [row[0] for row in result]
        print(f"已创建的表: {tables}")
    
    print("\n迁移完成！")

if __name__ == "__main__":
    migrate()
