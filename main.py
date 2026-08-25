"""
Multi-Agent System API
Simple FastAPI server for the multi-agent system
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import shutil
from pathlib import Path
import uuid
from datetime import datetime

from agents.orchestrator import AgentOrchestrator

app = FastAPI(
    title="Multi-Agent System API",
    description="A simple multi-agent system for data analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = ''
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable not set")

orchestrator = AgentOrchestrator(api_key=GEMINI_API_KEY)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

VIZ_DIR = Path("visualizations")
VIZ_DIR.mkdir(exist_ok=True)

sessions: Dict[str, Dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    session_id: str
    response: Dict[str, Any]
    timestamp: str


class AgentInfo(BaseModel):
    name: str
    capabilities: List[str]

class EditCsvRequest(BaseModel):
    session_id: str
    filename: str
    edit_instructions: str
    save_as_new: Optional[bool] = False


@app.get("/")
async def root():
    return {
        "name": "Multi-Agent System API",
        "version": "1.0.0",
        "status": "running",
        "agents": list(orchestrator.list_agents().keys()),
    }


@app.get("/agents", response_model=List[AgentInfo])
async def list_agents():
    """List all available agents"""
    agents_info = []
    for name, capabilities in orchestrator.list_agents().items():
        agents_info.append(AgentInfo(name=name, capabilities=capabilities))
    return agents_info


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint - process natural language queries"""
    try:
        session_id = request.session_id or str(uuid.uuid4())

        if session_id not in sessions:
            sessions[session_id] = {
                "created_at": datetime.now().isoformat(),
                "context": {},
                "history": [],
            }

        session = sessions[session_id]

        files = session.get("uploaded_files", None)
        results = await orchestrator.chat(
            message=request.message,
            files=files,
            conversation_context=session["context"],
        )

        if results["success"] and results.get("agent_results"):
            for agent_name, agent_result in results["agent_results"].items():
                session["context"][f"{agent_name.lower()}_data"] = agent_result["data"]

        session["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "message": request.message,
                "results": results,
            }
        )

        return ChatResponse(
            success=results["success"],
            session_id=session_id,
            response=results,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    message: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
):
    """Upload a CSV file"""
    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        session_id = session_id or str(uuid.uuid4())

        if session_id not in sessions:
            sessions[session_id] = {
                "created_at": datetime.now().isoformat(),
                "context": {},
                "history": [],
                "uploaded_files": {},
            }

        session = sessions[session_id]

        file_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        session["uploaded_files"][file.filename] = str(file_path)

        if message:
            results = await orchestrator.chat(
                message=message,
                files={file.filename: str(file_path)},
                conversation_context=session["context"],
                session_id=session_id,
            )

            if results["success"] and results.get("agent_results"):
                for agent_name, agent_result in results["agent_results"].items():
                    session["context"][f"{agent_name.lower()}_data"] = agent_result[
                        "data"
                    ]

            session["history"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "message": message,
                    "file": file.filename,
                    "results": results,
                }
            )

            return {
                "success": True,
                "session_id": session_id,
                "file_uploaded": file.filename,
                "response": results,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "success": True,
                "session_id": session_id,
                "file_uploaded": file.filename,
                "message": "File uploaded successfully. Send a message to analyze it.",
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session information"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "session": sessions[session_id]}


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    if "uploaded_files" in session:
        for filename, filepath in session["uploaded_files"].items():
            try:
                Path(filepath).unlink()
            except:
                pass

    del sessions[session_id]
    return {"success": True, "message": f"Session {session_id} deleted"}


@app.get("/history")
async def get_history():
    """Get execution history"""
    return {"history": orchestrator.get_execution_history()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)



@app.post("/edit-csv")
async def edit_csv_file(request: EditCsvRequest):
    """Edit an existing CSV file in a session"""
    try:
        # Validate session exists
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions[request.session_id]
        
        # Check if uploaded_files exists in session
        if "uploaded_files" not in session:
            raise HTTPException(status_code=400, detail="No files uploaded in this session")
        
        # Find the file
        if request.filename not in session["uploaded_files"]:
            raise HTTPException(status_code=404, detail=f"File '{request.filename}' not found in session")
        
        original_file_path = Path(session["uploaded_files"][request.filename])
        
        # Verify file exists on disk
        if not original_file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Verify it's a CSV file
        if not original_file_path.suffix.lower() == ".csv":
            raise HTTPException(status_code=400, detail="File must be a CSV file")
        
        # Prepare edit message for orchestrator
        edit_message = f"Edit the CSV file according to these instructions: {request.edit_instructions}"
        
        # If saving as new file, create a new file path
        if request.save_as_new:
            file_id = str(uuid.uuid4())
            edited_file_path = UPLOAD_DIR / f"{file_id}_edited_{request.filename}"
        else:
            # Create backup of original file
            backup_path = original_file_path.with_suffix('.csv.backup')
            shutil.copy2(original_file_path, backup_path)
            edited_file_path = original_file_path
        
        # Use orchestrator to perform the edit
                # Use orchestrator to perform the edit
        results = await orchestrator.edit_csv(
            file_path=str(original_file_path),
            edit_instructions=request.edit_instructions,
            output_path=str(edited_file_path),
            conversation_context=session["context"],
            session_id=request.session_id,
        )
        
        # Check if edit was successful
        if not results["success"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Edit failed: {results.get('error', 'Unknown error')}"
            )
        
        # If the orchestrator created/modified the file, update session
        # Note: This assumes the orchestrator/agent handles file writing
        # You may need to adjust this based on how your agents work
        
        # Update session context with edit results
        if results.get("agent_results"):
            for agent_name, agent_result in results["agent_results"].items():
                session["context"][f"{agent_name.lower()}_data"] = agent_result["data"]
        
        # Update file path in session if saving as new
        if request.save_as_new:
            session["uploaded_files"][f"edited_{request.filename}"] = str(edited_file_path)
        
        # Add to history
        session["history"].append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": "edit_csv",
                "filename": request.filename,
                "edit_instructions": request.edit_instructions,
                "results": results,
            }
        )
        
        return {
            "success": True,
            "session_id": request.session_id,
            "filename": request.filename,
            "edited_filename": f"edited_{request.filename}" if request.save_as_new else request.filename,
            "file_path": str(edited_file_path),
            "response": results,
            "timestamp": datetime.now().isoformat(),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

