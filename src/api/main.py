"""
FastAPI Application for Simplex KG-RAG System
Exposes RESTful endpoints for Bill of Quantities generation
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import logging
import os
from datetime import datetime
import json
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.orchestrator import BYOKGRAGPipeline

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Simplex KG-RAG API",
    description="Knowledge Graph-based RAG system for Simplex fire alarm products",
    version="1.0.0"
)

# Setup templates for web interface
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for connections
neo4j_driver = None
openai_client = None
pipeline = None

# Request/Response models
class BOQRequest(BaseModel):
    """Request model for BOQ generation"""
    project_description: str = Field(
        ...,
        description="Natural language description of the fire alarm system requirements",
        example="I need a fire alarm system for a 3-story office building with 50 rooms"
    )
    max_iterations: Optional[int] = Field(
        default=2,
        description="Maximum iterations for the BYOKG-RAG algorithm",
        ge=1,
        le=5
    )

class BOQItem(BaseModel):
    """Single item in the Bill of Quantities"""
    item: str
    sku: str
    quantity: int
    description: str
    notes: Optional[str] = None

class BOQResponse(BaseModel):
    """Response model for BOQ generation"""
    request_id: str
    timestamp: str
    answer: str
    bill_of_quantities: List[BOQItem]
    metadata: Dict[str, Any]

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    neo4j_connected: bool
    openai_connected: bool
    timestamp: str

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global neo4j_driver, openai_client, pipeline
    
    try:
        # Initialize Neo4j driver
        neo4j_driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        
        # Test Neo4j connection
        with neo4j_driver.session() as session:
            session.run("RETURN 1")
        logger.info("Neo4j connection established")
        
        # Initialize OpenAI client
        openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        logger.info("OpenAI client initialized")
        
        # Initialize BYOKG-RAG pipeline
        pipeline = BYOKGRAGPipeline(
            openai_client=openai_client,
            neo4j_driver=neo4j_driver,
            max_iterations=2
        )
        logger.info("BYOKG-RAG pipeline initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global neo4j_driver
    
    if neo4j_driver:
        neo4j_driver.close()
        logger.info("Neo4j connection closed")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - serve chat interface directly"""
    return HTMLResponse(content=get_chat_template())

def get_chat_template():
    """Get the chat interface HTML template"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simplex KG-RAG Fire Alarm Assistant</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .chat-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            width: 90%;
            max-width: 800px;
            height: 80vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .chat-header {
            background: linear-gradient(135deg, #ff6b6b, #feca57);
            color: white;
            padding: 20px;
            text-align: center;
        }
        
        .chat-header h1 {
            font-size: 24px;
            margin-bottom: 5px;
        }
        
        .chat-header p {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .message {
            max-width: 80%;
            padding: 15px 20px;
            border-radius: 20px;
            line-height: 1.5;
        }
        
        .message.user {
            background: #667eea;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 5px;
        }
        
        .message.assistant {
            background: #f8f9fa;
            color: #333;
            align-self: flex-start;
            border-bottom-left-radius: 5px;
            border: 1px solid #e9ecef;
        }
        
        .message.assistant .boq-section {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #dee2e6;
        }
        
        .message.assistant .boq-title {
            font-weight: bold;
            color: #495057;
            margin-bottom: 10px;
        }
        
        .boq-item {
            background: #fff;
            padding: 10px;
            margin: 5px 0;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        
        .boq-item .item-header {
            font-weight: bold;
            color: #333;
        }
        
        .boq-item .sku {
            color: #6c757d;
            font-size: 12px;
        }
        
        .loading {
            display: none;
            align-self: flex-start;
            background: #f8f9fa;
            padding: 15px 20px;
            border-radius: 20px;
            border-bottom-left-radius: 5px;
        }
        
        .loading-dots {
            display: inline-block;
        }
        
        .loading-dots:after {
            content: '...';
            animation: dots 1.5s steps(5, end) infinite;
        }
        
        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60% { content: '...'; }
            90%, 100% { content: ''; }
        }
        
        .chat-input {
            padding: 20px;
            border-top: 1px solid #e9ecef;
            display: flex;
            gap: 10px;
        }
        
        .chat-input input {
            flex: 1;
            padding: 15px 20px;
            border: 1px solid #e9ecef;
            border-radius: 25px;
            outline: none;
            font-size: 16px;
        }
        
        .chat-input input:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .chat-input button {
            padding: 15px 25px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            transition: background 0.3s;
        }
        
        .chat-input button:hover {
            background: #5a6fd8;
        }
        
        .chat-input button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .quality-metrics {
            margin-top: 10px;
            padding: 10px;
            background: #e8f4ff;
            border-radius: 8px;
            font-size: 12px;
            color: #0066cc;
        }
        
        .iteration-info {
            margin-top: 5px;
            font-size: 11px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>🔥 Simplex KG-RAG Assistant</h1>
            <p>Advanced Fire Alarm System Design with Knowledge Graph Intelligence</p>
        </div>
        
        <div class="chat-messages" id="messages">
            <div class="message assistant">
                <strong>👋 Welcome to the Simplex Fire Alarm Assistant!</strong><br><br>
                I'm powered by advanced Knowledge Graph technology and iterative refinement algorithms to provide the highest quality fire alarm system recommendations.<br><br>
                <strong>What makes me different:</strong><br>
                • 🧠 Multi-iteration analysis for better accuracy<br>
                • 📊 Knowledge graph-based product compatibility<br>
                • 🔄 Automatic quality comparison with baseline RAG<br>
                • 🎯 Confidence-weighted technical recommendations<br><br>
                <strong>Ask me about:</strong><br>
                • Fire alarm system design for any building type<br>
                • Specific Simplex product recommendations<br>
                • Product compatibility and technical specifications<br>
                • Detailed bill of quantities with justifications<br><br>
                <em>Try: "I need a fire alarm system for a 10-story office building with 200 rooms and a parking garage"</em>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <strong>🤖 Running BYOKG-RAG iterations</strong><span class="loading-dots"></span>
        </div>
        
        <div class="chat-input">
            <input type="text" id="messageInput" placeholder="Describe your fire alarm system requirements..." maxlength="500">
            <button id="sendButton" onclick="sendMessage()">Analyze</button>
        </div>
    </div>

    <script>
        const messagesDiv = document.getElementById('messages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const loadingDiv = document.getElementById('loading');
        
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;
            
            // Add user message
            addMessage(message, 'user');
            messageInput.value = '';
            
            // Show loading
            showLoading();
            
            try {
                const response = await fetch('/generate_boq', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        project_description: message,
                        max_iterations: 3
                    })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    addAssistantMessage(data);
                } else {
                    addMessage('Sorry, I encountered an error: ' + (data.detail || 'Unknown error'), 'assistant');
                }
                
            } catch (error) {
                addMessage('Sorry, I encountered a connection error. Please try again.', 'assistant');
                console.error('Error:', error);
            } finally {
                hideLoading();
            }
        }
        
        function addMessage(text, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}`;
            messageDiv.innerHTML = text.replace(/\\n/g, '<br>');
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function addAssistantMessage(data) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message assistant';
            
            let content = `<strong>🔬 Advanced Knowledge Graph Analysis</strong><br><br>`;
            content += data.answer.replace(/\\n/g, '<br>');
            
            if (data.bill_of_quantities && data.bill_of_quantities.length > 0) {
                content += `<div class="boq-section">`;
                content += `<div class="boq-title">📊 Optimized Bill of Quantities:</div>`;
                
                data.bill_of_quantities.forEach(item => {
                    content += `<div class="boq-item">`;
                    content += `<div class="item-header">${item.quantity}x ${item.item}</div>`;
                    content += `<div class="sku"><strong>SKU:</strong> ${item.sku}</div>`;
                    content += `<div style="margin-top: 5px;">${item.description}</div>`;
                    if (item.notes) {
                        content += `<div style="margin-top: 5px; font-style: italic; color: #666;"><strong>Technical Notes:</strong> ${item.notes}</div>`;
                    }
                    content += `</div>`;
                });
                content += `</div>`;
            }
            
            // Add quality metrics if available
            if (data.metadata && data.metadata.baseline_comparison) {
                const metrics = data.metadata.baseline_comparison;
                content += `<div class="quality-metrics">`;
                content += `<strong>🎯 Quality Analysis:</strong> ${metrics.method_used.replace(/_/g, ' ')} `;
                if (metrics.improvement > 0) {
                    content += `<br><strong>Improvement:</strong> +${metrics.improvement.toFixed(1)} points vs baseline RAG`;
                }
                if (metrics.reasoning) {
                    content += `<br><strong>Selection Reason:</strong> ${metrics.reasoning}`;
                }
                content += `</div>`;
            }
            
            // Add iteration info
            if (data.metadata) {
                content += `<div class="iteration-info">`;
                content += `🔄 ${data.iterations_performed} BYOKG-RAG iterations`;
                if (data.metadata.total_context_items) {
                    content += `, ${data.metadata.total_context_items} context items analyzed`;
                }
                if (data.metadata.unique_facts_discovered) {
                    content += `, ${data.metadata.unique_facts_discovered} unique facts discovered`;
                }
                content += `</div>`;
            }
            
            messageDiv.innerHTML = content;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function showLoading() {
            loadingDiv.style.display = 'block';
            sendButton.disabled = true;
            sendButton.textContent = 'Analyzing...';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function hideLoading() {
            loadingDiv.style.display = 'none';
            sendButton.disabled = false;
            sendButton.textContent = 'Analyze';
        }
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=get_chat_template())

@app.get("/chat", response_class=HTMLResponse)
async def chat_interface():
    """Serve the chat interface"""
    return HTMLResponse(content=get_chat_template())

@app.get("/api", response_model=Dict[str, str])
async def api_info():
    """API information endpoint"""
    return {
        "message": "Simplex KG-RAG API",
        "documentation": "/docs",
        "health": "/health",
        "chat_interface": "/chat"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    neo4j_connected = False
    openai_connected = False
    
    # Check Neo4j
    try:
        with neo4j_driver.session() as session:
            session.run("RETURN 1")
        neo4j_connected = True
    except:
        pass
    
    # Check OpenAI
    try:
        # Simple test - list models
        openai_client.models.list()
        openai_connected = True
    except:
        pass
    
    return HealthResponse(
        status="healthy" if neo4j_connected and openai_connected else "unhealthy",
        neo4j_connected=neo4j_connected,
        openai_connected=openai_connected,
        timestamp=datetime.utcnow().isoformat()
    )

@app.post("/generate_boq", response_model=BOQResponse)
async def generate_boq(request: BOQRequest):
    """
    Generate a Bill of Quantities based on project requirements
    
    This endpoint processes natural language project descriptions and returns
    a structured BOQ with compatible Simplex products.
    """
    global pipeline
    
    if not pipeline:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Generate request ID
        request_id = f"boq_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Processing BOQ request {request_id}: {request.project_description[:100]}...")
        
        # Update pipeline iterations if specified
        if request.max_iterations:
            pipeline.max_iterations = request.max_iterations
        
        # Process query through BYOKG-RAG pipeline
        result = pipeline.process_query(request.project_description)
        
        # Convert to response format
        boq_items = []
        for item in result.bill_of_quantities:
            boq_items.append(BOQItem(
                item=item.get('item', ''),
                sku=item.get('sku', ''),
                quantity=item.get('quantity', 1),
                description=item.get('description', ''),
                notes=item.get('notes')
            ))
        
        response = BOQResponse(
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
            answer=result.answer,
            bill_of_quantities=boq_items,
            metadata={
                "iterations_performed": result.iterations_performed,
                "context_items_used": result.metadata.get('total_context_items', 0)
            }
        )
        
        logger.info(f"Successfully generated BOQ {request_id} with {len(boq_items)} items")
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating BOQ: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating BOQ: {str(e)}")

@app.get("/graph/stats", response_model=Dict[str, Any])
async def get_graph_stats():
    """Get statistics about the knowledge graph"""
    try:
        stats = {}
        
        with neo4j_driver.session() as session:
            # Count nodes by type
            node_counts = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY count DESC
            """)
            
            stats['nodes'] = {record['label']: record['count'] for record in node_counts}
            
            # Count relationships by type
            rel_counts = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """)
            
            stats['relationships'] = {record['type']: record['count'] for record in rel_counts}
            
            # Total counts
            total_nodes = session.run("MATCH (n) RETURN count(n) as count").single()['count']
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()['count']
            
            stats['totals'] = {
                'nodes': total_nodes,
                'relationships': total_rels
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting graph stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting graph statistics: {str(e)}")

@app.post("/graph/search", response_model=List[Dict[str, Any]])
async def search_graph(query: str, limit: int = 10):
    """Search for products in the knowledge graph"""
    try:
        results = []
        
        with neo4j_driver.session() as session:
            # Search across different node types
            search_results = session.run("""
                MATCH (n)
                WHERE n.name CONTAINS $query 
                   OR n.sku CONTAINS $query 
                   OR n.description CONTAINS $query
                RETURN n, labels(n)[0] as label
                LIMIT $limit
            """, query=query, limit=limit)
            
            for record in search_results:
                node_data = dict(record['n'])
                node_data['_label'] = record['label']
                results.append(node_data)
        
        return results
        
    except Exception as e:
        logger.error(f"Error searching graph: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching graph: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)