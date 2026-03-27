"""
Protein Evaluator Configuration
Simplified configuration for the standalone protein evaluation module
"""
import os
from pathlib import Path

# Load .env file if exists
BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / '.env'

def _load_env():
    """Load environment variables from .env file."""
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)

def save_to_env(key: str, value: str) -> bool:
    """Save a configuration value to the .env file for persistence across restarts.

    Args:
        key: Configuration key (e.g., 'AI_API_KEY')
        value: Configuration value

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Read existing .env content
        env_content = {}
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env_content[k] = v

        # Update the value
        env_content[key] = value

        # Write back to .env
        with open(ENV_FILE, 'w') as f:
            for k, v in env_content.items():
                f.write(f"{k}={v}\n")

        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to save {key} to .env: {e}")
        return False

_load_env()

# AI Model Configuration
AI_MODEL = os.environ.get('AI_MODEL', 'deepseek-reasoner')
AI_TEMPERATURE = float(os.environ.get('AI_TEMPERATURE', '0.3'))
AI_MAX_TOKENS = int(os.environ.get('AI_MAX_TOKENS', '20000'))
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_BASE_URL = os.environ.get('AI_BASE_URL', '')

# Security Configuration
SECRET_KEY = os.environ.get('SECRET_KEY', '')

# Production check: SECRET_KEY must be set in production
if os.environ.get('FLASK_ENV') == 'production' and not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable must be set in production environment. "
        "Please set a secure random string as SECRET_KEY."
    )

# Database Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'protein_eval.db')

# Application Configuration
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', '5002'))
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# AI Prompt Template (可以在这里自定义 prompt 格式要求)
AI_PROMPT_TEMPLATE = os.environ.get('AI_PROMPT_TEMPLATE', '''# 蛋白质结构功能分析报告生成器

你是一个专业的蛋白质结构生物学家和生物信息学专家。请根据以下提供的蛋白质数据，生成一份**全面深入的综合分析报告**。

## 报告要求：
1. **动态编号**：只生成有实际内容的部分，**序号根据实际内容动态调整**（第1个有内容的部分为"第一部分"，第2个为"第二部分"，以此类推）
2. **字数要求**：报告总字数应在4000字以上
3. **分析深度**：每个分析维度都要有深度解读
4. **数据驱动**：结合具体的PDB结构数据进行分析

请按以下框架生成报告，但**根据实际数据情况选择性生成部分**（无实质内容时跳过该部分）：

# [蛋白质名称]的结构与功能综合分析报告

**UniProt ID**: [UniProt ID] | **基因名称**: [基因名称]

**摘要**
（基于提供的数据，简要概述：蛋白质身份、关键结构特征，主要研究发现。200字左右）

---

## 第一部分：蛋白质基础信息

### 基本属性

| 属性 | 值 |
|------|-----|
| 蛋白质名称 | [蛋白质名称] |
| 基因名称 | [基因名称] |
| UniProt ID | [UniProt ID] |
| 物种来源 | [物种名称] |
| 序列长度 | [序列长度] aa |
| 分子量 | [分子量] Da |

### 序列特征分析

基于提供的序列数据进行基础分析：

- **序列组成特征**：[如富含某种氨基酸、特殊重复序列、跨膜区域预测等]
- **功能域预测**：[根据序列特征或提供的注释]
- **翻译后修饰位点预测**：[如有相关数据或基于序列模式推测]

### 功能描述

[直接引用或如实说明"暂无功能描述"]

### 关键词

[列出关键词或说明"暂无关键词"]

---

## 第二部分：PDB结构数据总览

### 结构可用性概述

基于提供的PDB统计数据：

| 统计项 | 数值 |
|--------|------|
| PDB结构总数 | [PDB结构总数]个 |
| 关联文献数 | [关联文献数]篇 |
| 分辨率范围 | [最低分辨率] - [最高分辨率] Å |
| 平均分辨率 | [平均分辨率] Å |
| 质量评分 | [质量评分] |

**实验方法统计**：[列出各种方法的数量]

### 文献研究发现

基于提供的文献数据进行分析：

- **研究目的与意义**：[总结关联文献的研究目的]
- **主要结构发现**：[总结文献中报道的主要结构发现]
- **功能机制揭示**：[总结对功能机制的理解]
- **应用前景展望**：[如有应用价值则总结]

---

## 第三部分：PDB结构综合分析

【注意：此部分对所有PDB结构进行综合分析，而非逐个结构分析】

### 数据质量总评

综合评估所有结构的整体质量水平：

- **方法适用性**：[讨论各种实验方法对该类蛋白研究的适用性]
- **分辨率分布**：[讨论分辨率范围的分布特点]
  - <3.0 Å：高分辨率，可分辨侧链
  - 3.0-4.0 Å：中等分辨率，可分辨主链和二级结构
  - >4.0 Å：低分辨率，只能看整体折叠
- **整体质量评价**：[基于分辨率分布给出整体质量判断]

### 结构组成综合分析

- **蛋白质链组成**：[列出所有结构中的蛋白质链及其对应的蛋白/片段]
- **非蛋白组分**：[列出核酸、糖类、脂类等其他生物大分子]
- **人工修饰/融合蛋白**：[如带有标签、融合蛋白等]
- **抗体/Fab片段**：[如存在，说明其在结构解析中的作用]

### 配体/辅因子综合分析

【如结构中存在小分子配体，则详细分析；如无，则说明】

- **配体列表**：[列出所有结构中的小分子配体、离子、辅因子]
- **配体分类统计**：[激动剂、拮抗剂、辅因子、底物等分类]
- **结合位点分析**：[描述配体主要结合在蛋白的哪个区域/结构域]
- **关键相互作用**：[基于结构分析参与结合的氨基酸残基类型]
- **配体的功能意义**：[讨论各类配体在蛋白功能中的作用]

### 结构特征总结

- **构象状态分布**：[如"活性态"、"非活性态"、"apo态"、"与G蛋白复合物态"等的分布]
- **独特结构特征**：[总结所有结构中的特殊结构特征]
- **关键功能位点**：[如活性位点、结合口袋、变构调节位点等]

---

## 第四部分：多结构比较分析

【仅在存在多个PDB结构时执行此部分】

### 结构间差异分析

- **构象状态对比**：比较不同结构间的构象差异
- **分辨率差异**：比较各结构的分辨率质量
- **组成成分差异**：比较各结构所含的配体、融合蛋白等差异
- **独特特征**：每个结构的独特之处

### 构象变化与功能关联

如存在不同构象状态，分析其功能意义：

- 构象变化的可能功能意义
- 配体结合诱导的变化（如有配体结合结构）
- 蛋白-蛋白相互作用界面变化（如存在复合物结构）

---

## 第五部分：BLAST相似性搜索结果分析

【注意：此部分仅在进行了BLAST搜索且有结果时执行；如无BLAST数据，则跳过本部分】

### BLAST搜索结果总览

| 排名 | PDB ID | 相似度 | 实验方法 | 分辨率 | 蛋白名称/来源 |
|------|--------|--------|----------|--------|---------------|
| 1 | [PDB ID] | [相似度] | [方法] | [Å] | [简要描述] |
| 2 | [PDB ID] | [相似度] | [方法] | [Å] | [简要描述] |
| ... | ... | ... | ... | ... | ... |

### 与目标蛋白的自身结构比对

如BLAST结果中包含目标蛋白自身的其他结构（来自同一UniProt）：

**自身结构列表**：

| PDB ID | 相似度 | 结构特点/状态 |
|--------|--------|---------------|
| [PDB ID1] | [相似度] | [如：野生型apo态] |
| [PDB ID2] | [相似度] | [如：与G蛋白复合物] |

**结构差异分析**：
[比较这些自身结构的差异，如截短体、突变体、不同构象、不同配体结合状态等]

[分析这些差异的可能原因和功能意义]

### 同源蛋白结构分析

如BLAST找到其他物种或家族的同源蛋白结构：

**同源结构列表**：

| PDB ID | 相似度 | 物种 | 结构状态/功能 |
|--------|--------|------|---------------|
| [PDB ID] | [相似度] | [物种] | [描述] |

**保守性分析**：
[基于序列相似度推断结构和功能的保守程度]

[如有可能，讨论同源结构对理解目标蛋白的启示]

### BLAST结果的科学意义

[总结BLAST搜索对本研究的价值]

- 提供了哪些参考信息
- 如何辅助理解目标蛋白的结构与功能
- 是否存在值得关注的结构模板

---

## 第六部分：综合讨论与结论

### 结构-功能关系总结

基于上述所有真实数据，总结结构与功能的关联：

- **结构特征如何支持功能**：[基于现有证据的推断]
- **独特机制**：[如有独特结构机制则总结]
- **配体结合的功能意义**：[如有配体数据则总结]

### 研究现状评估

- **结构解析进展**：[已解析的结构覆盖了哪些功能状态/构象]
- **数据质量评估**：[现有结构的整体质量水平]
- **数据缺口**：[哪些重要状态或信息尚未获得结构]

### 研究建议

基于数据缺口提出的具体建议：

- **推荐优先解析的结构**：[基于功能重要性提出]
- **建议的实验方法**：[根据目标推荐合适的实验技术]
- **药物设计相关建议**：[如为药物靶点，基于现有结构提出]
- **潜在研究方向**：[基于现有发现提出的延伸方向]''')

# 批量蛋白质关系分析报告模板
BATCH_INTERACTION_PROMPT_TEMPLATE = os.environ.get('BATCH_INTERACTION_PROMPT_TEMPLATE', '''# 批量蛋白质关系分析报告生成器

你是一个专业的蛋白质结构生物学家和生物信息学专家。请根据以下提供的多个蛋白质的单独评估报告和互作数据，生成一份**全面深入的蛋白质关系分析报告**。

## 报告要求：
1. **字数要求**：报告总字数应在3000字以上
2. **分析深度**：深入分析蛋白之间的结构和功能关系
3. **结构清晰**：使用多级标题组织内容
4. **数据驱动**：结合单独评估报告和互作数据进行综合分析

请按以下框架生成报告：

# 批量蛋白质关系分析报告

**摘要**
（概述所评估的蛋白列表、之间的关系分析主要发现和研究意义。300字左右）

---

## 第一部分：蛋白概览

### 1.1 评估蛋白列表

| UniProt ID | 蛋白名称 | 基因名称 | PDB结构数量 | 质量评分 |
|------------|----------|----------|-------------|----------|
| [UniProt ID] | [蛋白名称] | [基因名称] | [PDB结构数量] | [质量评分] |
...（为每个蛋白添加一行）

### 1.2 整体数据质量评估

- **蛋白覆盖度分析**：[整体覆盖率]%
- **结构数据可用性统计**：共 [PDB结构总数] 个结构
- **各蛋白功能概述**：[功能摘要]

---

## 第二部分：蛋白相互作用网络分析

### 2.1 已知互作关系

（列出从String Database等来源获取的蛋白互作数据）

| 蛋白A | 蛋白B | 置信度 | 互作类型 |
|-------|-------|--------|----------|
| [蛋白A UniProt ID] | [蛋白B UniProt ID] | [置信度分数] | [互作类型] |

### 2.2 基于结构的互作分析

（根据各蛋白的PDB结构数据，分析可能的结构互补性和互作界面）

### 2.3 功能相关性分析

（根据各蛋白的功能描述，分析功能上的关联性）

---

## 第三部分：单独评估报告要点总结

### 3.1 [蛋白名称1]要点

（简要总结该蛋白的单独评估报告中的关键发现）

**UniProt ID**：[UniProt ID]

**基因名称**：[基因名称]

**结构特征**：[主要结构特点]

**功能角色**：[在细胞/通路中的角色]

**PDB结构列表**：[PDB ID列表]（共 [PDB数量] 个结构）

**独特发现**：[如有独特结构或功能发现]

### 3.2 [蛋白名称2]要点

（同样格式为其他蛋白添加）

...（为每个蛋白添加独立小节）

### 3.3 蛋白比较分析

- **结构相似性对比**：[比较结果]
- **功能域对比**：[功能域分析]
- **配体/结合位点对比**：[配体分析]

---

## 第四部分：综合关系分析

### 4.1 结构-功能关联网络

基于上述分析，总结蛋白之间的结构-功能关联网络。

### 4.2 可能的复合物分析

（如多个蛋白可能形成复合物，分析其可能性和结构基础）

### 4.3 通路与生物学过程

分析这些蛋白共同参与的生物学通路和过程。

### 4.4 疾病相关性

（如有）分析这些蛋白与人类疾病的关系。

---

## 第五部分：研究建议

### 5.1 结构解析建议

- **建议优先解析的蛋白/复合物**：[推荐]
- **推荐的研究方法**：[方法建议]

### 5.2 功能验证建议

- **建议的实验验证方向**：[实验方向]
- **可能的互作验证方法**：[验证方法]

### 5.3 潜在应用

- **药物靶点分析**：[靶点分析]
- **生物标志物研究**：[生物标志物]
- **其他应用前景**：[应用前景]

---

## 附录：数据来源

- 单独评估报告（各蛋白结构功能分析）
- String Database 蛋白相互作用网络数据
- UniProt 元数据
- PDB 结构数据库''')

# Batch Protein Interaction Analysis Template (English)
BATCH_INTERACTION_PROMPT_TEMPLATE_EN = os.environ.get('BATCH_INTERACTION_PROMPT_TEMPLATE_EN', '''# Batch Protein Relationship Analysis Report Generator

You are a professional protein structure biologist and bioinformatics expert. Based on the individual evaluation reports and interaction data of multiple proteins, generate a **comprehensive and in-depth protein relationship analysis report**.

## Report Requirements:
1. **Word Count**: Total report should be at least 3000 words
2. **Analysis Depth**: In-depth analysis of structural and functional relationships between proteins
3. **Clear Structure**: Organize content with multi-level headings
4. **Data-Driven**: Combine individual evaluation reports and interaction data for comprehensive analysis

Please generate the report following this framework:

# Batch Protein Relationship Analysis Report

**Abstract**
(Overview of the evaluated protein list, main findings from relationship analysis, and research significance. Approximately 300 words)

---

## Part 1: Protein Overview

### 1.1 Evaluated Protein List

| UniProt ID | Protein Name | Gene Name | PDB Structure Count | Quality Score |
|------------|--------------|-----------|---------------------|---------------|
| [UniProt ID] | [Protein Name] | [Gene Name] | [PDB Structure Count] | [Quality Score] |
... (add a row for each protein)

### 1.2 Overall Data Quality Assessment

- **Protein Coverage Analysis**: [Overall Coverage]%
- **Structure Data Availability**: Total of [Total PDB Structures] structures
- **Functional Overview**: [Functional Summary]

---

## Part 2: Protein Interaction Network Analysis

### 2.1 Known Interaction Relationships

(List protein interaction data from sources like String Database)

| Protein A | Protein B | Confidence | Interaction Type |
|----------|----------|------------|-----------------|
| [Protein A UniProt ID] | [Protein B UniProt ID] | [Confidence Score] | [Interaction Type] |

### 2.2 Structure-Based Interaction Analysis

(Analyze possible structural complementarity and interaction interfaces based on PDB structure data of each protein)

### 2.3 Functional Correlation Analysis

(Analyze functional relationships based on functional descriptions of each protein)

---

## Part 3: Individual Evaluation Report Summary

### 3.1 [Protein Name 1] Key Points

(Briefly summarize key findings from this protein's individual evaluation report)

**UniProt ID**: [UniProt ID]

**Gene Name**: [Gene Name]

**Structural Features**: [Main structural characteristics]

**Functional Role**: [Role in cell/pathway]

**PDB Structure List**: [PDB ID List] (Total [PDB Count] structures)

**Unique Findings**: [If any unique structural or functional findings]

### 3.2 [Protein Name 2] Key Points

(Add similar section for other proteins in the same format)

... (add independent subsections for each protein)

### 3.3 Protein Comparative Analysis

- **Structural Similarity Comparison**: [Comparison results]
- **Functional Domain Comparison**: [Functional domain analysis]
- **Ligand/Binding Site Comparison**: [Ligand analysis]

---

## Part 4: Comprehensive Relationship Analysis

### 4.1 Structure-Function Correlation Network

Based on the above analysis, summarize the structure-function correlation network between proteins.

### 4.2 Possible Complex Analysis

(If multiple proteins may form a complex, analyze their likelihood and structural basis)

### 4.3 Pathways and Biological Processes

Analyze the biological pathways and processes that these proteins collectively participate in.

### 4.4 Disease Association

(If applicable) Analyze the relationship between these proteins and human diseases.

---

## Part 5: Research Recommendations

### 5.1 Structure Determination Recommendations

- **Recommended Priority for Protein/Complex Resolution**: [Recommendation]
- **Recommended Research Methods**: [Method suggestions]

### 5.2 Functional Verification Recommendations

- **Suggested Experimental Verification Directions**: [Experimental directions]
- **Possible Interaction Verification Methods**: [Verification methods]

### 5.3 Potential Applications

- **Drug Target Analysis**: [Target analysis]
- **Biomarker Research**: [Biomarkers]
- **Other Application Prospects**: [Application prospects]

---

## Appendix: Data Sources

- Individual evaluation reports (structural and functional analysis of each protein)
- String Database protein interaction network data
- UniProt metadata
- PDB structure database''')

# English Prompt Template
AI_PROMPT_TEMPLATE_EN = os.environ.get('AI_PROMPT_TEMPLATE_EN', '''# Protein Structure-Function Analysis Report Generator

You are a professional structural biologist and bioinformatics expert. Based on the protein data provided below, generate a **comprehensive and in-depth analysis report**.

## Report Requirements:
1. **Dynamic Numbering**: Only generate sections with actual content, **renumber sections dynamically based on actual content** (the 1st content section is "Part 1", the 2nd is "Part 2", and so on)
2. **Word Count**: Total report should be over 4000 words
3. **Analysis Depth**: Each analysis dimension should have in-depth interpretation
4. **Data-Driven**: Combine specific PDB structure data for analysis

Please generate the report according to the following framework, but **selectively generate sections based on actual data** (skip sections without substantial content):

# [Protein Name] Structure and Function Comprehensive Analysis Report

**UniProt ID**: [UniProt ID] | **Gene Name**: [Gene Name]

**Abstract**
(Based on the provided data, briefly summarize: protein identity, key structural features, main research findings. Approximately 200 words)

---

## Part 1: Protein Basic Information

### Basic Attributes

| Attribute | Value |
|----------|-------|
| Protein Name | [Protein Name] |
| Gene Name | [Gene Name] |
| UniProt ID | [UniProt ID] |
| Organism | [Organism Name] |
| Sequence Length | [Sequence Length] aa |
| Molecular Weight | [Molecular Weight] Da |

### Sequence Feature Analysis

Basic analysis based on provided sequence data:

- **Sequence Composition**: [e.g., rich in certain amino acids, special repeat sequences, transmembrane region predictions]
- **Functional Domain Prediction**: [based on sequence features or provided annotations]
- **Post-Translational Modification Sites**: [if data available or predicted from sequence patterns]

### Function Description

[Direct quote or state "No function description available"]

### Keywords

[List keywords or state "No keywords available"]

---

## Part 2: PDB Structure Overview

### Structure Availability Overview

Based on provided PDB statistics:

| Statistics | Value |
|-----------|-------|
| Total PDB Structures | [Total Structures] |
| Associated Literature | [Literature Count] articles |
| Resolution Range | [Min Resolution] - [Max Resolution] Å |
| Average Resolution | [Average Resolution] Å |
| Quality Score | [Quality Score] |

**Experimental Method Statistics**: [List counts of various methods]

### Literature Research Findings

Analysis based on provided literature data:

- **Research Purpose and Significance**: [Summarize research purposes of associated literature]
- **Main Structural Findings**: [Summarize main structural findings reported in literature]
- **Functional Mechanism Insights**: [Summarize understanding of functional mechanisms]
- **Application Prospects**: [If applicable, summarize application value]

---

## Part 3: PDB Structure Comprehensive Analysis

【Note: This section provides comprehensive analysis of ALL PDB structures, not individual structure-by-structure analysis】

### Overall Data Quality Assessment

Comprehensive evaluation of the overall quality of all structures:

- **Method Applicability**: [Discuss applicability of various experimental methods for this type of protein research]
- **Resolution Distribution**: [Discuss the distribution characteristics of resolution range]
  - <3.0 Å: High resolution, can resolve side chains
  - 3.0-4.0 Å: Medium resolution, can resolve main chain and secondary structure
  - >4.0 Å: Low resolution, can only see overall fold
- **Overall Quality Assessment**: [Provide overall quality judgment based on resolution distribution]

### Comprehensive Structural Composition Analysis

- **Protein Chain Composition**: [List protein chains and their corresponding proteins/fragments across all structures]
- **Non-Protein Components**: [List nucleic acids, glycans, lipids, and other biological macromolecules]
- **Artificial Modifications/Fusion Proteins**: [e.g., tags, fusion proteins (such as BRIL), mutation sites]
- **Antibodies/Fab Fragments**: [If present, explain their role in structural elucidation]

### Comprehensive Ligand/Cofactor Analysis

【If small molecule ligands exist in structures, analyze in detail; if not, explain】

- **Ligand List**: [List all small molecule ligands, ions, cofactors across structures]
- **Ligand Classification**: [Agonists, antagonists, cofactors, substrates, etc.]
- **Binding Site Analysis**: [Describe which region/domain of the protein ligands mainly bind to]
- **Key Interactions**: [Based on structural analysis, types of amino acid residues involved in binding]
- **Functional Significance of Ligands**: [Discuss the role of various ligands in protein function]

### Structural Feature Summary

- **Conformational State Distribution**: [e.g., "active state", "inactive state", "apo state", "G protein complex state", etc.]
- **Unique Structural Features**: [Summarize unique structural features across all structures]
- **Key Functional Sites**: [Active sites, binding pockets, allosteric regulatory sites, etc.]

---

## Part 4: Multi-Structure Comparative Analysis

【Only execute this section when multiple PDB structures exist】

### Structural Difference Analysis

- **Conformational State Comparison**: Compare conformational differences between structures
- **Resolution Differences**: Compare resolution quality of each structure
- **Composition Differences**: Compare ligands, fusion proteins, etc. across structures
- **Unique Features**: Unique aspects of each structure

### Conformational Changes and Functional Correlation

If different conformational states exist, analyze their functional significance:

- Possible functional significance of conformational changes
- Ligand-induced changes (if ligand-bound structures exist)
- Protein-protein interaction interface changes (if complex structures exist)

---

## Part 5: BLAST Similarity Search Results Analysis

【Note: This section is only executed when BLAST search was performed and results are available; skip this section if no BLAST data】

### BLAST Search Results Overview

| Rank | PDB ID | Similarity | Method | Resolution | Protein Name/Source |
|------|--------|-----------|--------|-----------|---------------------|
| 1 | [PDB ID] | [Similarity] | [Method] | [Å] | [Brief description] |
| 2 | [PDB ID] | [Similarity] | [Method] | [Å] | [Brief description] |
| ... | ... | ... | ... | ... | ... |

### Comparison with Target Protein's Own Structures

If BLAST results contain other structures of the target protein itself (from the same UniProt):

**Own Structure List**:

| PDB ID | Similarity | Structural Features/State |
|--------|-----------|---------------------------|
| [PDB ID1] | [Similarity] | [e.g., wild-type apo state] |
| [PDB ID2] | [Similarity] | [e.g., G protein complex] |

**Structural Difference Analysis**:
[Compare differences between these own structures, such as truncations, mutations, different conformations, different ligand-bound states]

[Analyze possible reasons for these differences and their functional significance]

### Homologous Protein Structure Analysis

If BLAST found homologous protein structures from other species or families:

**Homologous Structure List**:

| PDB ID | Similarity | Species | Structural State/Function |
|--------|-----------|---------|--------------------------|
| [PDB ID] | [Similarity] | [Species] | [Description] |

**Conservation Analysis**:
[Infer structural and functional conservation based on sequence similarity]

[If possible, discuss what homologous structures reveal about the target protein]

### Scientific Significance of BLAST Results

[Summarize the value of BLAST search for this research]

- What reference information is provided
- How it helps understand the target protein's structure and function
- Whether there are noteworthy structural templates

---

## Part 6: Comprehensive Discussion and Conclusions

### Structure-Function Relationship Summary

Based on all the real data above, summarize the structure-function relationship:

- **How Structural Features Support Function**: [Inference based on existing evidence]
- **Unique Mechanisms**: [Summarize if there are unique structural mechanisms]
- **Functional Significance of Ligand Binding**: [Summarize if ligand data is available]

### Current Research Status Assessment

- **Structural Elucidation Progress**: [What functional states/conformations are covered by resolved structures]
- **Data Quality Assessment**: [Overall quality level of existing structures]
- **Data Gaps**: [What important states or information lack structural data]

### Research Recommendations

Specific recommendations based on data gaps:

- **Recommended Priority Structures for Resolution**: [Proposed based on functional importance]
- **Recommended Experimental Methods**: [Appropriate experimental techniques based on targets]
- **Drug Design Related Recommendations**: [If target is a drug target, propose based on existing structures]
- **Potential Research Directions**: [Proposed extension directions based on existing findings]''')
