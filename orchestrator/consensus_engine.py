# Consensus Engine - Handles parallel worker queries

import asyncio
import aiohttp
import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ConsensusEngine:
    def __init__(self, model_pool):
        self.model_pool = model_pool
        self.stats = {
            "total_requests": 0,
            "consensus_requests": 0,
            "avg_latency": 0,
            "worker_usage": {}
        }
    
    async def query_all_workers(
        self,
        messages: List[Dict],
        worker_count: int,
        temperature: float = 0.7,
        max_tokens: int = None,
        tools: List[Dict] = None
    ) -> Dict[str, Any]:
        """Query multiple workers in parallel"""
        
        # Get available workers
        available_workers = self.model_pool.get_available_workers()
        
        if len(available_workers) < worker_count:
            logger.warning(f"Requested {worker_count} workers but only {len(available_workers)} available")
            worker_count = len(available_workers)
        
        # Select workers
        selected_workers = available_workers[:worker_count]
        
        # Create tasks for parallel execution
        tasks = []
        for worker in selected_workers:
            task = self._query_worker_with_timeout(
                worker_id=worker['id'],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools
            )
            tasks.append((worker['id'], task))
        
        # Execute all queries in parallel
        responses = {}
        start_time = datetime.now()
        
        results = await asyncio.gather(
            *[task for _, task in tasks],
            return_exceptions=True
        )
        
        latency = (datetime.now() - start_time).total_seconds()
        
        # Process results
        for (worker_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.error(f"Worker {worker_id} failed: {result}")
                responses[worker_id] = {
                    "error": str(result),
                    "content": "[Worker failed to respond]"
                }
            else:
                responses[worker_id] = result
                responses[worker_id]['worker_id'] = worker_id
                
                # Update stats
                self.stats["worker_usage"][worker_id] = self.stats["worker_usage"].get(worker_id, 0) + 1
        
        # Update statistics
        self.stats["total_requests"] += 1
        self.stats["consensus_requests"] += 1
        
        # Update average latency
        n = self.stats["consensus_requests"]
        self.stats["avg_latency"] = (self.stats["avg_latency"] * (n - 1) + latency) / n
        
        logger.info(f"Consensus query completed in {latency:.2f}s with {len(responses)} responses")
        
        return responses
    
    async def _query_worker_with_timeout(
        self,
        worker_id: str,
        messages: List[Dict],
        temperature: float,
        max_tokens: int,
        tools: List[Dict],
        timeout: int = 120
    ) -> Dict:
        """Query a worker with timeout"""
        try:
            return await asyncio.wait_for(
                self.model_pool.query_worker(
                    worker_id=worker_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise Exception(f"Worker {worker_id} timed out after {timeout}s")
    
    def get_stats(self) -> Dict:
        """Get consensus engine statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics"""
        self.stats = {
            "total_requests": 0,
            "consensus_requests": 0,
            "avg_latency": 0,
            "worker_usage": {}
        }
