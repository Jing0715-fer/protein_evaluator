# Initializer Session Log

## Session Info
- **Date**: 2026-03-29
- **Agent**: Initializer Agent
- **CWD**: /Users/lijing/protein_evaluator
- **Branch**: main

## Files Analyzed

### Python Source Files (36 files)
```
app.py                          (280 lines)   ✓ Read
config.py                       (794 lines)   ✓ Read
src/database.py                 (662 lines)   ✓ Read
src/models.py                   (241 lines)   ✓ Read
src/api_clients.py             (1157 lines)  ✓ Read
src/ai_client_wrapper.py       (1380 lines)  ✓ Read
src/evaluation_worker.py        (274 lines)   ✓ Read
src/service.py                 (417 lines)   ✓ Read
src/prompt_helpers.py           (735 lines)   ✓ Read
src/report_generator.py         (372 lines)   ✓ Read
src/multi_target_scheduler.py  (1037 lines)  ✓ Read
src/cache_service.py            (337 lines)   ✓ Read
src/database_service.py         (509 lines)   ✓ Read
routes/evaluation.py           (1357 lines)  ✓ Read
routes/multi_target_v2.py       (100 lines)   ✓ Partial (first 100)
routes/__init__.py               (few lines)   ✓ Read
utils/api_utils.py              (365 lines)   ✓ Read
tests/conftest.py                (33 lines)   ✓ Read
tests/test_smoke.py             (148 lines)   ✓ Read
tests/test_multi_target_v2_api.py (80 lines)   ✓ Partial
core/simple_singleton.py         (not read)
core/pubmed_client.py           (not read)
core/uniprot_client.py          (not read)
core/pdb_fetcher.py             (not read)
src/multi_target_models.py       (not read)
src/batch_processor.py           (not read)
src/coverage_calculator.py       (not read)
src/alphafold_client.py          (not read)
src/emdb_client.py               (not read)
src/interaction_service.py       (not read)
src/target_interaction_analyzer.py (not read)
src/chain_interaction_analyzer.py (not read)
src/multi_target_report_generator.py (not read)
src/report_service.py            (not read)
```

### TypeScript Files (16 files — out of scope)
All frontend files in `frontend/src/` skipped for initial review.

### Key Confirmations During Analysis

1. **`from datetime import datetime`** IS present at module level in:
   - `src/multi_target_scheduler.py` (line 9)
   - `routes/evaluation.py` (line 8)
   - `src/service.py` (line 11)
   - `src/database_service.py` (line 8)
   - → S001 and S002 were **false positives** — removed from active list.

2. **SECRET_KEY priority order** in `app.py` line 32:
   `os.environ.get('SECRET_KEY') or config.SECRET_KEY`
   → Environment variable correctly takes priority over config file default.
   → config.py line 67: `SECRET_KEY = os.environ.get('SECRET_KEY', '')`
   → Default is empty string (intentional). Production check uses `FLASK_ENV`.

3. **`_run_migrations()` in `src/database.py`**:
   Line 64 calls `_run_migrations()` unconditionally at module import.
   This runs `CREATE TABLE IF NOT EXISTS` via `Base.metadata.create_all(engine)` (line 34)
   AND runs column-level `ALTER TABLE` migrations (lines 37-64).
   → S003 confirmed: **critical for pytest/test isolation**.

4. **Lazy app in `app.py`**:
   `LazyApp` class (line 176) and `_app_instance` (line 166) provide lazy initialization.
   `_get_app()` is called only when `app` is accessed.
   → No `create_app()` call at module import time for the `app` object.
   → BUT `_init_default_templates()` IS called inside `create_app()` (line 109),
     which opens a DB session — still lazy (only when app is created).
   → `src.database` is imported at line 22, which DOES run `_run_migrations()` immediately.

5. **SQLAlchemy `.get()` usage**:
   Confirmed in: `src/database.py`, `src/multi_target_scheduler.py`, `routes/evaluation.py`
   Total occurrences: ~30+
   → S009 confirmed.

6. **Inline `import re`**:
   - `src/prompt_helpers.py` line 215: inside `_clean_abstract()`
   - `src/api_clients.py` line 985: inside `search_by_title()`
   → S011, S012 confirmed.

7. **Global mutable state**:
   - `routes/multi_target_v2.py` line 37: `_scheduler = None`
   - `utils/api_utils.py` line 33: `http_session = create_no_proxy_session()`
   - `src/cache_service.py` line 310: `_cache_service = None` (lazy singleton pattern — OK)
   → S015, S014 confirmed.

8. **Bare `except Exception`**:
   - `src/service.py` lines 164-170: `_run_evaluation_task` catch-all
   - `src/api_clients.py` lines 1095-1156: `fetch_abstracts_for_structures` per-citation
   → S010, S013 confirmed.

9. **`__del__` in cache service**:
   `src/cache_service.py` lines 60-66: `__del__` calls `self.db.close()`
   → S017 confirmed.

10. **`conftest.mock_env` fixture**:
    `tests/conftest.py` lines 25-32: `os.environ.clear()` then `update()`
    → S020 confirmed.

## Review Items Count

| Category      | Total | Critical | High | Medium | Low  |
|---------------|-------|----------|------|--------|------|
| Correctness   |   12  |    1     |  1   |   6    |  4   |
| Security      |    5  |    0     |  3   |   2    |  0   |
| Error/Hndl   |    3  |    0     |  0   |   2    |  1   |
| Pytest       |    3  |    1     |  1   |   1    |  0   |
| Resolved     |    2  |    0     |  0   |   0    |  2   |
| **TOTAL**     | **25** |   **2**  | **5**| **11** | **7** |

## Hints for Reviewer Agent

### How to Reproduce S003 (module-level DB init):
```bash
cd /Users/lijing/protein_evaluator
.venv/bin/python -c "import src.database; print('DB engine created at import time')"
# Before any Flask app is created, the SQLite DB file is created and migrations run
```

### How to Reproduce S004 (SQL injection in LIKE):
```python
# Any of these query strings will modify search behavior:
# '%'  → matches everything
# '_'  → matches single char
# " OR 1=1 --" → would match all records (in some LIKE configurations)
```

### How to Verify S009 (.get() deprecation):
```bash
grep -rn "query.*\.get(" src/ routes/ --include="*.py" | grep -v "session.get\|Model\.get\|\.get(" | head -40
```

### Key Files NOT in Scope
- `frontend/` — TypeScript/React, separate review
- `migrations/` — likely empty or legacy
- `core/` — old client code replaced by `src/api_clients.py`

## Output Files

| File | Description |
|------|-------------|
| `.claude-harness/feature_list.json` | Structured JSON list of 25 review items (23 pending, 2 resolved) |
| `.claude-harness/review_plan.md` | Detailed review plan with phases, priority matrix, execution order |
| `.claude-harness/session_log.md` | This file — initializer session record |

## Next Steps

1. **Reviewer Agent** picks up `feature_list.json` and starts Phase 1 (S003, S006)
2. Each fix should update the `status` field in `feature_list.json` to `"in_progress"` then `"resolved"`
3. After Phase 2, run `pytest tests/ -v` to verify nothing broke
4. Final report written to `.claude-harness/review_report.md`
