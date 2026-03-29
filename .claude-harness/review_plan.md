# Code Review Plan — Protein Evaluator

**Project**: Protein Evaluator — Flask-based protein structure/function evaluation system
**Reviewer**: Initializer Agent
**Date**: 2026-03-29
**Scope**: Python backend (`src/`, `routes/`, `utils/`, `core/`, `app.py`, `config.py`), test suite (`tests/`)

---

## Review Phases

### Phase 1: Critical Bugs (Must Fix Before Any Deployment)

| ID | File | Issue | Effort |
|----|------|-------|--------|
| S003 | `src/database.py` | Module-level DB engine + `_run_migrations()` run at import time, bypassing pytest fixtures and causing production DB to initialize in test environments | High |
| S006 | `tests/test_smoke.py` | `importlib.reload()` + `clear=True` corrupts module state for other tests in same pytest worker | Medium |

**Gate**: These two must be resolved before any code lands. They cause test pollution and test infra breakage.

---

### Phase 2: Security (High Priority — Production Risk)

| ID | File | Issue | Effort |
|----|------|-------|--------|
| S004 | `src/database.py` | SQL injection in `search_protein_evaluations()` — unescaped `%`/`_` in LIKE pattern | Low |
| S007 | `routes/evaluation.py` | Path traversal in `download_report()` — incomplete check misses `~`, Windows paths, URL-encoded sequences | Medium |
| S005 | `routes/evaluation.py` | Broken regex save in `get_settings()` — `re.escape()` corrupts triple-quoted templates; silently fails | Medium |
| S018 | `config.py + app.py` | `FLASK_ENV` check is deprecated; auto-generated SECRET_KEY silently used in production if FLASK_ENV misconfigured | Low |
| S023 | `config.py` | Race condition in `save_to_env()` — concurrent writes lose updates; no file locking | Medium |

**Gate**: S004, S007, S018 must be fixed before any production deployment. S005 and S023 are important but can be mitigated.

---

### Phase 3: SQLAlchemy Correctness (Medium Priority)

| ID | File | Issue | Effort |
|----|------|-------|--------|
| S009 | `src/database.py`, `src/multi_target_scheduler.py`, `routes/evaluation.py` | Deprecated `.get()` API in ~30+ locations (`session.query(Model).get(id)` → `session.get(Model, id)`) | Low (global replace) |
| S008 | `src/multi_target_scheduler.py` | `_generate_report()` opens a second DB session while outer `_execute_job()` has one open; potential stale reads | Medium |
| S019 | `src/database.py` | `_run_migrations()` — ALTER TABLE failures crash entire app startup; no migration tracking table | Medium |
| S021 | `routes/evaluation.py` | N+1 query in `generate_multi_target_report_endpoint()` — 2N+1 queries for N relationships | Medium |

**Gate**: S009 is mechanical (global search-replace). S008, S019, S021 require careful refactoring with tests.

---

### Phase 4: Error Handling & Robustness

| ID | File | Issue | Effort |
|----|------|-------|--------|
| S010 | `src/service.py` | Bare `except Exception` swallows all errors in `_run_evaluation_task`; error context lost | Low |
| S013 | `src/api_clients.py` | Silent exception swallowing in `fetch_abstracts_for_structures()` — no failure count summary | Low |
| S017 | `src/cache_service.py` | `__del__` for session cleanup — not guaranteed to run in Python | Low |

---

### Phase 5: Concurrency & Global State

| ID | File | Issue | Effort |
|----|------|-------|--------|
| S015 | `routes/multi_target_v2.py` | Global `_scheduler` singleton — race condition in multi-threaded WSGI; test isolation failure | Medium |
| S014 | `utils/api_utils.py` | Global `http_session` created at module import — cannot be patched per-test | Low |
| S016 | `app.py` | In-memory config mutations only visible in the worker process that handles them | Low |

---

### Phase 6: Code Quality (Low Priority)

| ID | File | Issue | Effort |
|----|------|-------|--------|
| S011, S012 | `src/prompt_helpers.py`, `src/api_clients.py` | Inline `import re` instead of module-level | Low |
| S022 | `src/ai_client_wrapper.py` | Ambiguous config precedence; no distinction between 'not set' and 'set to empty' | Low |
| S025 | `src/models.py` | `default=datetime.now` (bare function ref) instead of `default=lambda: datetime.now()` | Low |
| S020 | `tests/conftest.py` | `os.environ.clear()` in fixture corrupts environment for other tests | Low |
| S024 | `tests/test_multi_target_v2_api.py` | Only mock-based tests — no Flask `test_client()` integration tests | Medium |

---

## Review Execution Order

```
1. Run pytest to establish baseline:
   cd protein_evaluator && .venv/bin/pytest tests/ -v --tb=short 2>&1 | head -100

2. Fix S003 (database.py lazy init) first:
   - This unblocks all other test fixes
   - Changes: engine/session → lazy factory

3. Fix S004 (SQL injection) second:
   - One-line fix with proper escaping

4. Fix S009 (deprecated .get() API):
   - Global replace, then verify with grep

5. Fix S007 (path traversal):
   - Add realpath check

6. Run pytest again to confirm fixes

7. Fix S005, S019, S021, S008 (bigger refactors)

8. Fix S010, S013 (error handling)

9. Fix S015 (global scheduler) + S014

10. Fix S006, S020, S024 (test quality)

11. Fix remaining low-priority items
```

---

## Files in Scope

### Primary (Most Complex)
- `src/database.py` — DB engine, migrations, all CRUD functions
- `src/multi_target_scheduler.py` — Job scheduling, threading
- `routes/evaluation.py` — Largest route file, 1357 lines

### Secondary
- `app.py` — Flask app factory
- `config.py` — Configuration management
- `src/api_clients.py` — External API clients (UniProt, PDB, BLAST, PubMed)
- `routes/multi_target_v2.py` — v2 API blueprint
- `src/service.py` — Main service orchestration

### Lower Risk
- `src/models.py` — SQLAlchemy models
- `src/cache_service.py` — Cache management
- `src/prompt_helpers.py` — Prompt construction utilities
- `src/ai_client_wrapper.py` — AI client wrapper
- `src/evaluation_worker.py` — Single-protein evaluation worker
- `src/report_generator.py` — Report generation
- `src/database_service.py` — DB service wrappers
- `utils/api_utils.py` — HTTP session, retry decorators
- `tests/` — All test files

---

## Out of Scope

- Frontend TypeScript/React code (`frontend/src/`)
- Documentation files (`docs/`, `README.md`, etc.)
- `migrations/` directory (empty/migration history)
- `core/simple_singleton.py`, `core/pubmed_client.py`, `core/uniprot_client.py`, `core/pdb_fetcher.py` (likely refactored/legacy code — not imported by main codebase)

---

## Known Test Gaps

1. **No integration tests** — routes are only tested with mocks, not actual Flask request handling
2. **No concurrency tests** — multi-target scheduler threading behavior not tested
3. **No database migration tests** — `_run_migrations()` has no tests
4. **No AI client tests** — only smoke import tests exist
5. **No cache tests** — `DataCacheService` has no unit tests
6. **pytest.ini exists but may be misconfigured** — worth checking for proper test discovery settings

---

## Priority Matrix

```
                    LOW EFFORT          HIGH EFFORT
HIGH PRIORITY    S004, S018, S012    S003, S006
MEDIUM PRIORITY  S009, S010, S013    S007, S015, S005, S019, S021, S008
LOW PRIORITY     S011, S022, S025    S014, S016, S017, S020, S024
```

**Recommended first sprint**: S003 → S004 → S009 → S007 → S018 → S006

---

## Verification Strategy

After each fix:
1. Run relevant pytest file: `pytest tests/test_X.py -v`
2. Run full suite: `pytest tests/ -v --tb=short`
3. Check for new warnings: `pytest tests/ -W always`
4. Verify SQLAlchemy deprecation warnings are gone after S009
