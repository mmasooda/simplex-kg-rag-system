"""
Simple web chat interface for the Simplex KG-RAG system
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path

# Create router
router = APIRouter()

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

@router.get("/chat", response_class=HTMLResponse)
async def chat_interface(request: Request):
    """Serve the chat interface"""
    return templates.TemplateResponse("chat.html", {"request": request})

# Create the chat template
chat_template = """
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
                I'm powered by advanced Knowledge Graph technology and can help you design fire alarm systems using Simplex products.<br><br>
                <strong>Ask me about:</strong><br>
                • Fire alarm system design for buildings<br>
                • Simplex product recommendations<br>
                • Product compatibility and specifications<br>
                • Bill of quantities generation<br><br>
                <em>Try: "I need a fire alarm system for a 3-story office building with 50 rooms"</em>
            </div>
        </div>
        
        <div class="loading" id="loading">
            <strong>🤖 Analyzing with Knowledge Graph</strong><span class="loading-dots"></span>
        </div>
        
        <div class="chat-input">
            <input type="text" id="messageInput" placeholder="Ask about fire alarm systems..." maxlength="500">
            <button id="sendButton" onclick="sendMessage()">Send</button>
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
            
            let content = `<strong>📋 Fire Alarm System Analysis</strong><br><br>`;
            content += data.answer.replace(/\\n/g, '<br>');
            
            if (data.bill_of_quantities && data.bill_of_quantities.length > 0) {
                content += `<div class="boq-section">`;
                content += `<div class="boq-title">📊 Bill of Quantities:</div>`;
                
                data.bill_of_quantities.forEach(item => {
                    content += `<div class="boq-item">`;
                    content += `<div class="item-header">${item.quantity}x ${item.item}</div>`;
                    content += `<div class="sku">SKU: ${item.sku}</div>`;
                    content += `<div>${item.description}</div>`;
                    if (item.notes) {
                        content += `<div style="margin-top: 5px; font-style: italic; color: #666;">${item.notes}</div>`;
                    }
                    content += `</div>`;
                });
                content += `</div>`;
            }
            
            // Add quality metrics if available
            if (data.metadata && data.metadata.baseline_comparison) {
                const metrics = data.metadata.baseline_comparison;
                content += `<div class="quality-metrics">`;
                content += `<strong>🎯 Quality Analysis:</strong> ${metrics.method_used} `;
                if (metrics.improvement) {
                    content += `(+${metrics.improvement.toFixed(1)} improvement)`;
                }
                content += `</div>`;
            }
            
            // Add iteration info
            if (data.metadata && data.iterations_performed) {
                content += `<div class="iteration-info">`;
                content += `🔄 ${data.iterations_performed} iterations, ${data.metadata.total_context_items || 0} context items analyzed`;
                content += `</div>`;
            }
            
            messageDiv.innerHTML = content;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function showLoading() {
            loadingDiv.style.display = 'block';
            sendButton.disabled = true;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function hideLoading() {
            loadingDiv.style.display = 'none';
            sendButton.disabled = false;
        }
    </script>
</body>
</html>
"""

# Write the template file
template_file = templates_dir / "chat.html"
with open(template_file, 'w') as f:
    f.write(chat_template)