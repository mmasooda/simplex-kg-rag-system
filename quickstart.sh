#!/bin/bash

echo "================================"
echo "Simplex KG-RAG System Quickstart"
echo "================================"

# Activate virtual environment
source venv/bin/activate

# Menu
echo ""
echo "What would you like to do?"
echo "1) Run system tests"
echo "2) Ingest documents and build knowledge graph"
echo "3) Start API server"
echo "4) Run full pipeline (ingest + API)"
echo "5) Exit"

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "Running system tests..."
        python scripts/test_system.py
        ;;
    2)
        echo "Starting document ingestion..."
        python scripts/run_ingestion.py
        ;;
    3)
        echo "Starting API server..."
        echo "API will be available at http://localhost:8000"
        echo "Documentation at http://localhost:8000/docs"
        python scripts/run_api.py
        ;;
    4)
        echo "Running full pipeline..."
        echo "Step 1: Ingesting documents..."
        python scripts/run_ingestion.py
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "Step 2: Starting API server..."
            echo "API will be available at http://localhost:8000"
            echo "Documentation at http://localhost:8000/docs"
            python scripts/run_api.py
        else
            echo "Ingestion failed. Please check the logs."
        fi
        ;;
    5)
        echo "Exiting..."
        exit 0
        ;;
    *)
        echo "Invalid choice. Please run the script again."
        ;;
esac