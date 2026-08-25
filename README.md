# Multi-Agent System Workshop

A simple, hands-on multi-agent system built from scratch. Perfect for learning how agents work and adding your own!

## 🎯 What This Is

This is a simplified multi-agent system where:
- **Agents** are independent components that handle specific tasks
- **Orchestrator** routes queries to the right agent
- **Base Classes** make it easy to create new agents
- **API** provides a simple interface to interact with agents

## 🚀 Quick Start

### 1. Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
export GEMINI_API_KEY="your-api-key-here"
```

### 2. Run the Server

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 3. Open the UI

Open `green.html` in your browser to interact with the system.

#### Choosing a theme

The UI ships with three display modes, selectable from the dial in the top-right of the header:

| Mode | Rune | Behaviour |
|------|------|-----------|
| **Lumos** | ☀ | Light — sunlit parchment |
| **Nox** | ☾ | Dark — the Great Hall at midnight |
| **Auto** | ◐ | Follows your operating system, and switches live if the OS setting changes |

Your choice is saved to `localStorage` (key `pensieve-theme`) and applied before first paint, so
there is no flash of the wrong theme on reload. **Auto** is the default. You can also press
`Shift + T` to cycle through the three modes.

## 📁 Project Structure

```
Python-Vanila-MultiAgent-Workshop/
├── agents/
│   ├── __init__.py              # Package initialization
│   ├── base_agent.py            # Base class for all agents
│   ├── orchestrator.py          # Routes queries to agents
│   ├── code_interpreter.py      # Example: Data analysis agent
│   ├── answer_synthesiser.py    # Example: Answer formatting agent
│   └── sample_custom_agent.py   # Template for creating new agents
├── main.py                      # FastAPI server
├── requirements.txt             # Dependencies
├── green.html                   # Web UI
└── README.md                    # This file
```

## 🤖 How Agents Work

### Agent Lifecycle

1. **User sends a query** → API receives it
2. **Orchestrator determines** which agent should handle it
3. **Agent processes** the query and returns a result
4. **Agent can route** to another agent (or return final answer)
5. **Result is returned** to the user

### Agent Structure

Every agent must:
- Inherit from `BaseAgent`
- Implement `get_capabilities()` - describe what it can do
- Implement `process()` - handle the main logic
- Return an `AgentResult` with success, data, and optionally next_agent

## ➕ How to Add Your Own Agent

### Step 1: Create Your Agent File

Create a new file in the `agents/` directory, e.g., `my_agent.py`:

```python
from .base_agent import BaseAgent, AgentResult
from typing import Dict, Any, List

class MyCustomAgent(BaseAgent):
    def __init__(self, api_key: str):
        super().__init__(name="MyCustomAgent", api_key=api_key)
        # Initialize any resources you need
    
    def get_capabilities(self) -> List[str]:
        return [
            "Does something specific",
            "Handles certain queries",
        ]
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResult:
        query = input_data.get("query", "")
        context = input_data.get("context", {})
        files = input_data.get("files", {})
        
        # Your agent logic here
        result_data = {"my_result": "something"}
        
        return AgentResult(
            success=True,
            data=result_data,
            message="Processing completed",
            agent_name=self.name,
            next_agent=None,  # or "AnotherAgent" to chain
        )
```

### Step 2: Register Your Agent

Open `agents/orchestrator.py` and add your agent:

```python
from .my_agent import MyCustomAgent

class AgentOrchestrator:
    def __init__(self, api_key: str):
        # ... existing code ...
        
        self.agents: Dict[str, BaseAgent] = {
            "CodeInterpreter": CodeInterpreterAgent(api_key),
            "AnswerSynthesiser": AnswerSynthesiserAgent(api_key),
            "MyCustomAgent": MyCustomAgent(api_key),  # Add your agent here!
        }
```

### Step 3: Update Routing (Optional)

If you want the orchestrator to automatically route to your agent, update the `_determine_start_agent()` method in `orchestrator.py`:

```python
def _determine_start_agent(self, message: str, files: Optional[Dict[str, str]]) -> str:
    message_lower = message.lower()
    
    # Add your routing logic
    if "my keyword" in message_lower:
        return "MyCustomAgent"
    
    # ... existing routing logic ...
```

### Step 4: Test It!

1. Restart the server
2. Send a query that should trigger your agent
3. Check the response!

## 📝 Example: Creating a Simple Agent

Let's create a "Greeting Agent" that handles greetings:

### 1. Create `agents/greeting_agent.py`:

```python
from .base_agent import BaseAgent, AgentResult
from typing import Dict, Any, List

class GreetingAgent(BaseAgent):
    def __init__(self, api_key: str):
        super().__init__(name="GreetingAgent", api_key=api_key)
    
    def get_capabilities(self) -> List[str]:
        return [
            "Handle greetings and casual conversation",
            "Respond to hello, hi, thanks, etc.",
        ]
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResult:
        query = input_data.get("query", "").lower()
        
        greetings = ["hello", "hi", "hey", "greetings"]
        thanks = ["thanks", "thank you", "appreciate"]
        
        if any(g in query for g in greetings):
            response = "Hello! How can I help you today?"
        elif any(t in query for t in thanks):
            response = "You're welcome! Is there anything else I can help with?"
        else:
            response = "Hi there! What would you like to know?"
        
        return AgentResult(
            success=True,
            data={"greeting": response},
            message="Greeting handled",
            agent_name=self.name,
            next_agent=None,
        )
```

### 2. Register in `orchestrator.py`:

```python
from .greeting_agent import GreetingAgent

# In __init__ method:
self.agents: Dict[str, BaseAgent] = {
    # ... existing agents ...
    "GreetingAgent": GreetingAgent(api_key),
}
```

### 3. Update routing:

```python
def _determine_start_agent(self, message: str, files: Optional[Dict[str, str]]) -> str:
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["hello", "hi", "hey", "thanks"]):
        return "GreetingAgent"
    
    # ... rest of routing ...
```

That's it! Your agent is now integrated.

## 🔄 Agent Chaining

Agents can chain together by setting `next_agent` in the result:

```python
return AgentResult(
    success=True,
    data={"some_data": "value"},
    message="Done processing",
    agent_name=self.name,
    next_agent="AnswerSynthesiser",  # This will be called next!
)
```

The orchestrator will automatically call the next agent with the context from previous agents.

## 📊 Understanding Context

Agents receive context from previous agents:

```python
async def process(self, input_data: Dict[str, Any]) -> AgentResult:
    context = input_data.get("context", {})
    
    # Access previous agent's data
    code_data = context.get("codeinterpreter_data", {})
    viz_data = context.get("visualizationagent_data", {})
    
    # Use the data in your processing
    # ...
```

When you return data, it's automatically added to context with the key `{agent_name.lower()}_data`.

## 🎓 Learning Path

1. **Start Simple**: Look at `sample_custom_agent.py` for a template
2. **Study Examples**: Read `code_interpreter.py` and `answer_synthesiser.py`
3. **Create Your Own**: Copy the template and modify it
4. **Test**: Use the API or UI to test your agent
5. **Iterate**: Add more features, chain agents, etc.

## 🔧 API Endpoints

- `GET /` - System info
- `GET /agents` - List all agents
- `POST /chat` - Send a message
- `POST /upload` - Upload CSV file
- `GET /session/{session_id}` - Get session info
- `DELETE /session/{session_id}` - Delete session
- `GET /history` - Get execution history

## 💡 Tips

1. **Keep agents focused**: Each agent should do one thing well
2. **Use context**: Pass data between agents via context
3. **Handle errors**: Always return proper AgentResult even on errors
4. **Test incrementally**: Test your agent in isolation first
5. **Read the base class**: `base_agent.py` has helpful methods

## 🐛 Troubleshooting

**Agent not found?**
- Make sure you registered it in `orchestrator.py`
- Check the agent name matches exactly

**Agent not being called?**
- Update routing logic in `_determine_start_agent()`
- Or explicitly set `start_agent` when calling `process_query()`

**Context not working?**
- Make sure you're accessing context with the right key: `{agent_name.lower()}_data`
- Check that previous agents are returning data in their results

## 📚 Next Steps

- Add more agents (calculator, translator, etc.)
- Implement agent-to-agent communication
- Add agent selection UI
- Create agent chains for complex workflows
- Add logging and monitoring

## 🤝 Contributing

This is a workshop project! Feel free to:
- Add your own agents
- Improve existing agents
- Add features
- Share your creations

Happy coding! 🚀

