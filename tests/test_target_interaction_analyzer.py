"""
靶点间相互作用分析单元测试
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.target_interaction_analyzer import (
    SequenceSimilarityAnalyzer,
    StructuralSimilarityAnalyzer,
    ProteinInteractionAnalyzer,
    TargetInteractionAnalyzer,
    SimilarityResult,
    analyze_target_interactions,
    get_target_similarity_matrix
)


class TestSequenceSimilarityAnalyzer:
    """测试序列相似性分析器"""
    
    def test_analyzer_init(self):
        """测试初始化"""
        analyzer = SequenceSimilarityAnalyzer(use_blast=True)
        assert analyzer.use_blast is True
    
    def test_calculate_identity(self):
        """测试相似度计算"""
        analyzer = SequenceSimilarityAnalyzer()
        
        # 相同序列
        score = analyzer._calculate_identity("MKT", "MKT")
        assert score > 0.5
        
        # 不同长度
        score = analyzer._calculate_identity("MKT", "MKTL")
        assert 0 < score <= 1
        
        # 空序列
        score = analyzer._calculate_identity("", "MKT")
        assert score == 0.0
    
    def test_local_alignment(self):
        """测试局部比对"""
        analyzer = SequenceSimilarityAnalyzer()
        result = analyzer._local_alignment("MKTLL", "MKT")
        
        assert result is not None
        assert result.method == "local"
        assert 0 <= result.score <= 1
    
    def test_global_alignment(self):
        """测试全局比对"""
        analyzer = SequenceSimilarityAnalyzer()
        result = analyzer._global_alignment("MKT", "MKTLL")
        
        assert result is not None
        assert result.method == "global"
        assert 0 <= result.score <= 1


class TestStructuralSimilarityAnalyzer:
    """测试结构相似性分析器"""
    
    def test_analyzer_init(self):
        """测试初始化"""
        analyzer = StructuralSimilarityAnalyzer(method="rmsd")
        assert analyzer.method == "rmsd"
    
    def test_calculate_rmsd(self):
        """测试 RMSD 计算"""
        analyzer = StructuralSimilarityAnalyzer(method="rmsd")
        struct1 = {"id": "1ABC", "atoms": []}
        struct2 = {"id": "1DEF", "atoms": []}
        
        result = analyzer._calculate_rmsd(struct1, struct2)
        
        assert result is not None
        assert result.method == "rmsd"
        assert "rmsd" in result.metadata
        assert 0 <= result.score <= 1
    
    def test_calculate_tm_score(self):
        """测试 TM-score 计算"""
        analyzer = StructuralSimilarityAnalyzer(method="tm_score")
        struct1 = {"id": "1ABC"}
        struct2 = {"id": "1DEF"}
        
        result = analyzer._calculate_tm_score(struct1, struct2)
        
        assert result is not None
        assert result.method == "tm_score"
        assert "tm_score" in result.metadata


class TestProteinInteractionAnalyzer:
    """测试蛋白质相互作用分析器"""
    
    def test_analyzer_init(self):
        """测试初始化"""
        analyzer = ProteinInteractionAnalyzer(sources=["string"])
        assert "string" in analyzer.sources
    
    def test_query_interaction(self):
        """测试相互作用查询"""
        analyzer = ProteinInteractionAnalyzer()
        confidence = analyzer._query_interaction("P12345", "P67890")
        
        assert 0 <= confidence <= 1
    
    def test_analyze_pair(self):
        """测试配对分析"""
        analyzer = ProteinInteractionAnalyzer()
        result = analyzer.analyze_pair("P12345", "P67890")
        
        assert result is not None
        assert result.method == "interaction"
        assert result.source_id == "P12345"
        assert result.target_id == "P67890"


class TestTargetInteractionAnalyzer:
    """测试靶点间相互作用分析主类"""
    
    def test_analyzer_init(self):
        """测试初始化"""
        analyzer = TargetInteractionAnalyzer()
        assert analyzer.sequence_analyzer is not None
        assert analyzer.structural_analyzer is not None
        assert analyzer.interaction_analyzer is not None


class TestSimilarityResult:
    """测试相似性结果数据类"""
    
    def test_result_creation(self):
        """测试结果创建"""
        result = SimilarityResult(
            source_id="P12345",
            target_id="P67890",
            score=0.85,
            method="blast",
            metadata={"identity": 0.85}
        )
        
        assert result.source_id == "P12345"
        assert result.target_id == "P67890"
        assert result.score == 0.85
        assert result.method == "blast"


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    @patch('src.target_interaction_analyzer.TargetInteractionAnalyzer')
    def test_analyze_target_interactions(self, mock_analyzer_class):
        """测试便捷函数"""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_job.return_value = []
        mock_analyzer_class.return_value = mock_analyzer
        
        result = analyze_target_interactions(1)
        assert result == []
    
    @patch('src.target_interaction_analyzer.TargetInteractionAnalyzer')
    def test_get_target_similarity_matrix(self, mock_analyzer_class):
        """测试获取相似性矩阵便捷函数"""
        mock_analyzer = MagicMock()
        mock_analyzer.get_similarity_matrix.return_value = {
            "targets": ["P1", "P2"],
            "sequence": [[0, 0.5], [0.5, 0]]
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        result = get_target_similarity_matrix(1)
        assert "targets" in result
        assert "sequence" in result
