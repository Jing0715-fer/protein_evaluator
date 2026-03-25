"""
多靶点模型单元测试
测试 MultiTargetJob, Target, TargetRelationship 模型
"""

import pytest
from datetime import datetime
from src.multi_target_models import MultiTargetJob, Target, TargetRelationship


class TestMultiTargetJob:
    """测试多靶点任务模型"""
    
    def test_job_creation(self):
        """测试基本任务创建"""
        job = MultiTargetJob(
            name="测试任务",
            description="测试描述",
            target_count=5,
            evaluation_mode="parallel",
            priority=8,
            status="pending"
        )
        assert job.name == "测试任务"
        assert job.description == "测试描述"
        assert job.target_count == 5
        assert job.evaluation_mode == "parallel"
        assert job.priority == 8
        assert job.status == "pending"
    
    def test_job_to_dict(self):
        """测试任务序列化"""
        job = MultiTargetJob(
            name="测试任务",
            description="测试描述",
            target_count=3,
            tags={"project": "test"},
            config={"timeout": 3600}
        )
        data = job.to_dict()
        assert data["name"] == "测试任务"
        assert data["target_count"] == 3
        assert data["tags"] == {"project": "test"}
        assert data["config"] == {"timeout": 3600}
        assert "job_id" in data
        assert "created_at" in data


class TestTarget:
    """测试靶点模型"""
    
    def test_target_creation(self):
        """测试基本靶点创建"""
        target = Target(
            job_id=1,
            target_index=0,
            uniprot_id="P12345",
            protein_name="Test Protein",
            gene_name="TEST",
            structure_source="alphafold",
            weight=1.0,
            status="pending"
        )
        assert target.uniprot_id == "P12345"
        assert target.target_index == 0
        assert target.structure_source == "alphafold"
        assert target.weight == 1.0
        assert target.status == "pending"
    
    def test_target_to_dict(self):
        """测试靶点序列化"""
        target = Target(
            job_id=1,
            target_index=1,
            uniprot_id="P67890",
            protein_name="Another Protein",
            structure_source="pdb",
            structure_id="1ABC",
            sequence_data={"sequence": "MKT..."}
        )
        data = target.to_dict()
        assert data["uniprot_id"] == "P67890"
        assert data["structure_source"] == "pdb"
        assert data["sequence_data"] == {"sequence": "MKT..."}


class TestTargetRelationship:
    """测试靶点关系模型"""
    
    def test_relationship_creation(self):
        """测试基本关系创建"""
        rel = TargetRelationship(
            job_id=1,
            source_target_id=1,
            target_target_id=2,
            relationship_type="sequence_similarity",
            score=0.85
        )
        assert rel.relationship_type == "sequence_similarity"
        assert rel.score == 0.85
        assert rel.source_target_id == 1
        assert rel.target_target_id == 2
    
    def test_relationship_with_metadata(self):
        """测试带元数据的关系"""
        rel = TargetRelationship(
            job_id=1,
            source_target_id=1,
            target_target_id=2,
            relationship_type="structural_similarity",
            score=0.92,
            relationship_metadata={"rmsd": 2.5, "tm_score": 0.92}
        )
        assert rel.relationship_metadata["rmsd"] == 2.5
        assert rel.relationship_metadata["tm_score"] == 0.92


class TestModelIntegration:
    """测试模型集成"""
    
    def test_job_targets_relationship(self):
        """测试任务和靶点关系"""
        # 注意：这里只是测试对象属性，不涉及数据库
        job = MultiTargetJob(name="集成测试")
        target1 = Target(job_id=1, target_index=0, uniprot_id="P1")
        target2 = Target(job_id=1, target_index=1, uniprot_id="P2")
        
        # 在实际数据库中，job.targets 会自动关联
        # 这里我们只是验证对象可以正确创建
        assert target1.job_id == target2.job_id
