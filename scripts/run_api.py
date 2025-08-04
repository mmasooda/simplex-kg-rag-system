#!/usr/bin/env python3
"""
Script to run the FastAPI application
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

import uvicorn
from src.api.main import app

if __name__ == "__main__":
    # Run the API server
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )