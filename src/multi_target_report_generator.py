"""
多靶点批量报告生成模块

本模块扩展了 ReportGenerator，支持：
- 多靶点批量评估报告生成
- 多种导出格式（Markdown、PDF、Excel、JSON）
- 异步报告生成（大报告后台生成）
- 汇总统计和可视化数据输出

设计原则：
1. 支持同步和异步两种生成模式
2. 模板化设计，易于扩展
3. 性能优化，支持大批量数据处理
4. 多语言支持（中英文）
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import tempfile
import zipfile

from src.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


@dataclass
class ReportTemplate:
    """报告模板配置"""
    name: str
    sections: List[str]  # 包含的章节列表
    include_summary: bool = True
    include_details: bool = True
    include_interactions: bool = True
    include_charts: bool = True
    language: str = 'zh'  # 'zh' 或 'en'


@dataclass
class BatchReportMetadata:
    """批量报告元数据"""
    report_id: str
    job_id: int
    job_name: str
    created_at: datetime
    target_count: int
    completed_count: int
    failed_count: int
    format: str
    file_size: Optional[int] = None
    download_url: Optional[str] = None


class MultiTargetReportGenerator(ReportGenerator):
    """多靶点批量报告生成器

    扩展 ReportGenerator，提供多靶点批量评估报告的生成和导出功能。
    支持多种格式（Markdown、PDF、Excel、JSON）和异步生成模式。

    Attributes:
        config: 配置字典，包含模板路径、输出目录等
        templates: 报告模板字典
        executor: 线程池执行器（用于异步任务）
    """

    # 预定义报告模板
    DEFAULT_TEMPLATES = {
        'full': ReportTemplate(
            name='完整报告',
            sections=['summary', 'statistics', 'targets', 'interactions', 'charts'],
            include_summary=True,
            include_details=True,
            include_interactions=True,
            include_charts=True
        ),
        'summary': ReportTemplate(
            name='摘要报告',
            sections=['summary', 'statistics'],
            include_summary=True,
            include_details=False,
            include_interactions=False,
            include_charts=True
        ),
        'detailed': ReportTemplate(
            name='详细报告',
            sections=['summary', 'targets', 'interactions'],
            include_summary=True,
            include_details=True,
            include_interactions=True,
            include_charts=False
        ),
        'minimal': ReportTemplate(
            name='精简报告',
            sections=['summary'],
            include_summary=True,
            include_details=False,
            include_interactions=False,
            include_charts=False
        ),
        'ai_only': ReportTemplate(
            name='AI分析报告',
            sections=['ai_analysis'],
            include_summary=False,
            include_details=False,
            include_interactions=False,
            include_charts=False
        ),
    }

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化多靶点报告生成器

        Args:
            config: 配置字典，可包含：
                - output_dir: 输出目录（默认：reports/）
                - template_dir: 模板目录
                - max_workers: 异步线程池大小（默认：4）
                - temp_dir: 临时文件目录
        """
        super().__init__(config)
        self.config = config or {}
        self.output_dir = self.config.get('output_dir', 'reports')
        self.temp_dir = self.config.get('temp_dir', tempfile.gettempdir())
        self.max_workers = self.config.get('max_workers', 4)
        self.templates = dict(self.DEFAULT_TEMPLATES)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_multi_target_report(
        self,
        job_data: Dict[str, Any],
        targets_data: List[Dict[str, Any]],
        interactions_data: Optional[Dict[str, Any]] = None,
        template: Union[str, ReportTemplate] = 'full',
        format: str = 'markdown'
    ) -> Dict[str, Any]:
        """
        生成多靶点批量评估报告

        Args:
            job_data: 任务基本信息
                - job_id: 任务ID
                - name: 任务名称
                - description: 任务描述
                - created_at: 创建时间
                - status: 任务状态
            targets_data: 靶点数据列表
            interactions_data: 相互作用数据（可选）
            template: 报告模板名称或自定义模板
            format: 输出格式 ('markdown', 'pdf', 'excel', 'json')

        Returns:
            Dict: 包含报告内容和元数据的字典
                - content: 报告内容
                - metadata: 报告元数据
                - statistics: 统计数据
        """
        # 获取模板
        if isinstance(template, str):
            template = self.templates.get(template, self.templates['full'])

        # 生成报告内容
        report_sections = []
        statistics = self._calculate_statistics(targets_data)

        # 报告头部
        report_sections.append(self._generate_report_header(job_data, template))

        # 执行摘要
        if template.include_summary and 'summary' in template.sections:
            report_sections.append(self._generate_executive_summary(
                job_data, targets_data, statistics, template.language
            ))

        # 统计数据
        if 'statistics' in template.sections:
            report_sections.append(self._generate_statistics_section(
                statistics, template.language
            ))

        # 靶点详情
        if template.include_details and 'targets' in template.sections:
            report_sections.append(self._generate_targets_section(
                targets_data, template.language
            ))

        # AI 分析章节
        if 'ai_analysis' in template.sections:
            report_sections.append(self._generate_ai_analysis_section(
                targets_data, template.language
            ))

        # 相互作用分析
        if template.include_interactions and 'interactions' in template.sections:
            report_sections.append(self._generate_interactions_section(
                interactions_data, template.language
            ))

        # 图表数据（JSON格式）
        charts_data = {}
        if template.include_charts and 'charts' in template.sections:
            charts_data = self._generate_charts_data(statistics, targets_data)

        # 合并报告
        report_content = '\n'.join(report_sections)

        # 创建元数据
        metadata = BatchReportMetadata(
            report_id=f"RPT_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job_data['job_id']}",
            job_id=job_data['job_id'],
            job_name=job_data.get('name', 'Unknown'),
            created_at=datetime.now(),
            target_count=len(targets_data),
            completed_count=statistics.get('completed', 0),
            failed_count=statistics.get('failed', 0),
            format=format
        )

        return {
            'content': report_content,
            'metadata': asdict(metadata),
            'statistics': statistics,
            'charts_data': charts_data,
            'template': template.name
        }

    def _generate_report_header(
        self,
        job_data: Dict[str, Any],
        template: ReportTemplate
    ) -> str:
        """生成报告头部"""
        lines = []

        if template.language == 'zh':
            lines.append("# 多靶点蛋白质评估报告\n")
            lines.append(f"**报告模板**: {template.name}\n")
            lines.append(f"**任务名称**: {job_data.get('name', 'N/A')}\n")
            lines.append(f"**任务ID**: {job_data.get('job_id', 'N/A')}\n")
            if job_data.get('description'):
                lines.append(f"**任务描述**: {job_data['description']}\n")
            lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            lines.append(f"**报告语言**: 中文\n")
        else:
            lines.append("# Multi-Target Protein Evaluation Report\n")
            lines.append(f"**Template**: {template.name}\n")
            lines.append(f"**Job Name**: {job_data.get('name', 'N/A')}\n")
            lines.append(f"**Job ID**: {job_data.get('job_id', 'N/A')}\n")
            if job_data.get('description'):
                lines.append(f"**Description**: {job_data['description']}\n")
            lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            lines.append(f"**Language**: English\n")

        lines.append("---\n")
        return ''.join(lines)

    def _generate_executive_summary(
        self,
        job_data: Dict[str, Any],
        targets_data: List[Dict[str, Any]],
        statistics: Dict[str, Any],
        language: str = 'zh'
    ) -> str:
        """生成执行摘要"""
        lines = []
        total = statistics.get('total', 0)
        completed = statistics.get('completed', 0)
        failed = statistics.get('failed', 0)
        success_rate = (completed / total * 100) if total > 0 else 0

        if language == 'zh':
            lines.append("## 执行摘要\n")
            lines.append(f"本报告包含 **{total}** 个靶点的评估结果。\n\n")
            lines.append(f"- **已完成**: {completed} 个靶点 ({success_rate:.1f}%)\n")
            lines.append(f"- **失败**: {failed} 个靶点\n")
            lines.append(f"- **任务状态**: {job_data.get('status', 'unknown')}\n\n")

            if statistics.get('avg_score'):
                lines.append(f"- **平均评分**: {statistics['avg_score']:.2f}\n")
            if statistics.get('high_quality_count'):
                lines.append(f"- **高质量靶点** (评分≥0.8): {statistics['high_quality_count']} 个\n")
            if statistics.get('interactions_count'):
                lines.append(f"- **相互作用关系**: {statistics['interactions_count']} 对\n")
        else:
            lines.append("## Executive Summary\n")
            lines.append(f"This report contains evaluation results for **{total}** targets.\n\n")
            lines.append(f"- **Completed**: {completed} targets ({success_rate:.1f}%)\n")
            lines.append(f"- **Failed**: {failed} targets\n")
            lines.append(f"- **Job Status**: {job_data.get('status', 'unknown')}\n\n")

            if statistics.get('avg_score'):
                lines.append(f"- **Average Score**: {statistics['avg_score']:.2f}\n")
            if statistics.get('high_quality_count'):
                lines.append(f"- **High Quality** (score≥0.8): {statistics['high_quality_count']} targets\n")
            if statistics.get('interactions_count'):
                lines.append(f"- **Interactions**: {statistics['interactions_count']} pairs\n")

        lines.append("\n")
        return ''.join(lines)

    def _generate_statistics_section(
        self,
        statistics: Dict[str, Any],
        language: str = 'zh'
    ) -> str:
        """生成统计信息章节"""
        lines = []

        if language == 'zh':
            lines.append("## 统计信息\n")

            lines.append("### 任务概览\n")
            lines.append(f"| 指标 | 数值 |\n")
            lines.append(f"|------|------|\n")
            lines.append(f"| 总靶点数 | {statistics.get('total', 0)} |\n")
            lines.append(f"| 已完成 | {statistics.get('completed', 0)} |\n")
            lines.append(f"| 失败 | {statistics.get('failed', 0)} |\n")
            lines.append(f"| 进行中 | {statistics.get('processing', 0)} |\n")
            lines.append(f"| 成功率 | {statistics.get('success_rate', 0):.1f}% |\n\n")

            if statistics.get('by_structure_source'):
                lines.append("### 数据来源分布\n")
                lines.append(f"| 来源 | 数量 |\n")
                lines.append(f"|------|------|\n")
                for source, count in statistics['by_structure_source'].items():
                    lines.append(f"| {source} | {count} |\n")
                lines.append("\n")

            if statistics.get('by_status'):
                lines.append("### 状态分布\n")
                lines.append(f"| 状态 | 数量 |\n")
                lines.append(f"|------|------|\n")
                for status, count in statistics['by_status'].items():
                    lines.append(f"| {status} | {count} |\n")
                lines.append("\n")

            if statistics.get('score_distribution'):
                lines.append("### 评分分布\n")
                lines.append(f"| 评分区间 | 数量 |\n")
                lines.append(f"|----------|------|\n")
                for range_name, count in statistics['score_distribution'].items():
                    lines.append(f"| {range_name} | {count} |\n")
                lines.append("\n")
        else:
            lines.append("## Statistics\n")
            lines.append("### Task Overview\n")
            lines.append(f"| Metric | Value |\n")
            lines.append(f"|--------|-------|\n")
            lines.append(f"| Total Targets | {statistics.get('total', 0)} |\n")
            lines.append(f"| Completed | {statistics.get('completed', 0)} |\n")
            lines.append(f"| Failed | {statistics.get('failed', 0)} |\n")
            lines.append(f"| Processing | {statistics.get('processing', 0)} |\n")
            lines.append(f"| Success Rate | {statistics.get('success_rate', 0):.1f}% |\n\n")

        return ''.join(lines)

    def _generate_targets_section(
        self,
        targets_data: List[Dict[str, Any]],
        language: str = 'zh'
    ) -> str:
        """生成靶点详情章节"""
        lines = []

        if language == 'zh':
            lines.append("## 靶点详情\n")
            lines.append(f"共 {len(targets_data)} 个靶点。\n\n")

            # 汇总表格
            lines.append("### 靶点汇总表\n")
            lines.append("| 序号 | UniProt ID | 名称 | 基因 | 状态 | 评分 | 结构数 |\n")
            lines.append("|------|------------|------|------|------|------|----------|\n")

            for idx, target in enumerate(targets_data, 1):
                uniprot_id = target.get('uniprot_id', 'N/A')
                name = (target.get('protein_name') or target.get('gene_name') or 'N/A')[:20]
                gene = (target.get('gene_name') or 'N/A')[:15]
                status = target.get('status', 'unknown')
                # 优先使用 evaluation 中的 quality_score
                eval_data = target.get('evaluation', {})
                score = eval_data.get('quality_score') if eval_data else None
                if score is None:
                    score = target.get('evaluation_score', 'N/A')
                score_str = f"{score:.2f}" if isinstance(score, (int, float)) else 'N/A'
                pdb_count = eval_data.get('pdb_count', 0) if eval_data else 0
                
                lines.append(f"| {idx} | {uniprot_id} | {name} | {gene} | {status} | {score_str} | {pdb_count} |\n")

            lines.append("\n")

            # 详细列表
            lines.append("### 靶点详细信息\n")
            for idx, target in enumerate(targets_data, 1):
                lines.append(f"#### {idx}. {target.get('uniprot_id', 'Unknown')}\n")
                lines.append(f"- **蛋白名称**: {target.get('protein_name', 'N/A')}\n")
                lines.append(f"- **基因名称**: {target.get('gene_name', 'N/A')}\n")
                lines.append(f"- **状态**: {target.get('status', 'N/A')}\n")
                
                # 评估详情
                eval_data = target.get('evaluation', {})
                if eval_data:
                    lines.append(f"- **评估 ID**: {eval_data.get('id', 'N/A')}\n")
                    lines.append(f"- **PDB 结构数**: {eval_data.get('pdb_count', 0)}\n")
                    lines.append(f"- **质量评分**: {eval_data.get('quality_score', 'N/A')}\n")
                    lines.append(f"- **序列覆盖率**: {eval_data.get('sequence_coverage', 'N/A')}%\n")

                    # PDB 结构详情
                    pdb_structures = eval_data.get('pdb_structures', [])
                    if pdb_structures:
                        lines.append(f"- **PDB 结构 ID**: {', '.join(pdb_structures[:5])}\n")
                        if len(pdb_structures) > 5:
                            lines.append(f"  （共 {len(pdb_structures)} 个结构）\n")

                    # AI 分析摘要
                    ai_analysis = eval_data.get('ai_analysis', {})
                    if ai_analysis:
                        # 支持 summary 和 analysis 两种格式
                        summary = ai_analysis.get('summary') or ai_analysis.get('analysis', '')
                        if summary:
                            # 显示完整 AI 分析内容
                            summary_display = summary
                            lines.append(f"\n**AI 分析摘要**:\n")
                            lines.append(f">{summary_display}\n")

                        # 质量评估详情
                        quality_assessment = ai_analysis.get('quality_assessment', {})
                        if quality_assessment:
                            lines.append(f"\n**结构质量评估**:\n")
                            for key, value in quality_assessment.items():
                                display_key = key.replace('_', ' ').title()
                                lines.append(f"- {display_key}: {value}\n")

                        # 功能位点
                        functional_sites = ai_analysis.get('functional_sites', [])
                        if functional_sites:
                            lines.append(f"\n**功能位点** ({len(functional_sites)} 个):\n")
                            for site in functional_sites[:5]:
                                site_name = site.get('name', site.get('site_name', 'Unknown'))
                                site_type = site.get('type', 'Unknown')
                                lines.append(f"- {site_name} ({site_type})\n")
                            if len(functional_sites) > 5:
                                lines.append(f"  ... 还有 {len(functional_sites) - 5} 个功能位点\n")

                        # 药物靶点潜力
                        drug_potential = ai_analysis.get('drug_target_potential', {})
                        if drug_potential:
                            lines.append(f"\n**药物靶点潜力**:\n")
                            druggability = drug_potential.get('druggability_score', 'N/A')
                            lines.append(f"- 可成药性评分：{druggability}\n")
                            if drug_potential.get('target_class'):
                                lines.append(f"- 靶点类别：{drug_potential['target_class']}\n")
                            if drug_potential.get('similar_targets'):
                                lines.append(f"- 相似靶点：{', '.join(drug_potential['similar_targets'][:3])}\n")

                    # 序列信息
                    if eval_data.get('sequence_length'):
                        lines.append(f"\n**序列信息**:\n")
                        lines.append(f"- 序列长度：{eval_data['sequence_length']} aa\n")
                    if eval_data.get('organism'):
                        lines.append(f"- 物种：{eval_data['organism']}\n")

                    # 日志信息
                    logs = eval_data.get('logs', [])
                    if logs:
                        lines.append(f"\n**评估日志** ({len(logs)} 条):\n")
                        for log in logs[-3:]:  # 显示最近 3 条日志
                            lines.append(f"- {log}\n")

                # 错误信息
                if target.get('error_message'):
                    lines.append(f"\n**错误信息**: {target['error_message']}\n")

                # 时间信息
                if target.get('started_at'):
                    lines.append(f"\n**开始时间**: {target['started_at']}\n")
                if target.get('completed_at'):
                    lines.append(f"**完成时间**: {target['completed_at']}\n")
        else:
            lines.append("## Target Details\n")
            lines.append(f"Total {len(targets_data)} targets.\n\n")

            lines.append("### Target Summary\n")
            lines.append("| No. | UniProt ID | Name | Gene | Status | Score | PDBs |\n")
            lines.append("|-----|------------|------|------|--------|-------|-------|\n")

            for idx, target in enumerate(targets_data, 1):
                uniprot_id = target.get('uniprot_id', 'N/A')
                name = (target.get('protein_name') or target.get('gene_name') or 'N/A')[:20]
                gene = (target.get('gene_name') or 'N/A')[:15]
                status = target.get('status', 'unknown')
                eval_data = target.get('evaluation', {})
                score = eval_data.get('quality_score') if eval_data else None
                if score is None:
                    score = target.get('evaluation_score', 'N/A')
                score_str = f"{score:.2f}" if isinstance(score, (int, float)) else 'N/A'
                pdb_count = eval_data.get('pdb_count', 0) if eval_data else 0
                
                lines.append(f"| {idx} | {uniprot_id} | {name} | {gene} | {status} | {score_str} | {pdb_count} |\n")

            lines.append("\n")

            # Detailed target information (English version)
            lines.append("### Detailed Target Information\n")
            for idx, target in enumerate(targets_data, 1):
                lines.append(f"#### {idx}. {target.get('uniprot_id', 'Unknown')}\n")
                lines.append(f"- **Protein Name**: {target.get('protein_name', 'N/A')}\n")
                lines.append(f"- **Gene Name**: {target.get('gene_name', 'N/A')}\n")
                lines.append(f"- **Status**: {target.get('status', 'N/A')}\n")

                # Structure information
                if target.get('structure_source'):
                    lines.append(f"- **Structure Source**: {target['structure_source']}\n")
                if target.get('structure_id'):
                    lines.append(f"- **Structure ID**: {target['structure_id']}\n")

                # Evaluation details
                eval_data = target.get('evaluation', {})
                if eval_data:
                    lines.append(f"- **Evaluation ID**: {eval_data.get('id', 'N/A')}\n")
                    lines.append(f"- **PDB Count**: {eval_data.get('pdb_count', 0)}\n")
                    lines.append(f"- **Quality Score**: {eval_data.get('quality_score', 'N/A')}\n")
                    lines.append(f"- **Sequence Coverage**: {eval_data.get('sequence_coverage', 'N/A')}%\n")

                    # PDB structure details
                    pdb_structures = eval_data.get('pdb_structures', [])
                    if pdb_structures:
                        lines.append(f"- **PDB Structure IDs**: {', '.join(pdb_structures[:5])}\n")
                        if len(pdb_structures) > 5:
                            lines.append(f"  (Total {len(pdb_structures)} structures)\n")

                    # AI analysis summary
                    ai_analysis = eval_data.get('ai_analysis', {})
                    if ai_analysis:
                        # Support both summary and analysis keys
                        summary = ai_analysis.get('summary') or ai_analysis.get('analysis', '')
                        if summary:
                            # Show only first 1000 chars
                            summary_display = summary[:1000] + '...' if len(summary) > 1000 else summary
                            lines.append(f"\n**AI Analysis Summary**:\n")
                            lines.append(f">{summary_display}\n")

                        # Quality assessment details
                        quality_assessment = ai_analysis.get('quality_assessment', {})
                        if quality_assessment:
                            lines.append(f"\n**Structure Quality Assessment**:\n")
                            for key, value in quality_assessment.items():
                                display_key = key.replace('_', ' ').title()
                                lines.append(f"- {display_key}: {value}\n")

                        # Functional sites
                        functional_sites = ai_analysis.get('functional_sites', [])
                        if functional_sites:
                            lines.append(f"\n**Functional Sites** ({len(functional_sites)}):\n")
                            for site in functional_sites[:5]:
                                site_name = site.get('name', site.get('site_name', 'Unknown'))
                                site_type = site.get('type', 'Unknown')
                                lines.append(f"- {site_name} ({site_type})\n")
                            if len(functional_sites) > 5:
                                lines.append(f"  ... {len(functional_sites) - 5} more functional sites\n")

                        # Drug target potential
                        drug_potential = ai_analysis.get('drug_target_potential', {})
                        if drug_potential:
                            lines.append(f"\n**Drug Target Potential**:\n")
                            druggability = drug_potential.get('druggability_score', 'N/A')
                            lines.append(f"- Druggability Score: {druggability}\n")
                            if drug_potential.get('target_class'):
                                lines.append(f"- Target Class: {drug_potential['target_class']}\n")
                            if drug_potential.get('similar_targets'):
                                lines.append(f"- Similar Targets: {', '.join(drug_potential['similar_targets'][:3])}\n")

                    # Sequence information
                    if eval_data.get('sequence_length'):
                        lines.append(f"\n**Sequence Information**:\n")
                        lines.append(f"- Sequence Length: {eval_data['sequence_length']} aa\n")
                    if eval_data.get('organism'):
                        lines.append(f"- Organism: {eval_data['organism']}\n")

                    # Log information
                    logs = eval_data.get('logs', [])
                    if logs:
                        lines.append(f"\n**Evaluation Logs** ({len(logs)} entries):\n")
                        for log in logs[-3:]:  # Show last 3 logs
                            lines.append(f"- {log}\n")

                # Error message
                if target.get('error_message'):
                    lines.append(f"\n**Error Message**: {target['error_message']}\n")

                # Timestamps
                if target.get('started_at'):
                    lines.append(f"\n**Started**: {target['started_at']}\n")
                if target.get('completed_at'):
                    lines.append(f"**Completed**: {target['completed_at']}\n")

                lines.append("\n")

        return ''.join(lines)

    def _generate_interactions_section(
        self,
        interactions_data: Optional[Dict[str, Any]],
        language: str = 'zh'
    ) -> str:
        """生成相互作用分析章节"""
        if not interactions_data:
            return ''

        lines = []
        interactions = interactions_data.get('interactions', [])

        if language == 'zh':
            lines.append("## 靶点间相互作用分析\n")
            lines.append(f"发现 **{len(interactions)}** 对相互作用关系。\n\n")

            if interactions:
                lines.append("### 相互作用列表\n")
                lines.append("| 靶点A | 靶点B | 关系类型 | 分数 |\n")
                lines.append("|-------|-------|----------|------|\n")

                for interaction in interactions[:50]:  # 限制显示数量
                    source = interaction.get('source_uniprot', 'N/A')
                    target = interaction.get('target_uniprot', 'N/A')
                    rel_type = interaction.get('relationship_type', 'unknown')
                    score = interaction.get('score', 'N/A')
                    score_str = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)

                    lines.append(f"| {source} | {target} | {rel_type} | {score_str} |\n")

                if len(interactions) > 50:
                    lines.append(f"\n*仅显示前 50 条，共 {len(interactions)} 条*\n")

            # 聚类信息
            if interactions_data.get('clusters'):
                lines.append("\n### 靶点聚类\n")
                for idx, cluster in enumerate(interactions_data['clusters'], 1):
                    lines.append(f"**聚类 {idx}**: {', '.join(cluster.get('targets', []))}\n")
                    lines.append(f"- 类型: {cluster.get('type', 'unknown')}\n")
                    avg_sim = cluster.get('avg_similarity', 'N/A')
                    avg_sim_str = f"{avg_sim:.3f}" if isinstance(avg_sim, (int, float)) else str(avg_sim)
                    lines.append(f"- 平均相似度: {avg_sim_str}\n\n")
        else:
            lines.append("## Target Interactions\n")
            lines.append(f"Found **{len(interactions)}** interaction pairs.\n\n")

            if interactions:
                lines.append("### Interaction List\n")
                lines.append("| Target A | Target B | Type | Score |\n")
                lines.append("|----------|----------|------|-------|\n")

                for interaction in interactions[:50]:
                    source = interaction.get('source_uniprot', 'N/A')
                    target = interaction.get('target_uniprot', 'N/A')
                    rel_type = interaction.get('relationship_type', 'unknown')
                    score = interaction.get('score', 'N/A')
                    score_str = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)

                    lines.append(f"| {source} | {target} | {rel_type} | {score_str} |\n")

        lines.append("\n")
        return ''.join(lines)

    def _calculate_statistics(
        self,
        targets_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算统计数据"""
        stats = {
            'total': len(targets_data),
            'completed': 0,
            'failed': 0,
            'processing': 0,
            'pending': 0,
            'success_rate': 0,
            'by_status': {},
            'by_structure_source': {},
            'score_distribution': {
                '0.0-0.2': 0, '0.2-0.4': 0, '0.4-0.6': 0,
                '0.6-0.8': 0, '0.8-1.0': 0
            },
            'scores': [],
            'high_quality_count': 0,
            'avg_score': None,
            'min_score': None,
            'max_score': None,
        }

        for target in targets_data:
            # 状态统计
            status = target.get('status', 'unknown')
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

            if status == 'completed':
                stats['completed'] += 1
            elif status == 'failed':
                stats['failed'] += 1
            elif status == 'processing':
                stats['processing'] += 1
            else:
                stats['pending'] += 1

            # 数据来源统计
            source = target.get('structure_source', 'unknown')
            stats['by_structure_source'][source] = stats['by_structure_source'].get(source, 0) + 1

            # 评分统计
            score = target.get('evaluation_score')
            if score is not None and isinstance(score, (int, float)):
                stats['scores'].append(score)

                if score >= 0.8:
                    stats['high_quality_count'] += 1

                # 分布区间
                if score < 0.2:
                    stats['score_distribution']['0.0-0.2'] += 1
                elif score < 0.4:
                    stats['score_distribution']['0.2-0.4'] += 1
                elif score < 0.6:
                    stats['score_distribution']['0.4-0.6'] += 1
                elif score < 0.8:
                    stats['score_distribution']['0.6-0.8'] += 1
                else:
                    stats['score_distribution']['0.8-1.0'] += 1

        # 计算成功率
        if stats['total'] > 0:
            stats['success_rate'] = (stats['completed'] / stats['total']) * 100

        # 计算分数统计
        if stats['scores']:
            stats['avg_score'] = sum(stats['scores']) / len(stats['scores'])
            stats['min_score'] = min(stats['scores'])
            stats['max_score'] = max(stats['scores'])

        return stats

    def _generate_charts_data(
        self,
        statistics: Dict[str, Any],
        targets_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成图表数据"""
        charts = {
            'status_distribution': {
                'labels': list(statistics.get('by_status', {}).keys()),
                'data': list(statistics.get('by_status', {}).values())
            },
            'score_distribution': {
                'labels': list(statistics.get('score_distribution', {}).keys()),
                'data': list(statistics.get('score_distribution', {}).values())
            },
            'source_distribution': {
                'labels': list(statistics.get('by_structure_source', {}).keys()),
                'data': list(statistics.get('by_structure_source', {}).values())
            }
        }

        # 评分趋势（按完成时间）
        if targets_data:
            scores_timeline = []
            for target in sorted(targets_data, key=lambda x: x.get('completed_at') or ''):
                if target.get('completed_at') and target.get('evaluation_score'):
                    scores_timeline.append({
                        'time': target['completed_at'],
                        'score': target['evaluation_score'],
                        'uniprot_id': target.get('uniprot_id')
                    })
            charts['score_timeline'] = scores_timeline

        return charts

    def export_to_json(
        self,
        report_data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """导出为 JSON 格式"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"batch_report_{timestamp}.json")

        try:
            # 序列化时处理 datetime 对象
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2, default=json_serializer)
            logger.info(f"Report exported to JSON: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to export JSON report: {e}")
            raise

    def export_to_excel(
        self,
        report_data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """导出为 Excel 格式（多个工作表）"""
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas is required for Excel export")
            raise ImportError("pandas is required for Excel export. Install with: pip install pandas openpyxl")

        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"batch_report_{timestamp}.xlsx")

        try:
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                # 工作表1: 摘要
                summary_data = {
                    '指标': ['总靶点数', '已完成', '失败', '进行中', '成功率(%)', '平均评分', '高质量靶点数'],
                    '数值': [
                        report_data['statistics'].get('total', 0),
                        report_data['statistics'].get('completed', 0),
                        report_data['statistics'].get('failed', 0),
                        report_data['statistics'].get('processing', 0),
                        report_data['statistics'].get('success_rate', 0),
                        report_data['statistics'].get('avg_score', 0) or 0,
                        report_data['statistics'].get('high_quality_count', 0)
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='摘要', index=False)

                # 工作表2: 靶点详情
                if 'targets' in str(report_data.get('content', '')):
                    # 解析靶点数据
                    targets = []
                    # 这里简化处理，实际应该从 report_data 中提取
                    pd.DataFrame(targets).to_excel(writer, sheet_name='靶点详情', index=False)

                # 工作表3: 统计数据
                stats = report_data.get('statistics', {})
                stats_df = pd.DataFrame({
                    '状态': list(stats.get('by_status', {}).keys()),
                    '数量': list(stats.get('by_status', {}).values())
                })
                stats_df.to_excel(writer, sheet_name='统计', index=False)

            logger.info(f"Report exported to Excel: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to export Excel report: {e}")
            raise

    def export_to_markdown(
        self,
        report_data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """导出为 Markdown 格式"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"batch_report_{timestamp}.md")

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_data.get('content', ''))
            logger.info(f"Report exported to Markdown: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to export Markdown report: {e}")
            raise

    async def generate_report_async(
        self,
        job_data: Dict[str, Any],
        targets_data: List[Dict[str, Any]],
        interactions_data: Optional[Dict[str, Any]] = None,
        template: str = 'full',
        format: str = 'markdown',
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """异步生成报告"""
        loop = asyncio.get_event_loop()

        # 在线程池中执行同步报告生成
        result = await loop.run_in_executor(
            self.executor,
            self.generate_multi_target_report,
            job_data,
            targets_data,
            interactions_data,
            template,
            format
        )

        # 导出报告
        if format == 'json':
            output_path = await loop.run_in_executor(
                self.executor,
                self.export_to_json,
                result
            )
        elif format == 'excel':
            output_path = await loop.run_in_executor(
                self.executor,
                self.export_to_excel,
                result
            )
        else:
            output_path = await loop.run_in_executor(
                self.executor,
                self.export_to_markdown,
                result
            )

        result['output_path'] = output_path

        if callback:
            callback(result)

        return result

    def create_batch_zip(
        self,
        report_paths: List[str],
        output_path: Optional[str] = None
    ) -> str:
        """创建批量报告 ZIP 包"""
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f"batch_reports_{timestamp}.zip")

        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for path in report_paths:
                    if os.path.exists(path):
                        zf.write(path, os.path.basename(path))
            logger.info(f"Batch reports zipped: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to create batch zip: {e}")
            raise

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# 便捷函数
def generate_multi_target_report(
    job_data: Dict[str, Any],
    targets_data: List[Dict[str, Any]],
    interactions_data: Optional[Dict[str, Any]] = None,
    template: str = 'full',
    format: str = 'markdown',
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    便捷函数：生成多靶点批量评估报告

    Args:
        job_data: 任务数据
        targets_data: 靶点数据列表
        interactions_data: 相互作用数据（可选）
        template: 模板名称
        format: 输出格式
        config: 配置字典（可选）

    Returns:
        Dict: 报告数据
    """
    generator = MultiTargetReportGenerator(config)
    return generator.generate_multi_target_report(
        job_data, targets_data, interactions_data, template, format
    )


async def generate_report_async(
    job_data: Dict[str, Any],
    targets_data: List[Dict[str, Any]],
    interactions_data: Optional[Dict[str, Any]] = None,
    template: str = 'full',
    format: str = 'markdown',
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    便捷函数：异步生成多靶点批量评估报告

    Args:
        job_data: 任务数据
        targets_data: 靶点数据列表
        interactions_data: 相互作用数据（可选）
        template: 模板名称
        format: 输出格式
        config: 配置字典（可选）

    Returns:
        Dict: 报告数据
    """
    generator = MultiTargetReportGenerator(config)
    return await generator.generate_report_async(
        job_data, targets_data, interactions_data, template, format
    )
