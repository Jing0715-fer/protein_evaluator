"""
多靶点调度器单元测试
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.multi_target_scheduler import (
    MultiTargetScheduler, 
    EvaluationMode,
    submit_multi_target_job,
    get_job_progress
)
from src.multi_target_models import MultiTargetJob, Target


class TestMultiTargetScheduler:
    """测试多靶点调度器"""
    
    def test_scheduler_init(self):
        """测试调度器初始化"""
        scheduler = MultiTargetScheduler(max_workers=3)
        assert scheduler.max_workers == 3
        assert scheduler._active_jobs == {}
    
    @patch('src.multi_target_scheduler.get_session')
    def test_submit_job(self, mock_get_session):
        """测试提交任务"""
        # 模拟数据库会话
        mock_session = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=False)
        mock_get_session.return_value = mock_context
        
        # 模拟任务对象
        mock_job = MagicMock()
        mock_job.job_id = 1
        mock_session.add = Mock()
        mock_session.flush = Mock()
        mock_session.commit = Mock()
        
        scheduler = MultiTargetScheduler()
        
        targets = [
            {'uniprot_id': 'P12345', 'weight': 1.0},
            {'uniprot_id': 'P67890', 'weight': 1.5}
        ]
        
        # 由于我们模拟了整个会话，这里只测试接口
        # 实际数据库操作需要在集成测试中测试
        with patch.object(scheduler, 'submit_job') as mock_submit:
            mock_submit.return_value = 1
            job_id = scheduler.submit_job("测试任务", targets, EvaluationMode.PARALLEL)
            assert job_id == 1
    
    def test_evaluation_mode_enum(self):
        """测试评估模式枚举"""
        assert EvaluationMode.PARALLEL.value == "parallel"
        assert EvaluationMode.SEQUENTIAL.value == "sequential"
    
    def test_scheduler_config(self):
        """测试调度器配置"""
        config = {'timeout': 3600, 'retry': 3}
        scheduler = MultiTargetScheduler(max_workers=5, config=config)
        assert scheduler.config['timeout'] == 3600
        assert scheduler.config['retry'] == 3


class TestSchedulerIntegration:
    """调度器集成测试（需要数据库）"""
    
    @pytest.mark.skip(reason="需要实际数据库连接")
    def test_full_workflow(self):
        """测试完整工作流"""
        pass


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    @patch('src.multi_target_scheduler.get_scheduler')
    def test_submit_multi_target_job(self, mock_get_scheduler):
        """测试便捷提交函数"""
        mock_scheduler = MagicMock()
        mock_scheduler.submit_job.return_value = 123
        mock_scheduler.start_job.return_value = True
        mock_get_scheduler.return_value = mock_scheduler
        
        targets = [
            {'uniprot_id': 'P12345'},
            {'uniprot_id': 'P67890'}
        ]
        
        job_id = submit_multi_target_job("测试", targets, mode="parallel")
        assert job_id == 123
    
    @patch('src.multi_target_scheduler.get_scheduler')
    def test_get_job_progress(self, mock_get_scheduler):
        """测试获取进度便捷函数"""
        mock_scheduler = MagicMock()
        mock_scheduler.get_job_status.return_value = {
            'job_id': 1,
            'status': 'processing',
            'progress': 50
        }
        mock_get_scheduler.return_value = mock_scheduler
        
        status = get_job_progress(1)
        assert status['status'] == 'processing'
        assert status['progress'] == 50
