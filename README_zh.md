# Protein Evaluator

蛋白质结构与功能综合评估系统，利用 UniProt、PDB、RCSB 等公共数据库和 AI 大模型生成专业的蛋白质评估报告。

## 简介

Protein Evaluator 帮助研究人员分析蛋白质结构与功能，主要功能包括：

- 从 UniProt 获取蛋白质元数据（蛋白名称、基因、物种、序列、功能描述）
- 检索 PDB 结构详细信息（实验方法、分辨率、文献引用）
- 通过 BLAST 搜索同源蛋白
- 在链级别分析蛋白质相互作用网络
- 生成基于 AI 的综合评估报告

## 主要功能

### 单蛋白评估
- 获取任意蛋白的完整 UniProt 元数据
- 检索所有相关 PDB 结构的详细信息
- BLAST 搜索同源蛋白
- AI 综合分析报告

### 多靶点评估
- 同时评估多个蛋白质
- 两种执行模式：并行（更快）或串行
- 自动分析靶点间的相互作用
- 生成综合多靶点报告

### 蛋白质相互作用分析
- **链级相互作用检测**：使用 PDBe Interfaces API 分析 PDB 结构中的链间接触
- **直接相互作用**：在同一 PDB 结构中链之间有物理接触的蛋白质
- **间接相互作用**：通过第三方蛋白（介导蛋白）连接的蛋白质
- 支持基因名称同义词和 ORF 名称进行精确匹配

### 报告生成
- 支持 PDF 或 Markdown 格式导出报告
- 丰富的相互作用网络可视化
- 每个蛋白的详细 PDB 结构信息

## 快速开始

### 环境要求
- Python 3.8+
- Node.js 18+
- OpenAI API Key 或兼容的 AI API（支持 OpenAI/Anthropic Claude/Gemini）

### 安装

```bash
# 克隆仓库
git clone <仓库地址>
cd protein_evaluator

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
```

### 配置

设置 AI API Key：

```bash
export AI_API_KEY="你的API密钥"
```

可选配置：

```bash
export AI_MODEL="gpt-4o"  # 默认模型
export HOST="0.0.0.0"
export PORT=5002
```

### 运行

**开发模式（推荐）：**

```bash
# 终端 1：启动后端
python app.py

# 终端 2：启动前端
cd frontend
npm run dev
```

访问 http://localhost:5173

**生产模式：**

```bash
cd frontend
npm run build
cd ..
python app.py
```

访问 http://localhost:5002

## 工作流程

### 单蛋白评估

```
输入 UniProt ID
    ↓
[步骤 1] 获取 UniProt 元数据 (30%)
    ↓ 蛋白名称、基因、物种、序列、PDB ID 列表
[步骤 2] 获取 PDB 结构数据 (50%)
    ↓ 实验方法、分辨率、文献引用
[步骤 3] BLAST 同源蛋白搜索 (70%)
    ↓ 搜索相似蛋白，分析同源性
[步骤 4] AI 深度分析 (90%)
    ↓ 生成综合分析报告
[步骤 5] 保存并导出 (100%)
```

### 多靶点评估

```
输入多个 UniProt ID
    ↓
[步骤 1] 创建多靶点任务
    ↓ 配置执行模式（并行/串行）、优先级
[步骤 2] 评估各靶点 (30%-90%)
    ↓ 获取各蛋白的 UniProt/PDB 数据
[步骤 3] 分析相互作用 (90%)
    ↓ 通过 PDBe API 检测链级接触
[步骤 4] AI 综合分析 (95%)
    ↓ 生成多靶点综合评估报告
[步骤 5] 生成报告 (100%)
```

## API 接口

### v2 API（多靶点）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v2/evaluate/multi` | GET | 列出所有多靶点任务 |
| `/api/v2/evaluate/multi` | POST | 创建新任务 |
| `/api/v2/evaluate/multi/<id>` | GET | 获取任务详情 |
| `/api/v2/evaluate/multi/<id>/start` | POST | 启动任务 |
| `/api/v2/evaluate/multi/<id>/progress` | GET | 获取进度 |
| `/api/v2/evaluate/multi/<id>/interactions/chain` | GET | 获取链级相互作用 |
| `/api/v2/evaluate/multi/<id>/report` | GET | 生成报告 |

### 示例

```bash
# 创建多靶点任务
curl -X POST http://localhost:5002/api/v2/evaluate/multi \
  -H "Content-Type: application/json" \
  -d '{
    "name": "我的评估任务",
    "uniprot_ids": ["P04637", "P00533"],
    "evaluation_mode": "parallel",
    "priority": 5
  }'
```

## 数据来源

- **UniProt**：蛋白质元数据、基因名称、序列
- **PDB/RCSB**：蛋白质结构数据
- **PDBe**：用于相互作用分析的链级接口数据
- **PubMed**：文献引用

## 许可证

MIT License
