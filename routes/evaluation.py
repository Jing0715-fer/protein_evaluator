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


# ========== Prompt Template Management ==========

@bp.route('/templates', methods=['GET'])
def get_templates():
    """获取所有模板"""
    from src.database import get_all_prompt_templates, get_default_prompt_template

    templates = get_all_prompt_templates()
    default_template = get_default_prompt_template()

    # 如果没有模板，返回配置文件中的默认模板
    if not templates:
        template = getattr(config, 'AI_PROMPT_TEMPLATE', '')
        return jsonify({
            'success': True,
            'templates': [],
            'default_content': template
        })

    return jsonify({
        'success': True,
        'templates': [t.to_dict() for t in templates],
        'default_id': default_template.id if default_template else None,
        'default_content': default_template.content if default_template else getattr(config, 'AI_PROMPT_TEMPLATE', '')
    })


@bp.route('/templates', methods=['POST'])
def create_template():
    """创建新模板"""
    from src.database import create_prompt_template

    data = request.get_json()
    name = data.get('name')
    content = data.get('content')
    description = data.get('description', '')
    is_default = data.get('is_default', False)

    if not name or not content:
        return jsonify({'success': False, 'message': '模板名称和内容不能为空'}), 400

    template = create_prompt_template(name, content, description, is_default)
    if template:
        return jsonify({'success': True, 'template': template.to_dict()})
    return jsonify({'success': False, 'message': '创建模板失败'}), 500


@bp.route('/templates/<int:template_id>', methods=['GET'])
def get_template(template_id):
    """获取单个模板"""
    from src.database import get_prompt_template

    template = get_prompt_template(template_id)
    if template:
        return jsonify({'success': True, 'template': template.to_dict()})
    return jsonify({'success': False, 'message': '模板不存在'}), 404


@bp.route('/templates/<int:template_id>', methods=['PUT'])
def update_template(template_id):
    """更新模板"""
    from src.database import update_prompt_template

    data = request.get_json()
    updates = {}

    if 'name' in data:
        updates['name'] = data['name']
    if 'content' in data:
        updates['content'] = data['content']
    if 'description' in data:
        updates['description'] = data['description']
    if 'is_default' in data:
        updates['is_default'] = data['is_default']

    if not updates:
        return jsonify({'success': False, 'message': '没有要更新的内容'}), 400

    if update_prompt_template(template_id, updates):
        return jsonify({'success': True, 'message': '模板已更新'})
    return jsonify({'success': False, 'message': '更新失败'}), 500


@bp.route('/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """删除模板"""
    from src.database import delete_prompt_template

    if delete_prompt_template(template_id):
        return jsonify({'success': True, 'message': '模板已删除'})
    return jsonify({'success': False, 'message': '删除失败'}), 500


@bp.route('/templates/<int:template_id>/set-default', methods=['POST'])
def set_default_template(template_id):
    """设置默认模板"""
    from src.database import set_default_prompt_template

    if set_default_prompt_template(template_id):
        return jsonify({'success': True, 'message': '已设为默认模板'})
    return jsonify({'success': False, 'message': '设置失败'}), 500


@bp.route('/templates/<int:template_id>/use', methods=['POST'])
def use_template(template_id):
    """使用模板进行评估（返回模板内容供评估使用）"""
    from src.database import get_prompt_template

    template = get_prompt_template(template_id)
    if template:
        return jsonify({'success': True, 'content': template.content})
    return jsonify({'success': False, 'message': '模板不存在'}), 404


# ========== Batch Evaluation API Endpoints ==========

@bp.route('/batch-start', methods=['POST'])
def start_batch_evaluation():
    """开始批量蛋白质评估"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        uniprot_ids = data.get('uniprot_ids', [])
        if not uniprot_ids:
            # Try to parse from string input
            uniprot_input = data.get('uniprot_ids_text', '')
            if uniprot_input:
                # Split by comma, newline, or space
                import re
                uniprot_ids = re.split(r'[,;\s\n]+', uniprot_input)
                uniprot_ids = [uid.strip().upper() for uid in uniprot_ids if uid.strip()]

        if not uniprot_ids or len(uniprot_ids) < 2:
            return jsonify({'success': False, 'error': '请提供至少2个UniProt ID'}), 400

        name = data.get('name')
        config = data.get('config', {})

        service = get_evaluation_service()
        result = service.start_batch_evaluation(
            uniprot_ids=uniprot_ids,
            name=name,
            config=config
        )

        if result.get('success'):
            return jsonify(result), 202
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"启动批量评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/batch', methods=['GET'])
def list_batch_evaluations():
    """获取批量评估列表"""
    try:
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))

        service = get_evaluation_service()
        result = service.list_batch_evaluations(limit=limit, offset=offset)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取批量评估列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/batch/<int:batch_id>', methods=['GET'])
def get_batch_evaluation(batch_id):
    """获取批量评估详情"""
    try:
        service = get_evaluation_service()
        result = service.get_batch_evaluation_status(batch_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取批量评估详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/batch/<int:batch_id>/status', methods=['GET'])
def get_batch_evaluation_status(batch_id):
    """获取批量评估进度"""
    try:
        service = get_evaluation_service()
        result = service.get_batch_evaluation_status(batch_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"获取批量评估状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/batch/<int:batch_id>', methods=['DELETE'])
def delete_batch_evaluation(batch_id):
    """删除批量评估"""
    try:
        service = get_evaluation_service()
        result = service.delete_batch_evaluation(batch_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"删除批量评估失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
