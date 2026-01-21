from typing import Any, Dict, List
from app.agents.base import Agent
from app.agents.specialized import Sensor, Analyzer, Responder, Learner
import time

class Orchestrator(Agent):
    def __init__(self):
        super().__init__(name="Orchestrator", role="Workflow Management")
        self.sensor = Sensor()
        self.analyzer = Analyzer()
        self.responder = Responder()
        self.learner = Learner()

    def process(self, prompt: str) -> Dict[str, Any]:
        """
        Main workflow execution:
        1. Orchestrator receives prompt.
        2. Calls Sensor to get data.
        3. Calls Analyzer to analyze data.
        4. Calls Responder to format report.
        5. Returns structured log of all steps.
        """
        
        start_time = time.time()
        logs = []
        
        # Step 1: Orchestrator Plan
        logs.append({
            "agent": self.name,
            "time": time.strftime("%I:%M:%S %p"),
            "message": f"Received request: '{prompt}'. Initiating workflow.",
            "status": "processing",
            "details": ["Planning workflow steps", "Assigning tasks to agents"]
        })
        
        # Step 2: Sensor
        sensor_result = self.sensor.process({})
        logs.append({
            "agent": self.sensor.name,
            "time": time.strftime("%I:%M:%S %p"),
            "message": sensor_result["message"],
            "status": sensor_result["status"],
            "metrics": sensor_result.get("metrics"),
            "details": ["Fetched latest payment history", "Retrieved bank transactions"]
        })
        
        if sensor_result["status"] == "error":
            return {"logs": logs, "final_report": "Error in data collection."}

        # Step 3: Analyzer
        analyzer_result = self.analyzer.process(sensor_result)
        logs.append({
            "agent": self.analyzer.name,
            "time": time.strftime("%I:%M:%S %p"),
            "message": analyzer_result["message"],
            "status": analyzer_result["status"],
            "metrics": analyzer_result.get("metrics"),
            "details": ["Analyzed cash flow trends", "Generated forecast"]
        })
        
        # Step 4: Responder
        responder_result = self.responder.process(analyzer_result)
        logs.append({
            "agent": self.responder.name,
            "time": time.strftime("%I:%M:%S %p"),
            "message": responder_result["message"],
            "status": responder_result["status"],
            "metrics": responder_result.get("metrics"),
            "details": ["Formatted final report", "Prepared visualization data"]
        })
        
        total_time = f"{time.time() - start_time:.2f}s"
        
        return {
            "logs": logs,
            "final_report": responder_result.get("report", ""),
            "workflow_metrics": [
                {"label": "Total Time", "value": total_time, "icon": "Clock"},
                {"label": "Agents Active", "value": "4", "icon": "Users"}
            ]
        }
