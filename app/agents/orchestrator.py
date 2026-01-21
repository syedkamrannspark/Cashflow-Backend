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

    def process_stream(self, prompt: str):
        """
        Stream workflow execution steps:
        Yields logs as they happen.
        """
        start_time = time.time()
        
        # Step 1: Orchestrator Plan
        yield {
            "type": "log",
            "data": {
                "agent": self.name,
                "time": time.strftime("%I:%M:%S %p"),
                "message": f"Received request: '{prompt}'. Initiating workflow.",
                "status": "processing",
                "details": ["Planning workflow steps", "Assigning tasks to agents"]
            }
        }
        
        # Step 2: Sensor
        sensor_result = self.sensor.process({"prompt": prompt})
        yield {
            "type": "log",
            "data": {
                "agent": self.sensor.name,
                "time": time.strftime("%I:%M:%S %p"),
                "message": sensor_result.get("message", "Data collected"),
                "status": sensor_result.get("status", "success"),
                "metrics": sensor_result.get("metrics"),
                "details": ["Fetched latest payment history", "Retrieved bank transactions"]
            }
        }
        
        if sensor_result.get("status") == "error":
            yield {"type": "error", "message": "Error in data collection"}
            return

        # Step 3: Analyzer
        analyzer_result = self.analyzer.process({**sensor_result, "prompt": prompt})
        yield {
            "type": "log",
            "data": {
                "agent": self.analyzer.name,
                "time": time.strftime("%I:%M:%S %p"),
                "message": analyzer_result.get("message", "Analysis complete"),
                "status": analyzer_result.get("status", "success"),
                "metrics": analyzer_result.get("metrics"),
                "details": ["Analyzed cash flow trends", "Generated forecast"]
            }
        }
        
        # Step 4: Responder
        responder_result = self.responder.process(analyzer_result)
        yield {
            "type": "log",
            "data": {
                "agent": self.responder.name,
                "time": time.strftime("%I:%M:%S %p"),
                "message": responder_result.get("message", "Report ready"),
                "status": responder_result.get("status", "success"),
                "metrics": responder_result.get("metrics"),
                "details": ["Formatted final report", "Prepared visualization data"]
            }
        }
        
        total_time = f"{time.time() - start_time:.2f}s"
        
        # Final Event
        yield {
            "type": "result",
            "final_report": responder_result.get("report", ""),
            "workflow_metrics": [
                {"label": "Total Time", "value": total_time, "icon": "Clock"},
                {"label": "Agents Active", "value": "4", "icon": "Users"}
            ]
        }
