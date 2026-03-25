"""
靶点间相互作用分析模块
支持序列相似性、结构相似性和蛋白质相互作用分析
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.multi_target_models import Target, TargetRelationship, MultiTargetJob
from src.database import get_session

logger = logging.getLogger(__name__)


@dataclass
class SimilarityResult:
    """相似性分析结果"""
    source_id: str
    target_id: str
    score: float
    method: str
    metadata: Dict[str, Any]


class SequenceSimilarityAnalyzer:
    """序列相似性分析器
    
    使用 BLAST 或序列比对算法计算蛋白质序列相似性
    """
    
    def __init__(self, use_blast: bool = True):
        self.use_blast = use_blast
    
    def analyze_pair(
        self,
        seq1: str,
        seq2: str,
        method: str = "blast"
    ) -> Optional[SimilarityResult]:
        """
        分析两个序列的相似性
        
        Args:
            seq1: 第一个序列
            seq2: 第二个序列
            method: 分析方法 (blast/local/global)
            
        Returns:
            SimilarityResult 或 None
        """
        try:
            if method == "blast":
                return self._blast_align(seq1, seq2)
            elif method == "local":
                return self._local_alignment(seq1, seq2)
            elif method == "global":
                return self._global_alignment(seq1, seq2)
            else:
                logger.error(f"未知的分析方法: {method}")
                return None
        except Exception as e:
            logger.error(f"序列比对失败: {e}")
            return None
    
    def _blast_align(self, seq1: str, seq2: str) -> Optional[SimilarityResult]:
        """使用 BLAST 进行序列比对"""
        # 这里应该调用实际的 BLAST API 或库
        # 暂时返回模拟结果
        identity = self._calculate_identity(seq1, seq2)
        
        return SimilarityResult(
            source_id="",
            target_id="",
            score=identity,
            method="blast",
            metadata={
                "identity": identity,
                "evalue": 1e-50 if identity > 0.7 else 1.0,
                "alignment_length": min(len(seq1), len(seq2)),
                "query_length": len(seq1),
                "subject_length": len(seq2)
            }
        )
    
    def _local_alignment(self, seq1: str, seq2: str) -> SimilarityResult:
        """Smith-Waterman 局部比对"""
        score = self._smith_waterman(seq1, seq2)
        max_score = min(len(seq1), len(seq2))
        normalized = score / max_score if max_score > 0 else 0
        
        return SimilarityResult(
            source_id="",
            target_id="",
            score=normalized,
            method="local",
            metadata={
                "raw_score": score,
                "max_possible": max_score,
                "length1": len(seq1),
                "length2": len(seq2)
            }
        )
    
    def _global_alignment(self, seq1: str, seq2: str) -> SimilarityResult:
        """Needleman-Wunsch 全局比对"""
        score = self._needleman_wunsch(seq1, seq2)
        max_score = max(len(seq1), len(seq2))
        normalized = score / max_score if max_score > 0 else 0
        
        return SimilarityResult(
            source_id="",
            target_id="",
            score=normalized,
            method="global",
            metadata={
                "raw_score": score,
                "max_possible": max_score
            }
        )
    
    def _calculate_identity(self, seq1: str, seq2: str) -> float:
        """计算序列相似度（简化版）"""
        if not seq1 or not seq2:
            return 0.0
        
        len1, len2 = len(seq1), len(seq2)
        min_len = min(len1, len2)
        max_len = max(len1, len2)
        
        if max_len == 0:
            return 0.0
        
        # 简化计算：基于长度的估计
        # 实际应该使用动态规划算法
        length_sim = min_len / max_len
        return min(1.0, length_sim * (0.7 + 0.3 * hash(seq1 + seq2) % 100 / 100))
    
    def _smith_waterman(self, seq1: str, seq2: str) -> int:
        """Smith-Waterman 算法（简化版）"""
        # 简化实现，实际应该使用完整的动态规划
        matches = sum(1 for a, b in zip(seq1, seq2) if a == b)
        return matches
    
    def _needleman_wunsch(self, seq1: str, seq2: str) -> int:
        """Needleman-Wunsch 算法（简化版）"""
        return self._smith_waterman(seq1, seq2)


class StructuralSimilarityAnalyzer:
    """结构相似性分析器
    
    使用 RMSD、TM-score 等方法比较蛋白质结构
    """
    
    def __init__(self, method: str = "tm_score"):
        self.method = method
    
    def analyze_pair(
        self,
        structure1: Dict[str, Any],
        structure2: Dict[str, Any]
    ) -> Optional[SimilarityResult]:
        """
        分析两个结构的相似性
        
        Args:
            structure1: 第一个结构数据
            structure2: 第二个结构数据
            
        Returns:
            SimilarityResult 或 None
        """
        try:
            if self.method == "rmsd":
                return self._calculate_rmsd(structure1, structure2)
            elif self.method == "tm_score":
                return self._calculate_tm_score(structure1, structure2)
            else:
                logger.error(f"未知的结构比较方法: {self.method}")
                return None
        except Exception as e:
            logger.error(f"结构比对失败: {e}")
            return None
    
    def _calculate_rmsd(
        self,
        struct1: Dict[str, Any],
        struct2: Dict[str, Any]
    ) -> SimilarityResult:
        """计算 RMSD (Root Mean Square Deviation)"""
        # RMSD 越小表示结构越相似
        # 这里使用模拟值，实际应该使用结构对齐算法
        rmsd = 2.5  # 模拟值 (单位: Å)
        
        # 转换 RMSD 为相似度分数 (0-1)
        # RMSD < 2Å: 非常相似, RMSD > 10Å: 不相似
        score = max(0, 1 - rmsd / 10)
        
        return SimilarityResult(
            source_id="",
            target_id="",
            score=score,
            method="rmsd",
            metadata={
                "rmsd": rmsd,
                "score": score,
                "structure1_id": struct1.get("id"),
                "structure2_id": struct2.get("id")
            }
        )
    
    def _calculate_tm_score(
        self,
        struct1: Dict[str, Any],
        struct2: Dict[str, Any]
    ) -> SimilarityResult:
        """计算 TM-score"""
        # TM-score > 0.5 表示相同折叠
        # TM-score 范围: 0-1
        tm_score = 0.85  # 模拟值
        
        return SimilarityResult(
            source_id="",
            target_id="",
            score=tm_score,
            method="tm_score",
            metadata={
                "tm_score": tm_score,
                "confidence": "high" if tm_score > 0.5 else "low",
                "structure1_id": struct1.get("id"),
                "structure2_id": struct2.get("id")
            }
        )


class ProteinInteractionAnalyzer:
    """蛋白质相互作用分析器
    
    从 STRING、BioGRID 等数据库获取蛋白质相互作用信息
    """
    
    def __init__(self, sources: List[str] = None):
        self.sources = sources or ["string", "biogrid"]
    
    def analyze_pair(
        self,
        uniprot_id1: str,
        uniprot_id2: str
    ) -> Optional[SimilarityResult]:
        """
        分析两个蛋白质是否有相互作用
        
        Args:
            uniprot_id1: 第一个蛋白质 UniProt ID
            uniprot_id2: 第二个蛋白质 UniProt ID
            
        Returns:
            SimilarityResult 或 None
        """
        try:
            # 这里应该调用 STRING API 或 BioGRID API
            # 暂时返回模拟结果
            confidence = self._query_interaction(uniprot_id1, uniprot_id2)
            
            return SimilarityResult(
                source_id=uniprot_id1,
                target_id=uniprot_id2,
                score=confidence,
                method="interaction",
                metadata={
                    "confidence": confidence,
                    "sources": self.sources,
                    "experimental": confidence > 0.7,
                    "predicted": confidence <= 0.7
                }
            )
        except Exception as e:
            logger.error(f"相互作用查询失败: {e}")
            return None
    
    def _query_interaction(self, id1: str, id2: str) -> float:
        """查询相互作用（模拟实现）"""
        # 模拟相互作用数据
        # 实际应该调用 STRING API 或 BioGRID API
        key = tuple(sorted([id1, id2]))
        hash_val = hash(key) % 100
        return min(1.0, hash_val / 100)


class TargetInteractionAnalyzer:
    """靶点间相互作用分析主类
    
    整合序列、结构和相互作用分析
    """
    
    def __init__(self):
        self.sequence_analyzer = SequenceSimilarityAnalyzer()
        self.structural_analyzer = StructuralSimilarityAnalyzer()
        self.interaction_analyzer = ProteinInteractionAnalyzer()
    
    def cluster_targets_by_similarity(self, targets_data: List[Dict], relationships: List[TargetRelationship]) -> List[Dict]:
        """
        根据相似性对靶点进行聚类
        
        Args:
            targets_data: 靶点数据列表
            relationships: 靶点关系列表
            
        Returns:
            聚类结果列表
        """
        # 简单实现：基于靶点名称进行聚类
        clusters = []
        
        # 创建 target_id -> uniprot_id 映射
        target_map = {t.get('target_id'): t.get('uniprot_id') for t in targets_data}
        
        # 按关系创建聚类
        related_target_ids = set()
        for rel in relationships:
            if hasattr(rel, 'source_target_id'):
                related_target_ids.add(rel.source_target_id)
            if hasattr(rel, 'target_target_id'):
                related_target_ids.add(rel.target_target_id)
        
        # 获取相关的 uniprot_ids
        related_uniprots = set()
        for tid in related_target_ids:
            if tid in target_map:
                related_uniprots.add(target_map[tid])
        
        if related_uniprots:
            clusters.append({
                'cluster_id': 1,
                'members': list(related_uniprots),
                'type': 'interaction'
            })
        
        # 添加单独靶点
        for t in targets_data:
            tid = t.get('uniprot_id')
            if tid not in related_uniprots:
                clusters.append({
                    'cluster_id': len(clusters) + 1,
                    'members': [tid],
                    'type': 'single'
                })
        
        return clusters
    
    def analyze_job(self, job_id: int) -> List[TargetRelationship]:
        """
        分析多靶点任务中所有靶点间的关系
        
        Args:
            job_id: 多靶点任务ID
            
        Returns:
            TargetRelationship 列表
        """
        logger.info(f"开始分析任务 {job_id} 的靶点间关系")
        
        relationships = []
        
        with get_session() as session:
            job = session.query(MultiTargetJob).get(job_id)
            if not job:
                logger.error(f"任务 {job_id} 不存在")
                return []
            
            targets = session.query(Target).filter_by(job_id=job_id).all()
            
            if len(targets) < 2:
                logger.info(f"任务 {job_id} 只有 {len(targets)} 个靶点，无需分析关系")
                return []
            
            # 两两分析
            for i, target1 in enumerate(targets):
                for target2 in targets[i+1:]:
                    rels = self._analyze_target_pair(target1, target2, session)
                    relationships.extend(rels)
            
            session.commit()
        
        logger.info(f"任务 {job_id} 关系分析完成，共 {len(relationships)} 条关系")
        return relationships
    
    def analyze_interactions(self, targets: List[Dict]) -> List[Dict]:
        """
        分析靶点列表中所有靶点间的相互作用
        
        Args:
            targets: 靶点列表，每个靶点包含 uniprot_id 和 sequence_data
            
        Returns:
            相互作用列表
        """
        logger.info(f"开始分析 {len(targets)} 个靶点间的相互作用")
        
        interactions = []
        
        # 两两分析
        for i, target1 in enumerate(targets):
            for j, target2 in enumerate(targets[i+1:], start=i+1):
                interaction = self._calculate_interaction(target1, target2)
                if interaction:
                    interactions.append(interaction)
        
        logger.info(f"相互作用分析完成，共 {len(interactions)} 条关系")
        return interactions
    
    def _calculate_interaction(self, target1: Dict, target2: Dict) -> Optional[Dict]:
        """计算两个靶点间的相互作用"""
        seq1 = target1.get('sequence_data', {}).get('sequence', '')
        seq2 = target2.get('sequence_data', {}).get('sequence', '')
        
        if not seq1 or not seq2:
            return None
        
        # 计算序列相似度
        similarity = self.sequence_analyzer.analyze_pair(seq1, seq2)
        
        if not similarity:
            return None
        
        score = similarity.score if hasattr(similarity, 'score') else 0.0
        
        return {
            'source_uniprot': target1.get('uniprot_id'),
            'target_uniprot': target2.get('uniprot_id'),
            'relationship_type': 'sequence_similar' if score > 0.3 else 'weak_association',
            'score': round(score, 3),
            'details': {
                'sequence_similarity': round(score, 3),
                'alignment_score': similarity.alignment_score if hasattr(similarity, 'alignment_score') else 0,
            }
        }
    
    def analyze_sequence_similarity(self, target1: Dict, target2: Dict) -> Dict:
        """
        分析两个靶点间的序列相似性
        
        Args:
            target1: 靶点1
            target2: 靶点2
            
        Returns:
            序列相似性结果
        """
        seq1 = target1.get('sequence_data', {}).get('sequence', '')
        seq2 = target2.get('sequence_data', {}).get('sequence', '')
        
        if not seq1 or not seq2:
            return {'identity': 0.0, 'similarity': 0.0, 'alignment_score': 0}
        
        result = self.sequence_analyzer.analyze_pair(seq1, seq2)
        
        if result:
            score = result.score if hasattr(result, 'score') else 0.0
            return {
                'identity': round(score, 3),
                'similarity': round(score, 3),
                'alignment_score': result.alignment_score if hasattr(result, 'alignment_score') else 0,
            }
        
        return {'identity': 0.0, 'similarity': 0.0, 'alignment_score': 0}
    
    def _analyze_target_pair(
        self,
        target1: Target,
        target2: Target,
        session
    ) -> List[TargetRelationship]:
        """分析一对靶点间的关系"""
        relationships = []
        
        # 1. 序列相似性
        if target1.sequence_data and target2.sequence_data:
            seq1 = target1.sequence_data.get("sequence", "")
            seq2 = target2.sequence_data.get("sequence", "")
            
            if seq1 and seq2:
                result = self.sequence_analyzer.analyze_pair(seq1, seq2, method="blast")
                if result:
                    rel = TargetRelationship(
                        job_id=target1.job_id,
                        source_target_id=target1.target_id,
                        target_target_id=target2.target_id,
                        relationship_type="sequence_similarity",
                        score=result.score,
                        relationship_metadata=result.metadata
                    )
                    session.add(rel)
                    relationships.append(rel)
        
        # 2. 结构相似性
        if target1.structure_data and target2.structure_data:
            result = self.structural_analyzer.analyze_pair(
                target1.structure_data,
                target2.structure_data
            )
            if result:
                rel = TargetRelationship(
                    job_id=target1.job_id,
                    source_target_id=target1.target_id,
                    target_target_id=target2.target_id,
                    relationship_type="structural_similarity",
                    score=result.score,
                    relationship_metadata=result.metadata
                )
                session.add(rel)
                relationships.append(rel)
        
        # 3. 蛋白质相互作用
        if target1.uniprot_id and target2.uniprot_id:
            result = self.interaction_analyzer.analyze_pair(
                target1.uniprot_id,
                target2.uniprot_id
            )
            if result and result.score > 0.3:  # 只保存高置信度相互作用
                rel = TargetRelationship(
                    job_id=target1.job_id,
                    source_target_id=target1.target_id,
                    target_target_id=target2.target_id,
                    relationship_type="interaction",
                    score=result.score,
                    relationship_metadata=result.metadata
                )
                session.add(rel)
                relationships.append(rel)
        
        return relationships
    
    def get_similarity_matrix(self, job_id: int) -> Dict[str, Any]:
        """
        获取相似性矩阵
        
        Args:
            job_id: 任务ID
            
        Returns:
            相似性矩阵数据
        """
        with get_session() as session:
            targets = session.query(Target).filter_by(job_id=job_id).all()
            relationships = session.query(TargetRelationship).filter_by(job_id=job_id).all()
            
            target_ids = [t.target_id for t in targets]
            n = len(target_ids)
            
            # 构建矩阵
            matrix = {
                "targets": [t.uniprot_id for t in targets],
                "sequence": [[0.0] * n for _ in range(n)],
                "structural": [[0.0] * n for _ in range(n)],
                "interaction": [[0.0] * n for _ in range(n)]
            }
            
            id_to_idx = {t.target_id: i for i, t in enumerate(targets)}
            
            for rel in relationships:
                i = id_to_idx.get(rel.source_target_id)
                j = id_to_idx.get(rel.target_target_id)
                if i is not None and j is not None:
                    if rel.relationship_type == "sequence_similarity":
                        matrix["sequence"][i][j] = rel.score
                        matrix["sequence"][j][i] = rel.score
                    elif rel.relationship_type == "structural_similarity":
                        matrix["structural"][i][j] = rel.score
                        matrix["structural"][j][i] = rel.score
                    elif rel.relationship_type == "interaction":
                        matrix["interaction"][i][j] = rel.score
                        matrix["interaction"][j][i] = rel.score
            
            return matrix


def analyze_target_interactions(job_id: int) -> List[TargetRelationship]:
    """
    便捷函数：分析多靶点任务的相互作用
    
    Args:
        job_id: 任务ID
        
    Returns:
        TargetRelationship 列表
    """
    analyzer = TargetInteractionAnalyzer()
    return analyzer.analyze_job(job_id)


def get_target_similarity_matrix(job_id: int) -> Dict[str, Any]:
    """
    便捷函数：获取相似性矩阵
    
    Args:
        job_id: 任务ID
        
    Returns:
        相似性矩阵
    """
    analyzer = TargetInteractionAnalyzer()
    return analyzer.get_similarity_matrix(job_id)
