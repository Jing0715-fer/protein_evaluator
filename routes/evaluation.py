# evaluation.py - 蛋白质评估API路由
"""
蛋白质评估API端点 - 独立运行版
"""

import os
import sys
from flask import Blueprint, jsonify, request, render_template
import logging

logger = logging.getLogger(__name__)

# 创建蓝图
bp = Blueprint('evaluation', __name__, url_prefix='/api/evaluation')

# 导入评估服务
from src.service import get_evaluation_service


@bp.route('', methods=['GET'])
def list_evaluations():
    """列出所有蛋白质评估"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        service = get_evaluation_service()
        result = service.list_evaluations(limit=limit, offset=offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"列出评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/search', methods=['GET'])
def search_evaluations():
    """搜索蛋白质评估"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': False, 'error': '请提供搜索关键词'})

        service = get_evaluation_service()
        result = service.search_evaluations(query)
        return jsonify(result)
    except Exception as e:
        logger.error(f"搜索评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/start', methods=['POST'])
def start_evaluation():
    """开始新的蛋白质评估"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        uniprot_id = data.get('uniprot_id', '').strip()
        if not uniprot_id:
            return jsonify({'success': False, 'error': '请提供UniProt ID'}), 400

        gene_name = data.get('gene_name')
        protein_name = data.get('protein_name')

        # Get config options
        config = data.get('config', {})

        service = get_evaluation_service()
        result = service.start_evaluation(
            uniprot_id=uniprot_id,
            gene_name=gene_name,
            protein_name=protein_name,
            config=config
        )

        if result.get('success'):
            return jsonify(result), 202
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"启动评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:evaluation_id>', methods=['GET'])
def get_evaluation(evaluation_id):
    """获取特定评估的详细信息"""
    try:
        service = get_evaluation_service()
        result = service.get_evaluation_status(evaluation_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:evaluation_id>/status', methods=['GET'])
def get_evaluation_status(evaluation_id):
    """获取评估状态（用于轮询）"""
    try:
        service = get_evaluation_service()
        result = service.get_evaluation_status(evaluation_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取评估状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:evaluation_id>/prompt', methods=['GET'])
def get_evaluation_prompt(evaluation_id):
    """获取评估的AI prompt"""
    try:
        service = get_evaluation_service()
        evaluation = service.get_evaluation_detail(evaluation_id)
        if not evaluation:
            return jsonify({'success': False, 'error': '评估记录不存在'}), 404

        prompt = evaluation.get('ai_prompt', '')
        if not prompt:
            return jsonify({'success': False, 'error': 'Prompt尚未生成'}), 404

        return jsonify({'success': True, 'prompt': prompt})
    except Exception as e:
        logger.error(f"获取Prompt失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:evaluation_id>', methods=['DELETE'])
def delete_evaluation(evaluation_id):
    """删除评估记录"""
    try:
        service = get_evaluation_service()
        result = service.delete_evaluation(evaluation_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"删除评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/batch-delete', methods=['POST'])
def batch_delete_evaluations():
    """批量删除评估记录"""
    try:
        data = request.get_json()
        if not data or not data.get('ids'):
            return jsonify({'success': False, 'error': '请提供要删除的评估ID'}), 400

        ids = data.get('ids', [])
        if not isinstance(ids, list):
            return jsonify({'success': False, 'error': 'IDs必须是数组'}), 400

        service = get_evaluation_service()
        result = service.batch_delete_evaluations(ids)
        return jsonify(result)
    except Exception as e:
        logger.error(f"批量删除评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== HTML页面路由 ==========

@bp.route('/page')
def evaluation_page():
    """蛋白质评估页面"""
    return render_template('evaluation.html')


@bp.route('/settings', methods=['GET', 'POST'])
def get_settings():
    """获取或保存设置"""
    import config

    if request.method == 'POST':
        data = request.get_json()
        template = data.get('prompt_template', '')

        # 保存到配置文件
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.py')
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        # 更新配置
        if 'AI_PROMPT_TEMPLATE' in config_content:
            # 替换现有的 AI_PROMPT_TEMPLATE
            import re
            pattern = r"AI_PROMPT_TEMPLATE\s*=\s*os\.environ\.get\('AI_PROMPT_TEMPLATE',\s*'''.*?'''\)"
            replacement = f"AI_PROMPT_TEMPLATE = os.environ.get('AI_PROMPT_TEMPLATE', '''{template}''')"
            config_content = re.sub(pattern, replacement, config_content, flags=re.DOTALL)

        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)

        return jsonify({'success': True, 'message': '设置已保存'})

    # GET: 返回当前模板
    template = getattr(config, 'AI_PROMPT_TEMPLATE', '')
    return jsonify({'success': True, 'prompt_template': template})
