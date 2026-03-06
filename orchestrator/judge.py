# Judge - Evaluates and selects best response from multiple workers

import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """You are an expert evaluator. You will be given a user's request and multiple responses from different AI models.

Your task is to evaluate each response and select the BEST one based on:
1. Accuracy and correctness
2. Completeness of the answer
3. Clarity and reasoning quality
4. Relevance to the request

USER REQUEST:
{request}

RESPONSES:
{responses}

Evaluate each response and select the best one. Provide your reasoning.

Respond in this exact format:
BEST: [worker_id]
REASONING: [your detailed explanation of why this response is best]
"""

class Judge:
    def __init__(self, model_pool):
        self.model_pool = model_pool
        self.judge_id = "judge"
    
    async def select_best(
        self,
        request: str,
        responses: Dict[str, Dict]
    ) -> Tuple[Dict, str]:
        """
        Select the best response from multiple worker responses.
        
        Returns:
            Tuple of (best_response_dict, reasoning_string)
        """
        
        # Format responses for judge
        formatted_responses = []
        for worker_id, response in responses.items():
            content = response.get('content', '[No content]')
            formatted_responses.append(f"\n--- {worker_id} ---\n{content[:2000]}")
        
        # Create judge prompt
        judge_prompt = JUDGE_PROMPT.format(
            request=request[:1000],
            responses="\n".join(formatted_responses)
        )
        
        logger.info("Querying judge for evaluation...")
        
        # Query judge model
        try:
            judge_response = await self.model_pool.query_worker(
                worker_id=self.judge_id,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator."},
                    {"role": "user", "content": judge_prompt}
                ],
                temperature=0.3,  # Lower temperature for consistent evaluation
                max_tokens=1000
            )
            
            # Parse judge response
            judge_text = judge_response.get('content', '')
            best_worker, reasoning = self._parse_judge_response(judge_text)
            
            if best_worker and best_worker in responses:
                logger.info(f"Judge selected: {best_worker}")
                best_response = responses[best_worker].copy()
                best_response['worker_id'] = best_worker
                return best_response, reasoning
            else:
                logger.warning(f"Judge selected unknown worker: {best_worker}, using first")
                first_key = list(responses.keys())[0]
                first_response = responses[first_key].copy()
                first_response['worker_id'] = first_key
                return first_response, f"Parse error, defaulted to {first_key}"
                
        except Exception as e:
            logger.error(f"Judge evaluation failed: {e}")
            # Fallback to first response
            first_key = list(responses.keys())[0]
            first_response = responses[first_key].copy()
            first_response['worker_id'] = first_key
            return first_response, f"Judge error: {str(e)}"
    
    def _parse_judge_response(self, text: str) -> Tuple[str, str]:
        """Parse judge response to extract best worker and reasoning"""
        lines = text.strip().split('\n')
        
        best_worker = None
        reasoning_lines = []
        in_reasoning = False
        
        for line in lines:
            line = line.strip()
            if line.startswith('BEST:'):
                best_worker = line.replace('BEST:', '').strip()
            elif line.startswith('REASONING:'):
                in_reasoning = True
                reasoning_lines.append(line.replace('REASONING:', '').strip())
            elif in_reasoning:
                reasoning_lines.append(line)
        
        reasoning = ' '.join(reasoning_lines) if reasoning_lines else "No reasoning provided"
        
        return best_worker, reasoning
    
    async def evaluate_individual(
        self,
        request: str,
        response: str,
        criteria: List[str] = None
    ) -> Dict[str, Any]:
        """Evaluate a single response with detailed scoring"""
        
        criteria = criteria or ["accuracy", "completeness", "clarity"]
        
        eval_prompt = f"""Evaluate the following response to the user's request.

REQUEST: {request[:500]}

RESPONSE: {response[:1000]}

Rate the response 1-10 on:
{chr(10).join(f"- {c.title()}" for c in criteria)}

Provide ratings and brief justification."""
        
        try:
            result = await self.model_pool.query_worker(
                worker_id=self.judge_id,
                messages=[{"role": "user", "content": eval_prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            return {
                "evaluation": result.get('content', ''),
                "criteria": criteria
            }
        except Exception as e:
            logger.error(f"Individual evaluation failed: {e}")
            return {"error": str(e)}
