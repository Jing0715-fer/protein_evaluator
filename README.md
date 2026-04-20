# Protein Evaluator

A comprehensive protein structure and function evaluation system that generates professional protein assessment reports using public databases (UniProt, PDB, RCSB) and AI models.

## Features

### Single Protein Evaluation
- Fetch complete UniProt metadata for any protein
- Retrieve all associated PDB structures with detailed information
- BLAST search for homologous proteins
- AI-generated two-stage analysis report (statistical summary + final report)

### Multi-Target Evaluation
- Evaluate multiple proteins simultaneously
- Two execution modes: parallel (faster) or sequential
- Automatic interaction analysis between targets at chain level
- Comprehensive multi-target report generation

### Real-time Progress Tracking
- Live log display during evaluation
- Bilingual step indicators: [Step 1/6] / [Step 1/6] - automatically translated in English interface
- Sub-progress tracking: PDB fetch (1/19, 2/19...), AI stages (Stage 1/2, Stage 2/2)
- Log messages are translated to English when using English interface

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 18+ (optional, for frontend mode)
- AI API key (OpenAI/Anthropic/Doubao compatible)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd protein_evaluator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## Configuration

You can configure API keys in two ways:

**Option 1: Environment variables (.env)**
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

Required in `.env`:
```bash
AI_API_KEY=your-api-key-here
AI_MODEL=doubao-seed-2.0-pro  # or gpt-4o, claude-3-opus, etc.
AI_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v1  # for Doubao
```

**Option 2: UI Settings (Template mode only)**
API keys can be configured directly in the web interface when using the HTML template mode. Navigate to Settings to add, edit, and test AI models.

---

## Running

You can run the application in two modes:

### Mode 1: Frontend (React/Vite)

This mode uses the React frontend with Vite dev server.

```bash
# Start backend (Terminal 1)
source venv/bin/activate
python app.py

# Start frontend (Terminal 2)
cd frontend && npm install && npm run dev
```

Access at http://localhost:5173

**Production build:**
```bash
cd frontend && npm run build && cd ..
python app.py
```

Access at http://localhost:5002 (frontend is served by Flask)

---

### Mode 2: HTML Template (No Node.js required)

This mode uses Jinja2 templates with vanilla JavaScript. No Node.js installation needed.

```bash
# Start backend only
source venv/bin/activate
python app.py
```

Access at http://localhost:5002/api/evaluation/page

This mode provides:
- Dashboard with job management
- Real-time SSE progress updates
- Job detail view with chain interaction visualization
- Settings page for API key configuration
- Template management

---

## Evaluation Workflow

```
[Step 1/6] Fetch UniProt metadata
[Step 2/6] Fetch PDB structures (progress: 1/19, 2/19...)
[Step 3/6] BLAST homology search (or skip if coverage > 50%)
[Step 4/6] Fetch PubMed abstracts
[Step 5/6] AI analysis (Stage 1/2: statistical summary, Stage 2/2: final report)
[Step 6/6] Generate evaluation report
```

## API Reference

### v2 API (Multi-Target)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/evaluate/multi` | GET | List all jobs |
| `/api/v2/evaluate/multi` | POST | Create new job |
| `/api/v2/evaluate/multi/<id>` | GET | Get job details |
| `/api/v2/evaluate/multi/<id>/start` | POST | Start job |
| `/api/v2/evaluate/multi/<id>/progress` | GET | Get progress |
| `/api/v2/evaluate/multi/<id>/logs` | GET | Get real-time logs |
| `/api/v2/evaluate/multi/<id>/interactions/chain` | GET | Chain-level interactions |
| `/api/v2/evaluate/multi/<id>/report` | POST | Generate report |

### Example

```bash
# Create and start a job
curl -X POST http://localhost:5002/api/v2/evaluate/multi \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Evaluation",
    "uniprot_ids": ["P04637", "P00533"],
    "evaluation_mode": "parallel"
  }'
```

## Data Sources

- **UniProt**: Protein metadata, gene names, sequences
- **PDB/RCSB**: Protein structure data
- **PDBe**: Chain-level interface data
- **PubMed**: Literature references

## License

MIT License
