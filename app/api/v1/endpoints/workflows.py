from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.orchestrator import Orchestrator

router = APIRouter()

class WorkflowRequest(BaseModel):
    prompt: str

class WorkflowResponse(BaseModel):
    logs: list
    final_report: str
    workflow_metrics: list

@router.post("/run", response_model=WorkflowResponse)
async def run_workflow(request: WorkflowRequest):
    try:
        orchestrator = Orchestrator()
        result = orchestrator.process(request.prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
