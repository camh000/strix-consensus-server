# Main orchestrator service for Strix Consensus Server
# Handles mode switching, request routing, and tool execution

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
import os
import logging
from datetime import datetime

from consensus_engine import ConsensusEngine
from judge import Judge
from tool_executor import ToolExecutor
from model_pool import ModelPool
from config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Strix Consensus Orchestrator")

# CORS for OpenCode access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
config_manager = ConfigManager()
model_pool = ModelPool()
consensus_engine = ConsensusEngine(model_pool)
judge = Judge(model_pool)
tool_executor = ToolExecutor()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None

class ModeConfig(BaseModel):
    mode: str  # "single" or "consensus"
    worker_count: Optional[int] = 3
    active_worker: Optional[str] = None
    use_judge: Optional[bool] = True

@app.on_event("startup")
async def startup_event():
    """Initialize model pool on startup"""
    logger.info("Starting Strix Consensus Orchestrator...")
    await model_pool.initialize()
    logger.info(f"Orchestrator ready. Mode: {config_manager.get_mode()}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": config_manager.get_mode(),
        "workers": model_pool.get_worker_status(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI compatible)"""
    config = config_manager.get_config()
    models = []
    
    if config['mode'] == 'single':
        # Show single model
        active = config['single_mode']['active_worker']
        models.append({
            "id": "local-model",
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "strix-consensus",
            "description": f"Single Mode: {active}"
        })
    else:
        # Show consensus as single model
        models.append({
            "id": "local-consensus",
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "strix-consensus",
            "description": f"Consensus Mode: {config['consensus_mode']['worker_count']} workers"
        })
    
    return {"object": "list", "data": models}

@app.post("/v1/chat/completions")
async def chat_completion(request: ChatRequest):
    """Main chat completion endpoint"""
    config = config_manager.get_config()
    mode = config['mode']
    
    logger.info(f"Received request in {mode} mode")
    
    try:
        if mode == 'single':
            return await handle_single_mode(request, config)
        else:
            return await handle_consensus_mode(request, config)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def handle_single_mode(request: ChatRequest, config: Dict):
    """Handle single model mode request"""
    worker_id = config['single_mode']['active_worker']
    
    logger.info(f"Routing to single worker: {worker_id}")
    
    response = await model_pool.query_worker(
        worker_id=worker_id,
        messages=[m.dict() for m in request.messages],
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=request.tools
    )
    
    # Handle tool calls if present
    if response.get('tool_calls'):
        logger.info("Executing tool calls...")
        tool_results = await tool_executor.execute_batch(response['tool_calls'])
        
        # Append tool results to conversation and re-query
        messages = [m.dict() for m in request.messages]
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": response['tool_calls']
        })
        
        for result in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": result['tool_call_id'],
                "content": json.dumps(result['output'])
            })
        
        response = await model_pool.query_worker(
            worker_id=worker_id,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
    
    return format_openai_response(response)

async def handle_consensus_mode(request: ChatRequest, config: Dict):
    """Handle consensus mode request"""
    worker_count = config['consensus_mode']['worker_count']
    use_judge = config['consensus_mode']['use_judge']
    
    logger.info(f"Starting consensus with {worker_count} workers (judge: {use_judge})")
    
    # Query all workers in parallel
    worker_responses = await consensus_engine.query_all_workers(
        messages=[m.dict() for m in request.messages],
        worker_count=worker_count,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=request.tools
    )
    
    # Check for tool calls
    any_tools = any(r.get('tool_calls') for r in worker_responses.values())
    
    if any_tools and request.tools:
        # Execute tools using the response that has them
        for worker_id, response in worker_responses.items():
            if response.get('tool_calls'):
                logger.info(f"Executing tools from {worker_id}...")
                tool_results = await tool_executor.execute_batch(response['tool_calls'])
                
                # Re-query all workers with tool results
                messages = [m.dict() for m in request.messages]
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": response['tool_calls']
                })
                
                for result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result['tool_call_id'],
                        "content": json.dumps(result['output'])
                    })
                
                worker_responses = await consensus_engine.query_all_workers(
                    messages=messages,
                    worker_count=worker_count,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                )
                break
    
    # Use judge to select best response
    if use_judge and len(worker_responses) > 1:
        best_response, reasoning = await judge.select_best(
            request=request.messages[-1].content if request.messages else "",
            responses=worker_responses
        )
        
        # Log the decision
        await log_consensus_decision(request, worker_responses, best_response, reasoning)
        
        return format_openai_response(best_response, consensus_info={
            "workers_consulted": list(worker_responses.keys()),
            "judge_reasoning": reasoning
        })
    else:
        # Just return first response if no judge
        first_response = list(worker_responses.values())[0]
        return format_openai_response(first_response)

def format_openai_response(response: Dict, consensus_info: Dict = None) -> Dict:
    """Format response to match OpenAI API spec"""
    return {
        "id": f"chatcmpl-{datetime.now().timestamp()}",
        "object": "chat.completion",
        "created": int(datetime.now().timestamp()),
        "model": response.get('model', 'local-model'),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response.get('content', ''),
                "tool_calls": response.get('tool_calls')
            },
            "finish_reason": response.get('finish_reason', 'stop')
        }],
        "usage": response.get('usage', {}),
        "system_fingerprint": "strix-consensus-v1",
        "consensus_info": consensus_info
    }

async def log_consensus_decision(request, responses, winner, reasoning):
    """Log consensus decision for analysis"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "prompt": request.messages[-1].content if request.messages else "",
        "responses": {k: v.get('content', '')[:500] for k, v in responses.items()},
        "winner": winner.get('worker_id', 'unknown'),
        "reasoning": reasoning
    }
    
    log_file = f"logs/consensus_{datetime.now().strftime('%Y%m%d')}.jsonl"
    os.makedirs('logs', exist_ok=True)
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

# Management endpoints for web UI

@app.get("/api/status")
async def get_status():
    """Get current system status"""
    return {
        "mode": config_manager.get_mode(),
        "config": config_manager.get_config(),
        "workers": model_pool.get_worker_status(),
        "stats": consensus_engine.get_stats()
    }

@app.post("/api/mode")
async def set_mode(mode_config: ModeConfig):
    """Change operating mode"""
    try:
        config_manager.set_mode(
            mode=mode_config.mode,
            worker_count=mode_config.worker_count,
            active_worker=mode_config.active_worker,
            use_judge=mode_config.use_judge
        )
        
        logger.info(f"Mode changed to: {mode_config.mode}")
        return {"status": "success", "mode": mode_config.mode}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/logs")
async def get_logs(limit: int = 100):
    """Get recent consensus logs"""
    log_file = f"logs/consensus_{datetime.now().strftime('%Y%m%d')}.jsonl"
    
    if not os.path.exists(log_file):
        return {"logs": []}
    
    logs = []
    with open(log_file, 'r') as f:
        for line in f:
            try:
                logs.append(json.loads(line))
            except:
                continue
    
    return {"logs": logs[-limit:]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('ORCHESTRATOR_PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
