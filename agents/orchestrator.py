"""
Agent Orchestrator - Manages agents and routes queries
This file shows how to register your custom agents!
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import google.generativeai as genai

from .base_agent import BaseAgent, AgentResult
from .code_interpreter import CodeInterpreterAgent
from .answer_synthesiser import AnswerSynthesiserAgent



class AgentOrchestrator:
    """Manages all agents and routes queries to the right one"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.routing_model = genai.GenerativeModel("gemini-2.5-flash")

        # ============================================
        # REGISTER AGENTS HERE
        # ============================================
        # Add your custom agents to this dictionary
        # Format: "AgentName": AgentClass(api_key)
        # ============================================
        self.agents: Dict[str, BaseAgent] = {
            "CodeInterpreter": CodeInterpreterAgent(api_key),
            "AnswerSynthesiser": AnswerSynthesiserAgent(api_key),
            # Add your custom agents here:
            # "YourCustomAgent": YourCustomAgent(api_key),
        }

        self.execution_history: List[Dict[str, Any]] = []
        self.current_context: Dict[str, Any] = {}

    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Get an agent by name"""
        return self.agents.get(agent_name)

    def list_agents(self) -> Dict[str, List[str]]:
        """List all registered agents and their capabilities"""
        return {name: agent.get_capabilities() for name, agent in self.agents.items()}

    def register_agent(self, name: str, agent: BaseAgent):
        """Register a new agent dynamically"""
        self.agents[name] = agent

    async def process_query(
        self,
        query: str,
        files: Optional[Dict[str, str]] = None,
        start_agent: str = "CodeInterpreter",
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a query through the agent system"""

        if files is None:
            files = {}

        execution_start = datetime.now()

        input_data = {
            "query": query,
            "context": self.current_context.copy(),
            "files": files,
            "session_id": session_id or "default",
        }

        results = {
            "query": query,
            "execution_flow": [],
            "agent_results": {},
            "final_result": None,
            "success": True,
            "error": None,
        }

        current_agent_name = start_agent
        max_iterations = 10
        iteration = 0

        try:
            while current_agent_name and iteration < max_iterations:
                iteration += 1

                agent = self.get_agent(current_agent_name)
                if not agent:
                    raise ValueError(f"Agent {current_agent_name} not found")

                results["execution_flow"].append(
                    {
                        "agent": current_agent_name,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # Process with the agent
                agent_result = await agent.process(input_data)

                results["agent_results"][current_agent_name] = {
                    "success": agent_result.success,
                    "message": agent_result.message,
                    "data": agent_result.data,
                    "metadata": agent_result.metadata,
                }

                if not agent_result.success:
                    results["success"] = False
                    results["error"] = agent_result.message
                    break

                # Add agent results to context
                context_key = f"{current_agent_name.lower()}_data"
                input_data["context"][context_key] = agent_result.data

                # Move to next agent if specified
                current_agent_name = agent_result.next_agent

                # Don't re-process files in subsequent iterations
                if iteration > 1:
                    input_data["files"] = {}

            if results["agent_results"]:
                last_agent = results["execution_flow"][-1]["agent"]
                results["final_result"] = results["agent_results"][last_agent]["data"]

            execution_end = datetime.now()
            self.execution_history.append(
                {
                    "timestamp": execution_start.isoformat(),
                    "duration": (execution_end - execution_start).total_seconds(),
                    "query": query,
                    "success": results["success"],
                    "agents_used": [
                        step["agent"] for step in results["execution_flow"]
                    ],
                }
            )

        except Exception as e:
            results["success"] = False
            results["error"] = str(e)

        return results

    async def chat(
        self,
        message: str,
        files: Optional[Dict[str, str]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Chat interface - determines which agent to start with"""
        start_agent = self._determine_start_agent(message, files)
        if conversation_context:
            self.current_context.update(conversation_context)

        return await self.process_query(message, files, start_agent, session_id)

    async def edit_csv(
        self,
        file_path: str,
        edit_instructions: str,
        output_path: Optional[str] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Edit a CSV file based on instructions"""
        from pathlib import Path
        
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "agent_results": {},
            }
        
        if not file_path_obj.suffix.lower() == ".csv":
            return {
                "success": False,
                "error": "File must be a CSV file",
                "agent_results": {},
            }
        
        # If no output path specified, use the input path (will overwrite)
        if output_path is None:
            output_path = str(file_path_obj)
        
        # Build edit query that includes saving the file
        edit_query = f"""Edit the CSV file at '{file_path}' according to these instructions: {edit_instructions}

IMPORTANT: After making the edits, save the modified DataFrame to '{output_path}' using df.to_csv('{output_path}', index=False)."""
        
        # Update context with edit-specific information
        edit_context = conversation_context.copy() if conversation_context else {}
        edit_context["edit_mode"] = True
        edit_context["input_file"] = file_path
        edit_context["output_file"] = output_path
        
        # Process with CodeInterpreter agent directly
        input_data = {
            "query": edit_query,
            "context": edit_context,
            "files": {file_path_obj.name: str(file_path_obj)},
            "session_id": session_id or "default",
        }
        
        # Use CodeInterpreter agent for CSV editing
        code_interpreter = self.get_agent("CodeInterpreter")
        if not code_interpreter:
            return {
                "success": False,
                "error": "CodeInterpreter agent not found",
                "agent_results": {},
            }
        
        try:
            agent_result = await code_interpreter.process(input_data)
            
            # Check if the file was actually saved
            output_path_obj = Path(output_path)
            file_exists = output_path_obj.exists()
            
            # Also check execution results for file_saved flag
            file_saved_from_code = False
            if agent_result.data and isinstance(agent_result.data, dict):
                # Check execution results
                if "results" in agent_result.data:
                    for exec_result in agent_result.data.get("results", []):
                        if isinstance(exec_result, dict) and exec_result.get("file_saved"):
                            file_saved_from_code = True
                            break
                # Also check if saved_files is in the data
                if agent_result.data.get("saved_files") or agent_result.data.get("file_saved"):
                    file_saved_from_code = True
            
            file_saved = file_exists or file_saved_from_code
            
            results = {
                "query": edit_query,
                "execution_flow": [{"agent": "CodeInterpreter", "timestamp": datetime.now().isoformat()}],
                "agent_results": {
                    "CodeInterpreter": {
                        "success": agent_result.success and file_saved,
                        "message": agent_result.message,
                        "data": {
                            **agent_result.data,
                            "edited_file_path": output_path if file_saved else None,
                            "file_saved": file_saved,
                        },
                        "metadata": agent_result.metadata,
                    }
                },
                "final_result": {
                    "edited_file_path": output_path if file_saved else None,
                    "file_saved": file_saved,
                },
                "success": agent_result.success and file_saved,
                "error": None if (agent_result.success and file_saved) else (
                    agent_result.message if not agent_result.success else "File was not saved"
                ),
            }
            
            # Add to execution history
            self.execution_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "duration": 0,  # Could track this if needed
                    "query": edit_query,
                    "success": results["success"],
                    "agents_used": ["CodeInterpreter"],
                    "action": "edit_csv",
                }
            )
            
            return results
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "agent_results": {},
            }

    def _determine_start_agent(
        self, message: str, files: Optional[Dict[str, str]]
    ) -> str:
        if files:
            return "CodeInterpreter"

        context_info = []
        if self.current_context.get("dataframes"):
            context_info.append("- Data/DataFrames are already loaded in context")
        if self.current_context.get("codeinterpreter_data"):
            context_info.append("- Code analysis has been performed")
        if self.current_context.get("visualizationagent_data"):
            context_info.append("- Visualizations have been created")

        context_str = "\n".join(context_info) if context_info else "- No prior context"

        agent_descriptions = []
        for agent_name, agent in self.agents.items():
            capabilities = agent.get_capabilities()
            agent_descriptions.append(
                f"{agent_name}:\n  " + "\n  ".join(f"• {cap}" for cap in capabilities)
            )

        agents_str = "\n\n".join(agent_descriptions)

        prompt = f"""You are an intelligent agent router. Based on the user's query and current context, determine which agent should handle this request.

                        User Query: "{message}"

                        Current Context:
                        {context_str}

                        Available Agents:
                        {agents_str}

                        Instructions:
                        1. Analyze the user's query carefully
                        2. Consider the current context (what has already been done)
                        3. Choose the MOST APPROPRIATE agent to start processing this query
                        4. Respond with ONLY the agent name, nothing else

                        Rules:
                        - If the query requires data analysis/computation on new data, choose CodeInterpreter
                        - If the query is a general question, explanation, or clarification, choose AnswerSynthesiser
                        - If the query asks about previous results/insights, choose AnswerSynthesiser
                        - If the query is conversational (hello, thanks, what can you do), choose AnswerSynthesiser
                        - DEFAULT: For simple questions or queries without data files, choose AnswerSynthesiser

                        Respond with ONLY ONE of these exact names:
                        - CodeInterpreter
                        - AnswerSynthesiser

                        Your response (agent name only):"""

        try:
            response = self.routing_model.generate_content(prompt)
            selected_agent = response.text.strip()

            if selected_agent in self.agents:
                return selected_agent
            else:
                for agent_name in self.agents.keys():
                    if agent_name.lower() in selected_agent.lower():
                        return agent_name
                print(
                    f"Warning: Gemini returned invalid agent '{selected_agent}', defaulting to CodeInterpreter"
                )
                return "CodeInterpreter"

        except Exception as e:
            print(
                f"Warning: Error in agent selection ({str(e)}), defaulting to CodeInterpreter"
            )
            return "CodeInterpreter"

    def clear_context(self):
        """Clear all context"""
        self.current_context = {}
        for agent in self.agents.values():
            agent.clear_history()

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get execution history"""
        return self.execution_history
