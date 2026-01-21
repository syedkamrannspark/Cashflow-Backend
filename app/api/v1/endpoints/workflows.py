from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.agents.orchestrator import Orchestrator
import json

router = APIRouter()

class WorkflowRequest(BaseModel):
    prompt: str

@router.post("/run")
async def run_workflow(request: WorkflowRequest):
    async def event_generator():
        orchestrator = Orchestrator()
        try:
            for event in orchestrator.process_stream(request.prompt):
                # SSE format: "data: <json>\n\n"
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
