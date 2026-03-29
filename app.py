# app.py - 蛋白质评估系统主应用（独立运行版）
"""
Protein Evaluation System - Standalone Flask Application
"""
import os
import sys
import logging
from flask import Flask, render_template, send_from_directory, jsonify, request, make_response

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import config
import config


def create_app(debug=None):
    """创建Flask应用

    Args:
        debug: Optional bool to override DEBUG setting. If None, reads
               from os.environ['DEBUG'] (consistent with config.DEBUG behaviour).
    """
    app = Flask(__name__)

    # Load config
    # Use SECRET_KEY: env var takes priority, then config, then auto-generate
    # In production, SECRET_KEY must be set (enforced in config.py)
    secret_key = os.environ.get('SECRET_KEY') or config.SECRET_KEY
    if not secret_key:
        # Development fallback - generate a random key
        import secrets
        secret_key = secrets.token_hex(32)
        logger.warning("SECRET_KEY not set, using auto-generated key for development")

    app.config['SECRET_KEY'] = secret_key
    if debug is not None:
        app.config['DEBUG'] = debug
    else:
        app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'

    # CORS middleware for all API routes
    @app.after_request
    def after_request(response):
        """Add CORS headers to all responses"""
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response

    # Handle OPTIONS requests for CORS preflight
    @app.route('/api/<path:path>', methods=['OPTIONS'])
    @app.route('/api/<path:path>/<path:subpath>', methods=['OPTIONS'])
    def handle_api_options(path=None, subpath=None):
        """Handle CORS preflight requests"""
        return make_response(jsonify({'success': True}), 200)

    # Register blueprints
    from routes.evaluation import bp as evaluation_bp
    app.register_blueprint(evaluation_bp)
    
    # Register v2 API blueprints
    try:
        from routes.multi_target_v2 import bp as multi_target_v2_bp
        app.register_blueprint(multi_target_v2_bp)
        logger.info("v2 多靶点API已注册")
    except ImportError as e:
        logger.warning(f"v2 多靶点API注册失败: {e}")

    # Frontend static files (Vite build from frontend/dist/)
    FRONTEND_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')

    @app.route('/')
    def index():
        """首页/评估页面 - 服务 Vite 构建的前端"""
        return send_from_directory(FRONTEND_DIST, 'index.html')

    @app.route('/evaluation')
    def evaluation_page():
        """评估页面 - 服务 Vite 构建的前端"""
        return send_from_directory(FRONTEND_DIST, 'index.html')

    # Serve static assets from Vite build
    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        """服务 Vite 构建的静态资源"""
        return send_from_directory(os.path.join(FRONTEND_DIST, 'assets'), filename)

    # Serve root-level static files from dist (favicon, icons, etc.)
    @app.route('/favicon.svg')
    def serve_favicon():
        return send_from_directory(FRONTEND_DIST, 'favicon.svg')

    @app.route('/icons.svg')
    def serve_icons():
        return send_from_directory(FRONTEND_DIST, 'icons.svg')

    @app.route('/health')
    def health():
        """健康检查"""
        return {'status': 'ok', 'service': 'protein-evaluator'}

    @app.route('/protein_evaluator_manual.html')
    def manual_page():
        """操作手册页面"""
        return send_from_directory(os.path.dirname(__file__), 'protein_evaluator_manual.html')

    # 初始化默认模板
    _init_default_templates()

    logger.info("Flask应用创建成功")
    return app


def _init_default_templates():
    """初始化默认模板"""
    from src.database import get_all_prompt_templates, create_prompt_template, get_session, PromptTemplate, update_prompt_template

    templates = get_all_prompt_templates()
    default_content_zh = getattr(config, 'AI_PROMPT_TEMPLATE', '')
    default_content_en = getattr(config, 'AI_PROMPT_TEMPLATE_EN', '')

    if not templates:
        # 没有模板，创建默认模板
        if default_content_zh:
            create_prompt_template(
                name="默认模板",
                name_en="Default Template",
                content=default_content_zh,
                content_en=default_content_en,
                description="系统默认的蛋白质分析报告模板",
                description_en="System default protein analysis report template",
                is_default=True
            )
            logger.info("已创建默认模板")
    else:
        # 更新现有模板，添加英文字段（如果缺少）
        session = get_session()
        try:
            for template in session.query(PromptTemplate).all():
                updates = {}
                # 只更新缺少英文内容的模板
                if template.template_type == 'single':
                    if not template.content_en and default_content_en:
                        updates['content_en'] = default_content_en
                    if not template.name_en:
                        updates['name_en'] = "Default Template"
                    if not template.description_en:
                        updates['description_en'] = "System default protein analysis report template"
                elif template.template_type == 'batch':
                    if not template.content_en and default_content_en:
                        updates['content_en'] = default_content_en
                    if not template.name_en:
                        updates['name_en'] = "Default Batch Analysis Template"
                    if not template.description_en:
                        updates['description_en'] = "System default batch relationship analysis template"

                if updates:
                    update_prompt_template(template.id, updates)
                    logger.info(f"已为模板 {template.id} 添加英文字段: {list(updates.keys())}")
        finally:
            session.close()


# Lazy app instance - only created when accessed (not at import time)
_app_instance = None

def _get_app():
    """Get or create the Flask app instance (lazy initialization)"""
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    return _app_instance

# For backwards compatibility: app object that lazily initializes
class LazyApp:
    """Lazy proxy to app instance"""
    def __getattr__(self, name):
        return getattr(_get_app(), name)

    def __call__(self, *args, **kwargs):
        return _get_app()(*args, **kwargs)

app = LazyApp()


@app.route('/api/config', methods=['GET', 'PUT', 'OPTIONS'])
def get_config():
    """Get or update AI configuration"""
    if request.method == 'OPTIONS':
        return make_response(jsonify({'success': True}), 200)

    if request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        # Update config values in memory (for current session)
        if 'model' in data:
            config.AI_MODEL = data['model']
        if 'temperature' in data:
            config.AI_TEMPERATURE = float(data['temperature'])
        if 'max_tokens' in data:
            config.AI_MAX_TOKENS = int(data['max_tokens'])

        return jsonify({
            'success': True,
            'message': '配置已更新',
            'config': {
                'model': config.AI_MODEL,
                'temperature': config.AI_TEMPERATURE,
                'max_tokens': config.AI_MAX_TOKENS,
            }
        })

    # GET: Return current config
    return jsonify({
        'success': True,
        'config': {
            'model': config.AI_MODEL,
            'temperature': config.AI_TEMPERATURE,
            'max_tokens': config.AI_MAX_TOKENS,
        }
    })


@app.route('/api/pdb/<pdb_id>', methods=['GET', 'OPTIONS'])
def get_pdb_info(pdb_id):
    """Get PDB structure information"""
    if request.method == 'OPTIONS':
        return make_response(jsonify({'success': True}), 200)
    try:
        from src.api_clients import PDBClient
        pdb_client = PDBClient()
        info = pdb_client.get_structure(pdb_id)
        if info:
            return jsonify({'success': True, **info})
        return jsonify({'success': False, 'error': 'PDB not found'}), 404
    except Exception as e:
        logger.error(f"Failed to get PDB info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alphafold/<uniprot_id>', methods=['GET', 'OPTIONS'])
def get_alphafold_info(uniprot_id):
    """Get AlphaFold prediction information"""
    if request.method == 'OPTIONS':
        return make_response(jsonify({'success': True}), 200)
    try:
        try:
            from src.alphafold_client import get_alphafold_model
            info = get_alphafold_model(uniprot_id)
            if info:
                return jsonify({'success': True, **info})
        except ImportError:
            pass
        return jsonify({
            'success': True,
            'model_id': f'AF-{uniprot_id}-F1',
            'confidence_score': 0.8
        })
    except Exception as e:
        logger.error(f"Failed to get AlphaFold info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
