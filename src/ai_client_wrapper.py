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
from src.database import get_default_report_template, get_default_prompt_template

logger = logging.getLogger(__name__)


class AIClientWrapper:
    """Wrapper for AI client operations."""

    # Model context windows (approximate, in tokens)
    MODEL_CONTEXT_WINDOWS = {
        'gpt-4o': 128000,
        'gpt-4o-mini': 128000,
        'gpt-4-turbo': 128000,
        'gpt-4': 8192,
        'gpt-3.5-turbo': 16385,
        'claude-3-opus': 200000,
        'claude-3-sonnet': 200000,
        'claude-3-haiku': 200000,
        'claude-2': 100000,
        'gemini-pro': 32768,
        'gemini-ultra': 32768,
    }

    # Reserve tokens for system/response overhead
    CONTEXT_RESERVE = 4000

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
        self.provider = provider if provider is not None else getattr(config, 'AI_PROVIDER', 'openai')
        self.model = model if model is not None else getattr(config, 'AI_MODEL', 'gpt-4o')
        self.api_key = api_key if api_key is not None else getattr(config, 'AI_API_KEY', '')
        self.base_url = base_url if base_url is not None else getattr(config, 'AI_BASE_URL', '')
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
        config: Dict[str, Any] = None,
        experimental_method: str = None
    ) -> str:
        """
        Build analysis prompt from protein data using two-stage generation.

        Stage 1: Generate statistical summary using prompt template
        Stage 2: Assemble final prompt (statistical summary + data + report template)

        This replaces the previous 3-part structure (variable_prompt + data + template)
        with a two-stage approach that first generates a summary, then uses it
        in the final report generation.

        Args:
            uniprot_data: UniProt protein data
            pdb_data: PDB structure data
            blast_results: BLAST search results
            custom_template: Custom prompt template (used as Part 3)
            language: Language code ('zh' for Chinese, 'en' for English)
            config: Configuration dictionary
            experimental_method: Experimental method for template selection (deprecated)

        Returns:
            Formatted prompt string for final report generation
        """
        # Detect homology mode first
        homology_info = self._detect_homology_mode(uniprot_data, pdb_data, blast_results)

        # Stage 1: Variable-built prompt with instructions
        variable_prompt = self._build_variable_prompt(
            uniprot_data, pdb_data, blast_results, homology_info, language
        )

        # Stage 2: Data section (includes PDB overview, entities, ligands, literature)
        data_section = self._generate_data_section(
            uniprot_data, pdb_data, blast_results, homology_info, language
        )

        # Stage 3: Report template (output format)
        if custom_template:
            template_section = self._apply_template_variables(
                custom_template, uniprot_data, pdb_data, blast_results, homology_info, language
            )
        else:
            template_section = self._get_default_report_template(language)

        # Assemble: variable_prompt + data + template (Stage 2 uses statistical summary)
        return f"{variable_prompt}\n\n{data_section}\n\n{template_section}"

    def build_analysis_prompt_with_summary(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        statistical_summary: str,
        custom_template: str = None,
        language: str = 'zh',
        config: Dict[str, Any] = None
    ) -> str:
        """
        Build analysis prompt with pre-generated statistical summary (two-stage).

        Stage 1 (already done): Generate statistical summary
        Stage 2: Assemble final prompt using the summary

        Args:
            uniprot_data: UniProt protein data
            pdb_data: PDB structure data
            blast_results: BLAST search results
            statistical_summary: Pre-generated statistical summary from Stage 1
            custom_template: Custom report template
            language: Language code
            config: Configuration dictionary

        Returns:
            Formatted prompt string for final report generation
        """
        # Detect homology mode
        homology_info = self._detect_homology_mode(uniprot_data, pdb_data, blast_results)

        # Part 1: Variable-built prompt with summary included
        variable_prompt = self._build_variable_prompt_with_summary(
            uniprot_data, pdb_data, blast_results, homology_info, statistical_summary, language
        )

        # Part 2: Current data section
        data_section = self._generate_data_section(
            uniprot_data, pdb_data, blast_results, homology_info, language
        )

        # Part 3: Report template
        if custom_template:
            template_section = self._apply_template_variables(
                custom_template, uniprot_data, pdb_data, blast_results, homology_info, language
            )
        else:
            template_section = self._get_default_report_template(language)

        return f"{variable_prompt}\n\n{data_section}\n\n{template_section}"

    def _build_variable_prompt_with_summary(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any],
        statistical_summary: str,
        language: str = 'zh'
    ) -> str:
        """
        Build Part 1 with pre-generated statistical summary included.

        This includes the summary from Stage 1 in the prompt for Stage 2.
        """
        if language == 'zh':
            return self._build_variable_prompt_chinese_with_summary(
                uniprot_data, pdb_data, blast_results, homology_info, statistical_summary
            )
        else:
            return self._build_variable_prompt_english_with_summary(
                uniprot_data, pdb_data, blast_results, homology_info, statistical_summary
            )

    def _build_variable_prompt_chinese_with_summary(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any],
        statistical_summary: str
    ) -> str:
        """Build Chinese variable prompt with statistical summary."""
        parts = []

        # Expert role
        parts.append("""# 结构生物学研究可行性分析提示

## 专家角色
你是一位资深的**结构生物学家**和**药物发现研究员**，在蛋白质结构解析、功能研究和药物靶点开发方面拥有15年以上的经验。请基于以下提供的蛋白质信息、现有结构数据和相关文献，撰写一份详细的**综合分析报告**。""")

        # Mode-specific introduction
        is_homolog = homology_info.get('is_homolog_mode', False)
        homolog_uniprot_id = homology_info.get('homolog_uniprot_id')

        protein_name = uniprot_data.get('protein_name', '目标蛋白质') if uniprot_data else '目标蛋白质'

        if is_homolog and homolog_uniprot_id:
            parts.append(f"""
**注意**：以下分析基于**同源蛋白质{homolog_uniprot_id}**的PDB结构，用于推断**{protein_name}**的结构研究可行性。这些结构虽然不是{pdb_data.get('structures', [{}])[0].get('pdb_id', '直接结构')}的直接结构，但提供了重要的同源结构信息。
""")
        else:
            parts.append(f"""
**分析目标**：蛋白质{protein_name}的结构生物学研究可行性分析。
""")

        # Report requirements
        parts.append("""
## 报告要求：
1. **专业性**：使用结构生物学和生物化学的专业术语，体现领域专业知识
2. **全面性**：涵盖技术可行性、科学价值、实验策略、风险分析等所有关键方面
3. **实用性**：提供具体的实验建议和可操作的备选方案
4. **结构清晰**：按照学术报告的格式组织内容，逻辑严谨
5. **数据驱动**：基于提供的数据进行分析，避免主观臆断
6. **完整性**：生成完整的报告，不要分段或省略
""")

        # Data availability notes
        structures = pdb_data.get('structures', []) if pdb_data else []
        has_pdb_structures = len(structures) > 0
        has_homology = len(homology_info.get('homology_details', [])) > 0

        parts.append(f"""
## 数据可用性说明：
- **直接PDB结构**: {'有' if has_pdb_structures else '无'} ({len(structures)}个)
- **同源结构信息**: {'有' if has_homology else '无'}
""")

        if is_homolog and homology_info.get('homology_stats'):
            stats = homology_info['homology_stats']
            parts.append(f"""
**同源结构统计**：
- 总同源结构数: {stats.get('total_homologs', 0)}
- 不同PDB结构数: {stats.get('unique_pdb_count', 0)}
- 最佳序列一致性: {stats.get('best_identity', 0)}% (PDB: {stats.get('best_pdb', 'N/A')})
- 最佳覆盖率: {stats.get('best_coverage', 0)}%
""")

        # Include statistical summary from Stage 1
        if statistical_summary:
            parts.append(f"""
## 统计摘要（第一阶段生成）

{statistical_summary}
""")

        return "".join(parts)

    def _build_variable_prompt_english_with_summary(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any],
        statistical_summary: str
    ) -> str:
        """Build English variable prompt with statistical summary."""
        parts = []

        protein_name = uniprot_data.get('protein_name', 'Target Protein') if uniprot_data else 'Target Protein'
        is_homolog = homology_info.get('is_homolog_mode', False)
        homolog_uniprot_id = homology_info.get('homolog_uniprot_id')

        parts.append(f"""# Structural Biology Research Feasibility Analysis Prompt

## Expert Role
You are a senior **structural biologist** and **drug discovery researcher** with over 15 years of experience in protein structure determination, functional research, and drug target development. Please generate a comprehensive analysis report based on the provided protein information, existing structural data, and relevant literature.

## Analysis Target: {protein_name}
""")

        if is_homolog and homolog_uniprot_id:
            parts.append(f"""
**Note**: This analysis is based on PDB structures of **homologous protein {homolog_uniprot_id}** to infer the structural research feasibility of **{protein_name}**. These structures are not direct structures of {protein_name} but provide important homologous structural information.
""")

        parts.append("""
## Report Requirements:
1. **Professionalism**: Use structural biology and biochemistry terminology
2. **Comprehensiveness**: Cover technical feasibility, scientific value, experimental strategies, and risk analysis
3. **Practicality**: Provide specific experimental recommendations and actionable alternatives
4. **Clarity**: Organize content in academic report format with rigorous logic
5. **Data-driven**: Base analysis on provided data, avoid speculation
6. **Completeness**: Generate a complete report without truncation or omission
""")

        # Include statistical summary from Stage 1
        if statistical_summary:
            parts.append(f"""
## Statistical Summary (Generated in Stage 1)

{statistical_summary}
""")

        return "".join(parts)

    def _detect_homology_mode(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict
    ) -> Dict[str, Any]:
        """
        Detect homology mode and extract relevant information.

        Returns a dict with:
        - is_homolog_mode: bool
        - homolog_uniprot_id: str or None
        - homology_details: list
        - homology_stats: dict or None
        """
        from src.prompt_helpers import extract_homology_statistics

        result = {
            'is_homolog_mode': False,
            'homolog_uniprot_id': None,
            'homology_details': [],
            'homology_stats': None
        }

        # Check for homolog_uniprotid in blast_results
        if blast_results:
            homolog_uniprot_id = blast_results.get('homolog_uniprotid')
            if not homolog_uniprot_id:
                homolog_uniprot_id = blast_results.get('sourceUniProtId')

            if homolog_uniprot_id and homolog_uniprot_id.strip():
                result['is_homolog_mode'] = True
                result['homolog_uniprot_id'] = homolog_uniprot_id.strip()
                logger.info(f"Detected homolog mode: {homolog_uniprot_id}")

        # Extract homology_details
        if blast_results:
            homology_details = blast_results.get('homology_details', [])
            if homology_details:
                result['homology_details'] = homology_details
                result['homology_stats'] = extract_homology_statistics(homology_details)

        return result

    def _build_variable_prompt(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any],
        language: str = 'zh'
    ) -> str:
        """
        Build Part 1: Variable-built prompt with instructions based on mode and data.

        This contains:
        - Expert role definition
        - Report requirements
        - Mode-specific instructions (homolog vs direct)
        - Data availability notes
        """
        if language == 'zh':
            return self._build_variable_prompt_chinese(uniprot_data, pdb_data, blast_results, homology_info)
        else:
            return self._build_variable_prompt_english(uniprot_data, pdb_data, blast_results, homology_info)

    def _build_variable_prompt_chinese(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any]
    ) -> str:
        """Build Chinese variable prompt (Part 1)."""
        parts = []

        # Expert role
        parts.append("""# 结构生物学研究可行性分析提示

## 专家角色
你是一位资深的**结构生物学家**和**药物发现研究员**，在蛋白质结构解析、功能研究和药物靶点开发方面拥有15年以上的经验。请基于以下提供的蛋白质信息、现有结构数据和相关文献，撰写一份详细的**综合分析报告**。""")

        # Mode-specific introduction
        is_homolog = homology_info.get('is_homolog_mode', False)
        homolog_uniprot_id = homology_info.get('homolog_uniprot_id')

        protein_name = uniprot_data.get('protein_name', '目标蛋白质') if uniprot_data else '目标蛋白质'

        if is_homolog and homolog_uniprot_id:
            parts.append(f"""
**注意**：以下分析基于**同源蛋白质{homolog_uniprot_id}**的PDB结构，用于推断**{protein_name}**的结构研究可行性。这些结构虽然不是{pdb_data.get('structures', [{}])[0].get('pdb_id', '直接结构')}的直接结构，但提供了重要的同源结构信息。
""")
        else:
            parts.append(f"""
**分析目标**：蛋白质{protein_name}的结构生物学研究可行性分析。
""")

        # Report requirements
        parts.append("""
## 报告要求：
1. **专业性**：使用结构生物学和生物化学的专业术语，体现领域专业知识
2. **全面性**：涵盖技术可行性、科学价值、实验策略、风险分析等所有关键方面
3. **实用性**：提供具体的实验建议和可操作的备选方案
4. **结构清晰**：按照学术报告的格式组织内容，逻辑严谨
5. **数据驱动**：基于提供的数据进行分析，避免主观臆断
""")

        # Data availability notes
        structures = pdb_data.get('structures', []) if pdb_data else []
        has_pdb_structures = len(structures) > 0
        has_homology = len(homology_info.get('homology_details', [])) > 0

        parts.append(f"""
## 数据可用性说明：
- **直接PDB结构**: {'有' if has_pdb_structures else '无'} ({len(structures)}个)
- **同源结构信息**: {'有' if has_homology else '无'}
""")

        if is_homolog and homology_info.get('homology_stats'):
            stats = homology_info['homology_stats']
            parts.append(f"""
**同源结构统计**：
- 总同源结构数: {stats.get('total_homologs', 0)}
- 不同PDB结构数: {stats.get('unique_pdb_count', 0)}
- 最佳序列一致性: {stats.get('best_identity', 0)}% (PDB: {stats.get('best_pdb', 'N/A')})
- 最佳覆盖率: {stats.get('best_coverage', 0)}%
""")

        return "".join(parts)

    def _build_variable_prompt_english(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any]
    ) -> str:
        """Build English variable prompt (Part 1)."""
        parts = []

        protein_name = uniprot_data.get('protein_name', 'Target Protein') if uniprot_data else 'Target Protein'
        is_homolog = homology_info.get('is_homolog_mode', False)
        homolog_uniprot_id = homology_info.get('homolog_uniprot_id')

        parts.append(f"""# Structural Biology Research Feasibility Analysis Prompt

## Expert Role
You are a senior **structural biologist** and **drug discovery researcher** with over 15 years of experience in protein structure determination, functional research, and drug target development. Please generate a comprehensive analysis report based on the provided protein information, existing structural data, and relevant literature.

## Analysis Target: {protein_name}
""")

        if is_homolog and homolog_uniprot_id:
            parts.append(f"""
**Note**: This analysis is based on PDB structures of **homologous protein {homolog_uniprot_id}** to infer the structural research feasibility of **{protein_name}**. These structures are not direct structures of {protein_name} but provide important homologous structural information.
""")

        parts.append("""
## Report Requirements:
1. **Professionalism**: Use structural biology and biochemistry terminology
2. **Comprehensiveness**: Cover technical feasibility, scientific value, experimental strategies, and risk analysis
3. **Practicality**: Provide specific experimental recommendations and actionable alternatives
4. **Clarity**: Organize content in academic report format with rigorous logic
5. **Data-driven**: Base analysis on provided data, avoid speculation
""")

        return "".join(parts)

    def _apply_template_variables(
        self,
        template: str,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        homology_info: Dict[str, Any],
        language: str = 'zh'
    ) -> str:
        """
        Apply template with variable substitution.

        Replaces bracket-style variables like [PDB_ENTITIES], [HOMOLOGY_STATS], etc.
        with actual data.
        """
        prompt = template

        # Replace simple variables
        simple_vars = {
            '[蛋白质名称]': uniprot_data.get('protein_name', 'N/A') if uniprot_data else 'N/A',
            '[Protein Name]': uniprot_data.get('protein_name', 'N/A') if uniprot_data else 'N/A',
            '[UniProt ID]': uniprot_data.get('uniprot_id', 'N/A') if uniprot_data else 'N/A',
            '[基因名称]': ', '.join(uniprot_data.get('gene_names', [])) if uniprot_data else 'N/A',
            '[Gene Name]': ', '.join(uniprot_data.get('gene_names', [])) if uniprot_data else 'N/A',
            '[物种名称]': uniprot_data.get('organism', 'N/A') if uniprot_data else 'N/A',
            '[Organism]': uniprot_data.get('organism', 'N/A') if uniprot_data else 'N/A',
            '[序列长度]': str(uniprot_data.get('sequence_length', 'N/A')) if uniprot_data else 'N/A',
            '[Sequence Length]': str(uniprot_data.get('sequence_length', 'N/A')) if uniprot_data else 'N/A',
            '[PDB结构总数]': str(len(pdb_data.get('structures', []))) if pdb_data else '0',
            '[Total PDB Structures]': str(len(pdb_data.get('structures', []))) if pdb_data else '0',
        }

        for var, value in simple_vars.items():
            prompt = prompt.replace(var, value)

        # Replace complex section variables
        if '[PDB_ENTITIES]' in prompt or '[PDB_LIGANDS]' in prompt:
            if language == 'zh':
                entity_section = build_entity_section_for_prompt(pdb_data, 'zh') if pdb_data else ''
                ligand_section = build_ligand_section_for_prompt(pdb_data, 'zh') if pdb_data else ''
            else:
                entity_section = build_entity_section_for_prompt(pdb_data, 'en') if pdb_data else ''
                ligand_section = build_ligand_section_for_prompt(pdb_data, 'en') if pdb_data else ''

            prompt = prompt.replace('[PDB_ENTITIES]', entity_section)
            prompt = prompt.replace('[PDB_LIGANDS]', ligand_section)

        if '[PDB_STATISTICS]' in prompt:
            structures = pdb_data.get('structures', []) if pdb_data else []
            if language == 'zh':
                stats_section = build_pdb_statistics_section(structures, 'zh')
            else:
                stats_section = build_pdb_statistics_section(structures, 'en')
            prompt = prompt.replace('[PDB_STATISTICS]', stats_section)

        if '[HOMOLOGY_STATS]' in prompt:
            homology_stats = homology_info.get('homology_stats')
            if homology_stats:
                if language == 'zh':
                    homology_section = build_homology_section_for_prompt(homology_stats, 'zh')
                else:
                    homology_section = build_homology_section_for_prompt(homology_stats, 'en')
                prompt = prompt.replace('[HOMOLOGY_STATS]', homology_section)
            else:
                prompt = prompt.replace('[HOMOLOGY_STATS]', '暂无同源结构统计信息')

        if '[LITERATURE_STATS]' in prompt or '[LITERATURE_FOR_AI]' in prompt:
            # Extract literature from PDB citations
            literature = []
            if pdb_data:
                for struct in pdb_data.get('structures', []):
                    citations = struct.get('citations', []) or []
                    for cite in citations:
                        if cite.get('pubmed_id') or cite.get('title'):
                            literature.append(cite)
                literature = extract_literature_for_ai(literature)

            if language == 'zh':
                lit_section = build_literature_section_for_prompt(literature, 'zh')
            else:
                lit_section = build_literature_section_for_prompt(literature, 'en')

            prompt = prompt.replace('[LITERATURE_STATS]', f"共{len(literature)}篇相关文献")
            prompt = prompt.replace('[LITERATURE_FOR_AI]', lit_section)

        # Replace literature-centric PDB data [LITERATURE_PDB_GROUPED]
        if '[LITERATURE_PDB_GROUPED]' in prompt:
            grouped_section = self._build_literature_pdb_grouped_section(pdb_data, language)
            prompt = prompt.replace('[LITERATURE_PDB_GROUPED]', grouped_section)

        # Handle {outline} placeholder (legacy compatibility)
        if '{outline}' in prompt:
            outline = self._generate_outline(uniprot_data, pdb_data, blast_results)
            prompt = prompt.replace('{outline}', outline)

        return prompt

    def _build_literature_pdb_grouped_section(
        self,
        pdb_data: Dict,
        language: str = 'zh'
    ) -> str:
        """
        Build literature-centric section with PDB structures grouped by literature.

        Each literature entry includes:
        - Literature info (title, authors, journal, year, abstract)
        - Associated PDB structures

        Args:
            pdb_data: PDB data dict with 'structures' list
            language: Language code

        Returns:
            Formatted string with literature and their PDB structures
        """
        if not pdb_data:
            return "暂无PDB结构数据"

        structures = pdb_data.get('structures', [])
        if not structures:
            return "暂无PDB结构数据"

        # Group PDB structures by literature (using pdb_id as grouping key initially,
        # but we'll restructure to group by literature)
        literature_pdb_map = self._group_pdbs_by_literature(structures)

        if not literature_pdb_map:
            return "暂无文献关联的PDB结构数据"

        sections = []
        if language == 'zh':
            sections.append("## 文献-PDB结构关联数据\n")
            sections.append(f"共 {len(literature_pdb_map)} 篇文献涉及PDB结构解析\n")
        else:
            sections.append("## Literature-PDB Structure Association Data\n")
            sections.append(f"Total of {len(literature_pdb_map)} literature entries with PDB structures\n")

        for idx, (lit_info, pdbs) in enumerate(literature_pdb_map, 1):
            # Literature header
            pmid = lit_info.get('pubmed_id', 'N/A')
            title = lit_info.get('title', '无标题')
            journal = lit_info.get('journal', '未知期刊')
            year = lit_info.get('year', 'N/A')
            abstract = lit_info.get('abstract', '')
            authors = lit_info.get('authors', [])

            author_str = ', '.join(authors[:5]) if len(authors) > 5 else ', '.join(authors)
            if len(authors) > 5:
                author_str += ' et al.'

            if language == 'zh':
                sections.append(f"\n### 文献 {idx}: PMID {pmid}\n")
                sections.append(f"**标题**: {title}\n")
                sections.append(f"**期刊**: {journal} ({year})\n")
                sections.append(f"**作者**: {author_str}\n")
                if abstract:
                    abstract_clean = abstract.replace('\n', ' ').strip()
                    sections.append(f"**摘要**: {abstract_clean}\n")
            else:
                sections.append(f"\n### Literature {idx}: PMID {pmid}\n")
                sections.append(f"**Title**: {title}\n")
                sections.append(f"**Journal**: {journal} ({year})\n")
                sections.append(f"**Authors**: {author_str}\n")
                if abstract:
                    abstract_clean = abstract.replace('\n', ' ').strip()
                    sections.append(f"**Abstract**: {abstract_clean}\n")

            # Associated PDB structures
            sections.append(f"\n**该文献解析的PDB结构** ({len(pdbs)}个):\n")
            sections.append("| PDB ID | 方法 | 分辨率(Å) | 沉积日期 | 标题 |")
            sections.append("|--------|------|------------|----------|------|")
            for struct in pdbs:
                pdb_id = struct.get('pdb_id', 'N/A')
                method = struct.get('experimental_method', 'N/A')[:20]
                resolution = struct.get('resolution', '')
                deposition_date = struct.get('deposition_date', '')[:10] if struct.get('deposition_date') else ''
                title_str = struct.get('title', 'N/A')[:40]
                sections.append(f"| {pdb_id} | {method} | {resolution} | {deposition_date} | {title_str} |")

            # Entity details for this structure
            for struct in pdbs:
                pdb_id = struct.get('pdb_id', 'N/A')
                entity_list = struct.get('entity_list', [])
                if entity_list:
                    if language == 'zh':
                        sections.append(f"\n**{pdb_id} 实体详情**:\n")
                    else:
                        sections.append(f"\n**{pdb_id} Entity Details**:\n")
                    for ent in entity_list[:3]:  # Show first 3 entities
                        ent_id = ent.get('entity_id', '')
                        chain = ent.get('chain', '')
                        polymer_type = ent.get('polymer_type', '')
                        length = ent.get('length', 0)
                        mol_name = ent.get('molecule_name', '')
                        gene = ent.get('gene_name', '')
                        name_str = f"{mol_name}" if mol_name else polymer_type
                        if language == 'zh':
                            gene_str = f", 基因: {gene}" if gene else ""
                            sections.append(f"- 实体 {ent_id} (链 {chain}): {name_str}{gene_str}, 长度 {length}\n")
                        else:
                            gene_str = f", Gene: {gene}" if gene else ""
                            sections.append(f"- Entity {ent_id} (Chain {chain}): {name_str}{gene_str}, Length {length}\n")

        return "".join(sections)

    def _group_pdbs_by_literature(self, structures: List[Dict]) -> Dict[Dict, List[Dict]]:
        """
        Group PDB structures by literature.

        Returns a dict mapping literature info -> list of PDB structures.

        Args:
            structures: List of PDB structure dicts

        Returns:
            Dict mapping lit_info dict -> list of PDB structures
        """
        from src.prompt_helpers import extract_literature_for_ai

        lit_to_pdbs = {}

        for struct in structures:
            pdb_id = struct.get('pdb_id', '')
            citations = struct.get('citations', []) or []

            if not citations:
                # Structure with no literature - create a placeholder with string key
                lit_key = f'no_literature_{pdb_id}'
                lit_info = {'pubmed_id': '', 'title': f'无文献 - {pdb_id}', 'journal': '', 'year': '', 'authors': [], 'abstract': ''}
                if lit_key not in lit_to_pdbs:
                    lit_to_pdbs[lit_key] = {'lit_info': lit_info, 'pdbs': []}
                lit_to_pdbs[lit_key]['pdbs'].append(struct)
                continue

            for cite in citations:
                pmid = cite.get('pubmed_id', '')
                title = cite.get('title', '')

                # Skip if neither pmid nor title
                if not pmid and not title:
                    continue

                # Create a key for this literature
                lit_info = {
                    'pubmed_id': pmid or '',
                    'title': title or '无标题',
                    'journal': cite.get('journal', ''),
                    'year': cite.get('year', ''),
                    'authors': cite.get('authors', []),
                    'abstract': cite.get('abstract', '')
                }

                # Use pmid as key if available, otherwise use title
                key = pmid if pmid else title.lower()

                if key not in lit_to_pdbs:
                    lit_to_pdbs[key] = {'lit_info': lit_info, 'pdbs': []}

                lit_to_pdbs[key]['pdbs'].append(struct)

        # Convert to list of tuples (lit_info, pdbs)
        result = []
        for key, data in lit_to_pdbs.items():
            result.append((data['lit_info'], data['pdbs']))

        return result

    def _get_default_report_template(self, language: str = 'zh') -> str:
        """
        Get the default report template (Part 3).

        First tries to fetch from database, falls back to hardcoded content.
        """
        # Try to get from database
        db_template = get_default_report_template()
        if db_template:
            if language == 'zh':
                return db_template.content
            else:
                return db_template.content_en or db_template.content

        # Fallback to hardcoded content
        if language == 'zh':
            return """---

## 报告结构要求

请按以下结构生成报告：

### 摘要
（基于提供的数据，简要概述：蛋白质身份、关键结构特征，主要研究发现。200字左右）

### 第一部分：蛋白质基础信息
- 基本属性（名称、基因、物种、序列长度）
- 功能描述
- 结构域组成

### 第二部分：PDB结构数据总览
- 结构可用性概述
- 实验方法统计
- 分辨率范围

### 第三部分：PDB结构综合分析
- 直接结构分析（如有）
- 同源结构分析（如有同源结构）

### 第四部分：实验可行性评估
- 技术路线建议
- 风险与备选方案

### 第五部分：结论与建议
- 总结研究发现
- 提出后续建议"""
        else:
            return """---

## Report Structure Requirements

Please generate the report following this structure:

### Abstract
(Based on provided data, briefly summarize: protein identity, key structural features, main findings. ~200 words)

### Part 1: Protein Basic Information
- Basic attributes (name, gene, organism, sequence length)
- Functional description
- Domain composition

### Part 2: PDB Structure Overview
- Structure availability overview
- Experimental method statistics
- Resolution range

### Part 3: Comprehensive PDB Structure Analysis
- Direct structure analysis (if available)
- Homologous structure analysis (if homology data exists)

### Part 4: Experimental Feasibility Assessment
- Technical approach recommendations
- Risks and alternatives

### Part 5: Conclusions and Recommendations
- Summary of research findings
- Recommendations for follow-up"""

    def _get_default_prompt_template(self, language: str = 'zh') -> str:
        """
        Get the default prompt template for generating statistical summary (Stage 1).

        Returns the prompt template used to generate a statistical summary of the protein data.
        """
        # Try to get from database
        db_template = get_default_prompt_template()
        if db_template:
            if language == 'zh':
                return db_template.content
            else:
                return db_template.content_en or db_template.content

        # Fallback to hardcoded content
        if language == 'zh':
            return """# 蛋白质数据结构摘要生成器

你是一个专业的蛋白质结构生物信息学专家。请根据以下数据生成一份结构化的统计摘要。

## 蛋白质信息
- 名称: {protein_name}
- UniProt: {uniprot_id}
- 基因: {gene_name}
- 物种: {organism}
- 序列长度: {length} aa

## PDB结构统计
{total_structures} 个结构
分辨率范围: {resolution_range}
实验方法分布: {method_distribution}

## 同源结构统计（如有）
{homology_stats}

## 文献统计
{literature_count} 篇相关文献

请生成简洁的统计摘要（300-500字），包含：
1. 蛋白质关键特征概述
2. PDB结构质量评估
3. 同源结构覆盖情况（如有）
4. 主要研究发现"""
        else:
            return """# Protein Data Summary Generator

You are a professional structural bioinformatics expert. Generate a structured statistical summary based on the following data.

## Protein Information
- Name: {protein_name}
- UniProt: {uniprot_id}
- Gene: {gene_name}
- Organism: {organism}
- Sequence Length: {length} aa

## PDB Structure Statistics
{total_structures} structures
Resolution Range: {resolution_range}
Experimental Method Distribution: {method_distribution}

## Homology Structure Statistics (if available)
{homology_stats}

## Literature Statistics
{literature_count} related papers

Please generate a concise statistical summary (300-500 words), containing:
1. Key protein characteristics overview
2. PDB structure quality assessment
3. Homology structure coverage (if available)
4. Main research findings"""

    def _format_prompt_template(self, template: str, uniprot_data: Dict, pdb_data: Dict,
                                 blast_results: Dict, homology_info: Dict[str, Any],
                                 language: str = 'zh') -> str:
        """
        Format the prompt template with actual data values.

        Replaces {variable} placeholders in the template with actual data.
        """
        prompt = template

        # Extract statistics for substitution
        structures = pdb_data.get('structures', []) if pdb_data else []
        stats = extract_pdb_statistics(structures) if structures else {}

        homology_stats = homology_info.get('homology_stats') if homology_info else None

        # Count literature
        literature_count = 0
        if pdb_data:
            for struct in pdb_data.get('structures', []):
                citations = struct.get('citations', []) or []
                literature_count += len([c for c in citations if c.get('pubmed_id') or c.get('title')])

        # Simple string substitutions
        replacements = {
            '{protein_name}': uniprot_data.get('protein_name', 'N/A') if uniprot_data else 'N/A',
            '{uniprot_id}': uniprot_data.get('uniprot_id', 'N/A') if uniprot_data else 'N/A',
            '{gene_name}': ', '.join(uniprot_data.get('gene_names', [])) if uniprot_data else 'N/A',
            '{organism}': uniprot_data.get('organism', 'N/A') if uniprot_data else 'N/A',
            '{length}': str(uniprot_data.get('sequence_length', 'N/A')) if uniprot_data else 'N/A',
            '{total_structures}': str(stats.get('total_structures', 0)),
            '{resolution_range}': stats.get('resolution_range', 'N/A'),
            '{method_distribution}': '; '.join([f"{k}: {v}" for k, v in stats.get('method_distribution', {}).items()]) if stats.get('method_distribution') else 'N/A',
            '{homology_stats}': self._format_homology_stats(homology_stats, language) if homology_stats else '暂无同源结构信息',
            '{literature_count}': str(literature_count),
        }

        for var, value in replacements.items():
            prompt = prompt.replace(var, value)

        # Replace [LITERATURE_PDB_GROUPED] placeholder with literature-centric PDB data
        if '[LITERATURE_PDB_GROUPED]' in prompt:
            grouped_section = self._build_literature_pdb_grouped_section(pdb_data, language)
            prompt = prompt.replace('[LITERATURE_PDB_GROUPED]', grouped_section)

        return prompt

    def _format_homology_stats(self, homology_stats: Dict, language: str = 'zh') -> str:
        """Format homology statistics for template substitution."""
        if not homology_stats:
            return '暂无同源结构信息'

        lines = []
        if language == 'zh':
            lines.append(f"总同源结构数: {homology_stats.get('total_homologs', 0)}")
            lines.append(f"不同PDB结构数: {homology_stats.get('unique_pdb_count', 0)}")
            best_identity = homology_stats.get('best_identity', 0)
            best_pdb = homology_stats.get('best_pdb', 'N/A')
            best_coverage = homology_stats.get('best_coverage', 0)
            if best_identity:
                lines.append(f"最佳序列一致性: {best_identity}% (PDB: {best_pdb})")
            if best_coverage:
                lines.append(f"最佳覆盖率: {best_coverage}%")
        else:
            lines.append(f"Total homologs: {homology_stats.get('total_homologs', 0)}")
            lines.append(f"Unique PDB structures: {homology_stats.get('unique_pdb_count', 0)}")
            best_identity = homology_stats.get('best_identity', 0)
            best_pdb = homology_stats.get('best_pdb', 'N/A')
            best_coverage = homology_stats.get('best_coverage', 0)
            if best_identity:
                lines.append(f"Best sequence identity: {best_identity}% (PDB: {best_pdb})")
            if best_coverage:
                lines.append(f"Best coverage: {best_coverage}%")

        return '\n'.join(lines)

    def generate_statistical_summary(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        language: str = 'zh'
    ) -> Dict[str, Any]:
        """
        Stage 1: Generate statistical summary using the prompt template.

        This generates a concise statistical summary of the protein data,
        which is then used in Stage 2 to generate the final report.

        Returns:
            Dictionary with 'summary', 'model', 'success', and optionally 'error'
        """
        if not self.client:
            return {'error': 'AI client not initialized', 'success': False}

        # Detect homology mode
        homology_info = self._detect_homology_mode(uniprot_data, pdb_data, blast_results)

        # Get prompt template
        prompt_template = self._get_default_prompt_template(language)

        # Format template with actual data
        prompt = self._format_prompt_template(
            prompt_template, uniprot_data, pdb_data, blast_results, homology_info, language
        )

        # Add system message
        if language == 'zh':
            system_message = "你是一个专业的蛋白质结构生物信息学专家。请根据提供的数据生成准确的统计摘要。"
        else:
            system_message = "You are a professional structural bioinformatics expert. Generate an accurate statistical summary based on the provided data."

        # Run AI analysis
        result = self.analyze(prompt, system_message=system_message, max_tokens=2000)

        if result.get('success'):
            return {
                'summary': result.get('analysis', ''),
                'model': result.get('model', self.model),
                'success': True,
                'prompt': prompt
            }
        else:
            return {
                'error': result.get('error', 'Failed to generate statistical summary'),
                'success': False,
                'prompt': prompt
            }

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
                    parts.append(f"- Title: {title}\n")
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
                        mol_name = ent.get('molecule_name', '')
                        gene = ent.get('gene_name', '')
                        name_str = f"{mol_name}" if mol_name else polymer_type
                        gene_str = f", Gene: {gene}" if gene else ""
                        parts.append(f"  - Entity {ent_id} (Chain {chain}): {name_str}{gene_str}, Length {length}\n")

                # Citations with abstracts
                if citations:
                    for cite in citations[:2]:  # Show first 2 citations per structure
                        cite_title = cite.get('title', '')
                        journal = cite.get('journal', '')
                        year = cite.get('year', '')
                        pubmed_id = cite.get('pubmed_id', '')
                        abstract = cite.get('abstract', '')
                        if cite_title:
                            parts.append(f"  - Citation: \"{cite_title}\"")
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
                    # Include citations with PMID, OR with title (even without PMID)
                    if cite.get('pubmed_id') or cite.get('title'):
                        all_articles.append({
                            'pubmed_id': cite.get('pubmed_id') or '',
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
                    parts.append(f"- 标题: {title}\n")
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
                        mol_name = ent.get('molecule_name', '')
                        gene = ent.get('gene_name', '')
                        # 显示实体详情
                        name_str = f"{mol_name}" if mol_name else polymer_type
                        gene_str = f", 基因: {gene}" if gene else ""
                        parts.append(f"  - 实体 {ent_id} (链 {chain}): {name_str}{gene_str}, 长度 {length}\n")

                # 文献引用（含摘要）
                if citations:
                    for cite in citations[:2]:  # 每个结构显示前2篇文献
                        cite_title = cite.get('title', '')
                        journal = cite.get('journal', '')
                        year = cite.get('year', '')
                        pubmed_id = cite.get('pubmed_id', '')
                        abstract = cite.get('abstract', '')
                        if cite_title:
                            parts.append(f"  - 文献: \"{cite_title}\"")
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
                    # Include citations with PMID, OR with title (even without PMID)
                    if cite.get('pubmed_id') or cite.get('title'):
                        all_articles.append({
                            'pubmed_id': cite.get('pubmed_id') or '',
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
        """Apply data to custom template (legacy method).

        Now uses 3-part structure:
        1. Variable-built prompt
        2. Data section
        3. Template
        """
        # Detect homology mode
        homology_info = self._detect_homology_mode(uniprot_data, pdb_data, blast_results)

        # Part 1: Variable-built prompt
        variable_prompt = self._build_variable_prompt(
            uniprot_data, pdb_data, blast_results, homology_info, language='zh'
        )

        # Part 2: Data section
        data_section = self._generate_data_section(
            uniprot_data, pdb_data, blast_results, homology_info, language='zh'
        )

        # Part 3: Template (with variable substitution)
        template_section = self._apply_template_variables(
            template, uniprot_data, pdb_data, blast_results, homology_info, language='zh'
        )

        return f"{variable_prompt}\n\n{data_section}\n\n{template_section}"

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
        blast_results: Dict,
        homology_info: Dict[str, Any] = None,
        language: str = 'zh'
    ) -> str:
        """Generate the actual protein data section for AI analysis (Part 2).

        数据结构（避免重复，节省 token）：
        1. 蛋白质基础信息
        2. PDB 结构总览（列表，不含重复详情）
        3. 实体信息汇总
        4. 配体/药物信息汇总
        5. 文献列表与摘要（统一在最后）
        6. BLAST 同源结构统计
        """
        if homology_info is None:
            homology_info = {}

        sections = []
        is_homolog_mode = homology_info.get('is_homolog_mode', False)
        homolog_uniprot_id = homology_info.get('homolog_uniprot_id')

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

                # ==================== 以文献为中心的数据结构 ====================
                # 每个文献条目包含：文献信息 + 该文献的PDB结构 + 实体详情
                literature_pdb_map = self._group_pdbs_by_literature(structures)

                if literature_pdb_map:
                    if language == 'zh':
                        sections.append("## 文献-PDB结构关联数据\n")
                        sections.append(f"共 {len(literature_pdb_map)} 篇文献涉及PDB结构解析\n\n")
                    else:
                        sections.append("## Literature-PDB Structure Association Data\n")
                        sections.append(f"Total of {len(literature_pdb_map)} literature entries with PDB structures\n\n")

                    for idx, (lit_info, pdbs) in enumerate(literature_pdb_map, 1):
                        # 文献信息
                        pmid = lit_info.get('pubmed_id', 'N/A')
                        title = lit_info.get('title', '无标题')
                        journal = lit_info.get('journal', '未知期刊')
                        year = lit_info.get('year', 'N/A')
                        abstract = lit_info.get('abstract', '')
                        authors = lit_info.get('authors', [])

                        author_str = ', '.join(authors[:5]) if len(authors) > 5 else ', '.join(authors)
                        if len(authors) > 5:
                            author_str += ' et al.'

                        if language == 'zh':
                            sections.append(f"### 文献 {idx}: PMID {pmid}\n")
                            sections.append(f"**标题**: {title}\n")
                            sections.append(f"**期刊**: {journal} ({year})\n")
                            sections.append(f"**作者**: {author_str}\n")
                            if abstract:
                                abstract_clean = abstract.replace('\n', ' ').strip()
                                sections.append(f"**摘要**: {abstract_clean[:500]}...\n" if len(abstract) > 500 else f"**摘要**: {abstract_clean}\n")
                        else:
                            sections.append(f"### Literature {idx}: PMID {pmid}\n")
                            sections.append(f"**Title**: {title}\n")
                            sections.append(f"**Journal**: {journal} ({year})\n")
                            sections.append(f"**Authors**: {author_str}\n")
                            if abstract:
                                abstract_clean = abstract.replace('\n', ' ').strip()
                                sections.append(f"**Abstract**: {abstract_clean[:500]}...\n" if len(abstract) > 500 else f"**Abstract**: {abstract_clean}\n")

                        # 该文献的PDB结构
                        sections.append(f"\n**该文献解析的PDB结构** ({len(pdbs)}个):\n")
                        sections.append("| PDB ID | 方法 | 分辨率(Å) | 标题 |")
                        sections.append("|--------|------|------------|------|")
                        for struct in pdbs:
                            pdb_id = struct.get('pdb_id', 'N/A')
                            method = struct.get('experimental_method', 'N/A')[:20]
                            resolution = struct.get('resolution', '')
                            title_str = struct.get('title', 'N/A')[:40]
                            sections.append(f"| {pdb_id} | {method} | {resolution} | {title_str} |")

                        # 实体详情
                        for struct in pdbs:
                            pdb_id = struct.get('pdb_id', 'N/A')
                            entity_list = struct.get('entity_list', [])
                            if entity_list:
                                if language == 'zh':
                                    sections.append(f"\n**{pdb_id} 实体详情**:\n")
                                else:
                                    sections.append(f"\n**{pdb_id} Entity Details**:\n")
                                for ent in entity_list[:2]:  # 每个结构最多2个实体
                                    ent_id = ent.get('entity_id', '')
                                    chain = ent.get('chain', '')
                                    polymer_type = ent.get('polymer_type', '')
                                    length = ent.get('length', 0)
                                    mol_name = ent.get('molecule_name', '')
                                    gene = ent.get('gene_name', '')
                                    name_str = f"{mol_name}" if mol_name else polymer_type
                                    if language == 'zh':
                                        gene_str = f", 基因: {gene}" if gene else ""
                                        sections.append(f"- 实体 {ent_id} (链 {chain}): {name_str}{gene_str}, 长度 {length}\n")
                                    else:
                                        gene_str = f", Gene: {gene}" if gene else ""
                                        sections.append(f"- Entity {ent_id} (Chain {chain}): {name_str}{gene_str}, Length {length}\n")
                        sections.append("")
            else:
                sections.append("## PDB 结构数据\n暂无 PDB 结构数据\n")

        # ==================== 6. BLAST 同源结构统计 ====================
        # Use homology_info if available (from _detect_homology_mode), otherwise extract from blast_results
        homology_details = homology_info.get('homology_details', [])
        if not homology_details and blast_results:
            homology_details = blast_results.get('homology_details', [])

        if homology_details:
            homology_stats = homology_info.get('homology_stats')
            if not homology_stats:
                homology_stats = extract_homology_statistics(homology_details)

            if homology_stats and homology_stats.get('total_homologs', 0) > 0:
                homology_section = build_homology_section_for_prompt(homology_stats, language=language)
                sections.append(homology_section)

                # 简洁的 BLAST 结果列表
                results = blast_results.get('results', []) if blast_results else []
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

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses rough character-based estimation (~4 chars per token for English,
        ~2 chars per token for Chinese).
        """
        if not text:
            return 0

        # Count Chinese characters (roughly 2 chars per token)
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        # Rest is roughly 4 chars per token
        other_chars = len(text) - chinese_chars

        return int(chinese_chars / 2) + int(other_chars / 4)

    def _get_context_limit(self) -> int:
        """Get the context window limit for the current model."""
        model_lower = self.model.lower()

        for model_pattern, limit in self.MODEL_CONTEXT_WINDOWS.items():
            if model_pattern in model_lower:
                return limit - self.CONTEXT_RESERVE

        # Default: assume 8k context
        return 8000 - self.CONTEXT_RESERVE

    def _generate_literature_grouped_data(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        language: str = 'zh'
    ) -> List[Dict[str, Any]]:
        """
        Generate data sections grouped by literature.

        Returns a list of chunks, where each chunk contains:
        - header: protein info header
        - literature_data: list of (literature, pdbs_citing_it) tuples
        - homology_data: homology statistics (for all, not split)

        The chunks are designed to be within context limits while
        keeping each literature's data together.
        """
        chunks = []

        # 1. Build the header section (protein info)
        header = self._build_protein_header(uniprot_data, language)

        # 2. Collect all literature and their associated PDBs
        literature_pdb_map = []  # List of (literature, pdb_structures) tuples

        structures = pdb_data.get('structures', []) if pdb_data else []

        # Build a map of literature -> PDB structures
        lit_to_pdbs = {}
        lit_to_structs = {}

        for struct in structures:
            pdb_id = struct.get('pdb_id', '')
            citations = struct.get('citations', []) or []

            for cite in citations:
                pmid = cite.get('pubmed_id', '')
                title = cite.get('title', '')

                # Create a unique key for this literature
                lit_key = pmid if pmid else title.lower()

                if not lit_key:
                    continue

                if lit_key not in lit_to_pdbs:
                    lit_to_pdbs[lit_key] = []
                    lit_to_structs[lit_key] = {
                        'pubmed_id': pmid,
                        'title': title,
                        'journal': cite.get('journal', ''),
                        'year': cite.get('year', ''),
                        'authors': cite.get('authors', []),
                        'abstract': cite.get('abstract', ''),
                        'doi': cite.get('doi', '')
                    }

                lit_to_pdbs[lit_key].append(struct)

        # Convert to list of tuples
        for lit_key, lit_info in lit_to_structs.items():
            literature_pdb_map.append((lit_info, lit_to_pdbs[lit_key]))

        # 3. Build homology section (not split, included in all chunks)
        homology_section = ""
        homology_details = blast_results.get('homology_details', []) if blast_results else []
        if homology_details:
            homology_stats = extract_homology_statistics(homology_details)
            if homology_stats and homology_stats.get('total_homologs', 0) > 0:
                homology_section = build_homology_section_for_prompt(homology_stats, language=language)

        # 4. Build chunks, keeping literatures together
        if not literature_pdb_map:
            # No literature data - build a single chunk with just protein/PDB info
            chunk_data = self._build_simple_chunk(header, structures, homology_section, language)
            chunks.append(chunk_data)
        else:
            # Group literatures into chunks based on context limit
            context_limit = self._get_context_limit()
            # Base tokens = header + homology (these are included in every chunk)
            base_tokens = self._estimate_tokens(header) + self._estimate_tokens(homology_section)

            current_chunk_literatures = []
            current_chunk_tokens = base_tokens

            for lit_info, pdbs in literature_pdb_map:
                # Estimate size of this literature + its PDBs
                lit_text = self._format_literature_for_prompt(lit_info, pdbs, language)
                lit_tokens = self._estimate_tokens(lit_text)

                # Check if adding this literature would exceed limit
                # If this is the first literature and it exceeds limit, add it anyway
                # (can't split further without splitting the literature itself)
                if current_chunk_literatures and current_chunk_tokens + lit_tokens > context_limit:
                    # Save current chunk and start new one
                    chunk_data = self._build_chunk_with_literatures(
                        header, current_chunk_literatures, homology_section, language
                    )
                    chunks.append(chunk_data)
                    current_chunk_literatures = []
                    current_chunk_tokens = base_tokens

                current_chunk_literatures.append((lit_info, pdbs))
                current_chunk_tokens += lit_tokens

            # Don't forget the last chunk
            if current_chunk_literatures:
                chunk_data = self._build_chunk_with_literatures(
                    header, current_chunk_literatures, homology_section, language
                )
                chunks.append(chunk_data)

        return chunks

    def _build_protein_header(self, uniprot_data: Dict, language: str) -> str:
        """Build the protein information header section."""
        parts = []

        if language == 'zh':
            parts.append("## 蛋白质基础信息\n")
            parts.append(f"- **UniProt ID**: {uniprot_data.get('uniprot_id', 'N/A')}")
            parts.append(f"- **蛋白名称**: {uniprot_data.get('protein_name', 'N/A')}")
            gene_names = uniprot_data.get('gene_names', [])
            if gene_names:
                parts.append(f"- **基因名称**: {', '.join(gene_names)}")
            parts.append(f"- **物种**: {uniprot_data.get('organism', 'N/A')}")
            seq_len = uniprot_data.get('sequence_length', 0)
            if seq_len:
                parts.append(f"- **序列长度**: {seq_len} aa")
            function = uniprot_data.get('function', '')
            if function:
                func_text = function[:1500] if len(function) > 1500 else function
                parts.append(f"- **功能描述**: {func_text}")
        else:
            parts.append("## Protein Basic Information\n")
            parts.append(f"- **UniProt ID**: {uniprot_data.get('uniprot_id', 'N/A')}")
            parts.append(f"- **Protein Name**: {uniprot_data.get('protein_name', 'N/A')}")
            gene_names = uniprot_data.get('gene_names', [])
            if gene_names:
                parts.append(f"- **Gene Names**: {', '.join(gene_names)}")
            parts.append(f"- **Organism**: {uniprot_data.get('organism', 'N/A')}")
            seq_len = uniprot_data.get('sequence_length', 0)
            if seq_len:
                parts.append(f"- **Sequence Length**: {seq_len} aa")
            function = uniprot_data.get('function', '')
            if function:
                func_text = function[:1500] if len(function) > 1500 else function
                parts.append(f"- **Function**: {func_text}")

        return "\n".join(parts)

    def _format_literature_for_prompt(
        self,
        lit_info: Dict,
        pdb_structures: List[Dict],
        language: str
    ) -> str:
        """Format a single literature and its associated PDBs for the prompt."""
        parts = []

        pmid = lit_info.get('pubmed_id', 'N/A')
        title = lit_info.get('title', 'No title')
        journal = lit_info.get('journal', 'Unknown')
        year = lit_info.get('year', 'N/A')
        authors = lit_info.get('authors', [])
        abstract = lit_info.get('abstract', '')

        author_str = ', '.join(authors[:5]) if len(authors) > 5 else ', '.join(authors)
        if len(authors) > 5:
            author_str += ' et al.'

        if language == 'zh':
            parts.append(f"\n### 文献: PMID {pmid}\n")
            parts.append(f"- **标题**: {title}\n")
            parts.append(f"- **期刊**: {journal} ({year})\n")
            parts.append(f"- **作者**: {author_str}\n")
            if abstract:
                parts.append(f"- **摘要**: {abstract}\n")
        else:
            parts.append(f"\n### Literature: PMID {pmid}\n")
            parts.append(f"- **Title**: {title}\n")
            parts.append(f"- **Journal**: {journal} ({year})\n")
            parts.append(f"- **Authors**: {author_str}\n")
            if abstract:
                parts.append(f"- **Abstract**: {abstract}\n")

        # PDB structures for this literature
        if pdb_structures:
            if language == 'zh':
                parts.append(f"\n**该文献中的PDB结构** ({len(pdb_structures)}个):\n")
            else:
                parts.append(f"\n**PDB structures in this literature** ({len(pdb_structures)}):\n")

            for idx, struct in enumerate(pdb_structures, 1):
                pdb_id = struct.get('pdb_id', 'N/A')
                method = struct.get('experimental_method', 'N/A')
                resolution = struct.get('resolution')
                title_str = struct.get('title', '')
                entity_list = struct.get('entity_list', [])
                entity_info = struct.get('entity_info', {})

                if language == 'zh':
                    parts.append(f"\n**{idx}. {pdb_id}**\n")
                    parts.append(f"- 方法: {method}\n")
                    if resolution:
                        parts.append(f"- 分辨率: {resolution} Å\n")
                    if title_str:
                        parts.append(f"- 标题: {title_str}\n")
                else:
                    parts.append(f"\n**{idx}. {pdb_id}**\n")
                    parts.append(f"- Method: {method}\n")
                    if resolution:
                        parts.append(f"- Resolution: {resolution} Å\n")
                    if title_str:
                        parts.append(f"- Title: {title_str}\n")

                # Entity info for this structure
                if entity_list:
                    polypeptide_count = entity_info.get('polypeptide', 0)
                    if polypeptide_count > 0:
                        if language == 'zh':
                            parts.append(f"- 实体: {polypeptide_count} 个多肽链\n")
                        else:
                            parts.append(f"- Entities: {polypeptide_count} polypeptide(s)\n")

                    for ent in entity_list[:2]:  # Show first 2 entities
                        ent_id = ent.get('entity_id', '')
                        chain = ent.get('chain', '')
                        polymer_type = ent.get('polymer_type', '')
                        length = ent.get('length', 0)
                        mol_name = ent.get('molecule_name', '')
                        gene = ent.get('gene_name', '')
                        name_str = f"{mol_name}" if mol_name else polymer_type
                        if language == 'zh':
                            gene_str = f", 基因: {gene}" if gene else ""
                            parts.append(f"  - 实体 {ent_id} (链 {chain}): {name_str}{gene_str}, 长度 {length}\n")
                        else:
                            gene_str = f", Gene: {gene}" if gene else ""
                            parts.append(f"  - Entity {ent_id} (Chain {chain}): {name_str}{gene_str}, Length {length}\n")

                # Ligand info - list all non-polypeptide entities
                non_polypeptides = [e for e in entity_list if e.get('polymer_type') not in ('Polypeptide', 'Nucleic Acid', '')]
                if non_polypeptides:
                    if language == 'zh':
                        parts.append(f"- 小分子配体: {', '.join([e.get('molecule_name', '') or e.get('polymer_type', '') for e in non_polypeptides])}\n")
                    else:
                        parts.append(f"- Small Molecule Ligands: {', '.join([e.get('molecule_name', '') or e.get('polymer_type', '') for e in non_polypeptides])}\n")

        return "".join(parts)

    def _build_chunk_with_literatures(
        self,
        header: str,
        literature_pdb_map: List[tuple],
        homology_section: str,
        language: str
    ) -> Dict[str, Any]:
        """Build a single chunk containing header + literatures + homology."""
        parts = [header]

        # PDB overview (brief statistics)
        if language == 'zh':
            parts.append("\n## PDB 结构统计\n")
        else:
            parts.append("\n## PDB Structure Statistics\n")

        structures = []
        for _, pdbs in literature_pdb_map:
            structures.extend(pdbs)

        # Deduplicate structures by pdb_id
        seen_pdb_ids = set()
        unique_structures = []
        for s in structures:
            pid = s.get('pdb_id', '')
            if pid and pid not in seen_pdb_ids:
                seen_pdb_ids.add(pid)
                unique_structures.append(s)

        if unique_structures:
            stats = extract_pdb_statistics(unique_structures)
            if language == 'zh':
                parts.append(f"- **结构总数**: {stats['total_structures']}")
                if stats['resolution_range']:
                    parts.append(f"- **分辨率范围**: {stats['resolution_range']} Å")
                if stats['method_distribution']:
                    methods_str = "; ".join([f"{k}: {v}" for k, v in stats['method_distribution'].items()])
                    parts.append(f"- **实验方法**: {methods_str}")
            else:
                parts.append(f"- **Total Structures**: {stats['total_structures']}")
                if stats['resolution_range']:
                    parts.append(f"- **Resolution Range**: {stats['resolution_range']} Å")
                if stats['method_distribution']:
                    methods_str = "; ".join([f"{k}: {v}" for k, v in stats['method_distribution'].items()])
                    parts.append(f"- **Methods**: {methods_str}")

        # Literature sections
        if language == 'zh':
            parts.append("\n## 文献与PDB结构详情\n")
        else:
            parts.append("\n## Literature and PDB Structure Details\n")

        for lit_info, pdbs in literature_pdb_map:
            lit_text = self._format_literature_for_prompt(lit_info, pdbs, language)
            parts.append(lit_text)

        # Homology section (shared, included in all chunks)
        if homology_section:
            if language == 'zh':
                parts.append("\n## 同源结构统计\n")
            else:
                parts.append("\n## Homology Structure Statistics\n")
            parts.append(homology_section)

        return {
            'text': "\n".join(parts),
            'literature_count': len(literature_pdb_map),
            'structure_count': len(unique_structures)
        }

    def _build_simple_chunk(
        self,
        header: str,
        structures: List[Dict],
        homology_section: str,
        language: str
    ) -> Dict[str, Any]:
        """Build a chunk when there's no literature data."""
        parts = [header]

        if structures:
            # PDB overview
            stats = extract_pdb_statistics(structures)
            if language == 'zh':
                parts.append("\n## PDB 结构总览\n")
                parts.append(f"- **结构总数**: {stats['total_structures']}")
                if stats['resolution_range']:
                    parts.append(f"- **分辨率范围**: {stats['resolution_range']} Å")
                if stats['method_distribution']:
                    methods_str = "; ".join([f"{k}: {v}" for k, v in stats['method_distribution'].items()])
                    parts.append(f"- **实验方法**: {methods_str}")
            else:
                parts.append("\n## PDB Structure Overview\n")
                parts.append(f"- **Total Structures**: {stats['total_structures']}")
                if stats['resolution_range']:
                    parts.append(f"- **Resolution Range**: {stats['resolution_range']} Å")
                if stats['method_distribution']:
                    methods_str = "; ".join([f"{k}: {v}" for k, v in stats['method_distribution'].items()])
                    parts.append(f"- **Methods**: {methods_str}")

            # Entity and ligand info
            entity_section = build_entity_section_for_prompt({'structures': structures}, language=language)
            if entity_section:
                parts.append("\n" + entity_section)

            ligand_section = build_ligand_section_for_prompt({'structures': structures}, language=language)
            if ligand_section:
                parts.append("\n" + ligand_section)
        else:
            if language == 'zh':
                parts.append("\n## PDB 结构数据\n暂无 PDB 结构数据\n")
            else:
                parts.append("\n## PDB Structure Data\nNo PDB structure data available.\n")

        if homology_section:
            parts.append("\n" + homology_section)

        return {
            'text': "\n".join(parts),
            'literature_count': 0,
            'structure_count': len(structures)
        }

    def _merge_reports(
        self,
        reports: List[str],
        language: str = 'zh'
    ) -> str:
        """
        Merge multiple AI-generated reports into a single comprehensive report.

        Args:
            reports: List of report strings from multiple AI calls
            language: Language code

        Returns:
            Merged comprehensive report
        """
        if not reports:
            return ""

        if len(reports) == 1:
            return reports[0]

        # For now, use a simple concatenation with headers
        # In a more advanced implementation, we could use an LLM to actually merge
        merged_parts = []

        if language == 'zh':
            merged_parts.append("# 蛋白质结构功能综合分析报告\n")
            merged_parts.append(f"\n*（本报告由 {len(reports)} 部分合并生成）*\n")
        else:
            merged_parts.append("# Protein Structure-Function Comprehensive Analysis Report\n")
            merged_parts.append(f"\n*(This report is generated by merging {len(reports)} parts)*\n")

        for idx, report in enumerate(reports, 1):
            if language == 'zh':
                merged_parts.append(f"\n\n## 第 {idx} 部分\n")
            else:
                merged_parts.append(f"\n\n## Part {idx}\n")
            merged_parts.append(report)

        return "".join(merged_parts)

    def analyze_with_chunking(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        custom_template: str = None,
        language: str = 'zh',
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Run AI analysis with intelligent prompt chunking.

        When the prompt exceeds the model's context window, it splits
        the literature data into multiple chunks, runs AI analysis
        on each, and merges the results.

        Returns:
            Dictionary with 'analysis', 'model', 'success', and optionally 'chunks'
        """
        if not self.client:
            return {'error': 'AI client not initialized', 'success': False}

        # Get context limit
        context_limit = self._get_context_limit()

        # Generate chunks
        chunks = self._generate_literature_grouped_data(
            uniprot_data, pdb_data, blast_results, language
        )

        if len(chunks) == 1:
            # Single chunk - no chunking needed
            prompt = chunks[0]['text']

            if custom_template:
                prompt = self._apply_template_to_prompt(custom_template, prompt, language)

            system_message = self._get_system_message(language)
            result = self.analyze(prompt, system_message=system_message)
            result['prompt'] = prompt
            return result

        # Multiple chunks needed
        reports = []
        prompts_used = []

        for idx, chunk in enumerate(chunks, 1):
            prompt = chunk['text']

            # Apply template to data first (if custom_template provided)
            if custom_template:
                prompt = self._apply_template_to_prompt(custom_template, prompt, language)

            # For multi-chunk, add part indicator AFTER template application
            if language == 'zh':
                chunk_intro = f"\n\n## 【第 {idx}/{len(chunks)} 部分】\n"
                chunk_intro += "请分析以下数据，这是完整报告的一部分。\n"
            else:
                chunk_intro = f"\n\n## 【Part {idx}/{len(chunks)}】\n"
                chunk_intro += "Please analyze the following data. This is part of a complete report.\n"

            full_prompt = chunk_intro + prompt

            system_message = self._get_system_message(language)
            result = self.analyze(full_prompt, system_message=system_message)

            if result.get('success'):
                reports.append(result.get('analysis', ''))
                prompts_used.append(full_prompt)
            else:
                logger.warning(f"Chunk {idx} analysis failed: {result.get('error')}")

        if not reports:
            return {
                'error': 'All chunk analyses failed',
                'success': False,
                'chunks': len(chunks)
            }

        # Merge reports
        merged_analysis = self._merge_reports(reports, language)

        # Combine all prompts for record keeping
        combined_prompt = "\n\n---\n\n".join(prompts_used)

        return {
            'analysis': merged_analysis,
            'model': self.model,
            'success': True,
            'chunks': len(chunks),
            'chunk_reports': reports,
            'prompts': prompts_used,
            'prompt': combined_prompt
        }

    def analyze_two_stage(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        custom_template: str = None,
        language: str = 'zh',
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Run AI analysis using two-stage generation.

        Stage 1: Generate a short statistical summary using the prompt template
        Stage 2: Generate the full report using the summary + data + report template

        This approach avoids the need for chunking because:
        1. The statistical summary is short (300-500 words)
        2. The final report is generated in one pass

        Returns:
            Dictionary with 'analysis', 'model', 'success', and optionally 'error'
        """
        if not self.client:
            return {'error': 'AI client not initialized', 'success': False}

        try:
            # Stage 1: Generate statistical summary
            summary_result = self.generate_statistical_summary(
                uniprot_data, pdb_data, blast_results, language
            )

            if not summary_result.get('success'):
                return {
                    'error': f"Stage 1 failed: {summary_result.get('error', 'Unknown error')}",
                    'success': False,
                    'stage': 1
                }

            statistical_summary = summary_result.get('summary', '')

            # Stage 2: Build final prompt and run analysis
            prompt = self.build_analysis_prompt_with_summary(
                uniprot_data=uniprot_data,
                pdb_data=pdb_data,
                blast_results=blast_results,
                statistical_summary=statistical_summary,
                custom_template=custom_template,
                language=language,
                config=config
            )

            system_message = self._get_system_message(language)
            result = self.analyze(prompt, system_message=system_message)

            if result.get('success'):
                return {
                    'analysis': result.get('analysis', ''),
                    'model': result.get('model', self.model),
                    'success': True,
                    'stage1_summary': statistical_summary,
                    'prompt': prompt
                }
            else:
                return {
                    'error': f"Stage 2 failed: {result.get('error', 'Unknown error')}",
                    'success': False,
                    'stage': 2,
                    'stage1_summary': statistical_summary,
                    'prompt': prompt
                }

        except Exception as e:
            logger.error(f"Two-stage analysis failed: {e}")
            return {'error': str(e), 'success': False}

    def _apply_template_to_prompt(
        self,
        template: str,
        data_prompt: str,
        language: str
    ) -> str:
        """Apply custom template structure to the data prompt."""
        prompt = template

        # Replace {outline} placeholder if present
        if '{outline}' in prompt:
            outline = self._generate_outline_from_prompt(data_prompt)
            prompt = prompt.replace('{outline}', outline)

        # Always append the data section
        if '{data}' in prompt:
            prompt = prompt.replace('{data}', data_prompt)
        else:
            prompt = prompt + "\n\n" + data_prompt

        return prompt

    def _generate_outline_from_prompt(self, data_prompt: str) -> str:
        """Generate a simple outline from the data prompt."""
        lines = []
        for line in data_prompt.split('\n'):
            if line.startswith('## '):
                lines.append(line.replace('## ', '').strip())
        return "\n".join(lines) if lines else ""

    def _get_system_message(self, language: str) -> str:
        """Get the appropriate system message for the language."""
        if language == 'en':
            return "You are a professional protein structural biologist. Please provide a comprehensive analysis of the given protein."
        else:
            return "你是一个专业的蛋白质结构生物学家。请对给定的蛋白质进行综合分析。"


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
