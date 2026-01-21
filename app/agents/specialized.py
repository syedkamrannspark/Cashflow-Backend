from typing import Any, Dict, List
from app.agents.base import Agent
from app.core.database import SessionLocal
from app.models import PaymentHistory, BankTransaction, AppInvoice, ForecastMetric
from sqlalchemy import text
from datetime import datetime
import textwrap

class Sensor(Agent):
    def __init__(self):
        super().__init__(name="Sensor", role="Data Collection")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # input_data contains the user prompt and other context
        prompt = input_data.get("prompt", "")
        # For simplicity, we fetch recent data from PaymentHistory and BankTransaction
        # In a more advanced version, we could use the prompt to filter what data we fetch.
        
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

            # Fetch recent invoices
            invoices = db.query(AppInvoice).limit(20).all()
            invoice_summary = [
                {
                    "invoice_number": i.invoice_number,
                    "customer": i.customer_name,
                    "amount": i.total_amount,
                    "due_date": str(i.due_date),
                    "status": i.status
                }
                for i in invoices
            ]

            # Fetch forecast metrics
            metrics_data = db.query(ForecastMetric).limit(20).all()
            metrics_summary = [
                {
                    "category": m.category,
                    "metric": m.metric_name,
                    "value": m.value_raw,
                    "period": m.period
                }
                for m in metrics_data
            ]
            
            return {
                "status": "success",
                "message": "Data collection completed successfully.",
                "data": {
                    "payments": payment_summary,
                    "transactions": transaction_summary,
                    "invoices": invoice_summary,
                    "metrics": metrics_summary
                },
                "metrics": [
                    {"label": "Records Fetched", "value": str(len(payments) + len(transactions) + len(invoices) + len(metrics_data))},
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
        # input_data should contain the data from Sensor and the user prompt
        sensor_data = input_data.get("data", {})
        user_prompt = input_data.get("prompt", "Analyze the financial data.")
        
        prompt = f"""
        You are a generic Financial Analyst Agent.
        Your goal is to answer the User's Request strictly based on the provided Financial Data.
        
        User Request: "{user_prompt}"
        
        --- AVAILABLE FINANCIAL DATA ---
        
        Recent Payments (Last 20):
        {sensor_data.get('payments', [])}
        
        Recent Bank Transactions (Last 20):
        {sensor_data.get('transactions', [])}

        Open Invoices (Last 20):
        {sensor_data.get('invoices', [])}

        Forecast Metrics (Last 20):
        {sensor_data.get('metrics', [])}
        
        --- INSTRUCTIONS ---
        1. Analyze the provided data to answer the User Request.
        2. If the data suggests an answer, provide it clearly with evidence.
        3. If the data is insufficient to answer the request, state what is missing.
        4. Do NOT hallucinate data. Only use what is provided above.
        5. Format your response in clean Markdown (no JSON).
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
