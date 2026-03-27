#!/bin/bash
# dev-flow.sh — Claude Code 本地自动化开发流程
# 用法: ./dev-flow.sh [review|backend-tests|frontend-tests|all]

set -e
PROJECT="/Users/lijing/protein_evaluator"
cd "$PROJECT"

ACTION="${1:-all}"

check_api_key() {
  if ! claude --version &>/dev/null; then
    echo "❌ Claude Code CLI 未安装"
    echo "   npm install -g @anthropic/claude-code"
    exit 1
  fi
}

echo "🔍 检查 Claude Code..."
if ! command -v claude &>/dev/null; then
  echo "📦 安装 Claude Code..."
  npm install -g @anthropic/claude-code
fi

# ── 代码审查 ────────────────────────────────────────────
run_review() {
  echo ""
  echo "═══════════════════════════════"
  echo "🤖 开始 Claude Code 代码审查"
  echo "═══════════════════════════════"
  check_api_key

  claude -p \
    --permission-mode bypassPermissions \
    --no-input \
    "You are a senior code reviewer for a React 19 + Flask protein evaluation platform.
Review ALL code in this project (backend + frontend).
Focus on:
1. 🔴 Logic errors or bugs
2. 🔴 Security issues (SQL injection, XSS, eval, unsafe deserialization)
3. 🔴 API contract breakage
4. 🟡 Error handling quality
5. 🟡 React 19 hooks correctness
6. 🟡 Test coverage gaps
7. 🟡 Performance concerns

Format:
## 🔴 Blocking Issues (files + line numbers + fix)
## 🟡 Suggestions (files + recommendation)
## ✅ What's Good
## 📊 Summary: X files reviewed | X blocking | X suggestions | Approve/Request Changes"
}

# ── 后端测试生成 ────────────────────────────────────────
run_backend_tests() {
  echo ""
  echo "═══════════════════════════════"
  echo "🧪 Claude 生成后端测试"
  echo "═══════════════════════════════"
  check_api_key

  mkdir -p tests/ai_generated

  claude -p \
    --permission-mode bypassPermissions \
    --no-input \
    "Analyze the Flask backend in this project.
Files: app.py, routes/evaluation.py, routes/multi_target_v2.py, core/*.py, utils/*.py

Generate comprehensive pytest tests in tests/ai_generated/:
1. test_routes.py — All Flask API endpoints
   - Each endpoint: success case + 400/404 error case + 500 error case
2. test_core_logic.py — Core evaluation functions
   - test_evaluate_target, test_database_service, test_cache_service
3. test_ai_clients.py — Mock AI API responses
   - Mock AlphaFold, UniProt, EMDB HTTP responses
   - Test timeout handling, retry logic, error responses

Use Flask test client (@pytest.fixture with app.test_client()).
Use unittest.mock for HTTP calls.
All tests must be runnable with: python -m pytest tests/ai_generated/ -v

Write files directly to tests/ai_generated/"
}

# ── 前端测试生成 ────────────────────────────────────────
run_frontend_tests() {
  echo ""
  echo "═══════════════════════════════"
  echo "🧪 Claude 生成前端测试"
  echo "═══════════════════════════════"
  check_api_key

  FRONTEND="$PROJECT/frontend"
  cd "$FRONTEND"

  # 安装测试依赖
  echo "📦 安装前端测试依赖..."
  npm install -D vitest @testing-library/react @testing-library/user-event jsdom 2>/dev/null

  # 确保 vitest 配置存在
  if [ ! -f vitest.config.ts ]; then
    cat > vitest.config.ts << 'EOF'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
EOF
  fi

  mkdir -p src/test
  cat > src/test/setup.ts << 'EOF'
import { expect, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import * as matchers from '@testing-library/jest-dom'
expect.extend(matchers)
afterEach(() => cleanup())
EOF

  # Claude 生成测试
  claude -p \
    --permission-mode bypassPermissions \
    --no-input \
    "Explore frontend/src/ — find all React components (*.tsx).

Generate Vitest + Testing Library tests for every component found.

For each component:
- Test: renders without crashing
- Test: shows loading state
- Test: shows success state with data
- Test: shows error state
- Test: major user interactions (button clicks, form inputs)

Mock all API/fetch calls with simple mock functions.
Use @testing-library/react and @testing-library/user-event.

Output format: write each test as a sibling file next to its component.
Example: src/components/Evaluator.tsx → src/components/Evaluator.test.tsx

After generating, run: npx vitest --run to verify tests work."
}

# ── 运行测试 ────────────────────────────────────────────
run_tests() {
  echo ""
  echo "═══════════════════════════════"
  echo "⚡ 运行全部测试"
  echo "═══════════════════════════════"

  echo "--- 后端测试 ---"
  cd "$PROJECT"
  python -m pytest tests/ -v --tb=short -m "not slow" 2>&1 | tail -50

  echo ""
  echo "--- 前端测试 ---"
  cd "$FRONTEND"
  npx vitest --run --reporter=verbose 2>&1 | tail -50
}

# ── 主入口 ──────────────────────────────────────────────
case "$ACTION" in
  review)
    run_review
    ;;
  backend-tests)
    run_backend_tests
    ;;
  frontend-tests)
    run_frontend_tests
    ;;
  test)
    run_tests
    ;;
  all)
    check_api_key
    run_review
    echo ""
    read -p "🤔 是否生成后端测试？(y/n) " -n 1 -r; echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then run_backend_tests; fi
    echo ""
    read -p "🤔 是否生成前端测试？(y/n) " -n 1 -r; echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then run_frontend_tests; fi
    echo ""
    read -p "🤔 是否运行测试？(y/n) " -n 1 -r; echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then run_tests; fi
    ;;
  *)
    echo "用法: $0 [review|backend-tests|frontend-tests|test|all]"
    echo "  review         — Claude Code 代码审查"
    echo "  backend-tests  — 生成后端 pytest 测试"
    echo "  frontend-tests — 生成前端 Vitest 测试"
    echo "  test           — 运行现有测试"
    echo "  all            — 完整流程（审查→生成→运行）"
    ;;
esac
