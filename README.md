# Protein Evaluator

蛋白质结构与功能综合评估系统，基于 UniProt、PDB、RCSB 等公共数据库，结合 AI 大模型生成专业的蛋白质评估报告。

## 功能特性

- **UniProt 元数据获取** - 获取蛋白名称、基因、物种、序列、功能描述、PDB ID 列表等信息
- **PDB 结构数据分析** - 获取结构实验方法、分辨率、文献引用、实体信息、UniProt 映射范围等详细信息
- **BLAST 同源蛋白搜索** - 搜索相似蛋白，分析同源性，支持跳过已覆盖结构
- **AI 智能分析报告** - 基于收集的所有数据，调用 AI 生成综合分析报告
- **PDF/Markdown 导出** - 支持多种格式导出评估报告
- **评估历史管理** - 支持搜索和多选批量删除评估记录
- **智能优化** - PDB 覆盖率 >= 50% 且结构数 >= 5 时自动跳过 BLAST
- **批量多 UniProt ID 评估** - 支持同时评估多个蛋白，分析蛋白相互作用网络

## 运行环境

- Python 3.8+
- OpenAI API Key 或其他 AI API (支持 OpenAI/Anthropic Claude/Gemini)

## 安装步骤

### 1. 克隆/复制项目

```bash
git clone <repository-url>
cd protein_evaluator
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `AI_API_KEY` | AI API Key（必需） | - |
| `AI_MODEL` | AI 模型 | `gpt-4o` |
| `AI_TEMPERATURE` | AI 温度参数 | `0.3` |
| `AI_MAX_TOKENS` | AI 最大 token 数 | `6000` |
| `HOST` | 服务器地址 | `0.0.0.0` |
| `PORT` | 服务器端口 | `5002` |
| `DEBUG` | 调试模式 | `True` |

### 配置示例

```bash
# 必需：AI API Key
export AI_API_KEY="your-api-key"

# 可选：AI 模型（支持 gpt-4o, claude-3-opus, gemini-pro 等）
export AI_MODEL="gpt-4o"

# 可选：服务器配置
export HOST="0.0.0.0"
export PORT=5002
```

## 运行方式

### 启动应用

```bash
python app.py
```

应用启动后，访问 http://localhost:5002/evaluation

## 运行逻辑和原理

### 评估流程

```
输入 UniProt ID
    ↓
[步骤1] 获取 UniProt 元数据 (progress: 30%)
    ↓ 获取蛋白名称、基因、物种、序列、PDB ID 列表等
[步骤2] 获取 PDB/RCSB 元数据 (progress: 50%)
    ↓ 获取每个 PDB 结构的实验方法、分辨率、文献引用等
[步骤3] 执行 BLAST/同源蛋白搜索 (progress: 70%)
    ↓ 搜索相似蛋白，分析同源性
[步骤4] AI 深度分析 (progress: 90%)
    ↓ 基于收集的所有数据，调用 AI 生成综合分析报告
[步骤5] 生成并保存报告 (progress: 100%)
    ↓ 保存到数据库，支持 PDF/Markdown 导出
```

### 批量评估流程

```
输入多个 UniProt ID
    ↓
[步骤1] 获取蛋白互作数据 (progress: 30%)
    ↓ 从 String Database 获取蛋白相互作用网络
[步骤2] 逐个评估蛋白质 (progress: 70%)
    ↓ 获取每个蛋白的 UniProt/PDB 数据
[步骤3] AI 综合分析 (progress: 90%)
    ↓ 分析蛋白相互作用网络，生成综合报告
[步骤4] 生成批量评估报告 (progress: 100%)
    ↓ 保存到数据库，展示结果
```

### 核心模块说明

| 模块 | 职责 |
|------|------|
| `src/service.py` | 核心评估服务，包含完整的评估流程 |
| `src/database.py` | SQLite 数据库操作 |
| `core/uniprot_client.py` | UniProt REST API 客户端 |
| `core/pdb_fetcher.py` | RCSB/PDBe API 客户端 |
| `core/pubmed_client.py` | PubMed 文献 API 客户端 |
| `utils/ai_client.py` | AI 模型统一接口（支持 OpenAI/Anthropic/Gemini） |

### 数据存储

- 使用 SQLite 轻量级数据库
- 数据库文件：`data/protein_eval.db`
- 主要表：`protein_evaluations` 存储评估记录

## API 接口

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/evaluation` | GET | 列出所有评估 |
| `/api/evaluation/start` | POST | 开始新评估 |
| `/api/evaluation/<id>` | GET | 获取评估详情 |
| `/api/evaluation/<id>/status` | GET | 获取评估状态 |
| `/api/evaluation/<id>` | DELETE | 删除单个评估 |
| `/api/evaluation/batch-delete` | POST | 批量删除评估 |
| `/api/evaluation/batch-start` | POST | 批量评估（多个 UniProt ID） |
| `/api/evaluation/batch` | GET | 获取批量评估列表 |
| `/api/evaluation/batch/<id>` | GET | 获取批量评估详情 |
| `/api/evaluation/batch/<id>/status` | GET | 获取批量评估进度 |
| `/api/evaluation/batch/<id>` | DELETE | 删除批量评估 |

### API 使用示例

#### 开始新评估

```bash
curl -X POST http://localhost:5002/api/evaluation/start \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P12345"}'
```

#### 获取评估状态

```bash
curl http://localhost:5002/api/evaluation/<id>/status
```

#### 批量删除评估

```bash
curl -X POST http://localhost:5002/api/evaluation/batch-delete \
  -H "Content-Type: application/json" \
  -d '{"ids": [1, 2, 3]}'
```

#### 开始批量评估（多个 UniProt ID）

```bash
curl -X POST http://localhost:5002/api/evaluation/batch-start \
  -H "Content-Type: application/json" \
  -d '{"uniprot_ids": ["P04637", "P00533", "P00720"], "name": "测试批量评估"}'
```

#### 获取批量评估列表

```bash
curl http://localhost:5002/api/evaluation/batch
```

#### 获取批量评估状态

```bash
curl http://localhost:5002/api/evaluation/batch/<id>/status
```

## 项目结构

```
protein_evaluator/
├── app.py                 # Flask 主应用入口
├── config.py              # 配置文件
├── requirements.txt       # Python 依赖
├── data/
│   └── protein_eval.db   # SQLite 数据库
├── core/                  # 核心模块
│   ├── uniprot_client.py # UniProt API 客户端
│   ├── pdb_fetcher.py    # PDB 数据获取器
│   ├── pubmed_client.py # PubMed 文献客户端
│   └── simple_singleton.py # 单例模式工具
├── utils/
│   └── ai_client.py      # AI 客户端（支持 OpenAI/Anthropic/Gemini）
├── src/
│   ├── service.py        # 核心评估服务
│   ├── database.py        # 数据库操作
│   └── models.py          # 数据模型
├── routes/
│   └── evaluation.py      # API 路由
├── templates/
│   ├── base.html         # 基础模板
│   └── evaluation.html   # 评估页面
└── static/
    └── css/
        └── evaluation.css # 样式文件
```

## 常见问题

### Q: 启动时提示缺少 AI_API_KEY

A: 请设置环境变量 `AI_API_KEY`，或者在运行前确保已正确配置。

### Q: 评估进度卡住不动

A: 检查网络连接，确保可以访问 UniProt、PDB 等外部 API。如果问题持续，可以查看日志了解具体错误信息。

### Q: 如何导出 PDF 报告？

A: 评估完成后，在评估详情页面点击"导出 PDF"按钮即可生成 PDF 格式的报告。

## License

MIT License
