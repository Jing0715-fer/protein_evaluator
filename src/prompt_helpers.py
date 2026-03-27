"""
Prompt Helper Functions for Structuring Data for AI Analysis

提供数据结构化函数，用于从原始数据中提取统计信息、实体详情等，
以结构化的方式组织后供 AI 分析使用。
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict


def extract_pdb_statistics(structures: List[Dict]) -> Dict[str, Any]:
    """
    从 PDB 结构列表中提取统计信息。

    Args:
        structures: PDB 结构列表

    Returns:
        包含统计信息的字典
    """
    if not structures:
        return {
            'total_structures': 0,
            'resolution_range': None,
            'method_distribution': {},
            'coverage_distribution': {},
            'avg_resolution': None
        }

    total = len(structures)
    methods = defaultdict(int)
    resolutions = []

    for struct in structures:
        # 实验方法分布
        method = struct.get('experimental_method', 'Unknown')
        if method:
            methods[method] = methods.get(method, 0) + 1

        # 分辨率
        resolution = struct.get('resolution')
        if resolution and isinstance(resolution, (int, float)):
            resolutions.append(resolution)

    # 计算分辨率范围
    resolution_range = None
    avg_resolution = None
    if resolutions:
        min_res = min(resolutions)
        max_res = max(resolutions)
        if min_res == max_res:
            resolution_range = f"{min_res:.2f}"
        else:
            resolution_range = f"{min_res:.2f} - {max_res:.2f}"
        avg_resolution = sum(resolutions) / len(resolutions)

    return {
        'total_structures': total,
        'resolution_range': resolution_range,
        'avg_resolution': round(avg_resolution, 2) if avg_resolution else None,
        'method_distribution': dict(methods),
        'resolutions': resolutions
    }


def extract_entity_details(pdb_data: Dict) -> List[Dict[str, Any]]:
    """
    从 PDB 数据中提取实体详细信息。

    Args:
        pdb_data: PDB 数据字典

    Returns:
        实体详情列表
    """
    entities = []

    structures = pdb_data.get('structures', [])
    for struct in structures:
        pdb_id = struct.get('pdb_id', 'Unknown')
        entity_list = struct.get('entity_list', [])

        if not entity_list:
            continue

        for entity in entity_list:
            entities.append({
                'pdb_id': pdb_id,
                'entity_id': entity.get('entity_id'),
                'molecule_type': entity.get('polymer_type', 'Unknown'),
                'molecule_name': entity.get('molecule_name', ''),
                'chain': entity.get('chain', ''),
                'length': entity.get('length'),
                'gene_name': entity.get('gene_name', ''),
                'organism': entity.get('organism', '')
            })

    return entities


def extract_ligand_info(pdb_data: Dict) -> List[Dict[str, Any]]:
    """
    从 PDB 数据中提取配体/药物结合信息。

    Args:
        pdb_data: PDB 数据字典

    Returns:
        配体信息列表
    """
    ligands = []

    structures = pdb_data.get('structures', [])
    for struct in structures:
        pdb_id = struct.get('pdb_id', 'Unknown')
        entity_list = struct.get('entity_list', [])

        if not entity_list:
            continue

        for entity in entity_list:
            mol_type = entity.get('polymer_type', '')

            # 配体 (bound) 或非多肽
            if mol_type == 'bound' or 'polypeptide' not in str(mol_type).lower():
                molecule_name = entity.get('molecule_name', '')

                # 判断是否是药物/活性分子
                is_drug = _is_drug_or_active_ligand(molecule_name)

                ligands.append({
                    'pdb_id': pdb_id,
                    'entity_id': entity.get('entity_id'),
                    'ligand_name': molecule_name,
                    'molecule_type': mol_type,
                    'chain': entity.get('chain', ''),
                    'is_drug': is_drug,
                    'organism': entity.get('organism', '')
                })

    return ligands


def _is_drug_or_active_ligand(molecule_name: str) -> bool:
    """
    判断分子是否是药物或活性配体。

    这是一个启发式判断，基于常见的药物/配体名称模式。
    """
    if not molecule_name:
        return False

    name_lower = molecule_name.lower()

    # 常见的药物/配体模式
    drug_patterns = [
        'drug', 'inhibitor', 'agonist', 'antagonist', 'activator',
        'blocker', 'modulator', 'binder', 'compound', 'molecule',
        'atp', 'gtp', 'nad', 'nap', 'heme', 'hem', 'fol', 'hdv',
        'sam', 'sah', 'coa', 'gdp', 'mg', 'mn', 'zn', 'fe', 'cu',
        'ca', 'mg', 'drug', 'pubchem'
    ]

    return any(pattern in name_lower for pattern in drug_patterns)


def extract_literature_for_ai(articles: List[Dict]) -> List[Dict[str, Any]]:
    """
    提取文献完整信息给 AI 分析。

    Args:
        articles: 文献列表

    Returns:
        包含完整摘要的文献列表
    """
    result = []

    for article in articles:
        result.append({
            'pubmed_id': article.get('pubmed_id', ''),
            'title': article.get('title', ''),
            'journal': article.get('journal', ''),
            'year': article.get('year', ''),
            'authors': article.get('authors', []),
            'abstract': article.get('abstract', ''),
            'doi': article.get('doi', '')
        })

    return result


def build_literature_section_for_prompt(
    literature: List[Dict],
    language: str = 'zh'
) -> str:
    """
    构建文献章节文本用于 prompt。

    Args:
        literature: 文献列表
        language: 语言 ('zh' 或 'en')

    Returns:
        格式化的文献章节字符串
    """
    if not literature:
        return ""

    if language == 'zh':
        return _build_literature_section_chinese(literature)
    else:
        return _build_literature_section_english(literature)


def _clean_abstract(text: str) -> str:
    """Clean abstract text for better formatting in prompt."""
    if not text:
        return "无摘要"
    # Replace newlines with spaces and strip extra whitespace
    import re
    text = text.replace('\n', ' ').strip()
    text = re.sub(r'\s+', ' ', text)
    return text if text else "无摘要"


def _build_literature_section_chinese(literature: List[Dict]) -> str:
    """构建中文文献章节"""
    parts = []

    parts.append("## 相关文献完整摘要\n\n")
    parts.append("【以下为文献完整摘要，请据此总结关键发现，不要复制原文】\n\n")

    for idx, article in enumerate(literature, 1):
        pmid = article.get('pubmed_id', 'N/A')
        title = article.get('title', '无标题')
        journal = article.get('journal', '未知期刊')
        year = article.get('year', 'N/A')
        authors = article.get('authors', [])
        author_str = ', '.join(authors[:5]) if len(authors) > 5 else ', '.join(authors)
        if len(authors) > 5:
            author_str += ' et al.'
        abstract = article.get('abstract', '无摘要')

        parts.append(f"### 文献 {idx}: PMID {pmid}\n")
        parts.append(f"- **标题**: {title}\n")
        parts.append(f"- **期刊**: {journal} ({year})\n")
        parts.append(f"- **作者**: {author_str}\n")
        parts.append(f"- **完整摘要**: {abstract}\n\n")

    parts.append("---\n\n")
    parts.append("## 文献关键发现总结\n\n")
    parts.append("【基于上述文献摘要，请自行总结关键发现，不要复制原文】\n\n")

    return "".join(parts)


def _build_literature_section_english(literature: List[Dict]) -> str:
    """构建英文文献章节"""
    parts = []

    parts.append("## Complete Literature Abstracts\n\n")
    parts.append("【The following are complete abstracts for your analysis. Please summarize key findings, do NOT copy the original text】\n\n")

    for idx, article in enumerate(literature, 1):
        pmid = article.get('pubmed_id', 'N/A')
        title = article.get('title', 'No title')
        journal = article.get('journal', 'Unknown journal')
        year = article.get('year', 'N/A')
        authors = article.get('authors', [])
        author_str = ', '.join(authors[:5]) if len(authors) > 5 else ', '.join(authors)
        if len(authors) > 5:
            author_str += ' et al.'
        abstract = article.get('abstract', 'No abstract')

        parts.append(f"### Literature {idx}: PMID {pmid}\n")
        parts.append(f"- **Title**: {title}\n")
        parts.append(f"- **Journal**: {journal} ({year})\n")
        parts.append(f"- **Authors**: {author_str}\n")
        parts.append(f"- **Complete Abstract**: {abstract}\n\n")

    parts.append("---\n\n")
    parts.append("## Key Findings Summary from Literature\n\n")
    parts.append("【Based on the above abstracts, please summarize the key findings. Do NOT copy the original text】\n\n")

    return "".join(parts)


def extract_homology_statistics(homology_details: List[Dict]) -> Dict[str, Any]:
    """
    从同源结构详情中提取统计信息。

    Args:
        homology_details: 同源结构详情列表

    Returns:
        同源结构统计字典
    """
    if not homology_details:
        return None

    identity_dist = {
        '90+': 0, '70-89': 0, '40-69': 0, '25-39': 0, '<25': 0
    }
    coverage_dist = {
        '90+': 0, '70-89': 0, '40-69': 0, '<40': 0
    }
    quality_dist = {
        'excellent': 0, 'good': 0, 'moderate': 0, 'low': 0
    }

    unique_pdbs = set()
    unique_uniprot = set()
    best_identity = 0.0
    best_coverage = 0.0
    best_pdb = None
    top_homologs = []

    for homolog in homology_details:
        pdb_id = homolog.get('pdb_id')
        if pdb_id:
            unique_pdbs.add(pdb_id)

        source_uniprot = homolog.get('sourceUniProtId') or homolog.get('source_uniprot_id')
        if source_uniprot:
            unique_uniprot.add(source_uniprot)

        # 提取序列一致性
        identity = float(homolog.get('percent_identity', 0) or 0)

        # 提取覆盖率
        coverage = float(homolog.get('coverage_percentage', 0) or 0)

        # 提取质量评估
        quality = str(homolog.get('quality_assessment', homolog.get('quality', 'low'))).lower()

        # 更新最佳匹配
        if identity > best_identity:
            best_identity = identity
            best_coverage = coverage
            best_pdb = pdb_id

        # 分布统计
        if identity >= 90:
            identity_dist['90+'] += 1
        elif identity >= 70:
            identity_dist['70-89'] += 1
        elif identity >= 40:
            identity_dist['40-69'] += 1
        elif identity >= 25:
            identity_dist['25-39'] += 1
        else:
            identity_dist['<25'] += 1

        # 覆盖率分布
        if coverage >= 90:
            coverage_dist['90+'] += 1
        elif coverage >= 70:
            coverage_dist['70-89'] += 1
        elif coverage >= 40:
            coverage_dist['40-69'] += 1
        else:
            coverage_dist['<40'] += 1

        # 质量分布
        if 'excellent' in quality:
            quality_dist['excellent'] += 1
        elif 'good' in quality:
            quality_dist['good'] += 1
        elif 'moderate' in quality or 'medium' in quality:
            quality_dist['moderate'] += 1
        else:
            quality_dist['low'] += 1

        # 收集高质量同源结构
        top_homologs.append({
            'pdb_id': pdb_id,
            'identity': identity,
            'coverage': coverage,
            'quality': quality,
            'source_uniprot_id': source_uniprot
        })

    # 按一致性排序，取前10
    top_homologs.sort(key=lambda x: (x['identity'], x['coverage']), reverse=True)
    top_homologs = top_homologs[:10]

    return {
        'total_homologs': len(homology_details),
        'unique_pdb_count': len(unique_pdbs),
        'unique_uniprot_ids': sorted(list(unique_uniprot)),
        'best_identity': round(best_identity, 1),
        'best_coverage': round(best_coverage, 1),
        'best_pdb': best_pdb,
        'identity_distribution': identity_dist,
        'coverage_distribution': coverage_dist,
        'quality_distribution': quality_dist,
        'unique_pdb_ids': sorted(list(unique_pdbs)),
        'top_homologs': top_homologs
    }


def build_entity_section_for_prompt(
    pdb_data: Dict,
    language: str = 'zh'
) -> str:
    """
    构建 PDB 实体详情章节用于 prompt。

    Args:
        pdb_data: PDB 数据字典
        language: 语言 ('zh' 或 'en')

    Returns:
        格式化的实体章节字符串
    """
    if language == 'zh':
        return _build_entity_section_chinese(pdb_data)
    else:
        return _build_entity_section_english(pdb_data)


def _build_entity_section_chinese(pdb_data: Dict) -> str:
    """构建中文 PDB 实体章节"""
    entities = extract_entity_details(pdb_data)

    if not entities:
        return ""

    parts = []
    parts.append("## PDB 实体详细信息\n\n")

    # 按 PDB ID 分组
    by_pdb = defaultdict(list)
    for ent in entities:
        by_pdb[ent['pdb_id']].append(ent)

    for pdb_id, entity_list in by_pdb.items():
        parts.append(f"### {pdb_id}\n\n")

        # 实体表格
        parts.append("| 实体ID | 分子类型 | 分子名称 | 链 | 长度 | 基因 | 物种 |\n")
        parts.append("|--------|----------|----------|-----|------|------|------|\n")

        for ent in entity_list:
            mol_type = ent.get('molecule_type', 'Unknown')
            mol_name = ent.get('molecule_name', 'N/A')
            chain = ent.get('chain', '-')
            length = ent.get('length') or 'N/A'
            gene = ent.get('gene_name', 'N/A')
            organism = ent.get('organism', 'N/A')

            # 截断过长的名称
            if len(str(mol_name)) > 30:
                mol_name = str(mol_name)[:30] + '...'

            parts.append(f"| {ent.get('entity_id', '-')} | {mol_type} | {mol_name} | {chain} | {length} | {gene} | {organism} |\n")

        parts.append("\n")

    return "".join(parts)


def _build_entity_section_english(pdb_data: Dict) -> str:
    """构建英文 PDB 实体章节"""
    entities = extract_entity_details(pdb_data)

    if not entities:
        return ""

    parts = []
    parts.append("## PDB Entity Details\n\n")

    # 按 PDB ID 分组
    by_pdb = defaultdict(list)
    for ent in entities:
        by_pdb[ent['pdb_id']].append(ent)

    for pdb_id, entity_list in by_pdb.items():
        parts.append(f"### {pdb_id}\n\n")

        # Entity table
        parts.append("| EntityID | Molecule Type | Molecule Name | Chain | Length | Gene | Organism |\n")
        parts.append("|----------|--------------|----------------|-------|--------|------|----------|\n")

        for ent in entity_list:
            mol_type = ent.get('molecule_type', 'Unknown')
            mol_name = ent.get('molecule_name', 'N/A')
            chain = ent.get('chain', '-')
            length = ent.get('length') or 'N/A'
            gene = ent.get('gene_name', 'N/A')
            organism = ent.get('organism', 'N/A')

            if len(str(mol_name)) > 30:
                mol_name = str(mol_name)[:30] + '...'

            parts.append(f"| {ent.get('entity_id', '-')} | {mol_type} | {mol_name} | {chain} | {length} | {gene} | {organism} |\n")

        parts.append("\n")

    return "".join(parts)


def build_ligand_section_for_prompt(
    pdb_data: Dict,
    language: str = 'zh'
) -> str:
    """
    构建配体/药物结合信息章节用于 prompt。

    Args:
        pdb_data: PDB 数据字典
        language: 语言 ('zh' 或 'en')

    Returns:
        格式化的配体章节字符串
    """
    ligands = extract_ligand_info(pdb_data)

    if not ligands:
        return ""

    if language == 'zh':
        return _build_ligand_section_chinese(ligands)
    else:
        return _build_ligand_section_english(ligands)


def _build_ligand_section_chinese(ligands: List[Dict]) -> str:
    """构建中文配体章节"""
    parts = []

    parts.append("## 配体/药物结合信息\n\n")

    # 检查是否有药物结合蛋白
    drug_ligands = [l for l in ligands if l.get('is_drug')]
    if drug_ligands:
        parts.append("### 药物/活性配体\n\n")
        for ligand in drug_ligands:
            parts.append(f"- **{ligand.get('ligand_name', 'N/A')}** (PDB: {ligand.get('pdb_id')}, 类型: {ligand.get('molecule_type', 'N/A')})\n")
            if ligand.get('organism'):
                parts.append(f"  - 来源: {ligand.get('organism')}\n")

    # 所有配体
    parts.append("\n### 所有配体/小分子\n\n")
    for ligand in ligands:
        parts.append(f"- {ligand.get('ligand_name', 'N/A')} (PDB: {ligand.get('pdb_id')}, 类型: {ligand.get('molecule_type', 'N/A')})\n")

    parts.append("\n")

    return "".join(parts)


def _build_ligand_section_english(ligands: List[Dict]) -> str:
    """构建英文配体章节"""
    parts = []

    parts.append("## Ligand/Drug Binding Information\n\n")

    drug_ligands = [l for l in ligands if l.get('is_drug')]
    if drug_ligands:
        parts.append("### Drug/Active Ligands\n\n")
        for ligand in drug_ligands:
            parts.append(f"- **{ligand.get('ligand_name', 'N/A')}** (PDB: {ligand.get('pdb_id')}, Type: {ligand.get('molecule_type', 'N/A')})\n")
            if ligand.get('organism'):
                parts.append(f"  - Source: {ligand.get('organism')}\n")

    parts.append("\n### All Ligands/Small Molecules\n\n")
    for ligand in ligands:
        parts.append(f"- {ligand.get('ligand_name', 'N/A')} (PDB: {ligand.get('pdb_id')}, Type: {ligand.get('molecule_type', 'N/A')})\n")

    parts.append("\n")

    return "".join(parts)


def build_pdb_statistics_section(
    structures: List[Dict],
    language: str = 'zh'
) -> str:
    """
    构建 PDB 统计摘要章节。

    Args:
        structures: PDB 结构列表
        language: 语言 ('zh' 或 'en')

    Returns:
        格式化的统计章节字符串
    """
    stats = extract_pdb_statistics(structures)

    if stats['total_structures'] == 0:
        return ""

    if language == 'zh':
        return _build_pdb_stats_section_chinese(stats)
    else:
        return _build_pdb_stats_section_english(stats)


def _build_pdb_stats_section_chinese(stats: Dict) -> str:
    """构建中文 PDB 统计章节"""
    parts = []

    parts.append("## PDB 结构统计摘要\n\n")

    parts.append(f"- **总结构数**: {stats['total_structures']}\n")

    if stats['resolution_range']:
        parts.append(f"- **分辨率范围**: {stats['resolution_range']} Å\n")
        if stats['avg_resolution']:
            parts.append(f"- **平均分辨率**: {stats['avg_resolution']} Å\n")

    if stats['method_distribution']:
        parts.append("- **实验方法分布**:\n")
        for method, count in stats['method_distribution'].items():
            parts.append(f"  - {method}: {count}\n")

    parts.append("\n")

    return "".join(parts)


def _build_pdb_stats_section_english(stats: Dict) -> str:
    """构建英文 PDB 统计章节"""
    parts = []

    parts.append("## PDB Structure Statistics Summary\n\n")

    parts.append(f"- **Total Structures**: {stats['total_structures']}\n")

    if stats['resolution_range']:
        parts.append(f"- **Resolution Range**: {stats['resolution_range']} Å\n")
        if stats['avg_resolution']:
            parts.append(f"- **Average Resolution**: {stats['avg_resolution']} Å\n")

    if stats['method_distribution']:
        parts.append("- **Experimental Method Distribution**:\n")
        for method, count in stats['method_distribution'].items():
            parts.append(f"  - {method}: {count}\n")

    parts.append("\n")

    return "".join(parts)


def build_homology_section_for_prompt(
    homology_stats: Dict,
    language: str = 'zh'
) -> str:
    """
    构建同源结构统计章节。

    Args:
        homology_stats: 同源结构统计字典
        language: 语言 ('zh' 或 'en')

    Returns:
        格式化的同源结构章节字符串
    """
    if not homology_stats:
        return ""

    if language == 'zh':
        return _build_homology_section_chinese(homology_stats)
    else:
        return _build_homology_section_english(homology_stats)


def _build_homology_section_chinese(stats: Dict) -> str:
    """构建中文同源结构章节"""
    parts = []

    parts.append("## 同源结构统计\n\n")

    parts.append(f"- **总同源结构数**: {stats['total_homologs']}\n")
    parts.append(f"- **不同 PDB 结构数**: {stats['unique_pdb_count']}\n")
    parts.append(f"- **最佳序列一致性**: {stats['best_identity']}% (PDB: {stats['best_pdb'] or 'N/A'})\n")
    parts.append(f"- **最佳覆盖率**: {stats['best_coverage']}%\n\n")

    # 序列一致性分布
    parts.append("**序列一致性分布**:\n")
    for range_name, count in stats['identity_distribution'].items():
        if count > 0:
            parts.append(f"- {range_name}%: {count} 个结构\n")

    parts.append("\n")

    # 覆盖率分布
    parts.append("**覆盖率分布**:\n")
    for range_name, count in stats['coverage_distribution'].items():
        if count > 0:
            parts.append(f"- {range_name}%: {count} 个结构\n")

    parts.append("\n")

    # 质量分布
    parts.append("**质量评估分布**:\n")
    for quality, count in stats['quality_distribution'].items():
        if count > 0:
            parts.append(f"- {quality.capitalize()}: {count} 个结构\n")

    parts.append("\n")

    # Top 同源结构
    if stats.get('top_homologs'):
        parts.append("**高质量同源结构示例 (Top 10)**:\n")
        for idx, homolog in enumerate(stats['top_homologs'], 1):
            parts.append(f"{idx}. {homolog['pdb_id']}: {homolog['identity']}% 一致性, {homolog['coverage']}% 覆盖率, 质量: {homolog['quality']}\n")

    parts.append("\n")

    return "".join(parts)


def _build_homology_section_english(stats: Dict) -> str:
    """构建英文同源结构章节"""
    parts = []

    parts.append("## Homology Structure Statistics\n\n")

    parts.append(f"- **Total Homologous Structures**: {stats['total_homologs']}\n")
    parts.append(f"- **Unique PDB Structures**: {stats['unique_pdb_count']}\n")
    parts.append(f"- **Best Sequence Identity**: {stats['best_identity']}% (PDB: {stats['best_pdb'] or 'N/A'})\n")
    parts.append(f"- **Best Coverage**: {stats['best_coverage']}%\n\n")

    # Identity distribution
    parts.append("**Identity Distribution**:\n")
    for range_name, count in stats['identity_distribution'].items():
        if count > 0:
            parts.append(f"- {range_name}%: {count} structures\n")

    parts.append("\n")

    # Coverage distribution
    parts.append("**Coverage Distribution**:\n")
    for range_name, count in stats['coverage_distribution'].items():
        if count > 0:
            parts.append(f"- {range_name}%: {count} structures\n")

    parts.append("\n")

    # Quality distribution
    parts.append("**Quality Assessment Distribution**:\n")
    for quality, count in stats['quality_distribution'].items():
        if count > 0:
            parts.append(f"- {quality.capitalize()}: {count} structures\n")

    parts.append("\n")

    # Top homologs
    if stats.get('top_homologs'):
        parts.append("**High-Quality Homolog Examples (Top 10)**:\n")
        for idx, homolog in enumerate(stats['top_homologs'], 1):
            parts.append(f"{idx}. {homolog['pdb_id']}: {homolog['identity']}% identity, {homolog['coverage']}% coverage, Quality: {homolog['quality']}\n")

    parts.append("\n")

    return "".join(parts)
