# service.py - 蛋白质评估服务
"""
蛋白质评估模块 - 独立运行版
功能：
1. 获取PDB/RCSB元数据
2. 获取UniProt元数据
3. 运行BLAST搜索
4. 运行AI分析
5. 生成评估报告
"""

import os
import sys
import json
import logging
import requests
import threading
import time
from functools import wraps
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入配置
import config

logger = logging.getLogger(__name__)

# Create不使用代理的session
def get_no_proxy_session():
    """创建不使用代理的session"""
    session = requests.Session()
    session.trust_env = False  # 禁用环境变量中的代理
    return session

# 全局session
http_session = get_no_proxy_session()


# ========== 重试装饰器 ==========
def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    API调用重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟倍增因子
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries}), {wait_time}秒后重试: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} 失败 (已重试{max_retries}次): {e}")
            raise last_exception
        return wrapper
    return decorator

# 导入数据库模型
from src.database import (
    create_protein_evaluation,
    get_protein_evaluation,
    get_protein_evaluation_by_uniprot,
    get_all_protein_evaluations,
    update_protein_evaluation,
    delete_protein_evaluation,
    search_protein_evaluations,
    create_batch_evaluation,
    get_batch_evaluation,
    get_all_batch_evaluations,
    update_batch_evaluation,
    delete_batch_evaluation,
    create_protein_interaction,
    get_protein_interactions,
    delete_protein_interactions
)

# 导入API客户端
from core.uniprot_client import UniProtAPIClient
from core.pdb_fetcher import PDBFetcher
from utils.ai_client import get_ai_client, OpenAIClient, AnthropicClient, GeminiClient

# 导入PubMed客户端
try:
    from core.pubmed_client import PubMedClient
    HAS_PUBMED = True
except ImportError:
    HAS_PUBMED = False

# 评估步骤定义
EVALUATION_STEPS = {
    'pending': {'progress': 0, 'message': '等待开始'},
    'fetching_pdb': {'progress': 10, 'message': '获取PDB数据'},
    'fetching_uniprot': {'progress': 30, 'message': '获取UniProt数据'},
    'blasting': {'progress': 50, 'message': '执行BLAST搜索'},
    'analyzing': {'progress': 70, 'message': 'AI分析中'},
    'generating_report': {'progress': 90, 'message': '生成报告'},
    'completed': {'progress': 100, 'message': '评估完成'},
    'failed': {'progress': 0, 'message': '评估失败'}
}


class ProteinEvaluationService:
    """蛋白质评估服务"""

    def __init__(self):
        self.uniprot_client = UniProtAPIClient()
        self.pdb_fetcher = PDBFetcher()
        self.ai_client = None
        self.config = {
            'max_pdb': 100,
            'max_literature': 20,
            'ai_temperature': 0.3,
            'ai_max_tokens': 6000,
            'ai_prompt': ''
        }
        self._init_ai_client()

    def _init_ai_client(self):
        """初始化AI客户端"""
        try:
            self.ai_client = get_ai_client()
            logger.info("AI客户端初始化成功")
        except Exception as e:
            logger.warning(f"AI客户端初始化失败: {e}")

    def start_evaluation(self, uniprot_id: str, gene_name: str = None, protein_name: str = None, config: Dict = None) -> Dict[str, Any]:
        """
        开始蛋白质评估（异步执行）

        参数:
            uniprot_id: UniProt蛋白质ID
            gene_name: 基因名称（可选）
            protein_name: 蛋白质名称（可选）
            config: 配置选项（可选）

        返回:
            评估任务信息
        """
        # Set default config
        if config is None:
            config = {}

        default_config = {
            'max_pdb': 100,
            'max_literature': 20,
            'ai_temperature': 0.3,
            'ai_max_tokens': 6000,
            'ai_prompt': ''
        }
        default_config.update(config)

        # Set config for this evaluation
        self.config = default_config

        try:
            # 创建评估记录
            evaluation = create_protein_evaluation(
                uniprot_id=uniprot_id,
                gene_name=gene_name,
                protein_name=protein_name
            )

            if not evaluation:
                return {'success': False, 'error': '创建评估记录失败'}

            # 在后台线程中执行评估
            thread = threading.Thread(
                target=self._run_evaluation_task,
                args=(evaluation.id, uniprot_id, default_config)
            )
            thread.daemon = True
            thread.start()

            return {
                'success': True,
                'evaluation_id': evaluation.id,
                'uniprot_id': uniprot_id,
                'message': '评估任务已启动'
            }

        except Exception as e:
            logger.error(f"启动评估失败: {e}")
            return {'success': False, 'error': str(e)}

    def _add_log(self, evaluation_id: int, message: str, level: str = 'info'):
        """添加日志到评估记录"""
        try:
            evaluation = get_protein_evaluation(evaluation_id)
            if evaluation:
                logs = evaluation.logs or []
                logs.append({
                    'timestamp': time.strftime('%H:%M:%S'),
                    'level': level,
                    'message': message
                })
                update_protein_evaluation(evaluation_id, {'logs': logs})
        except Exception as e:
            logger.warning(f"添加日志失败: {e}")

    def _run_evaluation_task(self, evaluation_id: int, uniprot_id: str, config: Dict = None):
        """在后台线程中执行评估任务"""
        task_start_time = time.time()
        step_times = {}  # 记录每个步骤的耗时
        logs = []  # 本地日志列表，用于批量更新

        # Set config for this evaluation
        default_config = {
            'max_pdb': 100,
            'max_literature': 20,
            'ai_temperature': 0.3,
            'ai_max_tokens': 6000,
            'ai_prompt': ''
        }
        if config:
            default_config.update(config)
        self.config = default_config

        try:
            logger.info(f"========== 开始评估任务 [ID={evaluation_id}, UniProt={uniprot_id}] ==========")
            logger.info(f"使用AI配置: provider={self.config.get('ai_provider')}, model={self.config.get('ai_model')}")

            # 添加开始日志
            self._add_log(evaluation_id, f"开始评估任务: UniProt ID = {uniprot_id}")

            # 更新状态为处理中
            update_protein_evaluation(evaluation_id, {
                'evaluation_status': 'processing',
                'current_step': 'fetching_pdb',
                'progress': 10
            })

            # 步骤1: 获取UniProt元数据
            self._add_log(evaluation_id, "[步骤1/6] 开始获取UniProt元数据...")
            step_start = time.time()
            uniprot_data = self._fetch_uniprot_metadata(uniprot_id)
            step_time = time.time() - step_start
            step_times['fetch_uniprot'] = step_time

            logger.info(f"[步骤1/6] 获取UniProt元数据: 耗时 {step_time:.2f}秒")
            if uniprot_data:
                self._add_log(evaluation_id, f"UniProt元数据获取成功: {uniprot_data.get('protein_name', 'N/A')[:50]}")
                self._add_log(evaluation_id, f"基因名: {', '.join(uniprot_data.get('gene_names', []))}")
                self._add_log(evaluation_id, f"物种: {uniprot_data.get('organism', 'N/A')}")
                self._add_log(evaluation_id, f"PDB结构数量: {len(uniprot_data.get('pdb_ids', []))}")
            else:
                self._add_log(evaluation_id, "警告: 未能获取UniProt数据", 'warning')

            update_protein_evaluation(evaluation_id, {
                'uniprot_data': uniprot_data,
                'current_step': 'fetching_uniprot',
                'progress': 30
            })

            # 从UniProt数据中提取基因名和蛋白质名
            if uniprot_data:
                gene_name = uniprot_data.get('gene_names', [None])[0]
                protein_name = uniprot_data.get('protein_name', None)
                update_protein_evaluation(evaluation_id, {
                    'gene_name': gene_name,
                    'protein_name': protein_name
                })

            # 步骤2: 获取PDB数据
            pdb_ids = uniprot_data.get('pdb_ids', []) if uniprot_data else []
            # Limit PDB count based on config
            max_pdb = self.config.get('max_pdb', 100)
            if len(pdb_ids) > max_pdb:
                pdb_ids = pdb_ids[:max_pdb]
                self._add_log(evaluation_id, f"限制PDB数量为 {max_pdb} 个 (原始: {len(uniprot_data.get('pdb_ids', []))})")

            self._add_log(evaluation_id, f"[步骤2/6] 开始获取PDB数据, 共 {len(pdb_ids)} 个结构...")
            step_start = time.time()
            pdb_data = self._fetch_pdb_metadata(pdb_ids, evaluation_id)
            step_time = time.time() - step_start
            step_times['fetch_pdb'] = step_time

            structures_count = len(pdb_data.get('structures', []))
            citations_count = sum(len(s.get('citations', [])) for s in pdb_data.get('structures', []))

            self._add_log(evaluation_id, f"PDB数据获取完成: 耗时 {step_time:.2f}秒")
            self._add_log(evaluation_id, f"获取到 {structures_count} 个PDB结构, {citations_count} 篇文献")

            # 统计分辨率信息
            resolutions = [s.get('basic_info', {}).get('resolution') for s in pdb_data.get('structures', []) if s.get('basic_info', {}).get('resolution')]
            if resolutions:
                avg_res = sum(resolutions)/len(resolutions)
                self._add_log(evaluation_id, f"分辨率范围: {min(resolutions):.2f} - {max(resolutions):.2f} Å (平均: {avg_res:.2f} Å)")

            # 统计实验方法
            methods = {}
            for s in pdb_data.get('structures', []):
                method = s.get('basic_info', {}).get('experimental_method', 'Unknown')
                methods[method] = methods.get(method, 0) + 1
            methods_str = ', '.join([f"{k}: {v}" for k, v in methods.items()])
            self._add_log(evaluation_id, f"实验方法: {methods_str}")

            update_protein_evaluation(evaluation_id, {
                'pdb_data': pdb_data,
                'current_step': 'blasting',
                'progress': 50
            })

            # 计算 PDB 序列覆盖度
            protein_length = uniprot_data.get('sequence_length', 0) if uniprot_data else 0
            coverage_info = self._calculate_pdb_coverage(pdb_data, protein_length, uniprot_id)
            coverage_pct = coverage_info.get('coverage_percent', 0)
            self._add_log(evaluation_id, f"PDB序列覆盖度: {coverage_pct:.1f}% (蛋白长度: {protein_length} aa, 覆盖残基: {coverage_info.get('covered_residues', 0)} aa)")

            # 检查是否需要执行 BLAST 搜索
            # 条件: 覆盖度 < 50% 或 PDB 数量 < 5
            pdb_count = len(pdb_data.get('structures', []))
            need_blast = coverage_pct < 50 or pdb_count < 5

            # 步骤3: 运行BLAST搜索（仅当需要时）
            if need_blast:
                self._add_log(evaluation_id, f"[步骤3/6] 开始执行BLAST同源蛋白搜索 (覆盖度 {coverage_pct:.1f}% < 50% 或 PDB {pdb_count} < 5)...")
                sequence = uniprot_data.get('sequence', '') if uniprot_data else ''
                # 确保 sequence 是字符串
                if isinstance(sequence, int):
                    sequence = ''
                step_start = time.time()
                blast_results = self._run_blast_search(uniprot_id, sequence, evaluation_id) if uniprot_id else {}
                step_time = time.time() - step_start
                step_times['blast_search'] = step_time

                blast_count = len(blast_results.get('results', []))
                blast_method = blast_results.get('method', 'unknown')
                self._add_log(evaluation_id, f"BLAST搜索完成: 耗时 {step_time:.2f}秒, 找到 {blast_count} 个相似蛋白 (方法: {blast_method})")
            else:
                self._add_log(evaluation_id, f"[步骤3/6] 跳过BLAST搜索 (覆盖度 {coverage_pct:.1f}% >= 50% 且 PDB {pdb_count} >= 5)")
                blast_results = {}

            # 如果 BLAST 返回了 PDB 数据，获取其元数据
            if blast_results.get('pdb_data'):
                self._add_log(evaluation_id, f"BLAST 相似结构 PDB 元数据获取完成")

                # 将BLAST本身的结构合并到主PDB数据中
                blast_pdb = blast_results.get('pdb_data', {})
                own_structures = blast_pdb.get('own_structures', [])
                homolog_structures = blast_pdb.get('homolog_structures', [])

                if own_structures:
                    # 获取本身结构的元数据
                    own_pdb_data = self._fetch_pdb_metadata(own_structures, None)
                    if own_pdb_data and own_pdb_data.get('structures'):
                        # 合并到主PDB数据
                        if not pdb_data:
                            pdb_data = {'structures': []}
                        if pdb_data.get('structures'):
                            pdb_data['structures'].extend(own_pdb_data['structures'])
                        else:
                            pdb_data['structures'] = own_pdb_data['structures']

                        # 更新计数
                        structures_count = len(pdb_data.get('structures', []))
                        citations_count = sum(len(s.get('citations', [])) for s in pdb_data.get('structures', []))
                        self._add_log(evaluation_id, f"本身结构已合并到PDB统计: 共 {structures_count} 个PDB结构, {citations_count} 篇文献")

                # 同源结构也合并到文献（标记为同源）
                if homolog_structures:
                    homolog_pdb = blast_pdb
                    if homolog_pdb and homolog_pdb.get('structures'):
                        if not pdb_data:
                            pdb_data = {'structures': []}
                        # 标记为同源结构文献
                        for struct in homolog_pdb.get('structures', []):
                            struct['is_homolog'] = True
                        if pdb_data.get('structures'):
                            pdb_data['structures'].extend(homolog_pdb['structures'])
                        else:
                            pdb_data['structures'] = homolog_pdb['structures']

            # 更新覆盖度信息（合并 BLAST 结果后重新计算）
            if pdb_data and protein_length > 0:
                final_coverage = self._calculate_pdb_coverage(pdb_data, protein_length, uniprot_id)
                pdb_data['coverage'] = final_coverage

            update_protein_evaluation(evaluation_id, {
                'blast_results': blast_results,
                'pdb_data': pdb_data,  # 保存合并后的PDB数据
                'current_step': 'analyzing',
                'progress': 70
            })

            # 步骤4: 运行AI分析
            self._add_log(evaluation_id, "[步骤4/6] 开始AI深度分析...")
            step_start = time.time()
            ai_analysis = self._run_ai_analysis(
                uniprot_data=uniprot_data,
                pdb_data=pdb_data,
                blast_results=blast_results,
                evaluation_id=evaluation_id
            )
            step_time = time.time() - step_start
            step_times['ai_analysis'] = step_time

            if ai_analysis.get('analysis'):
                self._add_log(evaluation_id, f"AI分析完成: 耗时 {step_time:.2f}秒, 生成 {len(ai_analysis['analysis'])} 字符")
            if ai_analysis.get('model'):
                self._add_log(evaluation_id, f"使用AI模型: {ai_analysis['model']}")

            if not ai_analysis.get('success', True):
                self._add_log(evaluation_id, f"AI分析警告: {ai_analysis.get('error', '未知错误')}", 'warning')

            update_protein_evaluation(evaluation_id, {
                'ai_analysis': ai_analysis,
                'current_step': 'generating_report',
                'progress': 90
            })

            # 步骤5: 生成报告
            self._add_log(evaluation_id, "[步骤5/6] 开始生成评估报告...")
            step_start = time.time()
            report = self._generate_report(
                uniprot_data=uniprot_data,
                pdb_data=pdb_data,
                blast_results=blast_results,
                ai_analysis=ai_analysis
            )
            step_time = time.time() - step_start
            step_times['generate_report'] = step_time

            self._add_log(evaluation_id, f"报告生成完成: 耗时 {step_time:.2f}秒, 报告字数: {len(report)} 字符")

            update_protein_evaluation(evaluation_id, {
                'report': report,
                'evaluation_status': 'completed',
                'current_step': 'completed',
                'progress': 100
            })

            # 计算总耗时
            total_time = time.time() - task_start_time
            step_times['total'] = total_time

            # 输出汇总
            logger.info(f"========== 评估任务完成 [ID={evaluation_id}] ==========")
            logger.info(f"总耗时: {total_time:.2f}秒 ({total_time/60:.2f}分钟)")

            # 添加完成日志
            self._add_log(evaluation_id, f"评估完成! 总耗时: {total_time:.2f}秒 ({total_time/60:.2f}分钟)")
            self._add_log(evaluation_id, "=" * 40)

        except Exception as e:
            logger.error(f"评估任务失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # 添加错误日志
            self._add_log(evaluation_id, f"评估失败: {str(e)}", 'error')
            self._add_log(evaluation_id, f"失败步骤: {traceback.format_exc()[-500:]}", 'error')

            update_protein_evaluation(evaluation_id, {
                'evaluation_status': 'failed',
                'error_message': str(e),
                'current_step': 'failed'
            })

    @retry_on_failure(max_retries=3, delay=1.0)
    def _fetch_uniprot_metadata(self, uniprot_id: str) -> Dict[str, Any]:
        """获取UniProt元数据 - 直接调用API"""
        try:
            # 直接调用UniProt API，绕过代理问题
            url = f"http://rest.uniprot.org/uniprotkb/{uniprot_id}?format=json"
            response = http_session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # 提取需要的字段
            uniprot_id = data.get('primaryAccession', '')
            entry_name = data.get('uniProtkbId', '')

            # 蛋白质名称
            protein_name = ''
            protein_desc = data.get('proteinDescription', {})
            if protein_desc.get('recommendedName'):
                protein_name = protein_desc['recommendedName'].get('fullName', {}).get('value', '')

            # 基因名
            gene_names = []
            genes = data.get('genes', [])
            for gene in genes:
                if gene.get('geneName'):
                    gene_names.append(gene['geneName'].get('value', ''))
                for syn in gene.get('synonyms', []):
                    gene_names.append(syn.get('value', ''))

            # 物种
            organism = ''
            org_data = data.get('organism', {})
            if org_data:
                organism = org_data.get('scientificName', '')

            # 功能描述 - 修复: UniProt API 使用 commentType 而非 type
            function = ''
            try:
                comments = data.get('comments')
                if isinstance(comments, list):
                    for comment in comments:
                        # 检查 commentType 或 type 字段
                        if comment.get('commentType') == 'FUNCTION' or comment.get('type') == 'function':
                            texts = comment.get('texts')
                            if isinstance(texts, list) and len(texts) > 0:
                                first_text = texts[0]
                                if isinstance(first_text, dict):
                                    function = first_text.get('value', '') or ''
                            if function:
                                break

                # 如果没有，尝试从 proteinDescription 中获取
                if not function:
                    protein_desc = data.get('proteinDescription', {})
                    # 尝试获取 recommendedName -> alternativeNames -> fullName
                    for name_type in ['recommendedName', 'alternativeNames', 'subunitName']:
                        name_data = protein_desc.get(name_type, {})
                        if isinstance(name_data, dict):
                            full_name = name_data.get('fullName', {})
                            if isinstance(full_name, dict):
                                fn = full_name.get('value', '')
                                if fn and len(fn) > 50:  # 功能描述通常较长
                                    function = fn
                                    break

                # 尝试从 genes 获取额外的功能信息
                if not function:
                    genes = data.get('genes', [])
                    for gene in genes:
                        syns = gene.get('synonyms', [])
                        for syn in syns:
                            if isinstance(syn, dict):
                                val = syn.get('value', '')
                                # 检查是否是功能描述
                                if val and len(val) > 100:
                                    function = val
                                    break

            except Exception as e:
                logger.warning(f"获取function失败: {e}")

            # 序列
            sequence_length = 0
            protein_sequence = ''
            sequence_info = data.get('sequence', {})
            if sequence_info:
                sequence_length = sequence_info.get('length', 0)
                protein_sequence = sequence_info.get('value', '')  # 实际的序列字符串

            # 分子量
            mass = sequence_info.get('molWeight', 0)

            # PDB IDs
            pdb_ids = []
            for ref in data.get('uniProtKBCrossReferences', []):
                if ref.get('database') == 'PDB':
                    pdb_ids.append(ref.get('id', ''))

            # 关键词
            keywords = []
            try:
                kw_list = data.get('keywords')
                if isinstance(kw_list, list):
                    for kw in kw_list:
                        if isinstance(kw, dict):
                            kw_obj = kw.get('keyword')
                            if isinstance(kw_obj, dict):
                                val = kw_obj.get('value')
                                if val:
                                    keywords.append(val)
            except Exception as e:
                logger.warning(f"获取keywords失败: {e}")

            logger.info(f"UniProt API 响应解析完成:")
            logger.info(f"  - primaryAccession: {uniprot_id}")
            logger.info(f"  - entryName: {entry_name}")
            logger.info(f"  - proteinName: {protein_name[:50]}..." if len(protein_name) > 50 else f"  - proteinName: {protein_name}")
            logger.info(f"  - geneNames: {gene_names}")
            logger.info(f"  - organism: {organism}")
            logger.info(f"  - sequenceLength: {sequence_length} aa")
            logger.info(f"  - mass: {mass} Da")
            logger.info(f"  - pdbIds: {list(set(pdb_ids))}")

            return {
                'uniprot_id': uniprot_id,
                'entry_name': entry_name,
                'protein_name': protein_name,
                'gene_names': gene_names,
                'organism': organism,
                'function': function,
                'sequence': protein_sequence,  # 存储实际的序列字符串
                'sequence_length': sequence_length,  # 序列长度
                'mass': mass,
                'pdb_ids': list(set(pdb_ids)),
                'keywords': keywords,
                'raw_data': data
            }
            logger.info(f"UniProt元数据获取成功: ID={uniprot_id}, function长度={len(function) if function else 0}")
        except Exception as e:
            logger.error(f"获取UniProt元数据失败: {e}")
            # 尝试备用方法
            try:
                entry = self.uniprot_client.get_by_uniprot_id(uniprot_id)
                if entry:
                    return {
                        'uniprot_id': entry.uniprot_id,
                        'entry_name': entry.entry_name,
                        'protein_name': entry.protein_name,
                        'gene_names': entry.gene_names,
                        'organism': entry.organism,
                        'function': entry.function or '',
                        'sequence': '',  # 备用方法不返回序列
                        'sequence_length': entry.sequence_length,
                        'mass': entry.mass,
                        'pdb_ids': entry.pdb_ids,
                        'keywords': entry.keywords or []
                    }
            except:
                pass
        return {}

    @retry_on_failure(max_retries=3, delay=1.0)
    def _fetch_pdb_metadata(self, pdb_ids: List[str], evaluation_id: int = None) -> Dict[str, Any]:
        """获取PDB元数据"""
        result = {'pdb_ids': [], 'structures': []}

        pdb_ids_to_fetch = pdb_ids[:100] if len(pdb_ids) > 100 else pdb_ids
        logger.info(f"开始获取 {len(pdb_ids_to_fetch)} 个PDB结构 (共 {len(pdb_ids)} 个)")

        if evaluation_id:
            self._add_log(evaluation_id, f"准备获取 {len(pdb_ids_to_fetch)} 个PDB结构...")

        success_count = 0
        fail_count = 0

        for idx, pdb_id in enumerate(pdb_ids_to_fetch):
            # 每获取 3 个 PDB 记录一次日志
            if evaluation_id and idx % 3 == 0:
                self._add_log(evaluation_id, f"正在获取PDB: {pdb_id} ({idx+1}/{len(pdb_ids_to_fetch)})")

            try:
                rcsb_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
                rcsb_response = http_session.get(rcsb_url, timeout=30)

                if rcsb_response.status_code == 200:
                    rcsb_data = rcsb_response.json()

                    basic_info = {
                        'title': '',
                        'experimental_method': '',
                        'resolution': None,
                        'deposition_date': '',
                    }

                    try:
                        struct_data = rcsb_data.get('struct')
                        if struct_data and isinstance(struct_data, dict):
                            title_val = struct_data.get('title')
                            basic_info['title'] = title_val if isinstance(title_val, str) else ''
                    except Exception as e:
                        logger.warning(f"获取title失败: {e}")

                    try:
                        exptl = rcsb_data.get('exptl')
                        if exptl and isinstance(exptl, list) and len(exptl) > 0:
                            first_exptl = exptl[0]
                            if first_exptl and isinstance(first_exptl, dict):
                                method_val = first_exptl.get('method')
                                basic_info['experimental_method'] = method_val if isinstance(method_val, str) else ''
                    except Exception as e:
                        logger.warning(f"获取experimental_method失败: {e}")

                    # 分辨率获取 - 支持 X-ray 和 EM
                    try:
                        rcsb_info = rcsb_data.get('rcsb_entry_info')
                        if rcsb_info and isinstance(rcsb_info, dict):
                            # 首先尝试 diffrn_resolution_high (X-ray)
                            diffrn_res = rcsb_info.get('diffrn_resolution_high')
                            if diffrn_res and isinstance(diffrn_res, dict):
                                res_val = diffrn_res.get('value')
                                if isinstance(res_val, (int, float)):
                                    basic_info['resolution'] = res_val

                            # 如果没有，尝试 resolution_combined (EM)
                            if basic_info['resolution'] is None:
                                res_combined = rcsb_info.get('resolution_combined')
                                if res_combined and isinstance(res_combined, list) and len(res_combined) > 0:
                                    res_val = res_combined[0]
                                    if isinstance(res_val, (int, float)):
                                        basic_info['resolution'] = res_val
                    except Exception as e:
                        logger.warning(f"获取分辨率失败: {e}")

                    # 沉积日期
                    try:
                        rcsb_info = rcsb_data.get('rcsb_entry_info')
                        if rcsb_info and isinstance(rcsb_info, dict):
                            date_val = rcsb_info.get('deposition_date')
                            basic_info['deposition_date'] = date_val if isinstance(date_val, str) else ''
                    except Exception as e:
                        logger.warning(f"获取deposition_date失败: {e}")

                    # 获取PDBe entities (使用较短超时，避免卡住)
                    entities = []
                    try:
                        pdbe_url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/entities/{pdb_id}"
                        pdbe_response = http_session.get(pdbe_url, timeout=10)
                        if pdbe_response.status_code == 200:
                            raw_entities = pdbe_response.json()
                            # 确保 raw_entities 是列表类型
                            if not isinstance(raw_entities, list):
                                raw_entities = []
                            # 提取关键实体信息
                            for ent in raw_entities:
                                if not isinstance(ent, dict):
                                    continue
                                entity_info = {
                                    'entity_id': ent.get('entity_id', ''),
                                    'description': ent.get('pdbx_description', ''),
                                    'type': ent.get('type', ''),
                                    'src_method': ent.get('src_method', ''),
                                    'pdbx_seq_one_letter_code': ent.get('pdbx_seq_one_letter_code', ''),
                                    'length': ent.get('length', 0),
                                }
                                # 获取生物种类
                                organisms = ent.get('rcsb_entity_source_organism', [])
                                if organisms and isinstance(organisms, list):
                                    first_org = organisms[0] if isinstance(organisms[0], dict) else {}
                                    entity_info['organism'] = first_org.get('scientific_name', '')
                                    entity_info['taxonomy_id'] = first_org.get('taxonomy_id', '')
                                entities.append(entity_info)
                    except Exception as e:
                        logger.warning(f"PDBe API 调用失败 (继续): {e}")

                    # 获取PDBe UniProt映射及残基范围
                    uniprot_ranges = {}
                    try:
                        pdbe_url = f"https://www.ebi.ac.uk/pdbe/api/mappings/all_isoforms/{pdb_id.lower()}"
                        pdbe_response = http_session.get(pdbe_url, timeout=10)
                        if pdbe_response.status_code == 200:
                            mapping_data = pdbe_response.json()
                            pdb_data = mapping_data.get(pdb_id.lower(), {})
                            uniprot_data = pdb_data.get('UniProt', {})
                            for up_id, chain_info in uniprot_data.items():
                                ranges = []
                                if isinstance(chain_info, list):
                                    for ci in chain_info:
                                        if 'uniprot_start' in ci and 'uniprot_end' in ci:
                                            ranges.append({
                                                'chain': ci.get('chain_id', ''),
                                                'uniprot_start': ci.get('uniprot_start'),
                                                'uniprot_end': ci.get('uniprot_end'),
                                                'pdb_start': ci.get('start'),
                                                'pdb_end': ci.get('end')
                                            })
                                elif isinstance(chain_info, dict):
                                    if 'uniprot_start' in chain_info:
                                        ranges.append({
                                            'chain': chain_info.get('chain_id', ''),
                                            'uniprot_start': chain_info.get('uniprot_start'),
                                            'uniprot_end': chain_info.get('uniprot_end'),
                                            'pdb_start': chain_info.get('start'),
                                            'pdb_end': chain_info.get('end')
                                        })
                                if ranges:
                                    uniprot_ranges[up_id] = ranges
                    except Exception as e:
                        logger.warning(f"PDBe UniProt映射获取失败 (继续): {e}")

                    # 获取引用
                    citations = []
                    primary_citation = rcsb_data.get('rcsb_primary_citation', {})

                    if isinstance(primary_citation, dict) and primary_citation.get('title'):
                        primary_pmids = primary_citation.get('pdbx_database_id_pub_med')
                        pubmed_id = None
                        if isinstance(primary_pmids, str):
                            pubmed_id = primary_pmids
                        elif isinstance(primary_pmids, list) and len(primary_pmids) > 0:
                            pubmed_id = primary_pmids[0]
                        elif isinstance(primary_pmids, int):
                            pubmed_id = str(primary_pmids)

                        citations.append({
                            'title': primary_citation.get('title', ''),
                            'authors': primary_citation.get('rcsb_authors', []),
                            'journal': primary_citation.get('journal_abbrev', ''),
                            'year': primary_citation.get('year'),
                            'volume': primary_citation.get('journal_volume', ''),
                            'pages': f"{primary_citation.get('page_first', '')}-{primary_citation.get('page_last', '')}",
                            'doi': primary_citation.get('pdbx_database_id_doi', ''),
                            'pubmed_id': pubmed_id
                        })

                    result['structures'].append({
                        'pdb_id': pdb_id,
                        'basic_info': basic_info,
                        'entities': entities,
                        'uniprot_ranges': uniprot_ranges,
                        'citations': citations,
                        'rcsb_data': rcsb_data
                    })
                    result['pdb_ids'].append(pdb_id)
                    success_count += 1
                else:
                    fail_count += 1
                    logger.warning(f"RCSB API返回 {rcsb_response.status_code} for {pdb_id}")

            except Exception as e:
                fail_count += 1
                logger.warning(f"获取PDB {pdb_id} 失败: {e}")

        logger.info(f"PDB获取完成: 成功 {success_count} 个, 失败 {fail_count} 个")

        if evaluation_id:
            self._add_log(evaluation_id, f"PDB获取完成: 成功 {success_count} 个, 失败 {fail_count} 个")

        # 获取PubMed摘要
        result = self._fetch_pubmed_abstracts(result)

        return result

    def _calculate_pdb_coverage(self, pdb_data: Dict, protein_length: int, target_uniprot_id: str = None) -> Dict[str, Any]:
        """计算 PDB 对蛋白质序列的覆盖度"""
        if not pdb_data or not pdb_data.get('structures') or protein_length <= 0:
            return {'coverage_percent': 0, 'covered_residues': 0, 'pdb_count': 0}

        # 获取每个 PDB 结构的序列覆盖范围
        # 需要查询 PDBe API 获取每个 PDB 的 UniProt 映射和序列范围
        covered_residues = set()
        pdb_ids = [s.get('pdb_id') for s in pdb_data.get('structures', [])]

        try:
            import requests
            session = requests.Session()
            session.headers.update({'Accept': 'application/json'})

            for pdb_id in pdb_ids:
                try:
                    # 使用 PDBe API 获取 UniProt 映射和序列范围
                    url = f"https://www.ebi.ac.uk/pdbe/api/mappings/all_isoforms/{pdb_id.lower()}"
                    resp = session.get(url, timeout=10)

                    if resp.status_code == 200:
                        data = resp.json()
                        pdb_entry = data.get(pdb_id.lower(), {})
                        uniprot_data = pdb_entry.get('UniProt', {})

                        for uniprot_id, uniprot_info in uniprot_data.items():
                            # 如果指定了目标 UniProt，只处理匹配的
                            if target_uniprot_id and uniprot_id.upper() != target_uniprot_id.upper():
                                # 跳过不匹配的 UniProt（比如 isoform ID 如 P04637-2）
                                if not uniprot_id.startswith(target_uniprot_id.upper()):
                                    continue

                            mappings = uniprot_info.get('mappings', [])
                            for mapping in mappings:
                                # 获取该 PDB 结构覆盖的 UniProt 序列范围
                                unp_start = mapping.get('unp_start')
                                unp_end = mapping.get('unp_end')

                                if unp_start and unp_end:
                                    # 添加到覆盖残基集合
                                    for pos in range(unp_start, unp_end + 1):
                                        covered_residues.add(pos)
                except Exception as e:
                    logger.warning(f"获取 {pdb_id} 覆盖度失败: {e}")
                    continue

        except Exception as e:
            logger.warning(f"计算 PDB 覆盖度失败: {e}")

        # 计算覆盖度（不超过100%）
        covered_count = len(covered_residues)
        coverage_percent = min((covered_count / protein_length * 100), 100) if protein_length > 0 else 0

        return {
            'coverage_percent': coverage_percent,
            'covered_residues': covered_count,
            'pdb_count': len(pdb_ids)
        }

    def _fetch_pdb_uniprot_mapping(self, pdb_ids: List[str]) -> Dict[str, Dict]:
        """查询 PDB 到 UniProt 的映射（返回所有映射的 UniProt ID 及残基范围）"""
        mapping = {}
        if not pdb_ids:
            return mapping

        try:
            # 使用 PDBe API 获取映射 - 正确的 API 端点
            import requests
            session = requests.Session()
            session.headers.update({'Accept': 'application/json'})

            # 批量查询，每个 PDB 单独查询
            for pdb_id in pdb_ids:
                try:
                    # 使用 mappings API 获取 UniProt 映射
                    url = f"https://www.ebi.ac.uk/pdbe/api/mappings/all_isoforms/{pdb_id.lower()}"
                    resp = session.get(url, timeout=30)

                    if resp.status_code == 200:
                        data = resp.json()
                        pdb_data = data.get(pdb_id.lower(), {})
                        uniprot_data = pdb_data.get('UniProt', {})
                        if uniprot_data:
                            # 获取所有映射的 UniProt ID 及其残基范围
                            mapping_info = {}
                            for uniprot_id, chain_data in uniprot_data.items():
                                # chain_data 可能是列表或字典
                                ranges = []
                                if isinstance(chain_data, list):
                                    for cd in chain_data:
                                        if 'start' in cd and 'end' in cd:
                                            ranges.append({
                                                'chain': cd.get('chain_id', ''),
                                                'start': cd.get('start'),
                                                'end': cd.get('end'),
                                                'uniprot_start': cd.get('uniprot_start'),
                                                'uniprot_end': cd.get('uniprot_end')
                                            })
                                elif isinstance(chain_data, dict):
                                    if 'start' in chain_data and 'end' in chain_data:
                                        ranges.append({
                                            'chain': chain_data.get('chain_id', ''),
                                            'start': chain_data.get('start'),
                                            'end': chain_data.get('end'),
                                            'uniprot_start': chain_data.get('uniprot_start'),
                                            'uniprot_end': chain_data.get('uniprot_end')
                                        })
                                mapping_info[uniprot_id] = ranges
                            mapping[pdb_id] = mapping_info
                except Exception as e:
                    logger.warning(f"获取 {pdb_id} UniProt映射失败: {e}")
                    continue

            logger.info(f"获取 PDB->UniProt 映射: {len(mapping)}/{len(pdb_ids)} 成功")

        except Exception as e:
            logger.error(f"查询 PDB UniProt 映射失败: {e}")

        return mapping

    @retry_on_failure(max_retries=3, delay=2.0)
    def _fetch_pubmed_abstract_with_retry(self, pubmed_client, pubmed_id: str) -> Dict:
        """带重试的PubMed摘要获取"""
        return pubmed_client.get_article_info_simple(str(pubmed_id))

    def _fetch_pubmed_abstracts(self, pdb_data: Dict) -> Dict:
        """获取PDB相关文献的PubMed摘要"""
        if not HAS_PUBMED:
            logger.warning("PubMed客户端未安装，跳过摘要获取")
            return pdb_data

        try:
            pubmed_client = PubMedClient()

            for struct in pdb_data.get('structures', []):
                citations = struct.get('citations', [])
                for cit in citations:
                    pubmed_id = cit.get('pubmed_id')
                    if pubmed_id:
                        try:
                            article_info = self._fetch_pubmed_abstract_with_retry(pubmed_client, str(pubmed_id))
                            if article_info:
                                cit['abstract'] = article_info.get('abstract', '')
                                logger.info(f"成功获取PMID {pubmed_id} 摘要")
                        except Exception as e:
                            logger.warning(f"获取PMID {pubmed_id} 摘要失败: {e}")

        except Exception as e:
            logger.warning(f"获取PubMed摘要失败: {e}")

        return pdb_data

    @retry_on_failure(max_retries=3, delay=2.0)
    def _run_blast_search(self, uniprot_id: str, sequence: str = None, evaluation_id: int = None) -> Dict[str, Any]:
        """运行 BLAST 相似蛋白搜索 - 使用 NCBI qBLAST"""
        results = []
        protein_sequence = sequence

        # 直接使用 NCBI qBLAST CGI 接口搜索 PDB 数据库
        try:
            return self._run_ncbi_qblast_search(uniprot_id, protein_sequence, evaluation_id)
        except Exception as e:
            logger.warning(f"NCBI qBLAST 失败: {e}, 详情: {type(e).__name__}, 使用 UniProt 同源搜索...")

        # 最终回退：UniProt 同源搜索
        return self._fallback_blast_search(uniprot_id, protein_sequence if protein_sequence else None, evaluation_id)

    def _run_rcsb_sequence_search(self, uniprot_id: str, protein_sequence: str = None, evaluation_id: int = None) -> Dict[str, Any]:
        """使用 PDBe API 搜索相似 PDB 结构"""
        import requests
        results = []
        pdb_data = None

        try:
            # 获取序列
            if not protein_sequence and uniprot_id:
                logger.info(f"从UniProt获取蛋白质序列: {uniprot_id}")
                url = f"http://rest.uniprot.org/uniprotkb/{uniprot_id}?format=json"
                response = http_session.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    seq_info = data.get('sequence', {})
                    if isinstance(seq_info, dict):
                        protein_sequence = seq_info.get('value', '')
                    elif isinstance(seq_info, str):
                        protein_sequence = seq_info
                    else:
                        protein_sequence = ''

            if not protein_sequence:
                return {'query_id': uniprot_id, 'results': [], 'method': 'pdbe_search', 'pdb_data': None}

            logger.info(f"获取到序列长度: {len(protein_sequence)} aa")

            logger.info("开始 PDBe Sequence Search 搜索相似 PDB 结构...")

            if evaluation_id:
                self._add_log(evaluation_id, "正在搜索相似 PDB 结构 (PDBe)...")

            # 使用 PDBe 的序列搜索 API
            search_url = "https://www.ebi.ac.uk/pdbe/api/pdb/sequence/similar"

            session = requests.Session()
            session.headers.update({'Content-Type': 'application/json', 'Accept': 'application/json'})

            # 发送序列进行搜索
            search_data = {
                "sequence": protein_sequence[:10000],
                "Evalue": 10,
                "sequenceId": "UniProt:" + uniprot_id if uniprot_id else "query"
            }

            search_resp = session.post(search_url, json=search_data, timeout=120)

            if search_resp.status_code != 200:
                raise Exception(f"PDBe 搜索失败: {search_resp.status_code}")

            search_json = search_resp.json()
            pdb_ids = []

            # 解析结果
            for entry in search_json:
                pdb_id = entry.get('alignment', [{}])[0].get('pdb_id', '')
                if pdb_id and len(pdb_id) == 4 and pdb_id not in pdb_ids:
                    pdb_ids.append(pdb_id)
                    identity = entry.get('alignment', [{}])[0].get('identity', 0)
                    results.append({
                        'pdb_id': pdb_id,
                        'title': f"PDB {pdb_id}",
                        'identity': int(identity * 100) if identity else None,
                        'score': entry.get('score', 0)
                    })

            logger.info(f"PDBe 搜索完成，找到 {len(pdb_ids)} 个相似 PDB 结构")

            # 获取这些 PDB 的元数据
            if pdb_ids and evaluation_id:
                self._add_log(evaluation_id, f"获取 {len(pdb_ids)} 个相似 PDB 的详细信息...")
                pdb_data = self._fetch_pdb_metadata(pdb_ids, evaluation_id)

            return {
                'query_id': uniprot_id,
                'results': results[:20],
                'method': 'pdbe_search',
                'pdb_data': pdb_data
            }

        except Exception as e:
            logger.error(f"PDBe 搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

            for hit in hits:
                # 提取 PDB ID (格式: "1ABC_1" -> "1ABC")
                identifier = hit.get('identifier', '')
                parts = identifier.split('_')
                pdb_id = parts[0] if parts else ''

                if len(pdb_id) == 4 and pdb_id.isalnum() and pdb_id not in pdb_ids:
                    pdb_ids.append(pdb_id)
                    # 获取更多信息
                    score = hit.get('score', 0)
                    results.append({
                        'pdb_id': pdb_id,
                        'title': f"PDB {pdb_id}",
                        'identity': int(score * 100) if score else None,  # RCSB 返回的是相似度分数
                        'score': score
                    })

            logger.info(f"RCSB 搜索完成，找到 {len(pdb_ids)} 个相似 PDB 结构")

            # 获取这些 PDB 的元数据
            if pdb_ids and evaluation_id:
                self._add_log(evaluation_id, f"获取 {len(pdb_ids)} 个相似 PDB 的详细信息...")
                pdb_data = self._fetch_pdb_metadata(pdb_ids, evaluation_id)

            return {
                'query_id': uniprot_id,
                'results': results[:20],
                'method': 'rcsb_search',
                'pdb_data': pdb_data
            }

        except Exception as e:
            logger.error(f"RCSB 搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _run_ncbi_qblast_search(self, uniprot_id: str, protein_sequence: str = None, evaluation_id: int = None) -> Dict[str, Any]:
        """使用 NCBI qBLAST CGI 接口搜索 PDB 数据库 - 使用 curl"""
        results = []

        try:
            # 获取序列
            if not protein_sequence and uniprot_id:
                logger.info(f"从UniProt获取蛋白质序列: {uniprot_id}")
                url = f"http://rest.uniprot.org/uniprotkb/{uniprot_id}?format=json"
                response = http_session.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    seq_info = data.get('sequence', {})
                    # 处理序列可能是字符串或字典的情况
                    if isinstance(seq_info, dict):
                        protein_sequence = seq_info.get('value', '')
                    elif isinstance(seq_info, str):
                        protein_sequence = seq_info
                    else:
                        protein_sequence = ''

                    if protein_sequence:
                        logger.info(f"获取到序列长度: {len(protein_sequence)} aa")
                    else:
                        logger.warning("无法从 UniProt 获取蛋白质序列")
                else:
                    logger.warning(f"获取 UniProt 数据失败: {response.status_code}")
                    raise Exception(f"获取 UniProt 数据失败: {response.status_code}")

            if not protein_sequence:
                logger.warning("没有蛋白质序列，无法执行 BLAST")
                raise Exception("没有蛋白质序列")

            logger.info("开始 NCBI qBLAST 搜索 (PDB 数据库)...")

            if evaluation_id:
                self._add_log(evaluation_id, "正在搜索相似 PDB 结构 (NCBI qBLAST)...")

            import subprocess
            import time
            import re
            import urllib.parse

            logger.info("开始提交 NCBI BLAST 任务...")

            if evaluation_id:
                self._add_log(evaluation_id, "正在提交 BLAST 任务到 NCBI...")

            # 检查序列
            if not protein_sequence:
                logger.warning("没有蛋白质序列，无法执行 BLAST")
                raise Exception("没有蛋白质序列")

            logger.info(f"蛋白质序列长度: {len(protein_sequence)}")

            # 步骤1: 提交 BLAST 任务 - 使用 curl
            query_params = urllib.parse.urlencode({
                'CMD': 'Put',
                'QUERY': protein_sequence[:10000],
                'DATABASE': 'pdb',
                'PROGRAM': 'blastp',
                'FORMAT_TYPE': 'JSON2',
                'HITLIST_SIZE': '20',
                'EXPECT': '0.001',
                'MATRIX': 'BLOSUM62',
                'FILTER': 'L',
            })

            curl_cmd = f'curl -s --max-time 60 "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi?{query_params}"'
            logger.info("执行 curl 命令...")

            try:
                result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True, timeout=120)
                response_text = result.stdout
                logger.info(f"curl 返回，长度: {len(response_text)}")
            except Exception as e:
                logger.error(f"curl 执行失败: {e}")
                raise Exception(f"curl 执行失败: {e}")

            if not response_text:
                raise Exception("BLAST 提交失败，无响应")

            # 解析 RID from HTML response - 使用更可靠的模式
            rid_match = re.search(r'<input[^>]*name=[\'"]RID[\'"][^>]*value=[\'"]([^\'"]+)[\'"]', response_text)
            rtoe_match = re.search(r'RTOE\s*=\s*(\d+)', response_text)

            if not rid_match:
                raise Exception("未获取到 RID")

            rid = rid_match.group(1)
            rtoe = int(rtoe_match.group(1)) if rtoe_match else 30

            logger.info(f"NCBI qBLAST 任务已提交, RID: {rid}, 预计等待 {rtoe} 秒")

            if evaluation_id:
                self._add_log(evaluation_id, f"BLAST任务已提交, RID: {rid}, 等待 {rtoe} 秒...")

            # 步骤2: 轮询等待结果 - 使用 curl
            max_wait = 900  # 增加到 15 分钟
            waited = 0
            initial_wait = max(rtoe, 30)
            found_ready = False

            # 初始等待
            time.sleep(initial_wait)
            waited += initial_wait

            while waited < max_wait:
                # 使用 curl 检查状态
                status_cmd = f'curl -s --max-time 30 "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi?CMD=Get&RID={rid}"'
                try:
                    status_text = subprocess.run(status_cmd, shell=True, capture_output=True, text=True, timeout=60).stdout

                    # Debug: log status response occasionally
                    if waited % 60 == 0:
                        logger.info(f"BLAST 状态检查 (waited={waited}s): {status_text[:200]}")

                    if 'Status=READY' in status_text:
                        logger.info("BLAST 任务完成")
                        if evaluation_id:
                            self._add_log(evaluation_id, "BLAST 搜索完成, 获取结果...")
                        found_ready = True
                        break
                    elif 'Status=FAILED' in status_text or 'Status=ERROR' in status_text:
                        raise Exception("BLAST 任务失败")
                    else:
                        logger.info(f"BLAST 任务进行中, 已等待 {waited} 秒")
                        time.sleep(10)
                        waited += 10
                except Exception as e:
                    logger.warning(f"检查 BLAST 状态出错: {e}, 继续等待...")
                    time.sleep(10)
                    waited += 10
                    rtoe = 15
                    continue

            if not found_ready:
                logger.warning(f"BLAST 任务在 {waited} 秒后仍未完成，继续等待...")
                # 继续等待，直到达到最大等待时间
                while waited < max_wait:
                    status_cmd = f'curl -s --max-time 30 "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi?CMD=Get&RID={rid}"'
                    try:
                        status_text = subprocess.run(status_cmd, shell=True, capture_output=True, text=True, timeout=60).stdout
                        if 'Status=READY' in status_text:
                            logger.info("BLAST 任务最终完成")
                            found_ready = True
                            break
                        elif 'Status=FAILED' in status_text or 'Status=ERROR' in status_text:
                            raise Exception("BLAST 任务失败")
                        else:
                            logger.info(f"BLAST 仍在进行中, 已等待 {waited} 秒")
                            time.sleep(15)
                            waited += 15
                    except Exception as e:
                        logger.warning(f"检查 BLAST 状态出错: {e}")
                        time.sleep(15)
                        waited += 15
                        continue

            if not found_ready:
                logger.warning(f"BLAST 任务在 {waited} 秒后仍未完成，尝试获取结果...")

            # 步骤3: 获取结果 - 使用 curl 和 Tabular 格式
            results_url = f'https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi?CMD=Get&RID={rid}&ALIGNMENT_VIEW=Tabular&FORMAT_TYPE=Text'
            result_text = None

            for retry in range(3):
                try:
                    result_cmd = f'curl -s --max-time 90 "{results_url}"'
                    result_text = subprocess.run(result_cmd, shell=True, capture_output=True, text=True, timeout=120).stdout
                    break
                except Exception as e:
                    logger.warning(f"获取 BLAST 结果重试 {retry+1}/3: {e}")
                    if retry < 2:
                        time.sleep(5)
                    continue

            if not result_text:
                raise Exception(f"获取 BLAST 结果失败")

            # 检查结果是否是有效的表格数据
            # 如果包含 HTML 标签，说明任务还没准备好，需要重试
            import re as re_module
            max_result_retries = 10
            for result_retry in range(max_result_retries):
                if '<!DOCTYPE html' in result_text or '<html' in result_text[:200]:
                    if result_retry < max_result_retries - 1:
                        logger.warning(f"BLAST 结果返回 HTML (尝试 {result_retry+1}/{max_result_retries})，等待后重试...")
                        time.sleep(30)
                        result_cmd = f'curl -s --max-time 90 "{results_url}"'
                        result_text = subprocess.run(result_cmd, shell=True, capture_output=True, text=True, timeout=120).stdout
                    else:
                        logger.error("BLAST 结果一直返回 HTML，放弃获取结果")
                        break
                else:
                    break

            # 解析 Tabular 格式的结果
            pdb_ids = []
            results = []

            # 提取 <PRE> 标签内的内容
            pre_match = re_module.search(r'<PRE>([\s\S]*?)</PRE>', result_text)
            if pre_match:
                result_text = pre_match.group(1)

            # Debug: log first 500 chars of result
            logger.info(f"BLAST 结果文本 (前500字符): {result_text[:500]}")

            # 解析 BLAST Tabular 输出
            lines = result_text.split('\n')
            logger.info(f"BLAST 结果总行数: {len(lines)}")
            for line in lines:
                line = line.strip()

                # 跳过注释行、空行和 HTML 标签
                if not line or line.startswith('#') or line.startswith('<') or line.startswith('>'):
                    continue

                # Tabular 格式: query acc, subject acc, % identity, alignment length, mismatches, gap opens, q.start, q.end, s.start, s.end, evalue, bit score
                parts = line.split('\t')
                if len(parts) >= 12:
                    subject_acc = parts[1]  # 例如: "1ABC_A"
                    identity = parts[2]
                    evalue = parts[10]

                    # 提取 PDB ID 和链 ID
                    pdb_id = subject_acc.split('_')[0] if '_' in subject_acc else subject_acc

                    if len(pdb_id) == 4 and pdb_id.isalnum():
                        try:
                            identity_float = float(identity)
                            if identity_float >= 20 and pdb_id not in pdb_ids:
                                pdb_ids.append(pdb_id)
                                results.append({
                                    'pdb_id': pdb_id,
                                    'title': f"PDB {pdb_id}",
                                    'identity': int(identity_float),
                                    'score': float(parts[11]) if len(parts) > 11 else None,
                                    'evalue': float(evalue)
                                })
                        except:
                            pass

            logger.info(f"NCBI qBLAST 搜索完成，找到 {len(pdb_ids)} 个相似 PDB 结构")

            # 获取这些 PDB 的元数据
            pdb_data = None
            homolog_pdb_data = None  # 同源结构的PDB数据
            if pdb_ids:
                if evaluation_id:
                    self._add_log(evaluation_id, f"获取 {len(pdb_ids)} 个相似 PDB 的详细信息...")
                pdb_data = self._fetch_pdb_metadata(pdb_ids, evaluation_id)

                # 查询 PDB 到 UniProt 的映射（返回所有映射的 UniProt 及残基范围）
                if evaluation_id:
                    self._add_log(evaluation_id, f"查询 PDB 的 UniProt 映射...")
                uniprot_mapping = self._fetch_pdb_uniprot_mapping(pdb_ids)

                # 区分本身结构和同源结构
                own_structures = []  # 本身结构
                homolog_structures = []  # 同源结构

                for result_item in results:
                    pdb_id = result_item.get('pdb_id')
                    # 获取该PDB所有映射的UniProt及其范围（新格式是dict）
                    mapping_info = uniprot_mapping.get(pdb_id, {})
                    mapped_uniprots = list(mapping_info.keys()) if isinstance(mapping_info, dict) else []

                    # 添加 UniProt 映射信息到结果
                    result_item['mapped_uniprot'] = mapped_uniprots[0] if mapped_uniprots else ''
                    result_item['mapped_uniprots'] = mapped_uniprots  # 保存所有映射
                    result_item['uniprot_ranges'] = mapping_info  # 保存残基范围信息

                    # 检查是否 ANY 映射的 UniProt 与输入的 UniProt 相同
                    is_own = False
                    if mapped_uniprots:
                        for mp in mapped_uniprots:
                            if mp.upper() == uniprot_id.upper():
                                is_own = True
                                break

                    if is_own:
                        result_item['structure_type'] = 'own'  # 本身结构
                        own_structures.append(pdb_id)
                    else:
                        result_item['structure_type'] = 'homolog'  # 同源结构
                        homolog_structures.append(pdb_id)

                logger.info(f"结构分类: 本身结构 {len(own_structures)} 个, 同源结构 {len(homolog_structures)} 个")

                if evaluation_id:
                    self._add_log(evaluation_id, f"本身结构: {len(own_structures)} 个, 同源结构: {len(homolog_structures)} 个")

                # 获取同源结构的PDB数据（用于文献）
                if homolog_structures and evaluation_id:
                    self._add_log(evaluation_id, f"获取 {len(homolog_structures)} 个同源 PDB 的详细信息...")
                    homolog_pdb_data = self._fetch_pdb_metadata(homolog_structures, evaluation_id)

                # 将分类信息添加到 pdb_data
                if pdb_data:
                    pdb_data['own_structures'] = own_structures
                    pdb_data['homolog_structures'] = homolog_structures
                    # 将同源结构的文献也加入
                    if homolog_pdb_data and homolog_pdb_data.get('structures'):
                        # 标记同源结构文献
                        for struct in homolog_pdb_data.get('structures', []):
                            struct['is_homolog'] = True  # 标记为同源结构文献
                        # 合并到主文献列表
                        if pdb_data.get('structures'):
                            pdb_data['structures'].extend(homolog_pdb_data['structures'])
                        else:
                            pdb_data['structures'] = homolog_pdb_data['structures']

            return {
                'query_id': uniprot_id,
                'results': results[:20],
                'method': 'ncbi_blast',
                'pdb_data': pdb_data
            }

        except Exception as e:
            logger.error(f"NCBI qBLAST 搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _run_ebi_blast_search(self, uniprot_id: str, protein_sequence: str = None, evaluation_id: int = None) -> Dict[str, Any]:
        """使用 UniProt 的 CD Search (Conserved Domain) 查找相似蛋白"""
        results = []
        pdb_data = None

        try:
            # 如果没有提供序列，从 UniProt 获取
            if not protein_sequence and uniprot_id:
                logger.info(f"从UniProt获取蛋白质序列: {uniprot_id}")
                url = f"http://rest.uniprot.org/uniprotkb/{uniprot_id}?format=json"
                response = http_session.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    seq_info = data.get('sequence', {})
                    if isinstance(seq_info, dict):
                        protein_sequence = seq_info.get('value', '')
                    elif isinstance(seq_info, str):
                        protein_sequence = seq_info
                    else:
                        protein_sequence = ''

            if not protein_sequence:
                return {'query_id': uniprot_id, 'results': [], 'method': 'uniprot_cd', 'pdb_data': None}

            logger.info(f"获取到序列长度: {len(protein_sequence)} aa")

            logger.info("使用 UniProt CD Search 查找相似蛋白...")

            if evaluation_id:
                self._add_log(evaluation_id, "正在搜索同源蛋白 (UniProt CD Search)...")

            # 使用 UniProt 的 InterProScan/CD Search API
            # 提交 CD Search 任务
            import requests

            # 首先获取蛋白质序列的 FASTA 格式
            fasta_seq = f">protein\n{protein_sequence[:10000]}"

            # 使用 UniProt 的 API 提交 CD Search
            submit_url = "https://www.ebi.ac.uk/interpro/api/cdn/"
            session = requests.Session()
            session.headers.update({
                'Content-Type': 'text/plain',
                'Accept': 'application/json'
            })

            try:
                # 尝试提交 CD Search
                submit_resp = session.post(submit_url, data=fasta_seq, timeout=60)

                if submit_resp.status_code == 200:
                    job_data = submit_resp.json()
                    job_id = job_data.get('jobId', '')

                    if job_id:
                        logger.info(f"InterPro/CD Search 任务已提交: {job_id}")

                        # 轮询结果
                        import time
                        for attempt in range(30):
                            time.sleep(3)
                            result_url = f"https://www.ebi.ac.uk/interpro/api/result/{job_id}/json"
                            result_resp = session.get(result_url, timeout=30)

                            if result_resp.status_code == 200:
                                result_data = result_resp.json()
                                if result_data.get('status') == 'finished':
                                    # 获取相似蛋白信息
                                    for protein in result_data.get('proteins', [])[:20]:
                                        accession = protein.get('accession', '')
                                        if len(accession) == 6:  # UniProt ID
                                            results.append({
                                                'uniprot_id': accession,
                                                'entry_name': protein.get('name', ''),
                                                'protein_name': protein.get('description', '')[:100],
                                                'organism': protein.get('organism', ''),
                                                'identity': None,
                                                'score': protein.get('score', 0)
                                            })
                                    break
                else:
                    raise Exception(f"CD Search 提交失败: {submit_resp.status_code}")
            except Exception as e:
                logger.warning(f"CD Search 失败: {e}，跳过此步骤")

            # 如果 CD Search 失败或没有结果，使用 UniProt 同源搜索作为替代
            if not results:
                logger.info("使用 UniProt 同源搜索作为替代...")
                if evaluation_id:
                    self._add_log(evaluation_id, "使用 UniProt 同源搜索...")

                # 获取物种信息
                taxonomy_id = None
                if uniprot_id:
                    url = f"http://rest.uniprot.org/uniprotkb/{uniprot_id}?format=json"
                    resp = http_session.get(url, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        organism_info = data.get('organism', {})
                        taxonomy_id = organism_info.get('taxonId', None)

                if taxonomy_id:
                    # 搜索同物种蛋白
                    search_url = "http://rest.uniprot.org/uniprotkb/search"
                    params = {
                        'query': f'organism_id:{taxonomy_id}',
                        'format': 'json',
                        'size': 20,
                        'fields': 'accession,gene_names,protein_name,organism_name'
                    }

                    resp = http_session.get(search_url, params=params, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        for entry in data.get('results', []):
                            accession = entry.get('primaryAccession', '')
                            if accession == uniprot_id:
                                continue

                            gene_names = entry.get('genes', [])
                            gene_name = gene_names[0].get('geneName', {}).get('value', '') if gene_names else ''

                            protein_rec = entry.get('proteinName', {})
                            protein_name_val = protein_rec.get('fullName', {}).get('value', '') if isinstance(protein_rec, dict) else str(protein_rec)

                            org_rec = entry.get('organism', {})
                            org_name = org_rec.get('scientificName', '') if isinstance(org_rec, dict) else ''

                            results.append({
                                'uniprot_id': accession,
                                'entry_name': gene_name,
                                'protein_name': protein_name_val[:100] if protein_name_val else '',
                                'organism': org_name,
                                'identity': None,
                                'score': None
                            })

            logger.info(f"同源蛋白搜索完成，找到 {len(results)} 个")

            return {
                'query_id': uniprot_id,
                'results': results[:20],
                'method': 'uniprot_cd',
                'pdb_data': None  # UniProt 搜索返回的是蛋白质，不是 PDB
            }

        except Exception as e:
            logger.error(f"同源蛋白搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise  # 让上层捕获并尝试 NCBI

    def _fallback_blast_search(self, uniprot_id: str, protein_sequence: str = None, evaluation_id: int = None) -> Dict[str, Any]:
        """回退方案：使用 UniProt PDB 相关蛋白搜索"""
        results = []
        pdb_data = None
        taxonomy_id = None

        try:
            # 获取物种信息
            if uniprot_id:
                logger.info(f"从UniProt获取蛋白质信息: {uniprot_id}")
                url = f"http://rest.uniprot.org/uniprotkb/{uniprot_id}?format=json"
                response = http_session.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    organism_info = data.get('organism', {})
                    taxonomy_id = organism_info.get('taxonId', None)
                    protein_name = data.get('proteinName', {})
                    if isinstance(protein_name, dict):
                        protein_name = protein_name.get('fullName', {}).get('value', '')

            logger.info("使用 UniProt PDB 相关蛋白搜索...")

            if evaluation_id:
                self._add_log(evaluation_id, "正在搜索 PDB 相关蛋白...")

            search_url = "http://rest.uniprot.org/uniprotkb/search"

            # 搜索有 PDB 结构的同源蛋白
            if taxonomy_id:
                # 首先搜索同物种有 PDB 结构的蛋白
                params = {
                    'query': f'database:pdb AND organism_id:{taxonomy_id}',
                    'format': 'json',
                    'size': 20,
                    'fields': 'accession,gene_names,protein_name,organism_name',
                    'sort': 'score desc'
                }

                response = http_session.get(search_url, params=params, timeout=60)

                if response.status_code == 200:
                    data = response.json()
                    results_list = data.get('results', [])

                    for entry in results_list:
                        accession = entry.get('primaryAccession', '')
                        if accession == uniprot_id:
                            continue

                        gene_names = entry.get('genes', [])
                        gene_name = gene_names[0].get('geneName', {}).get('value', '') if gene_names else ''

                        protein_rec = entry.get('proteinName', {})
                        protein_name_val = protein_rec.get('fullName', {}).get('value', '') if isinstance(protein_rec, dict) else str(protein_rec)

                        org_rec = entry.get('organism', {})
                        org_name = org_rec.get('scientificName', '') if isinstance(org_rec, dict) else ''

                        results.append({
                            'uniprot_id': accession,
                            'entry_name': gene_name,
                            'protein_name': protein_name_val[:100] if protein_name_val else '',
                            'organism': org_name,
                            'identity': None,
                            'score': None
                        })

                    logger.info(f"UniProt PDB 搜索返回 {len(results)} 个有 PDB 结构的蛋白")

            # 如果没有找到足够的蛋白，扩大搜索范围
            if len(results) < 5:
                logger.info("扩大搜索范围...")
                params = {
                    'query': 'database:pdb',
                    'format': 'json',
                    'size': 30,
                    'fields': 'accession,gene_names,protein_name,organism_name'
                }

                response = http_session.get(search_url, params=params, timeout=60)
                if response.status_code == 200:
                    data = response.json()
                    for entry in data.get('results', []):
                        accession = entry.get('primaryAccession', '')
                        if accession == uniprot_id:
                            continue
                        if any(r['uniprot_id'] == accession for r in results):
                            continue

                        gene_names = entry.get('genes', [])
                        gene_name = gene_names[0].get('geneName', {}).get('value', '') if gene_names else ''

                        protein_rec = entry.get('proteinName', {})
                        protein_name_val = protein_rec.get('fullName', {}).get('value', '') if isinstance(protein_rec, dict) else str(protein_rec)

                        org_rec = entry.get('organism', {})
                        org_name = org_rec.get('scientificName', '') if isinstance(org_rec, dict) else ''

                        results.append({
                            'uniprot_id': accession,
                            'entry_name': gene_name,
                            'protein_name': protein_name_val[:100] if protein_name_val else '',
                            'organism': org_name,
                            'identity': None,
                            'score': None
                        })

        except Exception as e:
            logger.error(f"UniProt 回退搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return {'query_id': uniprot_id, 'results': results[:20], 'method': 'uniprot', 'pdb_data': None}

    def _run_ai_analysis(self, uniprot_data: Dict, pdb_data: Dict, blast_results: Dict, evaluation_id: int = None) -> Dict[str, Any]:
        """运行AI分析"""
        try:
            # 从配置获取 AI 参数
            ai_provider = self.config.get('ai_provider', 'openai')
            ai_model = self.config.get('ai_model', 'gpt-4o')
            ai_base_url = self.config.get('ai_base_url', '')
            ai_api_key = self.config.get('ai_api_key', '')
            ai_max_tokens = self.config.get('ai_max_tokens', 6000)
            ai_temperature = self.config.get('ai_temperature', 0.3)

            # 根据配置创建 AI 客户端
            if ai_provider == 'anthropic':
                client = AnthropicClient(api_key=ai_api_key, model=ai_model, base_url=ai_base_url)
            elif ai_provider == 'gemini':
                client = GeminiClient(api_key=ai_api_key, model=ai_model, base_url=ai_base_url)
            else:
                client = OpenAIClient(api_key=ai_api_key, base_url=ai_base_url, model=ai_model)

            prompt = self._build_analysis_prompt(uniprot_data, pdb_data, blast_results)

            # 保存 prompt 到数据库
            if evaluation_id:
                full_prompt = f"System: 你是一个专业的蛋白质结构生物学家。请对给定的蛋白质进行综合分析。\n\nUser: {prompt}"
                update_protein_evaluation(evaluation_id, {'ai_prompt': full_prompt})

            messages = [
                {"role": "system", "content": "你是一个专业的蛋白质结构生物学家。请对给定的蛋白质进行综合分析。"},
                {"role": "user", "content": prompt}
            ]

            response = client.chat(messages, max_tokens=ai_max_tokens, temperature=ai_temperature, timeout=300)

            if response.get('success'):
                return {
                    'analysis': response.get('content', ''),
                    'model': response.get('model', ai_model)
                }
            else:
                return {'error': response.get('error', 'AI分析失败')}

        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return {'error': str(e)}

    def _build_analysis_prompt(self, uniprot_data: Dict, pdb_data: Dict, blast_results: Dict) -> str:
        """构建AI分析提示"""
        parts = []

        # 优先使用 config 中的模板，其次使用配置文件中的模板
        template = self.config.get('ai_prompt_template') or getattr(config, 'AI_PROMPT_TEMPLATE', None)
        if template and '{outline}' in template:
            # 模板中有 {outline} 占位符，拆分为头部和尾部
            template_parts = template.split('{outline}')
            parts.append(template_parts[0])  # 头部：格式要求
            # 中间：实际数据（在后面添加）
            parts.append("")  # 空行
        else:
            # 没有 {outline} 占位符，使用默认行为
            if template:
                parts.append(template)
            else:
                parts.append("""# 蛋白质结构功能分析报告生成器

你是一个专业的蛋白质结构生物学家和生物信息学专家。请根据以下提供的蛋白质数据，生成一份**全面深入的综合分析报告**。

## 报告要求：
1. **字数要求**：报告总字数应在4000字以上
2. **分析深度**：每个分析维度都要有深度解读
3. **结构清晰**：使用多级标题组织内容
4. **数据驱动**：结合具体的PDB结构数据进行分析

请按以下框架生成报告：""")
            parts.append("")

        # 1. 蛋白质基本信息
        if uniprot_data:
            uniprot_id = uniprot_data.get('uniprot_id', 'N/A')
            protein_name = uniprot_data.get('protein_name', 'N/A')
            gene_names = ', '.join(uniprot_data.get('gene_names', []))
            organism = uniprot_data.get('organism', 'N/A')
            sequence = uniprot_data.get('sequence', 'N/A')
            mass = uniprot_data.get('mass', 'N/A')
            function = uniprot_data.get('function', '无数据')
            keywords = ', '.join(uniprot_data.get('keywords', [])[:30])
            pdb_count = len(uniprot_data.get('pdb_ids', []))

            # 收集所有 PDB ID 用于显示
            all_pdb_ids = list(set(uniprot_data.get('pdb_ids', [])))

            parts.append(f"""
# 蛋白质基础信息

## 基本信息

| 属性 | 值 |
|------|-----|
| UniProt ID | {uniprot_id} |
| 蛋白质名称 | {protein_name} |
| 基因名 | {gene_names} |
| 物种 | {organism} |
| 序列长度 | {sequence} aa |
| 分子量 | {mass} Da |
| 可用PDB结构 | {pdb_count}个 ({', '.join(all_pdb_ids[:10])}{'...' if len(all_pdb_ids) > 10 else ''}) |

## 功能描述
{function if function and function != '无数据' else '暂无功能描述'}

## 关键词
{keywords if keywords else '暂无关键词'}
""")

        # 2. PDB结构详情
        if pdb_data and pdb_data.get('structures'):
            structures = pdb_data['structures']
            pdb_list = []

            # 先对文献进行去重（按PMID），同时收集每个PMID关联的PDB ID
            all_citations = {}
            pmid_to_pdb = {}  # PMID -> [PDB IDs]
            for struct in structures:
                pdb_id = struct.get('pdb_id', '')
                citations = struct.get('citations', [])
                for cit in citations:
                    pubmed_id = cit.get('pubmed_id', '')
                    if pubmed_id:
                        if pubmed_id not in pmid_to_pdb:
                            pmid_to_pdb[pubmed_id] = []
                        if pdb_id not in pmid_to_pdb[pubmed_id]:
                            pmid_to_pdb[pubmed_id].append(pdb_id)

                        if pubmed_id not in all_citations:
                            all_citations[pubmed_id] = cit

            # 去重后的文献列表
            unique_citations = list(all_citations.values())
            total_citations = len(unique_citations)

            # 构建去重后的文献详情（只显示一次）
            citation_details = ""
            if unique_citations:
                citation_details = "\n**相关文献**:\n"
                for i, cit in enumerate(unique_citations, 1):
                    authors = ', '.join(cit.get('authors', [])[:3]) if cit.get('authors') else 'Unknown'
                    year = cit.get('year', 'N/A')
                    journal = cit.get('journal', 'N/A')
                    title = cit.get('title', 'N/A')[:80]
                    doi = cit.get('doi', '')
                    pubmed_id = cit.get('pubmed_id', '')
                    pmid_link = f" [PMID: {pubmed_id}]" if pubmed_id else ""
                    doi_link = f" [DOI: {doi}]" if doi else ""

                    # 显示关联的 PDB
                    related_pdbs = pmid_to_pdb.get(pubmed_id, [])
                    pdb_str = f" (关联PDB: {', '.join(related_pdbs)})" if related_pdbs else ""

                    citation_details += f"{i}. {authors} ({year}). {title}... - {journal}{pmid_link}{doi_link}{pdb_str}\n"

                    # 添加文献摘要（如果有）- 不截断
                    abstract = cit.get('abstract', '')
                    if abstract:
                        citation_details += f"   摘要: {abstract}\n"

            # 构建每个PDB的详情，包含关联的文献（只显示标题，不重复摘要）
            pdb_to_pmids = {}  # PDB ID -> [PMIDs]
            for pubmed_id, pdb_ids in pmid_to_pdb.items():
                for pdb_id in pdb_ids:
                    if pdb_id not in pdb_to_pmids:
                        pdb_to_pmids[pdb_id] = []
                    if pubmed_id not in pdb_to_pmids[pdb_id]:
                        pdb_to_pmids[pdb_id].append(pubmed_id)

            for struct in structures:
                pdb_id = struct.get('pdb_id', 'N/A')
                basic = struct.get('basic_info', {})
                entities = struct.get('entities', [])
                uniprot_ranges = struct.get('uniprot_ranges', {})

                resolution = basic.get('resolution')
                resolution_str = f"{resolution:.2f} Å" if resolution else 'N/A'

                # 构建实体信息
                entity_details = ""
                if entities:
                    entity_details = "\n- **实体详情**:\n"
                    for ent in entities:
                        ent_desc = ent.get('description', '')[:80]
                        ent_len = ent.get('length', 0)
                        ent_org = ent.get('organism', '')
                        ent_type = ent.get('type', 'polymer')
                        entity_details += f"  - 实体{ent.get('entity_id', '')}: {ent_desc}"
                        if ent_len:
                            entity_details += f" (长度: {ent_len} aa"
                        if ent_type:
                            entity_details += f", 类型: {ent_type}"
                        if ent_org:
                            entity_details += f", 物种: {ent_org}"
                        entity_details += ")\n"

                # 构建UniProt映射范围信息
                uniprot_details = ""
                if uniprot_ranges:
                    uniprot_details = "\n- **UniProt映射**:\n"
                    for up_id, ranges in uniprot_ranges.items():
                        range_strs = []
                        for r in ranges:
                            chain = r.get('chain', '')
                            up_start = r.get('uniprot_start', '')
                            up_end = r.get('uniprot_end', '')
                            pdb_start = r.get('pdb_start', '')
                            pdb_end = r.get('pdb_end', '')
                            if chain:
                                range_strs.append(f"链{chain}: {up_id} {up_start}-{up_end} (PDB {pdb_start}-{pdb_end})")
                            else:
                                range_strs.append(f"{up_id} {up_start}-{up_end} (PDB {pdb_start}-{pdb_end})")
                        uniprot_details += f"  - {', '.join(range_strs)}\n"

                pdb_info = f"""
### {pdb_id}

- **实验方法**: {basic.get('experimental_method', 'N/A')}
- **分辨率**: {resolution_str}
- **沉积日期**: {basic.get('deposition_date', 'N/A')}
- **结构标题**: {basic.get('title', 'N/A')[:200]}
{entity_details}{uniprot_details}
"""
                # 添加关联的文献信息（只显示标题）
                related_pmids = pdb_to_pmids.get(pdb_id, [])
                if related_pmids:
                    pdb_info += "- **关联文献**:\n"
                    for pmid in related_pmids:
                        cit = all_citations.get(pmid, {})
                        cit_title = cit.get('title', 'N/A')[:60]
                        pdb_info += f"  - PMID: {pmid} - {cit_title}...\n"

                pdb_list.append(pdb_info)

            # 统计
            methods = {}
            resolutions = []
            total_entity_length = 0
            for struct in structures:
                method = struct.get('basic_info', {}).get('experimental_method', 'Unknown')
                methods[method] = methods.get(method, 0) + 1
                res = struct.get('basic_info', {}).get('resolution')
                if res:
                    resolutions.append(res)
                # 累加实体长度
                for ent in struct.get('entities', []):
                    total_entity_length += ent.get('length', 0)

            method_stats = "\n".join([f"- {method}: {count}个" for method, count in methods.items()])
            res_range = f"{min(resolutions):.2f} - {max(resolutions):.2f} Å" if resolutions else "N/A"
            res_avg = f"{sum(resolutions)/len(resolutions):.2f} Å" if resolutions else "N/A"

            parts.append(f"""
# PDB结构详情

共检索到 **{len(structures)}** 个PDB结构（覆盖蛋白质约 {total_entity_length} 个残基），关联 **{total_citations}** 篇文献。

## 结构统计

{method_stats}
- 分辨率范围: {res_range}
- 平均分辨率: {res_avg}

{citation_details}
## 各PDB结构详细信息
{chr(10).join(pdb_list)}
""")

        # 3. 相似蛋白 (BLAST)
        if blast_results and blast_results.get('results'):
            blast_list = []
            blast_pdb_data = blast_results.get('pdb_data', {})

            # 如果有 BLAST 返回的 PDB 数据，添加到 prompt
            if blast_pdb_data and blast_pdb_data.get('structures'):
                parts.append("""
# BLAST 相似结构详情

以下是与目标蛋白结构相似的 PDB 结构：""")
                blast_structures = blast_pdb_data.get('structures', [])
                for struct in blast_structures[:5]:
                    pdb_id = struct.get('pdb_id', 'N/A')
                    basic = struct.get('basic_info', {})
                    title = basic.get('title', '')[:80]
                    method = basic.get('experimental_method', 'N/A')
                    resolution = basic.get('resolution')
                    res_str = f"{resolution:.2f} Å" if resolution else 'N/A'
                    parts.append(f"""
### {pdb_id}
- 实验方法: {method}
- 分辨率: {res_str}
- 标题: {title}""")
                parts.append("")

            # 添加相似蛋白列表
            for result in blast_results['results'][:10]:
                if 'pdb_id' in result:
                    blast_list.append(f"| {result.get('pdb_id')} | {result.get('title', 'N/A')[:50]} | {result.get('identity', 'N/A')}% |")
                else:
                    blast_list.append(f"| {result.get('uniprot_id')} | {result.get('protein_name', 'N/A')} | {result.get('organism', 'N/A')} |")

            method = blast_results.get('method', 'unknown')
            if method == 'ncbi_blast':
                # 检查是否全部是本身结构
                results = blast_results.get('results', [])
                own_count = sum(1 for r in results if r.get('structure_type') == 'own')
                homolog_count = sum(1 for r in results if r.get('structure_type') == 'homolog')

                if own_count > 0 and homolog_count == 0:
                    # 全部是本身结构
                    parts.append(f"""
# 本身结构分析 (BLAST搜索)

共找到 **{len(results)}** 个与目标蛋白相同的本身结构（来自同一UniProt）：

| PDB ID | 标题/名称 | 相似度 |
|--------|-----------|--------|
{chr(10).join(blast_list)}

这些结构来自同一蛋白的不同表达/突变体，请分析它们的结构特点和差异。
""")
                elif own_count > 0 and homolog_count > 0:
                    # 混合本身和同源结构
                    parts.append(f"""
# 结构分析 (BLAST搜索)

共找到 **{len(results)}** 个相关结构，其中 **{own_count}** 个是本身结构（来自同一UniProt），**{homolog_count}** 个是同源结构：

| PDB ID | 类型 | 标题/名称 | 相似度 |
|--------|------|-----------|--------|
""")
                    for r in results[:10]:
                        struct_type = r.get('structure_type', 'unknown')
                        type_label = '本身' if struct_type == 'own' else '同源'
                        parts[-1] += f"\n| {r.get('pdb_id')} | {type_label} | {r.get('title', 'N/A')[:40]} | {r.get('identity', 'N/A')}% |"

                    parts.append("""

请分析这些结构与目标蛋白的关系，包括本身结构的特征和同源结构的进化关系。
""")
                else:
                    # 全部是同源结构
                    parts.append(f"""
# 同源蛋白分析 (BLAST搜索)

共找到 **{len(results)}** 个同源结构（来自不同UniProt）：

| PDB ID | 标题/名称 | 相似度 |
|--------|-----------|--------|
{chr(10).join(blast_list)}

请分析这些同源结构与目标蛋白的关系，讨论序列/结构相似度和功能保守性。
""")
            else:
                parts.append(f"""
# 同源蛋白分析 (UniProt同源搜索)

共找到 **{len(blast_results['results'])}** 个同源蛋白：

| UniProt ID | 蛋白质名称 | 物种 |
|------------|-----------|------|
{chr(10).join(blast_list)}

请分析这些同源蛋白与目标蛋白的关系，讨论序列相似度和功能保守性。
""")
        else:
            parts.append("""
# 同源蛋白分析

未找到显著相似的蛋白，或BLAST搜索未返回结果。
""")

        # 检查模板中是否有尾部需要添加（模板尾部已包含"深入分析要求"）
        template = getattr(config, 'AI_PROMPT_TEMPLATE', None)
        if template and '{outline}' in template:
            template_parts = template.split('{outline}')
            if len(template_parts) > 1 and template_parts[1].strip():
                # 有尾部模板
                parts.append(template_parts[1])

        return "\n".join(parts)

    def _generate_report(self, uniprot_data: Dict, pdb_data: Dict, blast_results: Dict, ai_analysis: Dict) -> str:
        """生成评估报告"""
        sections = []

        sections.append("# 蛋白质评估报告\n")

        # 基本信息
        sections.append("## 1. 基本信息\n")
        if uniprot_data:
            sections.append(f"**UniProt ID**: {uniprot_data.get('uniprot_id', 'N/A')}\n")
            sections.append(f"**蛋白质名称**: {uniprot_data.get('protein_name', 'N/A')}\n")
            sections.append(f"**基因名**: {', '.join(uniprot_data.get('gene_names', []))}\n")
            sections.append(f"**物种**: {uniprot_data.get('organism', 'N/A')}\n")
            sections.append(f"**序列长度**: {uniprot_data.get('sequence', 'N/A')} aa\n")
            if uniprot_data.get('function'):
                sections.append(f"**功能描述**: {uniprot_data.get('function')}\n")
        else:
            sections.append("未获取到UniProt数据\n")

        # 结构信息
        sections.append("\n## 2. 结构信息\n")
        if pdb_data and pdb_data.get('structures'):
            for struct in pdb_data['structures']:
                pdb_id = struct.get('pdb_id', 'N/A')
                basic = struct.get('basic_info', {})
                sections.append(f"### {pdb_id}\n")
                sections.append(f"- 实验方法: {basic.get('experimental_method', 'N/A')}\n")
                sections.append(f"- 分辨率: {basic.get('resolution', 'N/A')} Å\n")
                sections.append(f"- 沉积日期: {basic.get('deposition_date', 'N/A')}\n")
        else:
            sections.append("未获取到PDB结构数据\n")

        # 相似蛋白
        sections.append("\n## 3. 相似蛋白 (BLAST)\n")
        if blast_results and blast_results.get('results'):
            sections.append("| UniProt ID | 蛋白质名称 | 物种 |\n")
            sections.append("|------------|------------|------|\n")
            for result in blast_results['results'][:10]:
                sections.append(f"| {result.get('uniprot_id')} | {result.get('protein_name', 'N/A')} | {result.get('organism', 'N/A')} |\n")
        else:
            sections.append("未获取到相似蛋白数据\n")

        # AI分析
        sections.append("\n## 4. AI分析\n")
        if ai_analysis and ai_analysis.get('analysis'):
            sections.append(ai_analysis['analysis'])
        elif ai_analysis and ai_analysis.get('error'):
            sections.append(f"AI分析失败: {ai_analysis['error']}")
        else:
            sections.append("未进行AI分析\n")

        return "".join(sections)

    def get_evaluation_status(self, evaluation_id: int) -> Dict[str, Any]:
        """获取评估状态"""
        evaluation = get_protein_evaluation(evaluation_id)
        if not evaluation:
            return {'success': False, 'error': '评估记录不存在'}

        return {
            'success': True,
            'evaluation': evaluation.to_dict()
        }

    def get_evaluation_detail(self, evaluation_id: int) -> Dict[str, Any]:
        """获取评估详情"""
        evaluation = get_protein_evaluation(evaluation_id)
        if not evaluation:
            return None
        return evaluation.to_dict()

    def list_evaluations(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """列出所有评估"""
        evaluations = get_all_protein_evaluations(limit, offset)
        return {
            'success': True,
            'evaluations': [e.to_dict() for e in evaluations],
            'total': len(evaluations)
        }

    def delete_evaluation(self, evaluation_id: int) -> Dict[str, Any]:
        """删除评估"""
        success = delete_protein_evaluation(evaluation_id)
        return {'success': success}

    def batch_delete_evaluations(self, evaluation_ids: List[int]) -> Dict[str, Any]:
        """批量删除评估"""
        deleted_count = 0
        failed_ids = []
        for eval_id in evaluation_ids:
            success = delete_protein_evaluation(eval_id)
            if success:
                deleted_count += 1
            else:
                failed_ids.append(eval_id)

        return {
            'success': True,
            'deleted': deleted_count,
            'failed': failed_ids,
            'total': len(evaluation_ids)
        }

    def search_evaluations(self, query: str) -> Dict[str, Any]:
        """搜索评估"""
        evaluations = search_protein_evaluations(query)
        return {
            'success': True,
            'evaluations': [e.to_dict() for e in evaluations]
        }

    # ========== 批量评估方法 ==========

    def start_batch_evaluation(self, uniprot_ids: List[str], name: str = None, config: Dict = None) -> Dict[str, Any]:
        """
        开始批量蛋白质评估

        参数:
            uniprot_ids: UniProt蛋白质ID列表
            name: 批量评估名称（可选）
            config: 配置选项（可选）

        返回:
            批量评估任务信息
        """
        # Parse and validate UniProt IDs
        parsed_ids = []
        for uniprot_id in uniprot_ids:
            # Clean the ID - remove whitespace, convert to upper case
            clean_id = uniprot_id.strip().upper()
            if clean_id and clean_id not in parsed_ids:
                parsed_ids.append(clean_id)

        if not parsed_ids:
            return {'success': False, 'error': '请提供有效的UniProt ID列表'}

        if len(parsed_ids) < 2:
            return {'success': False, 'error': '批量评估至少需要2个UniProt ID'}

        try:
            # Create batch evaluation record
            batch_name = name or f"批量评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            batch = create_batch_evaluation(
                name=batch_name,
                uniprot_ids=parsed_ids,
                config=config or {}
            )

            if not batch:
                return {'success': False, 'error': '创建批量评估记录失败'}

            # Start background task for batch evaluation
            thread = threading.Thread(
                target=self._run_batch_evaluation_task,
                args=(batch.id, parsed_ids, config or {})
            )
            thread.daemon = True
            thread.start()

            return {
                'success': True,
                'batch_id': batch.id,
                'uniprot_ids': parsed_ids,
                'name': batch_name,
                'message': '批量评估任务已启动'
            }

        except Exception as e:
            logger.error(f"启动批量评估失败: {e}")
            return {'success': False, 'error': str(e)}

    def _run_batch_evaluation_task(self, batch_id: int, uniprot_ids: List[str], config: Dict):
        """在后台线程中执行批量评估任务"""
        try:
            # Set config for this batch evaluation
            default_config = {
                'max_pdb': 100,
                'max_literature': 20,
                'ai_temperature': 0.3,
                'ai_max_tokens': 6000,
                'ai_prompt': ''
            }
            if config:
                default_config.update(config)
            self.config = default_config

            logger.info(f"========== 开始批量评估任务 [ID={batch_id}, UniProt IDs={uniprot_ids}] ==========")
            logger.info(f"使用AI配置: provider={self.config.get('ai_provider')}, model={self.config.get('ai_model')}")

            # Update status to processing
            update_batch_evaluation(batch_id, {
                'status': 'processing',
                'progress': 10
            })

            # Step 1: Fetch protein interaction data from String Database
            self._add_batch_log(batch_id, "开始获取蛋白互作数据...")
            interaction_data = self._fetch_protein_interactions(uniprot_ids)

            update_batch_evaluation(batch_id, {
                'interaction_data': interaction_data,
                'progress': 30
            })

            self._add_batch_log(batch_id, f"获取到 {len(interaction_data.get('interactions', []))} 条互作关系")

            # Step 2: Run individual evaluations for each protein
            total_proteins = len(uniprot_ids)
            individual_results = []

            for idx, uniprot_id in enumerate(uniprot_ids):
                self._add_batch_log(batch_id, f"[{idx+1}/{total_proteins}] 开始评估蛋白 {uniprot_id}...")

                # Create individual evaluation
                evaluation = create_protein_evaluation(uniprot_id=uniprot_id)
                if evaluation:
                    # Run the individual evaluation in a synchronous way
                    try:
                        # Create a new instance for synchronous execution
                        eval_config = config.copy() if config else {}
                        eval_result = self._run_evaluation_task_sync(evaluation.id, uniprot_id, eval_config)
                        individual_results.append({
                            'uniprot_id': uniprot_id,
                            'evaluation_id': evaluation.id,
                            'status': eval_result.get('status', 'unknown')
                        })
                    except Exception as e:
                        logger.error(f"评估蛋白 {uniprot_id} 失败: {e}")
                        individual_results.append({
                            'uniprot_id': uniprot_id,
                            'evaluation_id': evaluation.id,
                            'status': 'failed',
                            'error': str(e)
                        })

                # Update batch progress
                progress = 30 + int((idx + 1) / total_proteins * 40)
                update_batch_evaluation(batch_id, {'progress': progress})

            self._add_batch_log(batch_id, "所有蛋白评估完成")

            # Step 3: Run batch AI analysis
            update_batch_evaluation(batch_id, {'progress': 75})
            self._add_batch_log(batch_id, "开始批量AI分析...")

            batch_ai_result = self._run_batch_ai_analysis(
                uniprot_ids=uniprot_ids,
                interaction_data=interaction_data,
                individual_results=individual_results
            )

            update_batch_evaluation(batch_id, {
                'batch_ai_analysis': batch_ai_result,
                'progress': 90
            })

            # Step 4: Generate final batch report
            self._add_batch_log(batch_id, "生成综合报告...")
            batch_report = self._generate_batch_report(uniprot_ids, interaction_data, individual_results, batch_ai_result)

            # Mark as completed
            update_batch_evaluation(batch_id, {
                'status': 'completed',
                'progress': 100,
                'batch_report': batch_report
            })

            self._add_batch_log(batch_id, "批量评估完成!")

            logger.info(f"========== 批量评估任务完成 [ID={batch_id}] ==========")

        except Exception as e:
            logger.error(f"批量评估任务失败: {e}")
            update_batch_evaluation(batch_id, {
                'status': 'failed'
            })
            self._add_batch_log(batch_id, f"评估失败: {str(e)}", 'error')

    def _fetch_protein_interactions(self, uniprot_ids: List[str]) -> Dict[str, Any]:
        """从String Database获取蛋白互作数据"""
        try:
            # String Database API
            # API: https://string-db.org/api/json/interaction_partners
            # Parameters: species=9606 (human), protein list (comma separated)

            url = "https://string-db.org/api/json/interaction_partners"
            params = {
                'species': 9606,  # Human
                'limit': 10,  # Limit results per protein
            }

            all_interactions = []

            # Query all proteins at once - String API accepts comma-separated list
            try:
                params['proteins'] = ','.join(uniprot_ids)
                response = http_session.get(url, params=params, timeout=30)

                if response.status_code == 400:
                    # If 400, try querying each protein individually with gene names
                    logger.warning("Bulk query failed, trying individual queries")
                    response = None

                if response and response.status_code == 200:
                    data = response.json()

                    # Parse interactions
                    for item in data:
                        protein_b_id = item.get('stringdb_B', '')
                        if protein_b_id in uniprot_ids:
                            interaction = {
                                'protein_a': item.get('stringdb_A', ''),
                                'protein_b': protein_b_id,
                                'protein_b_name': item.get('preferredName_B', {}).get('geneName', ''),
                                'score': item.get('score', 0),
                                'type': item.get('interaction_type', 'unknown')
                            }
                            all_interactions.append(interaction)
            except Exception as e:
                logger.warning(f"Bulk query failed: {e}, trying individual queries")

            # If bulk query failed, try individual queries with gene names
            if not all_interactions:
                for uniprot_id in uniprot_ids:
                    try:
                        # First get gene name from UniProt
                        uniprot_data = self._fetch_uniprot_metadata(uniprot_id)
                        gene_names = uniprot_data.get('gene_names', []) if uniprot_data else []
                        if not gene_names:
                            continue

                        gene_name = gene_names[0]
                        params['proteins'] = gene_name

                        response = http_session.get(url, params=params, timeout=30)
                        if response.status_code != 200:
                            continue

                        data = response.json()

                        # Parse interactions
                        for item in data:
                            protein_b_id = item.get('stringdb_B', '')
                            # Check if the interacting protein is in our list
                            if protein_b_id in uniprot_ids:
                                interaction = {
                                    'protein_a': uniprot_id,
                                    'protein_b': protein_b_id,
                                    'protein_b_name': item.get('preferredName_B', {}).get('geneName', ''),
                                    'score': item.get('score', 0),
                                    'type': item.get('interaction_type', 'unknown')
                                }
                                all_interactions.append(interaction)
                    except Exception as e:
                        logger.warning(f"获取蛋白 {uniprot_id} 的互作数据失败: {e}")
                        continue

            return {
                'interactions': all_interactions,
                'source': 'string_db'
            }

        except Exception as e:
            logger.error(f"获取蛋白互作数据失败: {e}")
            return {'interactions': [], 'source': 'string_db', 'error': str(e)}

    def _run_batch_ai_analysis(self, uniprot_ids: List[str], interaction_data: Dict,
                               individual_results: List[Dict]) -> Dict[str, Any]:
        """运行批量AI分析"""
        try:
            # Get AI client based on config
            ai_provider = self.config.get('ai_provider', 'openai')
            ai_model = self.config.get('ai_model', 'gpt-4o')
            ai_base_url = self.config.get('ai_base_url', '')
            ai_api_key = self.config.get('ai_api_key', '')
            ai_max_tokens = self.config.get('ai_max_tokens', 8000)
            ai_temperature = self.config.get('ai_temperature', 0.3)

            # Create client based on provider
            if ai_provider == 'anthropic':
                client = AnthropicClient(api_key=ai_api_key, model=ai_model, base_url=ai_base_url)
            elif ai_provider == 'gemini':
                client = GeminiClient(api_key=ai_api_key, model=ai_model, base_url=ai_base_url)
            else:
                client = OpenAIClient(api_key=ai_api_key, base_url=ai_base_url, model=ai_model)

            # Get individual evaluation reports
            individual_reports = self._get_individual_reports(uniprot_ids)

            # Build the prompt for batch analysis with individual reports
            prompt = self._build_batch_prompt(uniprot_ids, interaction_data, individual_reports)

            # Create messages in the format expected by AI clients
            messages = [
                {"role": "system", "content": "你是一个专业的蛋白质结构生物学家和生物信息学专家。请对多个蛋白质进行综合比较分析。"},
                {"role": "user", "content": prompt}
            ]

            # Call AI API
            response = client.chat(messages, max_tokens=ai_max_tokens, temperature=ai_temperature, timeout=300)

            if response.get('success'):
                return {
                    'success': True,
                    'analysis': response.get('content', ''),
                    'model': response.get('model', ai_model)
                }
            else:
                return {'success': False, 'error': response.get('error', 'AI分析失败')}

        except Exception as e:
            logger.error(f"批量AI分析失败: {e}")
            return {'success': False, 'error': str(e)}

    def _get_individual_reports(self, uniprot_ids: List[str]) -> Dict[str, str]:
        """获取各单独评估的报告"""
        reports = {}
        for uniprot_id in uniprot_ids:
            try:
                evaluation = get_protein_evaluation_by_uniprot(uniprot_id)
                if evaluation and evaluation.report:
                    reports[uniprot_id] = evaluation.report
                else:
                    reports[uniprot_id] = None
            except Exception as e:
                logger.warning(f"获取蛋白 {uniprot_id} 的单独评估报告失败: {e}")
                reports[uniprot_id] = None
        return reports

    def _build_batch_prompt(self, uniprot_ids: List[str], interaction_data: Dict,
                            individual_reports: Dict[str, str]) -> str:
        """构建批量分析提示词 - 使用单独评估报告"""
        import config as cfg

        # Try to get batch template from database first
        from src.database import get_default_batch_template
        batch_template_obj = get_default_batch_template()

        if batch_template_obj and batch_template_obj.content:
            batch_template = batch_template_obj.content
        else:
            batch_template = getattr(cfg, 'BATCH_INTERACTION_PROMPT_TEMPLATE', '')

        # Get basic protein info for each ID
        protein_info = []
        for uniprot_id in uniprot_ids:
            try:
                uniprot_data = self._fetch_uniprot_metadata(uniprot_id)
                if uniprot_data:
                    protein_info.append({
                        'uniprot_id': uniprot_id,
                        'name': uniprot_data.get('protein_name', 'Unknown'),
                        'gene': ', '.join(uniprot_data.get('gene_names', [])),
                        'organism': uniprot_data.get('organism', 'Unknown'),
                        'pdb_count': len(uniprot_data.get('pdb_ids', []))
                    })
            except Exception:
                protein_info.append({
                    'uniprot_id': uniprot_id,
                    'name': 'Unknown',
                    'gene': 'Unknown',
                    'organism': 'Unknown',
                    'pdb_count': 0
                })

        # Get the batch interaction template
        batch_template = getattr(cfg, 'BATCH_INTERACTION_PROMPT_TEMPLATE', '')

        # Build the prompt
        prompt = batch_template + "\n\n"

        # Add protein basic info
        prompt += "## 输入数据\n\n### 蛋白质基本信息\n\n"
        for info in protein_info:
            prompt += f"- **UniProt ID**: {info['uniprot_id']}\n"
            prompt += f"  - 蛋白名称: {info['name']}\n"
            prompt += f"  - 基因名称: {info['gene']}\n"
            prompt += f"  - 物种: {info['organism']}\n"
            prompt += f"  - PDB结构数量: {info['pdb_count']}\n\n"

        # Add interaction data
        interactions = interaction_data.get('interactions', [])
        if interactions:
            prompt += "### 蛋白相互作用网络（来自String Database）\n\n"
            prompt += f"检测到 {len(interactions)} 条互作关系：\n\n"
            prompt += "| 蛋白A | 蛋白B | 置信度分数 | 互作类型 |\n"
            prompt += "|-------|-------|------------|----------|\n"
            for interaction in interactions[:20]:
                prompt += f"| {interaction.get('protein_a', '')} | {interaction.get('protein_b_name', interaction.get('protein_b', ''))} | {interaction.get('score', 0):.2f} | {interaction.get('type', 'unknown')} |\n"
            prompt += "\n"

        # Add individual reports
        prompt += "### 单独评估报告要点\n\n"
        for uniprot_id in uniprot_ids:
            report = individual_reports.get(uniprot_id)
            info = next((p for p in protein_info if p['uniprot_id'] == uniprot_id), None)
            protein_name = info['name'] if info else uniprot_id

            prompt += f"#### {protein_name} ({uniprot_id})\n\n"
            if report:
                # Extract key parts from the report (first 1500 chars as summary)
                report_summary = report[:1500] + "..." if len(report) > 1500 else report
                prompt += f"评估报告摘要：\n{report_summary}\n\n"
            else:
                prompt += "（暂无单独评估报告）\n\n"

        return prompt

    def _generate_batch_report(self, uniprot_ids: List[str], interaction_data: Dict,
                                individual_results: List[Dict], batch_ai_result: Dict) -> str:
        """生成批量评估综合报告"""
        sections = []

        # Title
        sections.append("# 批量蛋白质评估综合报告\n")

        # Overview
        sections.append(f"## 概述\n")
        sections.append(f"- 评估蛋白数量: {len(uniprot_ids)}")
        sections.append(f"- UniProt IDs: {', '.join(uniprot_ids)}")
        sections.append(f"- 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Interaction summary
        interactions = interaction_data.get('interactions', [])
        sections.append(f"\n## 蛋白互作网络\n")
        sections.append(f"- 检测到互作关系: {len(interactions)} 条")
        sections.append(f"- 数据来源: String Database")

        # Individual results summary
        sections.append(f"\n## 单蛋白评估结果\n")
        sections.append(f"| UniProt ID | 状态 |")
        sections.append(f"|------------|------|")
        for result in individual_results:
            status = result.get('status', 'unknown')
            uniprot_id = result.get('uniprot_id', '')
            sections.append(f"| {uniprot_id} | {status} |")

        # AI Analysis
        if batch_ai_result.get('success') and batch_ai_result.get('analysis'):
            sections.append(f"\n## AI分析报告\n")
            sections.append(batch_ai_result.get('analysis', ''))

        return "\n".join(sections)

    def _run_evaluation_task_sync(self, evaluation_id: int, uniprot_id: str, config: Dict = None) -> Dict[str, Any]:
        """同步执行单个蛋白评估任务（供批量评估调用）"""
        # This is a simplified version that runs synchronously
        try:
            # Update status
            update_protein_evaluation(evaluation_id, {
                'evaluation_status': 'processing',
                'current_step': 'fetching_pdb',
                'progress': 10
            })

            # Fetch UniProt data
            uniprot_data = self._fetch_uniprot_metadata(uniprot_id)
            if uniprot_data:
                gene_name = uniprot_data.get('gene_names', [None])[0]
                protein_name = uniprot_data.get('protein_name', None)
                update_protein_evaluation(evaluation_id, {
                    'gene_name': gene_name,
                    'protein_name': protein_name,
                    'uniprot_data': uniprot_data
                })

            # Fetch PDB data
            pdb_ids = uniprot_data.get('pdb_ids', []) if uniprot_data else []
            max_pdb = config.get('max_pdb', 50) if config else 50
            if len(pdb_ids) > max_pdb:
                pdb_ids = pdb_ids[:max_pdb]

            pdb_data = self._fetch_pdb_metadata(pdb_ids, evaluation_id)
            update_protein_evaluation(evaluation_id, {
                'pdb_data': pdb_data,
                'progress': 50
            })

            # Run AI analysis for individual evaluation report
            self._add_log(evaluation_id, "开始生成单独评估报告...")
            ai_result = self._run_ai_analysis(uniprot_data, pdb_data, {}, evaluation_id)

            # Save the report
            if ai_result.get('analysis'):
                report = ai_result.get('analysis')
            else:
                # Generate a simple report if AI failed
                report = f"# {uniprot_id} 蛋白质评估报告\n\n"
                report += f"蛋白名称: {uniprot_data.get('protein_name', 'Unknown')}\n"
                report += f"基因名称: {', '.join(uniprot_data.get('gene_names', []))}\n"
                report += f"PDB结构数量: {len(pdb_data.get('structures', []))}\n"
                report += "\n（注：AI分析未能成功完成，仅保存基础数据）"

            update_protein_evaluation(evaluation_id, {
                'report': report,
                'ai_analysis': ai_result,
                'evaluation_status': 'completed',
                'progress': 100,
                'current_step': 'completed'
            })

            return {'status': 'completed', 'evaluation_id': evaluation_id, 'report': report}

        except Exception as e:
            logger.error(f"同步评估失败: {e}")
            update_protein_evaluation(evaluation_id, {
                'evaluation_status': 'failed',
                'error_message': str(e)
            })
            return {'status': 'failed', 'error': str(e)}

    def _add_batch_log(self, batch_id: int, message: str, level: str = 'info'):
        """添加批量评估日志"""
        try:
            batch = get_batch_evaluation(batch_id)
            if batch:
                # Get existing logs from config or create new
                logs = batch.config.get('logs', []) if batch.config else []
                logs.append({
                    'timestamp': time.strftime('%H:%M:%S'),
                    'level': level,
                    'message': message
                })
                update_batch_evaluation(batch_id, {
                    'config': {**batch.config, 'logs': logs} if batch.config else {'logs': logs}
                })
        except Exception as e:
            logger.warning(f"添加批量评估日志失败: {e}")

    # ========== Batch Evaluation API Methods ==========

    def get_batch_evaluation_status(self, batch_id: int) -> Dict[str, Any]:
        """获取批量评估状态"""
        batch = get_batch_evaluation(batch_id)
        if not batch:
            return {'success': False, 'error': '批量评估记录不存在'}

        # Get individual evaluations for this batch - include full report
        evaluations = get_all_protein_evaluations(limit=100)
        batch_evaluations = []
        for e in evaluations:
            if e.batch_id == batch_id:
                eval_dict = e.to_dict()
                # Include full report if available
                if e.report:
                    eval_dict['full_report'] = e.report
                batch_evaluations.append(eval_dict)

        return {
            'success': True,
            'batch': batch.to_dict(),
            'evaluations': batch_evaluations,
            'interactions': get_protein_interactions(batch_id)
        }

    def list_batch_evaluations(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """列出所有批量评估"""
        batches = get_all_batch_evaluations(limit, offset)
        return {
            'success': True,
            'batches': [b.to_dict() for b in batches],
            'total': len(batches)
        }

    def delete_batch_evaluation(self, batch_id: int) -> Dict[str, Any]:
        """删除批量评估"""
        # Delete interactions first
        delete_protein_interactions(batch_id)
        # Delete batch
        success = delete_batch_evaluation(batch_id)
        return {'success': success}


# 全局实例
_evaluation_service = None

def get_evaluation_service() -> ProteinEvaluationService:
    """获取评估服务实例"""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = ProteinEvaluationService()
    return _evaluation_service


# ========== 测试函数 ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    service = get_evaluation_service()

    print("测试启动评估任务...")
    result = service.start_evaluation("P04637")  # p53
    print(f"结果: {result}")

    time.sleep(2)
    if result.get('success'):
        eval_id = result.get('evaluation_id')
        status = service.get_evaluation_status(eval_id)
        print(f"状态: {status}")
