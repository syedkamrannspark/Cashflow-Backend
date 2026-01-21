from typing import Any, Dict, List
from app.agents.base import Agent
from app.core.database import SessionLocal
from app.models import PaymentHistory, BankTransaction
from sqlalchemy import text
from datetime import datetime
import textwrap

class Sensor(Agent):
    def __init__(self):
        super().__init__(name="Sensor", role="Data Collection")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # input_data is likely the user prompt or parsed requirements
        # For simplicity, we fetch recent data from PaymentHistory and BankTransaction
        
        db = SessionLocal()
        try:
            # Fetch summary of recent payments
            payments = db.query(PaymentHistory).limit(20).all()
            payment_summary = [
                {
                    "customer": p.customer_name,
                    "amount": p.invoice_amount,
                    "payment_date": str(p.payment_date),
                    "status": p.payment_status
                }
                for p in payments
            ]
            
            # Fetch recent bank transactions
            transactions = db.query(BankTransaction).limit(20).all()
            transaction_summary = [
                {
                    "date": str(t.date),
                    "desc": t.description,
                    "balance": t.balance
                }
                for t in transactions
            ]
            
            return {
                "status": "success",
                "message": "Data collection completed successfully.",
                "data": {
                    "payments": payment_summary,
                    "transactions": transaction_summary
                },
                "metrics": [
                    {"label": "Records Fetched", "value": str(len(payments) + len(transactions))},
                    {"label": "Sources", "value": "Database"}
                ]
            }
        except Exception as e:
            return {"status": "error", "message": f"Data collection failed: {str(e)}"}
        finally:
            db.close()

class Analyzer(Agent):
    def __init__(self):
        super().__init__(name="Analyzer", role="Data Analysis")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # input_data should contain the data from Sensor
        sensor_data = input_data.get("data", {})
        
        prompt = f"""
        Analyze the following financial data and provide a cash flow forecast summary or insights.
        
        Payments: {sensor_data.get('payments', [])[:5]} ... (truncated)
        Transactions: {sensor_data.get('transactions', [])[:5]} ... (truncated)
        
        Provide:
        1. Key trends
        2. Potential risks
        3. Simple forecast (next 30 days)
        
        Format the output as a clean, professional financial summary. Do NOT use JSON. Use Markdown headings and bullet points.
        """
        
        analysis_text = self.llm.generate(prompt, system_message="You are a simplified financial analyst helper.")
        
        # In a real app, we would parse JSON. For now, we wrap the text.
        return {
            "status": "success",
            "message": "Financial analysis completed.",
            "analysis": analysis_text,
            "metrics": [
                {"label": "Analysis Time", "value": "0.5s"}, # Mock
                {"label": "Data Points", "value": "Active"}
            ]
        }

class Responder(Agent):
    def __init__(self):
        super().__init__(name="Responder", role="Report Generator")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # input_data is the analysis result
        analysis = input_data.get("analysis", "")
        
        # Just formatting for the final report
        # Use LLM to ensure the final report is polished (optional, but good for "Responder" role)
        # But for now, we trust the Analyzer's markdown output and just wrap it.
        
        report = textwrap.dedent(f"""
            # Financial Report

            {analysis}

            *Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
        """)
        
        return {
            "status": "success",
            "message": "Report generated and delivered.",
            "report": report,
            "metrics": [
                {"label": "Report Length", "value": f"{len(report)} chars"}
            ]
        }

class Learner(Agent):
    def __init__(self):
        super().__init__(name="Learner", role="Continuous Learning")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # Stub implementation
        return {
            "status": "idle",
            "message": "Learning cycle deferred.",
            "metrics": []
        }
