"""
多靶点批量报告生成器测试

测试覆盖：
1. 报告生成基本功能
2. 不同模板类型
3. 多格式导出
4. 统计数据计算
5. 异步生成
"""

import pytest
import json
import os
import tempfile
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch

from src.multi_target_report_generator import (
    MultiTargetReportGenerator,
    ReportTemplate,
    BatchReportMetadata,
    generate_multi_target_report,
    generate_report_async
)


class TestMultiTargetReportGenerator:
    """多靶点报告生成器测试类"""

    @pytest.fixture
    def generator(self):
        """创建报告生成器实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'output_dir': tmpdir, 'max_workers': 2}
            yield MultiTargetReportGenerator(config)

    @pytest.fixture
    def sample_job_data(self):
        """示例任务数据"""
        return {
            'job_id': 1,
            'name': '测试批量评估任务',
            'description': '测试用多靶点评估任务',
            'status': 'completed',
            'created_at': datetime.now().isoformat()
        }

    @pytest.fixture
    def sample_targets_data(self):
        """示例靶点数据"""
        return [
            {
                'target_id': 1,
                'uniprot_id': 'P12345',
                'protein_name': '测试蛋白1',
                'gene_name': 'TEST1',
                'status': 'completed',
                'structure_source': 'alphafold',
                'structure_id': 'AF-P12345',
                'evaluation_score': 0.85,
                'weight': 1.0,
                'completed_at': datetime.now().isoformat()
            },
            {
                'target_id': 2,
                'uniprot_id': 'P67890',
                'protein_name': '测试蛋白2',
                'gene_name': 'TEST2',
                'status': 'completed',
                'structure_source': 'pdb',
                'structure_id': '6ABC',
                'evaluation_score': 0.72,
                'weight': 1.0,
                'completed_at': datetime.now().isoformat()
            },
            {
                'target_id': 3,
                'uniprot_id': 'P11111',
                'protein_name': '测试蛋白3',
                'gene_name': 'TEST3',
                'status': 'failed',
                'structure_source': 'emdb',
                'structure_id': 'EMD-1234',
                'error_message': '结构数据获取失败'
            }
        ]

    @pytest.fixture
    def sample_interactions_data(self):
        """示例相互作用数据"""
        return {
            'interactions': [
                {
                    'source_uniprot': 'P12345',
                    'target_uniprot': 'P67890',
                    'relationship_type': 'sequence_similarity',
                    'score': 0.65
                },
                {
                    'source_uniprot': 'P12345',
                    'target_uniprot': 'P11111',
                    'relationship_type': 'structural_similarity',
                    'score': 0.45
                }
            ],
            'clusters': [
                {
                    'targets': ['P12345', 'P67890'],
                    'type': 'sequence_similarity',
                    'avg_similarity': 0.65
                }
            ]
        }

    def test_initialization(self, generator):
        """测试初始化"""
        assert generator.output_dir is not None
        assert generator.max_workers == 2
        assert len(generator.templates) == 4
        assert 'full' in generator.templates
        assert 'summary' in generator.templates

    def test_report_template_dataclass(self):
        """测试报告模板数据类"""
        template = ReportTemplate(
            name='测试模板',
            sections=['summary', 'targets'],
            include_summary=True,
            include_details=False
        )
        assert template.name == '测试模板'
        assert template.sections == ['summary', 'targets']
        assert template.include_summary is True
        assert template.include_details is False

    def test_generate_multi_target_report_full_template(self, generator, sample_job_data, sample_targets_data):
        """测试生成完整模板报告"""
        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template='full',
            format='markdown'
        )

        assert 'content' in result
        assert 'metadata' in result
        assert 'statistics' in result
        assert 'charts_data' in result

        # 验证内容
        content = result['content']
        assert '多靶点蛋白质评估报告' in content
        assert 'P12345' in content
        assert 'P67890' in content

        # 验证统计数据
        stats = result['statistics']
        assert stats['total'] == 3
        assert stats['completed'] == 2
        assert stats['failed'] == 1

    def test_generate_multi_target_report_summary_template(self, generator, sample_job_data, sample_targets_data):
        """测试生成摘要模板报告"""
        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template='summary',
            format='markdown'
        )

        content = result['content']
        # 摘要模板不包含详细信息
        assert '执行摘要' in content
        assert '统计信息' in content

    def test_generate_multi_target_report_english(self, generator, sample_job_data, sample_targets_data):
        """测试英文报告生成"""
        template = ReportTemplate(
            name='Full Report',
            sections=['summary'],
            include_summary=True,
            language='en'
        )

        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template=template,
            format='markdown'
        )

        content = result['content']
        assert 'Multi-Target Protein Evaluation Report' in content

    def test_calculate_statistics(self, generator, sample_targets_data):
        """测试统计数据计算"""
        stats = generator._calculate_statistics(sample_targets_data)

        assert stats['total'] == 3
        assert stats['completed'] == 2
        assert stats['failed'] == 1
        assert stats['processing'] == 0
        assert stats['success_rate'] == 66.66666666666666

        # 验证评分统计
        assert stats['avg_score'] is not None
        assert stats['min_score'] == 0.72
        assert stats['max_score'] == 0.85
        assert stats['high_quality_count'] == 1  # 只有 P12345 >= 0.8

        # 验证分布
        assert stats['score_distribution']['0.8-1.0'] == 1
        assert stats['score_distribution']['0.6-0.8'] == 1

    def test_calculate_statistics_empty_list(self, generator):
        """测试空列表统计"""
        stats = generator._calculate_statistics([])
        assert stats['total'] == 0
        assert stats['avg_score'] is None
        assert stats['success_rate'] == 0

    def test_generate_charts_data(self, generator, sample_targets_data):
        """测试图表数据生成"""
        stats = generator._calculate_statistics(sample_targets_data)
        charts = generator._generate_charts_data(stats, sample_targets_data)

        assert 'status_distribution' in charts
        assert 'score_distribution' in charts
        assert 'source_distribution' in charts

        assert 'labels' in charts['status_distribution']
        assert 'data' in charts['status_distribution']

    def test_export_to_json(self, generator, sample_job_data, sample_targets_data):
        """测试 JSON 导出"""
        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template='full',
            format='json'
        )

        output_path = generator.export_to_json(result)

        assert os.path.exists(output_path)
        assert output_path.endswith('.json')

        # 验证 JSON 内容
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert 'content' in data
            assert 'metadata' in data
            assert 'statistics' in data

    def test_export_to_markdown(self, generator, sample_job_data, sample_targets_data):
        """测试 Markdown 导出"""
        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template='full',
            format='markdown'
        )

        output_path = generator.export_to_markdown(result)

        assert os.path.exists(output_path)
        assert output_path.endswith('.md')

        # 验证内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert '# 多靶点蛋白质评估报告' in content

    @pytest.mark.skipif(
        not pytest.importorskip('pandas', reason='pandas not installed'),
        reason='pandas not installed'
    )
    def test_export_to_excel(self, generator, sample_job_data, sample_targets_data):
        """测试 Excel 导出"""
        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template='full',
            format='excel'
        )

        try:
            output_path = generator.export_to_excel(result)
            assert os.path.exists(output_path)
            assert output_path.endswith('.xlsx')
        except ImportError:
            pytest.skip('openpyxl not installed')

    def test_generate_with_interactions(self, generator, sample_job_data, sample_targets_data, sample_interactions_data):
        """测试带相互作用的报告生成"""
        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            interactions_data=sample_interactions_data,
            template='full',
            format='markdown'
        )

        content = result['content']
        assert '靶点间相互作用分析' in content
        assert 'P12345' in content
        assert 'P67890' in content
        assert 'sequence_similarity' in content

    def test_convenience_function(self, sample_job_data, sample_targets_data):
        """测试便捷函数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'output_dir': tmpdir}
            result = generate_multi_target_report(
                sample_job_data,
                sample_targets_data,
                template='summary',
                format='markdown',
                config=config
            )

            assert 'content' in result
            assert 'metadata' in result

    @pytest.mark.asyncio
    async def test_generate_report_async(self, generator, sample_job_data, sample_targets_data):
        """测试异步报告生成"""
        result = await generator.generate_report_async(
            sample_job_data,
            sample_targets_data,
            template='full',
            format='markdown'
        )

        assert 'content' in result
        assert 'output_path' in result
        assert os.path.exists(result['output_path'])

    def test_custom_template(self, generator, sample_job_data, sample_targets_data):
        """测试自定义模板"""
        custom_template = ReportTemplate(
            name='自定义模板',
            sections=['summary', 'statistics'],
            include_summary=True,
            include_details=False,
            include_interactions=False,
            include_charts=False
        )

        result = generator.generate_multi_target_report(
            sample_job_data,
            sample_targets_data,
            template=custom_template,
            format='markdown'
        )

        content = result['content']
        # 自定义模板不应包含靶点详情
        assert '靶点详情' not in content
        assert '执行摘要' in content

    def test_report_with_different_structure_sources(self, generator):
        """测试不同结构来源的靶点"""
        targets = [
            {'uniprot_id': 'P1', 'status': 'completed', 'structure_source': 'alphafold', 'evaluation_score': 0.8},
            {'uniprot_id': 'P2', 'status': 'completed', 'structure_source': 'pdb', 'evaluation_score': 0.7},
            {'uniprot_id': 'P3', 'status': 'completed', 'structure_source': 'emdb', 'evaluation_score': 0.6},
        ]

        job_data = {'job_id': 1, 'name': 'Test'}
        result = generator.generate_multi_target_report(job_data, targets)

        stats = result['statistics']
        assert 'alphafold' in stats['by_structure_source']
        assert 'pdb' in stats['by_structure_source']
        assert 'emdb' in stats['by_structure_source']

    def test_report_with_missing_optional_fields(self, generator):
        """测试缺少可选字段的靶点"""
        targets = [
            {'uniprot_id': 'P1', 'status': 'completed'},  # 缺少 evaluation_score
            {'uniprot_id': 'P2', 'status': 'pending'},     # 缺少 structure_source
        ]

        job_data = {'job_id': 1, 'name': 'Test'}
        result = generator.generate_multi_target_report(job_data, targets)

        assert result['statistics']['total'] == 2

    def test_create_batch_zip(self, generator, sample_job_data, sample_targets_data):
        """测试批量 ZIP 包创建"""
        import zipfile

        # 生成多个报告
        result1 = generator.generate_multi_target_report(sample_job_data, sample_targets_data)
        path1 = generator.export_to_markdown(result1)

        result2 = generator.generate_multi_target_report(sample_job_data, sample_targets_data)
        path2 = generator.export_to_json(result2)

        # 创建 ZIP
        zip_path = generator.create_batch_zip([path1, path2])

        assert os.path.exists(zip_path)
        assert zipfile.is_zipfile(zip_path)

        # 验证 ZIP 内容
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            assert len(names) == 2


class TestReportMetadata:
    """报告元数据测试类"""

    def test_batch_report_metadata(self):
        """测试报告元数据"""
        metadata = BatchReportMetadata(
            report_id='RPT_20240314_120000_1',
            job_id=1,
            job_name='测试任务',
            created_at=datetime.now(),
            target_count=10,
            completed_count=8,
            failed_count=2,
            format='markdown'
        )

        assert metadata.report_id.startswith('RPT_')
        assert metadata.job_id == 1
        assert metadata.target_count == 10

    def test_batch_report_metadata_with_optional_fields(self):
        """测试带可选字段的元数据"""
        metadata = BatchReportMetadata(
            report_id='RPT_001',
            job_id=1,
            job_name='Test',
            created_at=datetime.now(),
            target_count=5,
            completed_count=5,
            failed_count=0,
            format='pdf',
            file_size=1024,
            download_url='http://example.com/report.pdf'
        )

        assert metadata.file_size == 1024
        assert metadata.download_url == 'http://example.com/report.pdf'
