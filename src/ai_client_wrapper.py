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
        custom_template: str = None
    ) -> str:
        """
        Build analysis prompt from protein data.

        Args:
            uniprot_data: UniProt protein data
            pdb_data: PDB structure data
            blast_results: BLAST search results
            custom_template: Custom prompt template

        Returns:
            Formatted prompt string
        """
        if custom_template:
            return self._apply_template(custom_template, uniprot_data, pdb_data, blast_results)

        # Default prompt builder
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
            parts.append(f"共有 {len(structures)} 个PDB结构\n\n")

            for idx, struct in enumerate(structures[:10], 1):
                pdb_id = struct.get('pdb_id', 'N/A')
                basic = struct.get('basic_info', {})

                parts.append(f"**{idx}. {pdb_id}**\n")
                parts.append(f"- 方法: {basic.get('experimental_method', 'N/A')}\n")

                resolution = basic.get('resolution')
                if resolution:
                    parts.append(f"- 分辨率: {resolution} Å\n")

                if basic.get('title'):
                    parts.append(f"- 标题: {basic.get('title', '')[:100]}\n")

                citations = struct.get('citations', [])
                if citations:
                    parts.append(f"- 文献: {len(citations)} 篇\n")

                parts.append("\n")

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

        return "".join(parts)

    def _apply_template(
        self,
        template: str,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict
    ) -> str:
        """Apply data to custom template."""
        # Simple template substitution
        # In a real implementation, you might use Jinja2 or similar
        if '{outline}' in template:
            # Generate outline from data
            outline = self._generate_outline(uniprot_data, pdb_data, blast_results)
            return template.replace('{outline}', outline)

        return template

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
