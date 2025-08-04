# Simplex KG-RAG System

A Knowledge Graph-based Retrieval Augmented Generation (RAG) system for Simplex fire alarm products, implementing the BYOKG-RAG framework.

## Overview

This system uses Neo4j as a graph database to store product information, compatibility rules, and licensing requirements for Simplex fire alarm systems. It combines graph-based retrieval with LLM-powered question answering to generate accurate Bills of Quantities (BOQ) for fire alarm projects.

## Architecture

- **Graph Database**: Neo4j for storing product knowledge graph
- **Document Processing**: PyMuPDF for PDF parsing
- **LLM Integration**: OpenAI GPT-4 for knowledge extraction and answer generation
- **API Framework**: FastAPI for RESTful endpoints
- **Cloud Storage**: AWS S3 for document storage

## Setup Instructions

### Prerequisites

- Python 3.11+
- Neo4j 4.4+ (running on DigitalOcean droplet)
- AWS S3 bucket configured
- OpenAI API key

### Installation

1. Clone the repository and navigate to the project directory:
```bash
cd simplex-kg-rag-system
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements-core.txt
```

4. Configure environment variables in `.env` file with your credentials

### Running the System

#### 1. Ingest Documents and Build Knowledge Graph

```bash
python scripts/run_ingestion.py
```

This will:
- Extract documents from S3
- Process them with LLM to extract entities and relationships
- Load the data into Neo4j

#### 2. Start the API Server

```bash
python scripts/run_api.py
```

The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /generate_boq` - Generate Bill of Quantities
- `GET /graph/stats` - Get graph statistics
- `POST /graph/search` - Search products in the graph

### Example Usage

```bash
curl -X POST "http://localhost:8000/generate_boq" \
  -H "Content-Type: application/json" \
  -d '{
    "project_description": "I need a fire alarm system for a 3-story office building with 50 rooms",
    "max_iterations": 2
  }'
```

## Docker Deployment

Build and run with Docker Compose:

```bash
docker-compose up --build
```

## Project Structure

```
simplex-kg-rag-system/
├── src/
│   ├── ingestion/       # Document parsing and knowledge extraction
│   ├── core/            # BYOKG-RAG implementation
│   └── api/             # FastAPI application
├── scripts/             # Utility scripts
├── data/                # Data directories
├── docker/              # Docker configuration
└── tests/               # Test files
```

## Key Components

1. **PDF Parser**: Extracts text and tables from Simplex product PDFs
2. **Knowledge Extractor**: Uses OpenAI to identify entities and relationships
3. **Graph Loader**: Bulk loads extracted knowledge into Neo4j
4. **KG-Linker**: Multi-task prompting for query analysis
5. **Graph Retriever**: Multi-strategy retrieval from knowledge graph
6. **Orchestrator**: Implements iterative refinement algorithm
7. **API**: RESTful endpoints for BOQ generation

## License

This project implements the BYOKG-RAG framework for educational and research purposes.