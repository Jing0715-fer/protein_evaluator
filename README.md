# Protein Evaluator

A comprehensive protein structure and function evaluation system that generates professional protein assessment reports using public databases (UniProt, PDB, RCSB) and AI models.

## Overview

Protein Evaluator helps researchers analyze protein structures and functions by:

- Collecting metadata from UniProt (protein names, genes, species, sequences, function descriptions)
- Retrieving detailed PDB structure data (experimental methods, resolution, literature citations)
- Finding homologous proteins through BLAST search
- Analyzing protein interaction networks at the chain level
- Generating comprehensive AI-powered assessment reports

## Key Features

### Single Protein Evaluation
- Fetch complete UniProt metadata for any protein
- Retrieve all associated PDB structures with detailed information
- BLAST search for homologous proteins
- AI-generated analysis report combining all data

### Multi-Target Evaluation
- Evaluate multiple proteins simultaneously
- Two execution modes: parallel (faster) or sequential
- Automatic interaction analysis between targets
- Comprehensive multi-target report generation

### Protein Interaction Analysis
- **Chain-level interaction detection**: Analyzes actual chain-chain contacts within PDB structures using PDBe Interfaces API
- **Direct interactions**: Proteins with chains that physically interact in the same PDB structure
- **Indirect interactions**: Proteins connected through a mediator protein
- Supports gene name synonyms and ORF names for accurate matching

### Report Generation
- Export reports in PDF or Markdown format
- Rich interaction network visualizations
- Detailed PDB structure information for each protein

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 18+
- OpenAI API key or compatible AI API (supports OpenAI/Anthropic Claude/Gemini)

### Installation

**Option 1: Automated script (recommended)**

```bash
# Clone the repository
git clone <repository-url>
cd protein_evaluator

# Run the install script
./install.sh

# Edit .env and add your API keys
nano .env
```

**Option 2: Manual installation**

```bash
# Clone the repository
git clone <repository-url>
cd protein_evaluator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### Configuration

Set your AI API key in the `.env` file:

```bash
export AI_API_KEY="your-api-key"
```

Optional settings:

```bash
export AI_MODEL="gpt-4o"  # Default model
export HOST="0.0.0.0"
export PORT=5002
```

### Running

**Development (recommended):**

```bash
# Terminal 1: Start backend
source .venv/bin/activate
FLASK_APP=app.py python3 -m flask run --port 5002

# Terminal 2: Start frontend
cd frontend
npm run dev
```

Access at http://localhost:5173

**Production:**

```bash
cd frontend
npm run build
cd ..
source .venv/bin/activate
FLASK_APP=app.py python3 -m flask run --port 5002
```

Access at http://localhost:5002

## Workflow

### Single Protein Evaluation

```
Input UniProt ID
    ↓
[Step 1] Fetch UniProt metadata (30%)
    ↓ Protein name, gene, species, sequence, PDB IDs
[Step 2] Fetch PDB structure data (50%)
    ↓ Experimental method, resolution, literature
[Step 3] BLAST homology search (70%)
    ↓ Find similar proteins, analyze homology
[Step 4] AI deep analysis (90%)
    ↓ Generate comprehensive analysis report
[Step 5] Save and export (100%)
```

### Multi-Target Evaluation

```
Input multiple UniProt IDs
    ↓
[Step 1] Create multi-target job
    ↓ Configure mode (parallel/sequential), priority
[Step 2] Evaluate each target (30%-90%)
    ↓ Fetch UniProt/PDB data for each protein
[Step 3] Analyze interactions (90%)
    ↓ Chain-level contact detection via PDBe API
[Step 4] AI comprehensive analysis (95%)
    ↓ Generate multi-target assessment report
[Step 5] Generate report (100%)
```

## API Reference

### v2 API (Multi-Target)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/evaluate/multi` | GET | List all multi-target jobs |
| `/api/v2/evaluate/multi` | POST | Create new job |
| `/api/v2/evaluate/multi/<id>` | GET | Get job details |
| `/api/v2/evaluate/multi/<id>/start` | POST | Start job |
| `/api/v2/evaluate/multi/<id>/progress` | GET | Get progress |
| `/api/v2/evaluate/multi/<id>/interactions/chain` | GET | Get chain-level interactions |
| `/api/v2/evaluate/multi/<id>/report` | GET | Generate report |

### Example

```bash
# Create a multi-target job
curl -X POST http://localhost:5002/api/v2/evaluate/multi \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Evaluation",
    "uniprot_ids": ["P04637", "P00533"],
    "evaluation_mode": "parallel",
    "priority": 5
  }'
```

## Data Sources

- **UniProt**: Protein metadata, gene names, sequences
- **PDB/RCSB**: Protein structure data
- **PDBe**: Chain-level interface data for interaction analysis
- **PubMed**: Literature references

## License

MIT License
