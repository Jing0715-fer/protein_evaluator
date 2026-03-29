"""
Report generation module for protein evaluation.
Handles generation of individual and batch evaluation reports.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generator for protein evaluation reports."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize report generator.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

    def generate_evaluation_report(
        self,
        uniprot_data: Dict,
        pdb_data: Dict,
        blast_results: Dict,
        ai_analysis: Dict
    ) -> str:
        """
        Generate a single protein evaluation report.

        Args:
            uniprot_data: UniProt protein data
            pdb_data: PDB structure data
            blast_results: BLAST search results
            ai_analysis: AI analysis results

        Returns:
            Formatted report string
        """
        sections = []

        sections.append("# 蛋白质评估报告\n")

        # Basic Information
        sections.append(self._format_basic_info(uniprot_data))

        # Structure Information
        sections.append(self._format_structure_info(pdb_data))

        # BLAST Results
        sections.append(self._format_blast_results(blast_results))

        # AI Analysis
        sections.append(self._format_ai_analysis(ai_analysis))

        return "".join(sections)

    def _format_basic_info(self, uniprot_data: Dict) -> str:
        """Format basic protein information section."""
        lines = ["## 1. 基本信息\n"]

        if uniprot_data:
            lines.append(f"**UniProt ID**: {uniprot_data.get('uniprot_id', 'N/A')}\n")
            lines.append(f"**蛋白质名称**: {uniprot_data.get('protein_name', 'N/A')}\n")
            lines.append(f"**基因名**: {', '.join(uniprot_data.get('gene_names', []))}\n")
            lines.append(f"**物种**: {uniprot_data.get('organism', 'N/A')}\n")
            lines.append(f"**序列长度**: {uniprot_data.get('sequence_length', 'N/A')} aa\n")

            if uniprot_data.get('mass'):
                lines.append(f"**分子量**: {uniprot_data.get('mass'):,} Da\n")

            if uniprot_data.get('function'):
                function = uniprot_data.get('function', '')
                lines.append(f"**功能描述**: {function[:500]}\n")

            if uniprot_data.get('keywords'):
                keywords = ', '.join(uniprot_data.get('keywords', [])[:10])
                lines.append(f"**关键词**: {keywords}\n")
        else:
            lines.append("未获取到UniProt数据\n")

        lines.append("\n")
        return "".join(lines)

    def _format_structure_info(self, pdb_data: Dict) -> str:
        """Format structure information section."""
        lines = ["## 2. 结构信息\n"]

        if pdb_data and pdb_data.get('structures'):
            structures = pdb_data.get('structures', [])
            lines.append(f"共有 {len(structures)} 个PDB结构\n\n")

            for struct in structures:
                pdb_id = struct.get('pdb_id', 'N/A')
                basic = struct.get('basic_info', {})

                lines.append(f"### {pdb_id}\n")
                lines.append(f"- **实验方法**: {basic.get('experimental_method', 'N/A')}\n")

                resolution = basic.get('resolution')
                if resolution:
                    lines.append(f"- **分辨率**: {resolution} Å\n")

                if basic.get('deposition_date'):
                    lines.append(f"- **沉积日期**: {basic.get('deposition_date')}\n")

                if basic.get('title'):
                    title = basic.get('title', '')
                    lines.append(f"- **标题**: {title}\n")

                # Entity list (macromolecules)
                entity_list = struct.get('entity_list', [])
                if entity_list:
                    # Filter macromolecules (polypeptides and nucleic acids)
                    macromolecules = [e for e in entity_list if e.get('polymer_type') in ('Polypeptide', 'Nucleic Acid')]
                    # Filter ligands (non-polymers)
                    ligands = [e for e in entity_list if e.get('polymer_type') not in ('Polypeptide', 'Nucleic Acid', '')]

                    if macromolecules:
                        lines.append(f"- **大分子实体**: {len(macromolecules)} 个多肽链\n")
                        for ent in macromolecules:
                            chain = ent.get('chain', '')
                            mol_name = ent.get('molecule_name', '')
                            gene = ent.get('gene_name', '')
                            length = ent.get('length', '')
                            lines.append(f"  - 链 {chain}: {mol_name or 'N/A'}")
                            if gene:
                                lines.append(f" (基因: {gene})")
                            if length:
                                lines.append(f", 长度: {length} aa")
                            lines.append("\n")

                    if ligands:
                        lines.append(f"- **小分子配体**: {len(ligands)} 个\n")
                        for lig in ligands:
                            chain = lig.get('chain', '')
                            mol_name = lig.get('molecule_name', '')
                            length = lig.get('length', '')
                            lines.append(f"  - 链 {chain or 'N/A'}: {mol_name or 'N/A'}")
                            if length:
                                lines.append(f", 长度: {length}")
                            lines.append("\n")

                citations = struct.get('citations', [])
                if citations:
                    lines.append(f"- **相关文献**: {len(citations)} 篇\n")

                lines.append("\n")

            # Coverage information
            coverage = pdb_data.get('coverage', {})
            if coverage:
                lines.append(f"**序列覆盖度**: {coverage.get('coverage_percent', 0):.1f}%\n")
                lines.append(f"**覆盖残基**: {coverage.get('covered_residues', 0)} / {coverage.get('total_residues', 0)}\n")
        else:
            lines.append("未获取到PDB结构数据\n")

        lines.append("\n")
        return "".join(lines)

    def _format_blast_results(self, blast_results: Dict) -> str:
        """Format BLAST search results section."""
        lines = ["## 3. 相似蛋白 (BLAST)\n"]

        if blast_results and blast_results.get('results'):
            results = blast_results.get('results', [])
            method = blast_results.get('method', 'unknown')

            lines.append(f"搜索方法: {method}\n")
            lines.append(f"找到 {len(results)} 个相似蛋白\n\n")

            lines.append("| 标识 | 名称 | 相似度 | 分数 |\n")
            lines.append("|------|------|--------|------|\n")

            for result in results[:10]:
                identifier = result.get('pdb_id') or result.get('uniprot_id', 'N/A')
                name = result.get('title') or result.get('protein_name', 'N/A')
                identity = result.get('identity')
                score = result.get('score', 0)

                identity_str = f"{identity:.1f}%" if identity else "N/A"
                lines.append(f"| {identifier} | {name[:30]} | {identity_str} | {score} |\n")
        else:
            lines.append("未获取到相似蛋白数据\n")

        lines.append("\n")
        return "".join(lines)

    def _format_ai_analysis(self, ai_analysis: Dict) -> str:
        """Format AI analysis section."""
        lines = ["## 4. AI分析\n"]

        if ai_analysis and ai_analysis.get('analysis'):
            analysis = ai_analysis.get('analysis', '')
            model = ai_analysis.get('model', 'unknown')

            lines.append(f"*分析模型: {model}*\n\n")
            lines.append(analysis)
        elif ai_analysis and ai_analysis.get('error'):
            lines.append(f"AI分析失败: {ai_analysis['error']}")
        else:
            lines.append("未进行AI分析\n")

        lines.append("\n")
        return "".join(lines)

    def generate_batch_report(
        self,
        uniprot_ids: List[str],
        interaction_data: Dict,
        individual_reports: Dict[str, str],
        ai_analysis: Dict
    ) -> str:
        """
        Generate a batch evaluation report.

        Args:
            uniprot_ids: List of UniProt IDs
            interaction_data: Protein interaction data
            individual_reports: Dictionary of individual reports by UniProt ID
            ai_analysis: Batch AI analysis results

        Returns:
            Formatted batch report string
        """
        sections = []

        # Header
        sections.append("# 批量蛋白质评估报告\n")
        sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        sections.append(f"**评估蛋白数量**: {len(uniprot_ids)}\n\n")

        # Protein list
        sections.append("## 评估蛋白列表\n")
        for idx, uniprot_id in enumerate(uniprot_ids, 1):
            sections.append(f"{idx}. {uniprot_id}\n")
        sections.append("\n")

        # Interactions
        if interaction_data and interaction_data.get('interactions'):
            sections.append(self._format_interactions(interaction_data))

        # Individual reports summary
        sections.append("## 单个蛋白评估摘要\n")
        for uniprot_id, report in individual_reports.items():
            # Extract first section (basic info) from each report
            lines = report.split('\n')
            sections.append(f"### {uniprot_id}\n")
            # Add first few lines as summary
            for line in lines[:20]:
                if line.strip():
                    sections.append(line + "\n")
            sections.append("\n")

        # Batch AI Analysis
        sections.append("## 综合分析\n")
        if ai_analysis and ai_analysis.get('analysis'):
            sections.append(ai_analysis['analysis'])
        elif ai_analysis and ai_analysis.get('error'):
            sections.append(f"分析失败: {ai_analysis['error']}")
        else:
            sections.append("未进行综合分析\n")

        return "".join(sections)

    def _format_interactions(self, interaction_data: Dict) -> str:
        """Format protein interactions section."""
        lines = ["## 蛋白质相互作用\n"]

        interactions = interaction_data.get('interactions', [])
        source = interaction_data.get('source', 'unknown')

        lines.append(f"数据来源: {source}\n")
        lines.append(f"发现 {len(interactions)} 个相互作用\n\n")

        if interactions:
            lines.append("| 蛋白A | 蛋白B | 类型 | 置信度 |\n")
            lines.append("|-------|-------|------|--------|\n")

            for interaction in interactions[:20]:
                protein_a = interaction.get('protein_a', 'N/A')
                protein_b = interaction.get('protein_b', 'N/A')
                int_type = interaction.get('type', 'unknown')
                score = interaction.get('score', 'N/A')

                lines.append(f"| {protein_a} | {protein_b} | {int_type} | {score} |\n")

        lines.append("\n")
        return "".join(lines)

    def export_report(
        self,
        report: str,
        format: str = 'markdown',
        output_path: Optional[str] = None
    ) -> str:
        """
        Export report to file.

        Args:
            report: Report content
            format: Export format ('markdown', 'txt')
            output_path: Optional output file path

        Returns:
            Output file path or report content
        """
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"protein_evaluation_{timestamp}.md"

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Report exported to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return report


def generate_report(
    uniprot_data: Dict,
    pdb_data: Dict,
    blast_results: Dict,
    ai_analysis: Dict
) -> str:
    """
    Convenience function to generate a single protein evaluation report.

    Args:
        uniprot_data: UniProt protein data
        pdb_data: PDB structure data
        blast_results: BLAST search results
        ai_analysis: AI analysis results

    Returns:
        Formatted report string
    """
    generator = ReportGenerator()
    return generator.generate_evaluation_report(
        uniprot_data, pdb_data, blast_results, ai_analysis
    )


def generate_batch_report(
    uniprot_ids: List[str],
    interaction_data: Dict,
    individual_reports: Dict[str, str],
    ai_analysis: Dict
) -> str:
    """
    Convenience function to generate a batch evaluation report.

    Args:
        uniprot_ids: List of UniProt IDs
        interaction_data: Protein interaction data
        individual_reports: Dictionary of individual reports
        ai_analysis: Batch AI analysis results

    Returns:
        Formatted batch report string
    """
    generator = ReportGenerator()
    return generator.generate_batch_report(
        uniprot_ids, interaction_data, individual_reports, ai_analysis
    )
