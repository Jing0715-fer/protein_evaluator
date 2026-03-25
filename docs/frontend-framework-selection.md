# Phase 3.1: 前端框架选型与搭建

## 技术选型决策文档

### 项目需求分析

**当前状态：**
- 后端: Flask + Jinja2 模板
- 现有: 纯 HTML/CSS/JS，无前端框架
- 需求: 升级为支持多靶点的现代化前端

**新功能需求：**
1. 多靶点可视化界面
2. 结果对比视图（表格、图表）
3. 批量操作界面
4. 移动端适配
5. 实时进度更新

---

## 框架评估

### 选项 1: React + shadcn/ui ⭐ 推荐

**优点：**
- 组件丰富、生态完善
- shadcn/ui 提供现代、美观的组件
- 优秀的 TypeScript 支持
- 大量社区资源和模板
- 适合数据密集型的仪表板应用

**缺点：**
- 学习曲线较陡
- 需要 Node.js 构建环境
- 与现有 Flask 集成需配置

**适用场景：** 企业级应用、数据仪表板

### 选项 2: Vue 3 + Element Plus

**优点：**
- 上手容易、文档友好
- 渐进式框架，可逐步采用
- 与 Flask 集成简单（可直接使用 CDN）
- 中文文档完善

**缺点：**
- 组件样式偏传统
- 生态系统比 React 小

**适用场景：** 快速开发、中小型项目

### 选项 3: SvelteKit

**优点：**
- 性能最好、体积小
- 无虚拟 DOM，运行时开销小
- 编译时优化

**缺点：**
- 生态较小
- 社区资源有限
- 学习成本较高

**适用场景：** 性能要求极高的应用

### 选项 4: Alpine.js + Tailwind CSS

**优点：**
- 无需构建步骤
- 轻量级，可直接嵌入 HTML
- 与现有 Flask 完美集成
- Tailwind 提供现代样式

**缺点：**
- 功能较简单
- 不适合复杂应用

**适用场景：** 快速原型、简单交互

---

## 最终决策: React + shadcn/ui

**决策理由：**

1. **多靶点数据可视化需求** - React 生态有大量图表库 (Recharts, Chart.js React wrapper)
2. **现代化 UI 需求** - shadcn/ui 提供专业的组件设计
3. **长期维护性** - React 是最主流的前端框架，招聘和社区支持最好
4. **与 Flask 集成** - 可作为独立 SPA，通过 API 与 Flask 后端通信

**技术栈：**
- **框架:** React 18 + TypeScript
- **构建工具:** Vite
- **UI 组件:** shadcn/ui
- **样式:** Tailwind CSS
- **状态管理:** React Query (TanStack Query)
- **图表:** Recharts
- **路由:** React Router

---

## 项目结构

```
protein-evaluator/
├── backend/                 # Flask 后端
│   ├── app.py
│   ├── src/
│   ├── routes/
│   └── tests/
├── frontend/               # React 前端 ⭐ 新建
│   ├── src/
│   │   ├── components/    # UI 组件
│   │   ├── pages/         # 页面
│   │   ├── hooks/         # 自定义 hooks
│   │   ├── lib/           # 工具函数
│   │   ├── services/      # API 服务
│   │   ├── types/         # TypeScript 类型
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
└── README.md
```

---

## 搭建步骤

### 1. 初始化项目

```bash
# 在项目根目录创建 frontend 文件夹
cd /Users/lijing/literature_agent-V2-claude/protein_evaluator
mkdir -p frontend
cd frontend

# 使用 Vite 创建 React + TypeScript 项目
npm create vite@latest . -- --template react-ts
```

### 2. 安装依赖

```bash
# UI 组件库
npx shadcn-ui@latest init

# 图表库
npm install recharts

# HTTP 客户端
npm install axios

# 状态管理
npm install @tanstack/react-query

# 路由
npm install react-router-dom

# 图标
npm install lucide-react

# 类型定义
npm install --save-dev @types/node
```

### 3. 配置 Tailwind

```javascript
// tailwind.config.js
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

### 4. 配置 Vite

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
```

---

## 组件规划

### 核心组件

1. **多靶点输入**
   - `MultiTargetInput` - 批量输入 UniProt ID
   - `TargetList` - 靶点列表管理
   - `FileUploader` - CSV/Excel 上传

2. **任务管理**
   - `JobList` - 任务列表
   - `JobCard` - 任务卡片
   - `ProgressBar` - 进度条
   - `JobFilter` - 任务过滤

3. **结果展示**
   - `TargetDetail` - 靶点详情
   - `InteractionGraph` - 相互作用网络图
   - `ScoreChart` - 评分分布图
   - `ComparisonTable` - 对比表格

4. **报告**
   - `ReportGenerator` - 报告生成器
   - `ReportPreview` - 报告预览
   - `ExportOptions` - 导出选项

---

## API 集成

### 服务层结构

```typescript
// src/services/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 多靶点任务 API
export const multiTargetApi = {
  createJob: (data: CreateJobRequest) => 
    api.post('/v2/evaluate/multi', data),
  
  listJobs: (params?: ListJobsParams) => 
    api.get('/v2/evaluate/multi', { params }),
  
  getJob: (id: number) => 
    api.get(`/v2/evaluate/multi/${id}`),
  
  getProgress: (id: number) => 
    api.get(`/v2/evaluate/multi/${id}/progress`),
  
  controlJob: (id: number, action: string) => 
    api.post(`/v2/evaluate/multi/${id}/${action}`),
  
  generateReport: (id: number, options: ReportOptions) => 
    api.post(`/v2/evaluate/multi/${id}/report`, options),
}
```

---

## 开发计划

### Week 1: 基础搭建
- [ ] 项目初始化 (Vite + React + TS)
- [ ] shadcn/ui 配置
- [ ] Tailwind 配置
- [ ] API 服务层搭建

### Week 2: 核心功能
- [ ] 多靶点输入界面
- [ ] 任务列表界面
- [ ] 进度显示

### Week 3: 结果展示
- [ ] 靶点详情页面
- [ ] 相互作用可视化
- [ ] 评分图表

### Week 4: 优化
- [ ] 移动端适配
- [ ] 性能优化
- [ ] 导出功能

---

## 风险评估

| 风险 | 可能性 | 影响 | 缓解策略 |
|------|--------|------|----------|
| 与 Flask 集成困难 | 低 | 中 | 使用 proxy 模式 |
| 学习曲线 | 中 | 低 | 使用 TypeScript 减少错误 |
| 构建配置复杂 | 低 | 低 | 使用 Vite 简化配置 |

---

## 验收标准

- [ ] 项目成功构建，无错误
- [ ] 所有 API 调用正常
- [ ] 组件渲染正常
- [ ] 支持热更新开发
- [ ] 生产构建成功

---

*决策日期: 2026-03-14*
*技术负责人: Claude Code*
