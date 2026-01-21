from typing import Any, Dict, List, Optional
from app.core.llm_client import LLMClient

class Agent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.llm = LLMClient()
    
    def process(self, input_data: Any) -> Dict[str, Any]:
        """
        Process the input and return a result dictionary.
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement process method")
