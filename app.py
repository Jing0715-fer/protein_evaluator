# app.py - 蛋白质评估系统主应用（独立运行版）
"""
Protein Evaluation System - Standalone Flask Application
"""
import os
import sys
import logging
from flask import Flask, render_template

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import config
import config


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)

    # Load config
    app.config['SECRET_KEY'] = 'protein-evaluator-secret-key'
    app.config['DEBUG'] = config.DEBUG

    # Register blueprints
    from routes.evaluation import bp as evaluation_bp
    app.register_blueprint(evaluation_bp)

    # Main routes
    @app.route('/')
    def index():
        """首页/评估页面"""
        return render_template('evaluation.html')

    @app.route('/evaluation')
    def evaluation_page():
        """评估页面"""
        return render_template('evaluation.html')

    @app.route('/health')
    def health():
        """健康检查"""
        return {'status': 'ok', 'service': 'protein-evaluator'}

    # 初始化默认模板
    _init_default_templates()

    logger.info("Flask应用创建成功")
    return app


def _init_default_templates():
    """初始化默认模板"""
    from src.database import get_all_prompt_templates, create_prompt_template

    templates = get_all_prompt_templates()
    if not templates:
        # 没有模板，创建默认模板
        default_content = getattr(config, 'AI_PROMPT_TEMPLATE', '')
        if default_content:
            create_prompt_template(
                name="默认模板",
                content=default_content,
                description="系统默认的蛋白质分析报告模板",
                is_default=True
            )
            logger.info("已创建默认模板")


# Create app instance
app = create_app()


if __name__ == '__main__':
    logger.info(f"启动蛋白质评估系统...")
    logger.info(f"数据库路径: {config.DATABASE_PATH}")
    logger.info(f"AI模型: {config.AI_MODEL}")
    logger.info(f"监听地址: {config.HOST}:{config.PORT}")

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    )
