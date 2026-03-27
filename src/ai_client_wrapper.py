"""
AI client wrapper for protein analysis.
Provides a unified interface for different AI providers.
"""

import logging
from typing import Dict, List, Any, Optional

import config
from utils.ai_client import get_ai_client, OpenAIClient, AnthropicClient, GeminiClient
from utils.api_utils import retry_with_backoff
from utils.exceptions import AIAnalysisError
from src.prompt_helpers import (
    extract_pdb_statistics,
    extract_entity_details,
    extract_ligand_info,
    extract_literature_for_ai,
    build_literature_section_for_prompt,
    build_entity_section_for_prompt,
    build_ligand_section_for_prompt,
    build_pdb_statistics_section,
    build_homology_section_for_prompt,
    extract_homology_statistics
)

logger = logging.getLogger(__name__)


class AIClientWrapper:
    """Wrapper for AI client operations."""

    def __init__(
        self,
        provider: str = None,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        max_tokens: int = 6000,
        temperature: float = 0.3
    ):
        """
        Initialize AI client wrapper.

        Args:
            provider: AI provider ('openai', 'anthropic', 'gemini')
            model: Model name
            api_key: API key
            base_url: Base URL for API
            max_tokens: Maximum tokens in response
            temperature: Temperature for generation
        """
        self.provider = provider or getattr(config, 'AI_PROVIDER', 'openai')
        self.model = model or getattr(config, 'AI_MODEL', 'gpt-4o')
        self.api_key = api_key or getattr(config, 'AI_API_KEY', '')
        self.base_url = base_url or getattr(config, 'AI_BASE_URL', '')
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = None

        self._init_client()

    def _init_client(self):
        """Initialize the AI client."""
        try:
            if self.provider == 'anthropic':
                self.client = AnthropicClient(
                    api_key=self.api_key,
                    model=self.model,
                    base_url=self.base_url
                )
            elif self.provider == 'gemini':
                self.client = GeminiClient(
                    api_key=self.api_key,
                    model=self.model,
                    base_url=self.base_url
                )
            else:  # default to openai
                self.client = OpenAIClient(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    model=self.model
                )

            logger.info(f"AI client initialized: provider={self.provider}, model={self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if AI client is available."""
        return self.client is not None

    @retry_with_backoff(max_retries=2, initial_delay=1.0)
    def analyze(
        self,
        prompt: str,
        system_message: str = None,
        max_tokens: int = None,
        temperature: float = None
    ) -> Dict[str, Any]:
        """
        Run AI analysis.

        Args:
            prompt: User prompt
            system_message: System message
            max_tokens: Override max tokens
            temperature: Override temperature

        Returns:
            Dictionary with 'analysis', 'model', and optional 'error'
        """
        if not self.client:
            return {'error': 'AI client not initialized'}

        try:
            messages = []

            if system_message:
                messages.append({"role": "system", "content": system_message})

            messages.append({"role": "user", "content": prompt})

            response = self.client.chat(
                messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                timeout=300
            )

            if response.get('success'):
                return {
                    'analysis': response.get('content', ''),
                    'model': response.get('model', self.model),
                    'success': True
                }
            else:
                return {
                    'error': response.get('error', 'AI analysis failed'),
                    'success': False
                }

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {'error': str(e), 'success': False}

    def build_analysis_prompt(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        custom_template: str = None,
        language: str = 'zh',
        config: Dict[str, Any] = None
    ) -> str:
        """
        Build analysis prompt from protein data.

        Args:
            uniprot_data: UniProt protein data
            pdb_data: PDB structure data
            blast_results: BLAST search results
            custom_template: Custom prompt template
            language: Language code ('zh' for Chinese, 'en' for English)
            config: Configuration dictionary

        Returns:
            Formatted prompt string
        """
        if custom_template:
            return self._apply_template(custom_template, uniprot_data, pdb_data, blast_results)

        if language == 'en':
            return self._build_english_prompt(uniprot_data, pdb_data, blast_results, config)
        else:
            return self._build_chinese_prompt(uniprot_data, pdb_data, blast_results, config)

    def _build_english_prompt(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        config: Dict[str, Any] = None
    ) -> str:
        """Build English analysis prompt."""
        parts = []

        parts.append("""# Protein Structure-Function Analysis Report Generator

You are a professional protein structural biologist and bioinformatics expert. Based on the following protein data, generate a **comprehensive and in-depth analysis report**.

## Report Requirements:
1. **Word Count**: Total report should be at least 4000 words
2. **Analysis Depth**: In-depth interpretation of each analysis dimension
3. **Clear Structure**: Organize content with multi-level headings
4. **Data-Driven**: Combine specific PDB structure data for analysis

Please generate the report following this framework:""")

        parts.append("")

        # 1. Protein basic info
        parts.append("## Provided Protein Data:\n")

        if uniprot_data:
            uniprot_id = uniprot_data.get('uniprot_id', 'N/A')
            protein_name = uniprot_data.get('protein_name', 'N/A')
            gene_names = ', '.join(uniprot_data.get('gene_names', []))
            organism = uniprot_data.get('organism', 'N/A')
            sequence_length = uniprot_data.get('sequence_length', 0)
            function = uniprot_data.get('function', 'No data available')

            parts.append(f"### Basic Information\n")
            parts.append(f"- UniProt ID: {uniprot_id}\n")
            parts.append(f"- Protein Name: {protein_name}\n")
            parts.append(f"- Gene Name: {gene_names}\n")
            parts.append(f"- Organism: {organism}\n")
            parts.append(f"- Sequence Length: {sequence_length} aa\n")

            if function:
                parts.append(f"- Function Description: {function[:1000]}\n")

        # 2. PDB structures
        parts.append("\n### PDB Structure Data\n")

        if pdb_data and pdb_data.get('structures'):
            structures = pdb_data.get('structures', [])
            max_pdb = config.get('max_pdb') if config else None
            if max_pdb and isinstance(max_pdb, int) and max_pdb > 0:
                structures = structures[:max_pdb]
            parts.append(f"Total of {len(structures)} PDB structures available\n\n")

            # Display all structures
            for idx, struct in enumerate(structures):
                pdb_id = struct.get('pdb_id', 'N/A')
                method = struct.get('experimental_method', 'N/A')
                resolution = struct.get('resolution')
                title = struct.get('title', '')
                authors = struct.get('authors', [])
                citations = struct.get('citations', [])
                deposition_date = struct.get('deposition_date', '')
                entity_list = struct.get('entity_list', [])
                entity_info = struct.get('entity_info', {})

                parts.append(f"**{idx + 1}. {pdb_id}**\n")
                parts.append(f"- Method: {method}\n")
                if resolution:
                    parts.append(f"- Resolution: {resolution} Å\n")
                if title:
                    parts.append(f"- Title: {title[:200]}\n")
                if authors:
                    parts.append(f"- Authors: {', '.join(authors[:5])}")
                    if len(authors) > 5:
                        parts.append(f" et al. ({len(authors)} total)\n")
                    else:
                        parts.append("\n")
                if deposition_date:
                    parts.append(f"- Deposition Date: {deposition_date}\n")

                # Entity information
                if entity_list:
                    polypeptide_count = entity_info.get('polypeptide', 0)
                    if polypeptide_count > 0:
                        parts.append(f"- Entities: {polypeptide_count} polypeptide(s)\n")
                    for ent in entity_list[:3]:  # Show first 3 entities
                        ent_id = ent.get('entity_id', '')
                        chain = ent.get('chain', '')
                        polymer_type = ent.get('polymer_type', '')
                        length = ent.get('length', 0)
                        seq = ent.get('sequence', '')
                        if seq and len(seq) > 0:
                            # Show first 50 chars of sequence
                            seq_preview = seq[:50] + '...' if len(seq) > 50 else seq
                            parts.append(f"  - Entity {ent_id} (Chain {chain}): {polymer_type}, Length {length}\n")
                            parts.append(f"    Sequence: {seq_preview}\n")

                # Citations with abstracts
                if citations:
                    for cite in citations[:2]:  # Show first 2 citations per structure
                        cite_title = cite.get('title', '')
                        journal = cite.get('journal', '')
                        year = cite.get('year', '')
                        pubmed_id = cite.get('pubmed_id', '')
                        abstract = cite.get('abstract', '')
                        if cite_title:
                            parts.append(f"  - Citation: \"{cite_title[:100]}\"")
                            if journal or year:
                                parts.append(f" ({journal}, {year})")
                            if pubmed_id:
                                parts.append(f" [PMID: {pubmed_id}]")
                            parts.append("\n")
                            if abstract:
                                # Include abstract - truncate if too long
                                abstract_text = abstract[:500] + '...' if len(abstract) > 500 else abstract
                                parts.append(f"    Abstract: {abstract_text}\n")
                parts.append("\n")

            parts.append(f"(Total: {len(structures)} structures)\n\n")

            # Coverage info
            coverage = pdb_data.get('coverage', {})
            if coverage:
                parts.append(f"**Sequence Coverage**: {coverage.get('coverage_percent', 0):.1f}%\n")

        else:
            parts.append("No PDB structure data available\n")

        # 3. BLAST results
        parts.append("\n### Similar Protein Search Results\n")

        if blast_results and blast_results.get('results'):
            results = blast_results.get('results', [])
            parts.append(f"Found {len(results)} similar proteins\n\n")

            for idx, result in enumerate(results[:10], 1):
                identifier = result.get('pdb_id') or result.get('uniprot_id', 'N/A')
                name = result.get('title') or result.get('protein_name', 'N/A')
                identity = result.get('identity')

                identity_str = f"({identity:.1f}% identity)" if identity else ""
                parts.append(f"{idx}. {identifier} - {name[:50]} {identity_str}\n")

        else:
            parts.append("No similar protein data available\n")

        # === NEW: PDB Statistics Summary ===
        if pdb_data and pdb_data.get('structures'):
            structures = pdb_data.get('structures', [])
            stats_section = build_pdb_statistics_section(structures, language='en')
            if stats_section:
                parts.append("\n" + stats_section)

            # === NEW: PDB Entity Details ===
            entity_section = build_entity_section_for_prompt(pdb_data, language='en')
            if entity_section:
                parts.append("\n" + entity_section)

            # === NEW: Ligand/Drug Binding Information ===
            ligand_section = build_ligand_section_for_prompt(pdb_data, language='en')
            if ligand_section:
                parts.append("\n" + ligand_section)

            # === NEW: Complete Literature Abstracts for AI (DO NOT copy in report) ===
            all_articles = []
            for struct in structures:
                citations = struct.get('citations', [])
                for cite in citations:
                    if cite.get('pubmed_id'):
                        all_articles.append({
                            'pubmed_id': cite.get('pubmed_id'),
                            'title': cite.get('title', ''),
                            'journal': cite.get('journal', ''),
                            'year': cite.get('year', ''),
                            'authors': cite.get('authors', []),
                            'abstract': cite.get('abstract', ''),
                            'doi': cite.get('doi', '')
                        })

            if all_articles:
                literature_for_ai = extract_literature_for_ai(all_articles)
                literature_section = build_literature_section_for_prompt(literature_for_ai, language='en')
                parts.append("\n" + literature_section)

        # === NEW: Homology Structure Statistics ===
        homology_details = blast_results.get('homology_details', []) if blast_results else []
        if homology_details:
            homology_stats = extract_homology_statistics(homology_details)
            if homology_stats:
                homology_section = build_homology_section_for_prompt(homology_stats, language='en')
                parts.append("\n" + homology_section)

        return "".join(parts)

    def _build_chinese_prompt(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        config: Dict[str, Any] = None
    ) -> str:
        """Build Chinese analysis prompt."""
        parts = []

        parts.append("""# 蛋白质结构功能分析报告生成器

你是一个专业的蛋白质结构生物学家和生物信息学专家。请根据以下提供的蛋白质数据，生成一份**全面深入的综合分析报告**。

## 报告要求：
1. **字数要求**：报告总字数应在4000字以上
2. **分析深度**：每个分析维度都要有深度解读
3. **结构清晰**：使用多级标题组织内容
4. **数据驱动**：结合具体的PDB结构数据进行分析

请按以下框架生成报告：""")

        parts.append("")

        # 1. Protein basic info
        parts.append("## 提供的蛋白质数据：\n")

        if uniprot_data:
            uniprot_id = uniprot_data.get('uniprot_id', 'N/A')
            protein_name = uniprot_data.get('protein_name', 'N/A')
            gene_names = ', '.join(uniprot_data.get('gene_names', []))
            organism = uniprot_data.get('organism', 'N/A')
            sequence_length = uniprot_data.get('sequence_length', 0)
            function = uniprot_data.get('function', '无数据')

            parts.append(f"### 基本信息\n")
            parts.append(f"- UniProt ID: {uniprot_id}\n")
            parts.append(f"- 蛋白质名称: {protein_name}\n")
            parts.append(f"- 基因名: {gene_names}\n")
            parts.append(f"- 物种: {organism}\n")
            parts.append(f"- 序列长度: {sequence_length} aa\n")

            if function:
                parts.append(f"- 功能描述: {function[:1000]}\n")

        # 2. PDB structures
        parts.append("\n### PDB结构数据\n")

        if pdb_data and pdb_data.get('structures'):
            structures = pdb_data.get('structures', [])
            max_pdb = config.get('max_pdb') if config else None
            if max_pdb and isinstance(max_pdb, int) and max_pdb > 0:
                structures = structures[:max_pdb]
            parts.append(f"共有 {len(structures)} 个PDB结构\n\n")

            # 显示所有结构
            for idx, struct in enumerate(structures):
                pdb_id = struct.get('pdb_id', 'N/A')
                method = struct.get('experimental_method', 'N/A')
                resolution = struct.get('resolution')
                title = struct.get('title', '')
                authors = struct.get('authors', [])
                citations = struct.get('citations', [])
                deposition_date = struct.get('deposition_date', '')
                entity_list = struct.get('entity_list', [])
                entity_info = struct.get('entity_info', {})

                parts.append(f"**{idx + 1}. {pdb_id}**\n")
                parts.append(f"- 实验方法: {method}\n")
                if resolution:
                    parts.append(f"- 分辨率: {resolution} Å\n")
                if title:
                    parts.append(f"- 标题: {title[:200]}\n")
                if authors:
                    parts.append(f"- 作者: {', '.join(authors[:5])}")
                    if len(authors) > 5:
                        parts.append(f" 等 {len(authors)} 人\n")
                    else:
                        parts.append("\n")
                if deposition_date:
                    parts.append(f"- 沉积日期: {deposition_date}\n")

                # 实体信息
                if entity_list:
                    polypeptide_count = entity_info.get('polypeptide', 0)
                    if polypeptide_count > 0:
                        parts.append(f"- 实体: {polypeptide_count} 个多肽链\n")
                    for ent in entity_list[:3]:  # 显示前3个实体
                        ent_id = ent.get('entity_id', '')
                        chain = ent.get('chain', '')
                        polymer_type = ent.get('polymer_type', '')
                        length = ent.get('length', 0)
                        seq = ent.get('sequence', '')
                        if seq and len(seq) > 0:
                            # 显示序列前50个字符
                            seq_preview = seq[:50] + '...' if len(seq) > 50 else seq
                            parts.append(f"  - 实体 {ent_id} (链 {chain}): {polymer_type}, 长度 {length}\n")
                            parts.append(f"    序列: {seq_preview}\n")

                # 文献引用（含摘要）
                if citations:
                    for cite in citations[:2]:  # 每个结构显示前2篇文献
                        cite_title = cite.get('title', '')
                        journal = cite.get('journal', '')
                        year = cite.get('year', '')
                        pubmed_id = cite.get('pubmed_id', '')
                        abstract = cite.get('abstract', '')
                        if cite_title:
                            parts.append(f"  - 文献: \"{cite_title[:100]}\"")
                            if journal or year:
                                parts.append(f" ({journal}, {year})")
                            if pubmed_id:
                                parts.append(f" [PMID: {pubmed_id}]")
                            parts.append("\n")
                            if abstract:
                                # 包含摘要 - 如果太长则截断
                                abstract_text = abstract[:500] + '...' if len(abstract) > 500 else abstract
                                parts.append(f"    摘要: {abstract_text}\n")
                parts.append("\n")

            parts.append(f"(共 {len(structures)} 个结构)\n\n")

            # Coverage info
            coverage = pdb_data.get('coverage', {})
            if coverage:
                parts.append(f"**序列覆盖度**: {coverage.get('coverage_percent', 0):.1f}%\n")

        else:
            parts.append("无PDB结构数据\n")

        # 3. BLAST results
        parts.append("\n### 相似蛋白搜索结果\n")

        if blast_results and blast_results.get('results'):
            results = blast_results.get('results', [])
            parts.append(f"找到 {len(results)} 个相似蛋白\n\n")

            for idx, result in enumerate(results[:10], 1):
                identifier = result.get('pdb_id') or result.get('uniprot_id', 'N/A')
                name = result.get('title') or result.get('protein_name', 'N/A')
                identity = result.get('identity')

                identity_str = f"({identity:.1f}% 相似)" if identity else ""
                parts.append(f"{idx}. {identifier} - {name[:50]} {identity_str}\n")

        else:
            parts.append("无相似蛋白数据\n")

        # === 新增：PDB 统计摘要 ===
        if pdb_data and pdb_data.get('structures'):
            structures = pdb_data.get('structures', [])
            stats_section = build_pdb_statistics_section(structures, language='zh')
            if stats_section:
                parts.append("\n" + stats_section)

            # === 新增：PDB 实体详情 ===
            entity_section = build_entity_section_for_prompt(pdb_data, language='zh')
            if entity_section:
                parts.append("\n" + entity_section)

            # === 新增：配体/药物结合信息 ===
            ligand_section = build_ligand_section_for_prompt(pdb_data, language='zh')
            if ligand_section:
                parts.append("\n" + ligand_section)

            # === 新增：文献完整摘要（给 AI 总结，不要复制原文）===
            all_articles = []
            for struct in structures:
                citations = struct.get('citations', [])
                for cite in citations:
                    if cite.get('pubmed_id'):
                        all_articles.append({
                            'pubmed_id': cite.get('pubmed_id'),
                            'title': cite.get('title', ''),
                            'journal': cite.get('journal', ''),
                            'year': cite.get('year', ''),
                            'authors': cite.get('authors', []),
                            'abstract': cite.get('abstract', ''),
                            'doi': cite.get('doi', '')
                        })

            if all_articles:
                literature_for_ai = extract_literature_for_ai(all_articles)
                literature_section = build_literature_section_for_prompt(literature_for_ai, language='zh')
                parts.append("\n" + literature_section)

        # === 新增：同源结构统计 ===
        homology_details = blast_results.get('homology_details', []) if blast_results else []
        if homology_details:
            homology_stats = extract_homology_statistics(homology_details)
            if homology_stats:
                homology_section = build_homology_section_for_prompt(homology_stats, language='zh')
                parts.append("\n" + homology_section)

        return "".join(parts)

    def _apply_template(
        self,
        template: str,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict
    ) -> str:
        """Apply data to custom template.

        The template is used as the base prompt structure/instructions,
        and the actual protein data is appended for the AI to analyze.
        """
        # First, do any placeholder replacement if needed
        prompt = template
        if '{outline}' in prompt:
            outline = self._generate_outline(uniprot_data, pdb_data, blast_results)
            prompt = prompt.replace('{outline}', outline)

        # Always append the actual protein data for AI to analyze
        # The template provides the report structure, but the data tells AI what to analyze
        data_section = self._generate_data_section(uniprot_data, pdb_data, blast_results)
        if data_section:
            prompt = prompt + "\n\n" + data_section

        return prompt

    def _generate_outline(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict
    ) -> str:
        """Generate data outline for template substitution."""
        lines = []

        if uniprot_data:
            lines.append(f"UniProt: {uniprot_data.get('uniprot_id', 'N/A')}")
            lines.append(f"Protein: {uniprot_data.get('protein_name', 'N/A')}")

        if pdb_data:
            structures = pdb_data.get('structures', [])
            lines.append(f"PDB structures: {len(structures)}")

        if blast_results:
            results = blast_results.get('results', [])
            lines.append(f"Similar proteins: {len(results)}")

        return "\n".join(lines)

    def _generate_data_section(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict
    ) -> str:
        """Generate the actual protein data section for AI analysis.

        数据结构（避免重复，节省 token）：
        1. 蛋白质基础信息
        2. PDB 结构总览（列表，不含重复详情）
        3. 实体信息汇总
        4. 配体/药物信息汇总
        5. 文献列表与摘要（统一在最后）
        6. BLAST 同源结构统计
        """
        sections = []

        # ==================== 1. 蛋白质基础信息 ====================
        if uniprot_data:
            sections.append("## 蛋白质基础信息\n")
            sections.append(f"- **UniProt ID**: {uniprot_data.get('uniprot_id', 'N/A')}")
            sections.append(f"- **蛋白名称**: {uniprot_data.get('protein_name', 'N/A')}")
            gene_names = uniprot_data.get('gene_names', [])
            if gene_names:
                sections.append(f"- **基因名称**: {', '.join(gene_names)}")
            sections.append(f"- **物种**: {uniprot_data.get('organism', 'N/A')}")
            seq_len = uniprot_data.get('sequence_length', 0)
            if seq_len:
                sections.append(f"- **序列长度**: {seq_len} aa")
            function = uniprot_data.get('function', '')
            if function:
                func_text = function[:1500] if len(function) > 1500 else function
                sections.append(f"- **功能描述**: {func_text}")
            sections.append("")

        # ==================== 2. PDB 结构总览 ====================
        if pdb_data:
            structures = pdb_data.get('structures', []) or []
            if structures:
                # PDB 统计摘要
                stats = extract_pdb_statistics(structures)
                sections.append("## PDB 结构总览\n")
                sections.append(f"- **结构总数**: {stats['total_structures']}")
                if stats['resolution_range']:
                    sections.append(f"- **分辨率范围**: {stats['resolution_range']} Å")
                    if stats['avg_resolution']:
                        sections.append(f"- **平均分辨率**: {stats['avg_resolution']} Å")
                if stats['method_distribution']:
                    methods_str = "; ".join([f"{k}: {v}" for k, v in stats['method_distribution'].items()])
                    sections.append(f"- **实验方法**: {methods_str}")
                sections.append("")

                # PDB 列表（简洁版，不重复详情）
                sections.append("### PDB 结构列表\n")
                sections.append("| PDB ID | 方法 | 分辨率(Å) | 沉积日期 | 标题 |")
                sections.append("|--------|------|------------|----------|------|")
                for struct in structures[:15]:  # 最多15个
                    pdb_id = struct.get('pdb_id', 'N/A')
                    method = struct.get('experimental_method', 'N/A')[:20]
                    resolution = struct.get('resolution', '')
                    deposition_date = struct.get('deposition_date', '')[:10] if struct.get('deposition_date') else ''
                    title = struct.get('title', 'N/A')
                    if title and len(title) > 40:
                        title = title[:40] + '...'
                    sections.append(f"| {pdb_id} | {method} | {resolution} | {deposition_date} | {title} |")
                sections.append("")

                # ==================== 3. 实体信息汇总 ====================
                entity_section = build_entity_section_for_prompt(pdb_data, language='zh')
                if entity_section and "暂无" not in entity_section:
                    sections.append(entity_section)

                # ==================== 4. 配体/药物信息汇总 ====================
                ligand_section = build_ligand_section_for_prompt(pdb_data, language='zh')
                if ligand_section and "暂无" not in ligand_section:
                    sections.append(ligand_section)

                # ==================== 5. 文献列表与摘要 ====================
                all_articles = []
                pdb_with_articles = {}  # 用于显示 PDB 与文献的关联
                for struct in structures:
                    pdb_id = struct.get('pdb_id', '')
                    citations = struct.get('citations', []) or []
                    for cite in citations:
                        if cite.get('pubmed_id'):
                            article = {
                                'pubmed_id': cite.get('pubmed_id'),
                                'title': cite.get('title', ''),
                                'journal': cite.get('journal', ''),
                                'year': cite.get('year', ''),
                                'authors': cite.get('authors', []),
                                'abstract': cite.get('abstract', ''),
                                'doi': cite.get('doi', ''),
                                'pdb_id': pdb_id  # 关联 PDB
                            }
                            all_articles.append(article)
                            if pdb_id not in pdb_with_articles:
                                pdb_with_articles[pdb_id] = []
                            pdb_with_articles[pdb_id].append(cite.get('pubmed_id'))

                if all_articles:
                    sections.append("## 文献列表与摘要\n")
                    sections.append(f"共 **{len(all_articles)}** 篇关联文献。\n")

                    # 按 PDB 分组显示文献关联（简洁列表）
                    if pdb_with_articles:
                        sections.append("### 文献-PDB 关联\n")
                        for pdb_id, pmids in list(pdb_with_articles.items())[:5]:
                            pmid_str = ", ".join([f"[{p}](https://pubmed.ncbi.nlm.nih.gov/{p}/)" for p in pmids[:3]])
                            if len(pmids) > 3:
                                pmid_str += f" 等{len(pmids)}篇"
                            sections.append(f"- **{pdb_id}**: {pmid_str}")
                        sections.append("")

                    # 完整文献摘要（给 AI 分析用，不要复制）
                    literature_for_ai = extract_literature_for_ai(all_articles)
                    literature_section = build_literature_section_for_prompt(literature_for_ai, language='zh')
                    sections.append(literature_section)
            else:
                sections.append("## PDB 结构数据\n暂无 PDB 结构数据\n")

        # ==================== 6. BLAST 同源结构统计 ====================
        homology_details = blast_results.get('homology_details', []) if blast_results else []
        if homology_details:
            homology_stats = extract_homology_statistics(homology_details)
            if homology_stats and homology_stats.get('total_homologs', 0) > 0:
                homology_section = build_homology_section_for_prompt(homology_stats, language='zh')
                sections.append(homology_section)

                # 简洁的 BLAST 结果列表
                results = blast_results.get('results', []) or []
                if results:
                    sections.append("### BLAST 搜索结果（Top 10）\n")
                    sections.append("| 排名 | PDB ID | 相似度 | 方法 | 分辨率 | 来源 |")
                    sections.append("|------|--------|--------|------|--------|------|")
                    for idx, result in enumerate(results[:10], 1):
                        pdb_id = result.get('pdb_id', 'N/A')
                        identity = result.get('identity', 0)
                        method = result.get('experimental_method', 'N/A')[:15]
                        resolution = result.get('resolution', '')
                        source = result.get('source_uniprot_id', result.get('uniprot_id', 'N/A'))[:15]
                        sections.append(f"| {idx} | {pdb_id} | {identity}% | {method} | {resolution} | {source} |")
                    sections.append("")

        return "\n".join(sections)


def get_ai_client_wrapper(config: Dict[str, Any] = None) -> AIClientWrapper:
    """
    Factory function to create AI client wrapper.

    Args:
        config: Configuration dictionary

    Returns:
        AIClientWrapper instance
    """
    if config is None:
        config = {}

    return AIClientWrapper(
        provider=config.get('ai_provider'),
        model=config.get('ai_model'),
        api_key=config.get('ai_api_key'),
        base_url=config.get('ai_base_url'),
        max_tokens=config.get('ai_max_tokens', 6000),
        temperature=config.get('ai_temperature', 0.3)
    )
