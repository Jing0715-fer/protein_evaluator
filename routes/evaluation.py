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
        logger.info(f"收到评估请求: uniprot_id={uniprot_id}, config={config}")

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
    """获取单个蛋白评估模板"""
    from src.database import get_single_templates, create_prompt_template, update_prompt_template

    # Import the filtered function
    from src.database import get_session, PromptTemplate
    session = None
    try:
        session = get_session()
        # Get only single templates
        templates = session.query(PromptTemplate).filter(
            PromptTemplate.template_type == 'single'
        ).order_by(PromptTemplate.is_default.desc(), PromptTemplate.name).all()

        # Get default (only single templates)
        default_template = session.query(PromptTemplate).filter(
            PromptTemplate.is_default == True,
            PromptTemplate.template_type == 'single'
        ).first()

    except Exception as e:
        logger.error(f"获取模板失败: {e}")
        templates = []
        default_template = None
    finally:
        if session:
            session.close()

    # 如果没有模板，自动创建默认模板
    if not templates:
        default_content = getattr(config, 'AI_PROMPT_TEMPLATE', '')
        default_content_en = getattr(config, 'AI_PROMPT_TEMPLATE_EN', '')
        template = create_prompt_template(
            name='默认分析模板',
            name_en='Default Analysis Template',
            content=default_content,
            content_en=default_content_en,
            description='系统默认分析模板',
            description_en='System default analysis template',
            is_default=True
        )
        if template:
            templates = [template]
            default_template = template

    # Update existing templates with English content if missing (separate session)
    if templates:
        try:
            default_content_en = getattr(config, 'AI_PROMPT_TEMPLATE_EN', '')
            for template in templates:
                if not template.content_en and default_content_en:
                    update_prompt_template(template.id, {
                        'content_en': default_content_en,
                        'description_en': template.description_en or "System default protein analysis report template",
                        'name_en': template.name_en or "Default Template"
                    })
                    logger.info(f"Added English content to single template {template.id}")
        except Exception as e:
            logger.error(f"Update template English content failed: {e}")

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
    name_en = data.get('name_en', '')
    content = data.get('content')
    content_en = data.get('content_en', '')
    description = data.get('description', '')
    description_en = data.get('description_en', '')
    is_default = data.get('is_default', False)

    if not name or not content:
        return jsonify({'success': False, 'message': '模板名称和内容不能为空'}), 400

    template = create_prompt_template(name, content, description, description_en, is_default, content_en, name_en)
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
    if 'name_en' in data:
        updates['name_en'] = data['name_en']
    if 'content' in data:
        updates['content'] = data['content']
    if 'content_en' in data:
        updates['content_en'] = data['content_en']
    if 'description' in data:
        updates['description'] = data['description']
    if 'description_en' in data:
        updates['description_en'] = data['description_en']
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


# ========== Batch Template Management ==========

@bp.route('/batch-templates', methods=['GET'])
def get_batch_templates():
    """获取批量分析模板"""
    from src.database import get_all_batch_templates, get_default_batch_template, create_batch_template, update_batch_template
    import config

    templates = get_all_batch_templates()
    default_template = get_default_batch_template()

    # If no templates in database, create default from config
    if not templates:
        default_content = getattr(config, 'BATCH_INTERACTION_PROMPT_TEMPLATE', '')
        default_content_en = getattr(config, 'BATCH_INTERACTION_PROMPT_TEMPLATE_EN', '')
        # Create default template in database
        template = create_batch_template(
            name='默认批量分析模板',
            name_en='Default Batch Analysis Template',
            content=default_content,
            content_en=default_content_en,
            description='系统默认批量关系分析模板',
            description_en='System default batch relationship analysis template',
            is_default=True,
            template_type='batch'
        )
        if template:
            templates = [template]
            default_template = template
            default_content = template.content

    # Update existing batch templates with English content if missing (separate session)
    if templates:
        try:
            default_content_en = getattr(config, 'BATCH_INTERACTION_PROMPT_TEMPLATE_EN', '')
            for template in templates:
                if not template.content_en and default_content_en:
                    update_batch_template(template.id, {
                        'content_en': default_content_en,
                        'description_en': template.description_en or "System default batch relationship analysis template",
                        'name_en': template.name_en or "Default Batch Analysis Template"
                    })
                    logger.info(f"Added English content to batch template {template.id}")
        except Exception as e:
            logger.error(f"Update batch template English content failed: {e}")

    return jsonify({
        'success': True,
        'templates': [t.to_dict() for t in templates],
        'default_id': default_template.id if default_template else None,
        'default_content': default_template.content if default_template else ''
    })


@bp.route('/batch-templates', methods=['POST'])
def create_batch_template():
    """创建批量分析模板"""
    from src.database import create_batch_template

    data = request.get_json()
    name = data.get('name')
    name_en = data.get('name_en', '')
    content = data.get('content')
    content_en = data.get('content_en', '')
    description = data.get('description', '')
    description_en = data.get('description_en', '')
    is_default = data.get('is_default', False)

    if not name or not content:
        return jsonify({'success': False, 'message': '模板名称和内容不能为空'}), 400

    template = create_batch_template(
        name, content, description, description_en, is_default, 'batch', content_en, name_en
    )
    if template:
        return jsonify({'success': True, 'template': template.to_dict()})
    return jsonify({'success': False, 'message': '创建模板失败'}), 500


@bp.route('/batch-templates/<int:template_id>', methods=['GET'])
def get_batch_template(template_id):
    """获取单个批量分析模板"""
    from src.database import get_batch_template

    template = get_batch_template(template_id)
    if template:
        return jsonify({'success': True, 'template': template.to_dict()})
    return jsonify({'success': False, 'message': '模板不存在'}), 404


@bp.route('/batch-templates/<int:template_id>', methods=['PUT'])
def update_batch_template(template_id):
    """更新批量分析模板"""
    from src.database import update_batch_template as db_update_batch_template

    data = request.get_json()
    updates = {}

    if 'name' in data:
        updates['name'] = data['name']
    if 'name_en' in data:
        updates['name_en'] = data['name_en']
    if 'content' in data:
        updates['content'] = data['content']
    if 'content_en' in data:
        updates['content_en'] = data['content_en']
    if 'description' in data:
        updates['description'] = data['description']
    if 'description_en' in data:
        updates['description_en'] = data['description_en']
    if 'is_default' in data:
        updates['is_default'] = data['is_default']

    if not updates:
        return jsonify({'success': False, 'message': '没有要更新的内容'}), 400

    if db_update_batch_template(template_id, updates):
        return jsonify({'success': True, 'message': '模板已更新'})
    return jsonify({'success': False, 'message': '更新失败'}), 500


@bp.route('/batch-templates/<int:template_id>', methods=['DELETE'])
def delete_batch_template(template_id):
    """删除批量分析模板"""
    from src.database import delete_batch_template

    if delete_batch_template(template_id):
        return jsonify({'success': True, 'message': '模板已删除'})
    return jsonify({'success': False, 'message': '删除失败'}), 500


@bp.route('/batch-templates/<int:template_id>/set-default', methods=['POST'])
def set_default_batch_template(template_id):
    """设置默认批量分析模板"""
    from src.database import set_default_batch_template

    if set_default_batch_template(template_id):
        return jsonify({'success': True, 'message': '已设为默认模板'})
    return jsonify({'success': False, 'message': '设置失败'}), 500


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


@bp.route('/batch/<int:batch_id>/stop', methods=['POST'])
def stop_batch_evaluation(batch_id):
    """停止批量评估"""
    try:
        service = get_evaluation_service()
        result = service.stop_batch_evaluation(batch_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"停止批量评估失败：{e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Multi-Target Report Generation API Endpoints ==========

@bp.route('/multi-target/<int:job_id>/report', methods=['POST'])
def generate_multi_target_report_endpoint(job_id):
    """生成多靶点批量评估报告
    
    Request Body:
        - template: 报告模板 (full/summary/detailed/minimal)，默认 full
        - format: 导出格式 (markdown/json/excel)，默认 markdown
        - include_interactions: 是否包含相互作用分析，默认 true
    
    Returns:
        - report_id: 报告ID
        - download_url: 下载链接
        - format: 格式
        - file_size: 文件大小
    """
    try:
        from src.multi_target_report_generator import MultiTargetReportGenerator
        from src.api_clients import UniProtClient
        from src.database import get_session, MultiTargetJob, Target, TargetRelationship
        from src.target_interaction_analyzer import TargetInteractionAnalyzer
        
        data = request.get_json() or {}
        template = data.get('template', 'full')
        format_type = data.get('format', 'markdown')
        include_interactions = data.get('include_interactions', True)
        
        # 验证模板和格式
        valid_templates = ['full', 'summary', 'detailed', 'minimal']
        valid_formats = ['markdown', 'json', 'excel']
        
        if template not in valid_templates:
            return jsonify({
                'success': False, 
                'error': f'无效的模板类型。有效选项: {valid_templates}'
            }), 400
            
        if format_type not in valid_formats:
            return jsonify({
                'success': False,
                'error': f'无效的格式类型。有效选项: {valid_formats}'
            }), 400
        
        # 获取任务数据
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            
            # 获取所有靶点数据
            targets = session.query(Target).filter_by(job_id=job_id).all()
            if not targets:
                return jsonify({'success': False, 'error': '任务没有靶点数据'}), 400
            
            # 构建任务数据
            job_data = {
                'job_id': job.job_id,
                'name': job.name,
                'description': job.description,
                'status': job.status,
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'target_count': len(targets),
                'evaluation_mode': job.evaluation_mode
            }
            
            # 构建靶点数据
            targets_data = []
            for target in targets:
                target_dict = target.to_dict()
                
                # 添加评估分数和详细数据（如果有）
                if target.evaluation:
                    eval_obj = target.evaluation
                    # 基本评估分数
                    target_dict['evaluation_score'] = getattr(eval_obj, 'overall_score', None)
                    
                    # 添加完整 evaluation 对象
                    evaluation_data = {
                        'id': eval_obj.id,
                        'quality_score': getattr(eval_obj, 'overall_score', None),
                        'ai_analysis': eval_obj.ai_analysis or {},
                        'pdb_data': eval_obj.pdb_data or {},
                    }
                    
                    # 从 ai_analysis 提取 quality_score
                    if eval_obj.ai_analysis and isinstance(eval_obj.ai_analysis, dict):
                        ai = eval_obj.ai_analysis
                        if ai.get('quality_score') is not None:
                            evaluation_data['quality_score'] = ai['quality_score']
                        
                        # PDB 结构数
                        if eval_obj.pdb_data and isinstance(eval_obj.pdb_data, dict):
                            pdb_ids = eval_obj.pdb_data.get('pdb_ids', [])
                            evaluation_data['pdb_count'] = len(pdb_ids)
                            evaluation_data['pdb_structures'] = pdb_ids[:10]
                    
                    target_dict['evaluation'] = evaluation_data
                
                targets_data.append(target_dict)
            
            # 获取相互作用数据（如果需要）
            interactions_data = None
            if include_interactions:
                relationships = session.query(TargetRelationship).filter_by(job_id=job_id).all()
                if relationships:
                    interactions = []
                    for rel in relationships:
                        source_target = session.query(Target).get(rel.source_target_id)
                        target_target = session.query(Target).get(rel.target_target_id)
                        interactions.append({
                            'source_uniprot': source_target.uniprot_id if source_target else None,
                            'target_uniprot': target_target.uniprot_id if target_target else None,
                            'relationship_type': rel.relationship_type,
                            'score': rel.score,
                            'metadata': rel.relationship_metadata
                        })
                    
                    # 构建聚类信息
                    analyzer = TargetInteractionAnalyzer()
                    clusters = analyzer.cluster_targets_by_similarity(targets_data, relationships)
                    
                    interactions_data = {
                        'interactions': interactions,
                        'clusters': clusters
                    }
        finally:
            session.close()
        
        # 生成报告
        generator = MultiTargetReportGenerator()
        report_result = generator.generate_multi_target_report(
            job_data=job_data,
            targets_data=targets_data,
            interactions_data=interactions_data,
            template=template,
            format=format_type
        )
        
        # 导出报告
        if format_type == 'json':
            output_path = generator.export_to_json(report_result)
        elif format_type == 'excel':
            try:
                output_path = generator.export_to_excel(report_result)
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': f'Excel导出失败: {str(e)}。请安装 pandas 和 openpyxl'
                }), 500
        else:
            output_path = generator.export_to_markdown(report_result)
        
        # 获取文件大小
        file_size = os.path.getsize(output_path)
        
        # 构建下载URL
        filename = os.path.basename(output_path)
        download_url = f'/api/evaluation/reports/{filename}'
        
        return jsonify({
            'success': True,
            'report_id': report_result['metadata']['report_id'],
            'job_id': job_id,
            'format': format_type,
            'template': template,
            'download_url': download_url,
            'file_path': output_path,
            'file_size': file_size,
            'statistics': report_result['statistics'],
            'message': '报告生成成功'
        })
        
    except Exception as e:
        logger.error(f"生成多靶点报告失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/multi-target/<int:job_id>/report-preview', methods=['GET'])
def preview_multi_target_report(job_id):
    """预览多靶点报告（生成但不保存，返回内容预览）
    
    Query Parameters:
        - template: 报告模板，默认 summary
        - max_targets: 预览的最大靶点数，默认 5
    
    Returns:
        - content: 报告内容（前2000字符）
        - total_targets: 总靶点数
        - preview_targets: 预览的靶点数
    """
    try:
        from src.multi_target_report_generator import MultiTargetReportGenerator
        from src.api_clients import UniProtClient
        from src.database import get_session, MultiTargetJob, Target
        
        template = request.args.get('template', 'summary')
        max_targets = int(request.args.get('max_targets', 5))
        
        # 获取任务数据
        session = get_session()
        try:
            job = session.query(MultiTargetJob).filter_by(job_id=job_id).first()
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            
            targets = session.query(Target).filter_by(job_id=job_id).limit(max_targets).all()
            
            job_data = {
                'job_id': job.job_id,
                'name': job.name,
                'description': job.description,
                'status': job.status,
                'created_at': job.created_at.isoformat() if job.created_at else None,
            }
            
            targets_data = []
            for target in targets:
                target_dict = target.to_dict()
                if target.evaluation:
                    target_dict['evaluation_score'] = getattr(target.evaluation, 'overall_score', None)
                targets_data.append(target_dict)
        finally:
            session.close()
        
        # 生成预览报告
        generator = MultiTargetReportGenerator()
        report_result = generator.generate_multi_target_report(
            job_data=job_data,
            targets_data=targets_data,
            template=template,
            format='markdown'
        )
        
        content = report_result['content']
        preview_content = content[:2000] + '...' if len(content) > 2000 else content
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'preview_content': preview_content,
            'total_targets': job.target_count,
            'preview_targets': len(targets_data),
            'template': template
        })
        
    except Exception as e:
        logger.error(f"预览报告失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/reports/<path:filename>', methods=['GET'])
def download_report(filename):
    """下载生成的报告文件"""
    try:
        from flask import send_from_directory
        
        # 安全检查：防止目录遍历攻击
        if '..' in filename or filename.startswith('/'):
            return jsonify({'success': False, 'error': '非法文件名'}), 400
        
        reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
        
        if not os.path.exists(os.path.join(reports_dir, filename)):
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        return send_from_directory(reports_dir, filename, as_attachment=True)
        
    except Exception as e:
        logger.error(f"下载报告失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/multi-target/<int:job_id>/reports', methods=['GET'])
def list_job_reports(job_id):
    """列出任务的所有报告"""
    try:
        import glob
        
        reports_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
        if not os.path.exists(reports_dir):
            return jsonify({'success': True, 'reports': []})
        
        # 查找与该任务相关的报告文件
        pattern = os.path.join(reports_dir, f'*_{job_id}.*')
        report_files = glob.glob(pattern)
        
        reports = []
        for filepath in sorted(report_files, key=os.path.getmtime, reverse=True):
            filename = os.path.basename(filepath)
            stat = os.stat(filepath)
            
            # 从文件名解析信息
            parts = filename.split('_')
            format_type = filename.split('.')[-1]
            
            reports.append({
                'filename': filename,
                'job_id': job_id,
                'format': format_type,
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'download_url': f'/api/evaluation/reports/{filename}'
            })
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'reports': reports,
            'total': len(reports)
        })
        
    except Exception as e:
        logger.error(f"列报告失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== AI Configuration API ==========

@bp.route('/config', methods=['GET'])
def get_ai_config():
    """获取当前 AI 配置
    
    Returns:
        - config: AI 配置对象
            - model: AI 模型名称
            - temperature: 温度参数
            - max_tokens: 最大 token 数
            - base_url: API 基础 URL（可选）
            - api_key: API Key（是否已设置，不返回实际值）
    """
    try:
        import config as app_config
        
        # 获取配置，隐藏实际的 API key
        ai_config = {
            'model': getattr(app_config, 'AI_MODEL', 'deepseek-reasoner'),
            'temperature': getattr(app_config, 'AI_TEMPERATURE', 0.3),
            'max_tokens': getattr(app_config, 'AI_MAX_TOKENS', 20000),
            'base_url': getattr(app_config, 'AI_BASE_URL', ''),
            'api_key': '已设置' if getattr(app_config, 'AI_API_KEY', '') else '',
        }
        
        return jsonify({
            'success': True,
            'config': ai_config
        })
        
    except Exception as e:
        logger.error(f"获取 AI 配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/config', methods=['PUT'])
def update_ai_config():
    """更新 AI 配置
    
    Request Body:
        - model: AI 模型名称（可选）
        - temperature: 温度参数（可选）
        - max_tokens: 最大 token 数（可选）
        - base_url: API 基础 URL（可选）
        - api_key: API Key（可选）
    
    Note:
        配置更新仅在当前进程有效，重启服务后将恢复为环境变量或默认值。
        如需持久化，建议通过环境变量设置。
    
    Returns:
        - success: 是否成功
        - message: 结果消息
    """
    try:
        import config as app_config

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400

        # 更新配置（内存中）
        if 'model' in data:
            app_config.AI_MODEL = data['model']
            app_config.save_to_env('AI_MODEL', data['model'])
        if 'temperature' in data:
            app_config.AI_TEMPERATURE = float(data['temperature'])
            app_config.save_to_env('AI_TEMPERATURE', str(data['temperature']))
        if 'max_tokens' in data:
            app_config.AI_MAX_TOKENS = int(data['max_tokens'])
            app_config.save_to_env('AI_MAX_TOKENS', str(data['max_tokens']))
        if 'base_url' in data:
            app_config.AI_BASE_URL = data['base_url']
            app_config.save_to_env('AI_BASE_URL', data['base_url'])
        if 'api_key' in data and data['api_key']:
            app_config.AI_API_KEY = data['api_key']
            app_config.save_to_env('AI_API_KEY', data['api_key'])

        logger.info(f"AI 配置已更新: model={app_config.AI_MODEL}, temp={app_config.AI_TEMPERATURE}")

        return jsonify({
            'success': True,
            'message': '配置已更新'
        })
        
    except Exception as e:
        logger.error(f"更新 AI 配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== AI Models Management API ==========

# In-memory storage for model configs (in production, use database)
_model_configs = []
_default_model_id = None

# 模型配置持久化文件路径
MODEL_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'model_configs.json')

def _load_model_configs():
    """从文件加载模型配置"""
    global _model_configs, _default_model_id
    import json

    if os.path.exists(MODEL_CONFIG_FILE):
        try:
            with open(MODEL_CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _model_configs = data.get('models', [])

                # Compute default_model_id from isDefault flag, not from JSON's potentially stale value
                default_model = next((m for m in _model_configs if m.get('isDefault')), None)
                if default_model:
                    _default_model_id = default_model['id']
                else:
                    _default_model_id = data.get('default_model_id')

                logger.info(f"已加载 {len(_model_configs)} 个模型配置")
        except Exception as e:
            logger.error(f"加载模型配置失败: {e}")

def _save_model_configs():
    """保存模型配置到文件"""
    global _model_configs, _default_model_id
    import json
    
    try:
        os.makedirs(os.path.dirname(MODEL_CONFIG_FILE), exist_ok=True)
        with open(MODEL_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'models': _model_configs,
                'default_model_id': _default_model_id
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存 {len(_model_configs)} 个模型配置到文件")
    except Exception as e:
        logger.error(f"保存模型配置失败: {e}")

# 启动时加载配置
_load_model_configs()

@bp.route('/models', methods=['GET'])
def get_models():
    """获取所有 AI 模型配置
    
    Returns:
        - success: 是否成功
        - models: 模型配置列表
    """
    try:
        global _model_configs, _default_model_id
        
        # If no configs saved, return empty list (frontend will use defaults)
        if not _model_configs:
            return jsonify({
                'success': True,
                'models': []
            })
        
        # Return configs with API keys masked
        models_response = []
        for model in _model_configs:
            model_copy = model.copy()
            if model_copy.get('apiKey'):
                model_copy['apiKey'] = '***'
            models_response.append(model_copy)
        
        return jsonify({
            'success': True,
            'models': models_response,
            'default_model_id': _default_model_id
        })
        
    except Exception as e:
        logger.error(f"获取模型配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models', methods=['PUT'])
def save_models():
    """保存所有 AI 模型配置
    
    Request Body:
        - models: 模型配置列表
    
    Returns:
        - success: 是否成功
        - message: 结果消息
    """
    try:
        global _model_configs, _default_model_id
        
        data = request.get_json()
        if not data or 'models' not in data:
            return jsonify({'success': False, 'error': '请求体必须包含 models 字段'}), 400
        
        models = data['models']
        if not isinstance(models, list):
            return jsonify({'success': False, 'error': 'models 必须是数组'}), 400
        
        # Validate models
        for model in models:
            if not model.get('id') or not model.get('name') or not model.get('model'):
                return jsonify({'success': False, 'error': '每个模型必须包含 id, name 和 model 字段'}), 400
        
        # Merge with existing configs to preserve API keys if not changed
        existing_models = {m['id']: m for m in _model_configs}
        merged_models = []
        for model in models:
            existing = existing_models.get(model['id'])
            if existing and model.get('apiKey') == '***':
                # API key not changed, keep existing
                model['apiKey'] = existing.get('apiKey', '')
            merged_models.append(model)
        
        _model_configs = merged_models
        
        # 持久化到文件
        _save_model_configs()
        
        # Update default model
        default_model = next((m for m in _model_configs if m.get('isDefault')), None)

        # If default model has no API key, find one that has API key
        if not default_model or not default_model.get('apiKey'):
            model_with_key = next((m for m in _model_configs if m.get('apiKey')), None)
            if model_with_key:
                default_model = model_with_key
                logger.info(f"默认模型无API Key，已切换到有Key的模型: {default_model['name']}")

        if default_model:
            _default_model_id = default_model['id']
            # Update app config
            import config as app_config
            app_config.AI_MODEL = default_model['model']
            app_config.AI_BASE_URL = default_model.get('baseUrl', '')
            app_config.AI_API_KEY = default_model.get('apiKey', '')
            app_config.AI_TEMPERATURE = default_model.get('temperature', 0.3)
            app_config.AI_MAX_TOKENS = default_model.get('maxTokens', 20000)

            # Persist to .env file for persistence across restarts
            app_config.save_to_env('AI_MODEL', default_model['model'])
            app_config.save_to_env('AI_BASE_URL', default_model.get('baseUrl', ''))
            app_config.save_to_env('AI_API_KEY', default_model.get('apiKey', ''))
            app_config.save_to_env('AI_TEMPERATURE', str(default_model.get('temperature', 0.3)))
            app_config.save_to_env('AI_MAX_TOKENS', str(default_model.get('maxTokens', 20000)))
        
        logger.info(f"已保存 {len(_model_configs)} 个模型配置")
        
        return jsonify({
            'success': True,
            'message': f'已保存 {len(_model_configs)} 个模型配置'
        })
        
    except Exception as e:
        logger.error(f"保存模型配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/test', methods=['POST'])
def test_model_connection():
    """测试模型连接
    
    Request Body:
        - model: 模型配置对象
    
    Returns:
        - success: 是否连接成功
        - message: 结果消息
        - error: 错误信息（如果失败）
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求体不能为空'}), 400
        
        logger.info(f"测试连接收到的数据: {data}")
        
        model_config = data
        
        # Get required fields
        model_id = model_config.get('model', '')
        base_url = model_config.get('baseUrl', '')
        api_key = model_config.get('apiKey', '')
        api_type = model_config.get('apiType', '')

        # If apiKey is masked placeholder, look up the real one from stored configs
        if api_key == '***':
            model_id_from_request = model_config.get('id', '')
            stored_model = next((m for m in _model_configs if m.get('id') == model_id_from_request), None)
            if stored_model and stored_model.get('apiKey'):
                api_key = stored_model['apiKey']
                logger.info(f"使用存储的真实 API Key 进行测试")

        # If baseUrl is empty, try to get from stored config or default
        if not base_url:
            if stored_model and stored_model.get('baseUrl'):
                base_url = stored_model['baseUrl']
            elif api_type == 'anthropic' or 'claude' in model_id.lower():
                base_url = 'https://api.anthropic.com/v1'
            else:
                base_url = 'https://api.openai.com/v1'

        if not model_id:
            return jsonify({'success': False, 'error': '模型 ID 不能为空'}), 400
        
        # Try to make a simple test request
        try:
            import requests
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Determine API endpoint based on apiType or model name
            if api_type == 'anthropic' or 'claude' in model_id.lower():
                # Anthropic API (including MiniMax anthropic-compatible API)
                if not api_key:
                    return jsonify({'success': False, 'error': 'Claude API 需要 API Key'})
                
                headers['x-api-key'] = api_key
                headers['anthropic-version'] = '2023-06-01'
                
                test_url = base_url or 'https://api.anthropic.com/v1'
                test_payload = {
                    'model': model_id,
                    'max_tokens': 10,
                    'messages': [{'role': 'user', 'content': 'Hello'}]
                }
                
                response = requests.post(
                    f"{test_url}/messages",
                    headers=headers,
                    json=test_payload,
                    timeout=30
                )
                
            elif 'gpt' in model_id.lower() or model_id.startswith('text-'):
                # OpenAI API
                if not api_key:
                    return jsonify({'success': False, 'error': 'OpenAI API 需要 API Key'})
                
                headers['Authorization'] = f'Bearer {api_key}'
                
                test_url = base_url or 'https://api.openai.com/v1'
                test_payload = {
                    'model': model_id,
                    'messages': [{'role': 'user', 'content': 'Hello'}],
                    'max_tokens': 10
                }
                
                response = requests.post(
                    f"{test_url}/chat/completions",
                    headers=headers,
                    json=test_payload,
                    timeout=30
                )
                
            else:
                # Generic OpenAI-compatible API (DeepSeek, Doubao, etc.)
                # 所有兼容 API 都需要 API Key
                if not api_key:
                    return jsonify({'success': False, 'error': 'API Key 不能为空'})
                
                headers['Authorization'] = f'Bearer {api_key}'
                
                test_url = base_url or 'https://api.deepseek.com/v1'
                test_payload = {
                    'model': model_id,
                    'messages': [{'role': 'user', 'content': 'Hello'}],
                    'max_tokens': 10
                }
                
                response = requests.post(
                    f"{test_url}/chat/completions",
                    headers=headers,
                    json=test_payload,
                    timeout=30
                )
            
            if response.status_code == 200:
                return jsonify({
                    'success': True,
                    'message': '连接成功'
                })
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}'
                return jsonify({
                    'success': False,
                    'error': f'API 错误: {error_msg}'
                })
                
        except requests.exceptions.Timeout:
            return jsonify({
                'success': False,
                'error': '连接超时，请检查网络或 API 地址'
            })
        except requests.exceptions.ConnectionError:
            return jsonify({
                'success': False,
                'error': '无法连接到 API，请检查 Base URL'
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'请求异常: {str(e)}'
            })
        
    except Exception as e:
        logger.error(f"测试模型连接失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
