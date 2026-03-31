"""
模板功能扩展迁移脚本
为 prompt_templates 表添加 experimental_method 字段

迁移版本: 003_add_experimental_method_to_templates
创建时间: 2026-03-31
"""

from sqlalchemy import create_engine, text
from src.database import get_engine


def migrate():
    """执行迁移"""
    print("开始模板功能扩展数据库迁移...")

    engine = get_engine()

    # 检查列是否已存在
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(prompt_templates)"))
        columns = [row[1] for row in result]

        if 'experimental_method' in columns:
            print("⚠️  experimental_method 列已存在，跳过迁移")
            return

    # 添加 experimental_method 列
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE prompt_templates
            ADD COLUMN experimental_method VARCHAR(50)
        """))
        conn.commit()
        print("✅ experimental_method 列添加成功")

    print("\n迁移完成！")


if __name__ == "__main__":
    migrate()
