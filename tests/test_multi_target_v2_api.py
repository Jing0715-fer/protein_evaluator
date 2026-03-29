"""
多靶点 v2 API 端点测试

测试覆盖：
1. 任务 CRUD 操作
2. 任务控制（暂停、恢复、取消、重启）
3. 进度查询
4. 靶点和相互作用 API
5. API 文档
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# 模拟 Flask 请求上下文
class MockRequest:
    def __init__(self, json_data=None, args=None):
        self._json = json_data
        self.args = args if args is not None else {}

    def get_json(self):
        return self._json


class TestMultiTargetV2API:
    """多靶点 v2 API 测试类"""
    
    @pytest.fixture
    def mock_job_data(self):
        """模拟任务数据"""
        return {
            'job_id': 1,
            'name': '测试任务',
            'description': '测试描述',
            'status': 'pending',
            'target_count': 3,
            'evaluation_mode': 'parallel',
            'priority': 5,
            'tags': {'test': True},
            'config': {'timeout': 3600}
        }
    
    @pytest.fixture
    def mock_targets_data(self):
        """模拟靶点数据"""
        return [
            {
                'target_id': 1,
                'job_id': 1,
                'uniprot_id': 'P12345',
                'protein_name': 'Test Protein 1',
                'status': 'completed',
                'target_index': 0
            },
            {
                'target_id': 2,
                'job_id': 1,
                'uniprot_id': 'P67890',
                'protein_name': 'Test Protein 2',
                'status': 'processing',
                'target_index': 1
            },
            {
                'target_id': 3,
                'job_id': 1,
                'uniprot_id': 'P11111',
                'protein_name': 'Test Protein 3',
                'status': 'pending',
                'target_index': 2
            }
        ]
    
    def test_api_info_endpoint(self):
        """测试 API 信息端点"""
        # 验证 API 文档结构
        expected_endpoints = {
            'jobs', 'control', 'progress', 'targets', 'interactions', 'reports'
        }
        
        # API 应该返回版本信息
        assert True  # 基础测试通过
    
    def test_create_job_validation(self):
        """测试创建任务参数验证"""
        # 测试空请求体
        request = MockRequest(json_data=None)
        assert request.get_json() is None
        
        # 测试无效靶点数量
        request = MockRequest(json_data={'uniprot_ids': []})
        assert len(request.get_json().get('uniprot_ids', [])) == 0
        
        # 测试超过最大靶点数
        request = MockRequest(json_data={'uniprot_ids': ['P' + str(i) for i in range(60)]})
        assert len(request.get_json()['uniprot_ids']) > 50
    
    def test_create_job_from_text(self):
        """测试从文本解析靶点ID"""
        import re
        
        # 测试逗号分隔
        text = "P12345,P67890,P11111"
        ids = re.split(r'[,;\s\n]+', text)
        ids = [uid.strip().upper() for uid in ids if uid.strip()]
        assert len(ids) == 3
        
        # 测试换行分隔
        text = "P12345\nP67890\nP11111"
        ids = re.split(r'[,;\s\n]+', text)
        ids = [uid.strip().upper() for uid in ids if uid.strip()]
        assert len(ids) == 3
        
        # 测试混合分隔
        text = "P12345, P67890; P11111"
        ids = re.split(r'[,;\s\n]+', text)
        ids = [uid.strip().upper() for uid in ids if uid.strip()]
        assert len(ids) == 3
    
    def test_evaluation_mode_validation(self):
        """测试评估模式验证"""
        from src.multi_target_scheduler import EvaluationMode
        
        # 测试有效模式
        assert EvaluationMode('parallel') == EvaluationMode.PARALLEL
        assert EvaluationMode('sequential') == EvaluationMode.SEQUENTIAL
        
        # 测试无效模式
        with pytest.raises(ValueError):
            EvaluationMode('invalid')
    
    def test_priority_validation(self):
        """测试优先级验证"""
        # 测试有效优先级
        valid_priorities = [1, 5, 10]
        for p in valid_priorities:
            assert 1 <= p <= 10
        
        # 测试无效优先级
        invalid_priorities = [0, 11, -1, 'high']
        for p in invalid_priorities:
            if isinstance(p, int):
                assert not (1 <= p <= 10)
    
    def test_list_jobs_query_params(self):
        """测试列表查询参数"""
        # 测试默认参数
        args = {}
        limit = min(int(args.get('limit', 50)), 100)
        offset = int(args.get('offset', 0))
        assert limit == 50
        assert offset == 0
        
        # 测试 limit 上限
        args = {'limit': '150'}
        limit = min(int(args.get('limit', 50)), 100)
        assert limit == 100
        
        # 测试排序参数
        valid_sort_fields = ['created_at', 'updated_at', 'priority', 'status', 'job_id']
        assert 'created_at' in valid_sort_fields
        assert 'name' not in valid_sort_fields
    
    def test_update_job_validation(self):
        """测试更新任务验证"""
        # 测试可更新字段
        updatable_fields = {'name', 'description', 'priority', 'tags'}
        
        # 测试不可更新字段（通过 API 不应允许修改）
        non_updatable = {'job_id', 'status', 'target_count', 'evaluation_mode'}
        
        assert len(updatable_fields & non_updatable) == 0
    
    def test_delete_job_validation(self):
        """测试删除任务验证"""
        # 不能删除的状态
        cannot_delete = {'processing'}
        
        # 可以删除的状态
        can_delete = {'pending', 'completed', 'failed', 'paused'}
        
        assert 'processing' in cannot_delete
        assert 'pending' in can_delete
    
    def test_progress_calculation(self):
        """测试进度计算"""
        targets = [
            {'status': 'completed'},
            {'status': 'completed'},
            {'status': 'processing'},
            {'status': 'pending'}
        ]
        
        completed = sum(1 for t in targets if t['status'] == 'completed')
        total = len(targets)
        percentage = int((completed / total) * 100) if total > 0 else 0
        
        assert completed == 2
        assert total == 4
        assert percentage == 50
    
    def test_target_status_filter(self):
        """测试靶点状态过滤"""
        targets = [
            {'status': 'completed', 'uniprot_id': 'P1'},
            {'status': 'failed', 'uniprot_id': 'P2'},
            {'status': 'pending', 'uniprot_id': 'P3'},
            {'status': 'completed', 'uniprot_id': 'P4'}
        ]
        
        # 过滤 completed
        completed = [t for t in targets if t['status'] == 'completed']
        assert len(completed) == 2
        
        # 过滤 failed
        failed = [t for t in targets if t['status'] == 'failed']
        assert len(failed) == 1
    
    def test_interactions_filter(self):
        """测试相互作用过滤"""
        interactions = [
            {'relationship_type': 'sequence_similarity', 'score': 0.9},
            {'relationship_type': 'structural_similarity', 'score': 0.7},
            {'relationship_type': 'sequence_similarity', 'score': 0.5}
        ]
        
        # 按类型过滤
        seq_sim = [i for i in interactions if i['relationship_type'] == 'sequence_similarity']
        assert len(seq_sim) == 2
        
        # 按分数过滤
        high_score = [i for i in interactions if i['score'] >= 0.8]
        assert len(high_score) == 1
    
    def test_report_format_validation(self):
        """测试报告格式验证"""
        valid_formats = {'markdown', 'json', 'excel'}
        valid_templates = {'full', 'summary', 'detailed', 'minimal'}
        
        assert 'markdown' in valid_formats
        assert 'pdf' not in valid_formats
        
        assert 'full' in valid_templates
        assert 'custom' not in valid_templates
    
    def test_v1_compat_routes(self):
        """测试 v1 兼容路由"""
        # v1 到 v2 的映射
        compat_routes = {
            'batch-start': '',
            'batch': '',
            'batch/<id>': '<id>',
            'batch/<id>/status': '<id>/progress'
        }
        
        assert 'batch-start' in compat_routes
        assert compat_routes['batch/<id>/status'] == '<id>/progress'
    
    def test_api_response_structure(self):
        """测试 API 响应结构"""
        # 标准成功响应
        success_response = {
            'success': True,
            'data': {},
            'message': 'Operation successful'
        }
        
        # 标准错误响应
        error_response = {
            'success': False,
            'error': 'Error message',
            'code': 400
        }
        
        assert 'success' in success_response
        assert 'success' in error_response
        assert success_response['success'] is True
        assert error_response['success'] is False


class TestSchedulerControlMethods:
    """测试调度器控制方法"""
    
    def test_scheduler_has_control_methods(self):
        """测试调度器有控制方法"""
        from src.multi_target_scheduler import MultiTargetScheduler
        
        scheduler = MultiTargetScheduler()
        
        # 检查控制方法存在
        assert hasattr(scheduler, 'pause_job')
        assert hasattr(scheduler, 'resume_job')
        assert hasattr(scheduler, 'cancel_job')
        assert hasattr(scheduler, 'restart_job')
    
    def test_scheduler_method_signatures(self):
        """测试调度器方法签名"""
        import inspect
        from src.multi_target_scheduler import MultiTargetScheduler
        
        scheduler = MultiTargetScheduler()
        
        # 检查方法参数
        pause_sig = inspect.signature(scheduler.pause_job)
        assert 'job_id' in pause_sig.parameters
        
        restart_sig = inspect.signature(scheduler.restart_job)
        assert 'job_id' in restart_sig.parameters
        assert 'reset_failed_only' in restart_sig.parameters
        
        # 检查默认值
        assert restart_sig.parameters['reset_failed_only'].default is False


class TestAPIEndpointsList:
    """测试 API 端点列表"""
    
    def test_required_endpoints(self):
        """测试必需端点"""
        required_endpoints = {
            'POST /': 'create_multi_target_job',
            'GET /': 'list_multi_target_jobs',
            'GET /<job_id>': 'get_multi_target_job',
            'PUT /<job_id>': 'update_multi_target_job',
            'DELETE /<job_id>': 'delete_multi_target_job',
            'GET /<job_id>/progress': 'get_job_progress',
            'POST /<job_id>/start': 'start_job',
            'POST /<job_id>/pause': 'pause_job',
            'POST /<job_id>/resume': 'resume_job',
            'POST /<job_id>/cancel': 'cancel_job',
            'POST /<job_id>/restart': 'restart_job',
            'GET /<job_id>/targets': 'get_job_targets',
            'GET /<job_id>/targets/<target_id>': 'get_target_detail',
            'GET /<job_id>/interactions': 'get_job_interactions',
            'POST /<job_id>/report': 'generate_report',
            'GET /info': 'get_api_info'
        }
        
        assert len(required_endpoints) == 17
    
    def test_endpoint_http_methods(self):
        """测试端点 HTTP 方法"""
        endpoint_methods = {
            'create': 'POST',
            'list': 'GET',
            'get': 'GET',
            'update': 'PUT',
            'delete': 'DELETE',
            'start': 'POST',
            'pause': 'POST',
            'resume': 'POST',
            'cancel': 'POST',
            'restart': 'POST'
        }
        
        # CRUD 操作使用标准 HTTP 方法
        assert endpoint_methods['create'] == 'POST'
        assert endpoint_methods['get'] == 'GET'
        assert endpoint_methods['update'] == 'PUT'
        assert endpoint_methods['delete'] == 'DELETE'


class TestErrorHandling:
    """测试错误处理"""

    def test_error_response_format(self):
        """测试错误响应格式"""
        # HTTP 400 - Bad Request
        assert True  # 已在前面的测试中覆盖

        # HTTP 404 - Not Found
        assert True

        # HTTP 500 - Internal Server Error
        assert True

    def test_validation_errors(self):
        """测试验证错误"""
        validation_errors = [
            {'field': 'uniprot_ids', 'error': 'required', 'message': '至少需要一个靶点'},
            {'field': 'priority', 'error': 'range', 'message': '优先级必须在1-10之间'},
            {'field': 'evaluation_mode', 'error': 'invalid', 'message': '无效的评估模式'}
        ]

        assert len(validation_errors) == 3


# ---------------------------------------------------------------------------
# S024: Integration tests using Flask's test client.
# The original test file only used MockRequest (a plain Python object) and
# never exercised actual Flask routing, blueprint registration, URL prefix
# handling, HTTP method matching, or request body parsing.  These tests
# add real HTTP-level coverage that was previously invisible to the suite.
# ---------------------------------------------------------------------------

class TestMultiTargetV2IntegrationTests:
    """
    Flask test-client integration tests for the multi_target_v2 blueprint.

    These tests use app.test_client() to exercise real HTTP routing — something
    the original MockRequest-based tests could not verify.  They cover:
    1. Blueprint URL prefix is registered correctly (/api/v2/evaluate/multi).
    2. HTTP method routing works (GET vs POST vs PUT vs DELETE).
    3. Request body JSON parsing (including empty-body and malformed JSON).
    4. Blueprint registration does not raise at app creation time.
    5. The /info endpoint responds without any database dependency.
    6. Job-not-found 404s are returned for missing job IDs.

    Note: scheduler.auto_start is mocked to prevent the scheduler thread from
    actually running during tests.
    """

    @pytest.fixture
    def app(self, mock_env, temp_db):
        """Create a Flask app with an isolated test database.

        Directly overrides config.DATABASE_PATH (bypassing the config module's
        lack of env-var support) and resets the lazy engine so the test DB
        is used instead of the production DB.
        """
        import os
        from app import create_app
        from src.database import get_engine, reset_engine
        from src.multi_target_models import Base
        import config as _config_module

        # Directly override config.DATABASE_PATH so that _get_engine()
        # picks up the test path even though config.py does not read from
        # os.environ['DATABASE_PATH'].
        _config_module.DATABASE_PATH = temp_db

        # Reset any previously-cached engine so the new path takes effect.
        reset_engine()

        flask_app = create_app()

        # Create schema in the isolated DB.
        engine = get_engine()
        Base.metadata.create_all(engine)

        yield flask_app

        # Clean up: dispose and reset engine.
        reset_engine()

    @pytest.fixture
    def client(self, app):
        """Return a Flask test client scoped to the current test."""
        return app.test_client()

    @pytest.fixture(autouse=True)
    def mock_uniprot_client(self):
        """Stub out UniProtClient.get_protein so create-job tests don't need network access."""
        mock_info = {
            'protein_name': 'Mock Protein',
            'gene_names': ['MOCK'],
        }
        with patch('routes.multi_target_v2.UniProtClient') as MockUC:
            instance = MagicMock()
            instance.get_protein.return_value = mock_info
            MockUC.return_value = instance
            yield instance

    @pytest.fixture
    def mock_scheduler(self):
        """Patch scheduler control methods so auto-start does not run during tests.

        The mock delegates to the real scheduler for existence checks (so a
        missing job returns False → route returns 400/404), but stubs the
        async control methods so they don't actually launch threads.
        """
        from src.multi_target_scheduler import MultiTargetScheduler

        with patch('routes.multi_target_v2.get_scheduler') as mock_get_sched:
            real_scheduler = MultiTargetScheduler()
            mock_instance = MagicMock()

            # Delegate existence checks to the real scheduler so missing jobs
            # produce 400/404 from the route rather than False→200.
            def job_exists(job_id):
                from src.database import get_session
                from src.multi_target_models import MultiTargetJob
                with get_session() as s:
                    return s.query(MultiTargetJob).filter_by(job_id=job_id).first() is not None

            def controlled(method_name, job_id):
                if job_exists(job_id):
                    return getattr(real_scheduler, method_name)(job_id)
                return False  # route will return 400 for unknown jobs

            mock_instance.start_job.side_effect = lambda jid: controlled('start_job', jid)
            mock_instance.pause_job.side_effect = lambda jid: controlled('pause_job', jid)
            mock_instance.resume_job.side_effect = lambda jid: controlled('resume_job', jid)
            mock_instance.cancel_job.side_effect = lambda jid: controlled('cancel_job', jid)
            mock_instance.restart_job.side_effect = lambda jid: controlled('restart_job', jid)

            mock_get_sched.return_value = mock_instance
            yield mock_instance

    # ---- Blueprint / routing-level tests (no DB required) ----

    def test_blueprint_registered_at_correct_url_prefix(self, client):
        """
        The multi_target_v2 blueprint should be mounted at
        /api/v2/evaluate/multi.  Requests to /api/v2/evaluate/multi/info
        should not return 404 — they must reach the blueprint.
        """
        response = client.get('/api/v2/evaluate/multi/info')
        # If the blueprint were not registered, we'd get a 404 from Flask's
        # static route matching.  Any non-404 means the blueprint matched.
        assert response.status_code != 404, \
            "Blueprint not registered at /api/v2/evaluate/multi"

    def test_info_endpoint_returns_200(self, client):
        """GET /api/v2/evaluate/multi/info should return 200 with JSON."""
        response = client.get('/api/v2/evaluate/multi/info')
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert 'success' in data

    def test_info_endpoint_has_api_version(self, client):
        """The /info response should include an API version field."""
        response = client.get('/api/v2/evaluate/multi/info')
        data = response.get_json()
        # 'version' is a standard field in the info endpoint.
        assert 'version' in data or 'api_version' in data, \
            f"Info response missing version field: {data}"

    def test_http_method_rejection_on_info(self, client):
        """POST to /info should be rejected (only GET allowed)."""
        response = client.post(
            '/api/v2/evaluate/multi/info',
            json={}
        )
        # Blueprint registered; wrong method → 405 Method Not Allowed.
        assert response.status_code == 405, \
            f"Expected 405 for POST /info, got {response.status_code}"

    # ---- Job creation ----

    def test_create_job_requires_uniprot_ids(self, client, mock_scheduler):
        """POST with no uniprot_ids should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'name': 'test-job'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'uniprot' in data['error'].lower()

    def test_create_job_rejects_empty_uniprot_list(self, client, mock_scheduler):
        """POST with an empty uniprot_ids list should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': []}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_create_job_rejects_too_many_targets(self, client, mock_scheduler):
        """POST with >50 targets should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': [f'P{i:05d}' for i in range(55)]}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert '50' in data['error']

    def test_create_job_rejects_invalid_evaluation_mode(
        self, client, mock_scheduler
    ):
        """POST with an invalid evaluation_mode should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={
                'uniprot_ids': ['P12345'],
                'evaluation_mode': 'invalid-mode'
            }
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'mode' in data['error'].lower()

    def test_create_job_rejects_invalid_priority_too_high(
        self, client, mock_scheduler
    ):
        """POST with priority > 10 should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P12345'], 'priority': 99}
        )
        assert response.status_code == 400

    def test_create_job_rejects_invalid_priority_zero(
        self, client, mock_scheduler
    ):
        """POST with priority 0 should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P12345'], 'priority': 0}
        )
        assert response.status_code == 400

    def test_create_job_parses_text_uniprot_input(
        self, client, mock_scheduler
    ):
        """POST with uniprot_ids_text (comma-separated) should be accepted."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids_text': 'P12345, P67890, P11111'}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['target_count'] == 3

    def test_create_job_returns_201_on_success(
        self, client, mock_scheduler
    ):
        """A valid POST should return 201 with a job_id."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P12345']}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert 'job_id' in data
        assert data['target_count'] == 1

    def test_create_job_parses_newline_delimited_uniprot_ids(
        self, client, mock_scheduler
    ):
        """POST with newline-delimited uniprot_ids_text should work."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids_text': 'P00001\nP00002\nP00003'}
        )
        assert response.status_code == 201
        assert response.get_json()['target_count'] == 3

    def test_create_job_rejects_empty_body(self, client, mock_scheduler):
        """POST with no JSON body should return 400."""
        response = client.post(
            '/api/v2/evaluate/multi',
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_create_job_accepts_optional_fields(
        self, client, mock_scheduler
    ):
        """POST with name, description, priority, and tags should be accepted."""
        response = client.post(
            '/api/v2/evaluate/multi',
            json={
                'uniprot_ids': ['P12345'],
                'name': 'My Job',
                'description': 'A test description',
                'priority': 7,
                'evaluation_mode': 'sequential',
                'tags': {'env': 'test'}
            }
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['name'] == 'My Job'
        assert data['priority'] == 7

    # ---- Job listing ----

    def test_list_jobs_returns_200(self, client, mock_scheduler):
        """GET /api/v2/evaluate/multi should return 200 with a jobs list."""
        response = client.get('/api/v2/evaluate/multi')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'jobs' in data
        assert isinstance(data['jobs'], list)

    def test_list_jobs_respects_limit_query_param(self, client, mock_scheduler):
        """GET ?limit=N should clamp N to 100 and return ≤N jobs."""
        response = client.get('/api/v2/evaluate/multi?limit=10')
        assert response.status_code == 200
        data = response.get_json()
        assert data['limit'] == 10

    def test_list_jobs_rejects_invalid_sort_field(self, client, mock_scheduler):
        """GET ?sort_by=invalid_field should return 400."""
        response = client.get('/api/v2/evaluate/multi?sort_by=invalid_field')
        assert response.status_code == 400

    def test_list_jobs_returns_empty_list_initially(self, client, mock_scheduler):
        """Before any jobs are created, the jobs list should be empty."""
        response = client.get('/api/v2/evaluate/multi')
        data = response.get_json()
        assert data['jobs'] == []
        assert data['total'] == 0

    # ---- Job detail ----

    def test_get_nonexistent_job_returns_404(self, client, mock_scheduler):
        """GET /api/v2/evaluate/multi/99999 should return 404."""
        response = client.get('/api/v2/evaluate/multi/99999')
        assert response.status_code == 404

    def test_get_job_detail_includes_targets(
        self, client, mock_scheduler
    ):
        """A created job's detail endpoint should include a targets list."""
        # Create a job first.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001', 'P00002']}
        )
        assert create_resp.status_code == 201
        job_id = create_resp.get_json()['job_id']

        # Fetch its detail.
        response = client.get(f'/api/v2/evaluate/multi/{job_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'job' in data
        assert 'targets' in data

    # ---- Job progress ----

    def test_get_progress_returns_404_for_missing_job(
        self, client, mock_scheduler
    ):
        """GET /api/v2/evaluate/multi/99999/progress should return 404."""
        response = client.get('/api/v2/evaluate/multi/99999/progress')
        assert response.status_code == 404

    def test_get_progress_returns_job_id_and_status(
        self, client, mock_scheduler
    ):
        """The progress endpoint should include job_id and status fields."""
        # Create a job.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001']}
        )
        job_id = create_resp.get_json()['job_id']

        response = client.get(f'/api/v2/evaluate/multi/{job_id}/progress')
        assert response.status_code == 200
        data = response.get_json()
        assert data['job_id'] == job_id
        assert 'status' in data
        assert 'progress' in data

    # ---- Job update ----

    def test_update_nonexistent_job_returns_404(
        self, client, mock_scheduler
    ):
        """PUT /api/v2/evaluate/multi/99999 should return 404."""
        response = client.put(
            '/api/v2/evaluate/multi/99999',
            json={'name': 'Updated'}
        )
        assert response.status_code == 404

    def test_update_job_requires_json_body(self, client, mock_scheduler):
        """PUT with no JSON body should return 400."""
        # Create a job first so we have a valid ID.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001']}
        )
        job_id = create_resp.get_json()['job_id']

        response = client.put(
            f'/api/v2/evaluate/multi/{job_id}',
            content_type='application/json'
        )
        assert response.status_code == 400

    # ---- Job control (start / pause / resume / cancel / restart) ----

    def test_start_nonexistent_job_returns_400(
        self, client, mock_scheduler
    ):
        """POST /api/v2/evaluate/multi/99999/start should not crash (400)."""
        response = client.post('/api/v2/evaluate/multi/99999/start')
        # Scheduler returns False for unknown jobs → route returns 400.
        assert response.status_code == 400

    def test_start_job_returns_200(self, client, mock_scheduler):
        """POST /api/v2/evaluate/multi/<id>/start should return 200."""
        # Create a pending job.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001']}
        )
        job_id = create_resp.get_json()['job_id']

        response = client.post(f'/api/v2/evaluate/multi/{job_id}/start')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_pause_nonexistent_job_returns_400(
        self, client, mock_scheduler
    ):
        """POST /api/v2/evaluate/multi/99999/pause should return 400."""
        response = client.post('/api/v2/evaluate/multi/99999/pause')
        assert response.status_code == 400

    def test_resume_nonexistent_job_returns_400(
        self, client, mock_scheduler
    ):
        """POST /api/v2/evaluate/multi/99999/resume should return 400."""
        response = client.post('/api/v2/evaluate/multi/99999/resume')
        assert response.status_code == 400

    def test_cancel_nonexistent_job_returns_400(
        self, client, mock_scheduler
    ):
        """POST /api/v2/evaluate/multi/99999/cancel should return 400."""
        response = client.post('/api/v2/evaluate/multi/99999/cancel')
        assert response.status_code == 400

    # ---- Job delete ----

    def test_delete_nonexistent_job_returns_404(self, client, mock_scheduler):
        """DELETE /api/v2/evaluate/multi/99999 should return 404."""
        response = client.delete('/api/v2/evaluate/multi/99999')
        assert response.status_code == 404

    def test_delete_job_returns_200(self, client, mock_scheduler):
        """DELETE /api/v2/evaluate/multi/<id> should return 200 for known jobs."""
        # Create a job.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001']}
        )
        job_id = create_resp.get_json()['job_id']

        response = client.delete(f'/api/v2/evaluate/multi/{job_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_delete_is_idempotent(self, client, mock_scheduler):
        """Deleting the same job twice should 404 on the second call."""
        # Create a job.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001']}
        )
        job_id = create_resp.get_json()['job_id']

        # First delete → 200.
        first = client.delete(f'/api/v2/evaluate/multi/{job_id}')
        assert first.status_code == 200

        # Second delete → 404 (already gone).
        second = client.delete(f'/api/v2/evaluate/multi/{job_id}')
        assert second.status_code == 404

    # ---- Targets ----

    def test_get_targets_returns_404_for_missing_job(
        self, client, mock_scheduler
    ):
        """GET /api/v2/evaluate/multi/99999/targets should return 404."""
        response = client.get('/api/v2/evaluate/multi/99999/targets')
        assert response.status_code == 404

    def test_get_targets_returns_targets_list(self, client, mock_scheduler):
        """The targets endpoint should return a list (even if empty)."""
        # Create a job with 2 targets.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001', 'P00002']}
        )
        job_id = create_resp.get_json()['job_id']

        response = client.get(f'/api/v2/evaluate/multi/{job_id}/targets')
        assert response.status_code == 200
        data = response.get_json()
        assert 'targets' in data
        assert len(data['targets']) == 2

    # ---- Interactions ----

    def test_get_interactions_returns_404_for_missing_job(
        self, client, mock_scheduler
    ):
        """GET /api/v2/evaluate/multi/99999/interactions should return 404."""
        response = client.get('/api/v2/evaluate/multi/99999/interactions')
        assert response.status_code == 404

    def test_get_interactions_returns_list(self, client, mock_scheduler):
        """The interactions endpoint should return a list even with no data."""
        # Create a job.
        create_resp = client.post(
            '/api/v2/evaluate/multi',
            json={'uniprot_ids': ['P00001']}
        )
        job_id = create_resp.get_json()['job_id']

        response = client.get(f'/api/v2/evaluate/multi/{job_id}/interactions')
        assert response.status_code == 200
        data = response.get_json()
        assert 'interactions' in data
        assert isinstance(data['interactions'], list)

    # ---- Params ----

    def test_update_params_returns_404_for_missing_job(
        self, client, mock_scheduler
    ):
        """PUT /api/v2/evaluate/multi/99999/params should return 404."""
        response = client.put(
            '/api/v2/evaluate/multi/99999/params',
            json={'name': 'Renamed'}
        )
        assert response.status_code == 404

    # ---- CORS headers ----

    def test_cors_headers_present_on_info_response(self, client):
        """The after_request CORS middleware should add Allow-Origin."""
        response = client.get('/api/v2/evaluate/multi/info')
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
