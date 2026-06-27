import uuid
import json
from typing import Dict, Any, List
from datetime import datetime

class AgentCycle:
    """
    Observe → Retrieve Memory → Plan → Execute → Evaluate → Reflect → Store → Repeat
    """
    def __init__(self, memory, llm, tools):
        self.memory = memory
        self.llm = llm
        self.tools = tools
    
    async def run(self, user_goal: str, max_iterations: int = 5) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        iteration = 0
        execution_history: List[Dict] = []
        
        # Store goal
        goal_id = self.memory.store(user_goal, "goal", task_id, importance=0.9, confidence=1.0)
        
        while iteration < max_iterations:
            iteration += 1
            
            # 1. OBSERVE: build current state from history
            state_text = f"Goal: {user_goal}\nCompleted steps: {len(execution_history)}"
            
            # 2. RETRIEVE semantic memory
            memories = self.memory.retrieve(
                query=state_text,
                categories=["goal", "plan", "reflection", "tool_output", 
                           "workflow_result", "learned_experience", "preference"],
                task_id=task_id,
                top_k=10
            )
            
            # 3. BUILD CONTEXT
            context = self._build_context(memories, user_goal)
            
            # 4. PLAN
            plan = await self._plan(user_goal, context, execution_history)
            plan_id = self.memory.store(
                json.dumps(plan), "plan", task_id, importance=0.7, confidence=0.8, related=[goal_id]
            )
            
            # 5. EXECUTE
            step_results = []
            for step in plan.get("steps", []):
                tool_name = step.get("tool")
                params = step.get("params", {})
                
                if tool_name and tool_name != "reasoning":
                    result = await self.tools.execute(tool_name, params, task_id)
                else:
                    result = {"success": True, "output": step.get("description", "Reasoning")}
                
                step_results.append({"step": step, "result": result})
                
                if not result.get("success"):
                    break
            
            execution_history.append({
                "iteration": iteration,
                "plan": plan,
                "results": step_results
            })
            
            # 6. EVALUATE & REFLECT
            reflection = await self._reflect(user_goal, plan, step_results, iteration)
            ref_id = self.memory.store(
                reflection.get("summary", "Reflection"),
                "reflection",
                task_id,
                importance=reflection.get("importance", 0.7),
                confidence=reflection.get("confidence", 0.8),
                related=[plan_id]
            )
            self.memory.link(goal_id, ref_id)
            
            # 7. CHECK COMPLETION
            if reflection.get("goal_complete", False):
                break
        
        # Generate the final response for the user
        final_prompt = f"""
            You are Synapse, a helpful AI assistant.

            The user's request:
            {user_goal}

            Relevant memory:
            {context}

            Reflection:
            {reflection.get("summary", "")}

            Respond naturally to the user. Do NOT explain your planning process.
            """

        final_response = await self.llm.generate(final_prompt)
        print("FINAL RESPONSE TYPE:", type(final_response))
        print("FINAL RESPONSE:", final_response)        
        return {
            "task_id": task_id,
            "iterations": iteration,
            "goal": user_goal,
            "history": execution_history,
            "final_reflection": reflection,
            "final_response": final_response,
            "status": "completed"
        }
    
    def _build_context(self, memories: List[Dict], goal: str) -> str:
        lines = [f"GOAL: {goal}\n--- RETRIEVED MEMORIES ---"]
        seen = set()
        for m in memories:
            key = m["text"][:80]
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"[{m['category'].upper()} | Score:{m['retrieval_score']:.2f} | {m['timestamp'][:10]}]\n{m['text'][:400]}"
            )
        lines.append("--- END CONTEXT ---")
        return "\n\n".join(lines)
    
    async def _plan(self, goal: str, context: str, history: List[Dict]) -> Dict[str, Any]:
        tools_info = self.tools.list_tools()
        system = "You are an autonomous planning agent. Return strict JSON only."
        prompt = f"""
{context}

HISTORY: {json.dumps([{"iteration": h["iteration"], "results": [r["result"].get("success") for r in h["results"]]} for h in history])}

AVAILABLE TOOLS:
{json.dumps(tools_info, indent=2)}

Create a plan to achieve the goal. If the goal is already achieved based on history, set goal_complete to true.
Return JSON:
{{
  "reasoning": "Why this plan",
  "steps": [
    {{"step_number": 1, "description": "...", "tool": "tool_name_or_null", "params": {{}}}}
  ],
  "goal_complete": false
}}
"""
        return await self.llm.generate_json(prompt, system)
    
    async def _reflect(self, goal: str, plan: Dict, results: List[Dict], iteration: int) -> Dict[str, Any]:
        system = "You are a self-reflective AI. Return strict JSON only."
        prompt = f"""
Goal: {goal}
Plan: {json.dumps(plan)}
Execution: {json.dumps([{"success": r["result"].get("success"), "output": str(r["result"].get("output",""))[:100]} for r in results])}
Iteration: {iteration}

Analyze execution. Return JSON:
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