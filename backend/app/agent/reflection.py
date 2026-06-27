# reflection.py
import json
from typing import Dict, List, Any

class Reflector:
    def __init__(self, llm):
        self.llm = llm

    async def reflect(self, goal: str, plan: Dict, results: List[Dict], iteration: int) -> Dict[str, Any]:
        system = "You are a self-reflective AI. Return strict JSON only."
        prompt = f"""
Goal: {goal}
Plan: {json.dumps(plan)}
Execution: {json.dumps([{"success": r["result"].get("success"), "output": str(r["result"].get("output",""))[:100]} for r in results])}
Iteration: {iteration}
Return JSON:
{{
  "summary": "Concise reflection text",
  "success": true/false,
  "lessons": ["lesson1"],
  "goal_complete": true/false,
  "importance": 0.0-1.0,
  "confidence": 0.0-1.0
}}
"""
        return await self.llm.generate_json(prompt, system)