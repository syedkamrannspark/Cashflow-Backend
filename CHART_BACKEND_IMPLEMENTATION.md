# Backend Implementation Guide for Chart Support

This guide helps you implement chart support in your backend `/dashboard/query` endpoint.

## Backend Changes Required

### 1. Update Your Query Handler

Your current backend endpoint should be modified to detect visualization requests and return appropriate chart data.

#### Python/FastAPI Example

```python
from fastapi import APIRouter
from typing import Optional, List, Dict, Any

router = APIRouter()

@router.post("/dashboard/query")
async def handle_query(query_data: dict):
    query = query_data.get("query", "").lower()
    
    # Detect if user is asking for visualization
    chart_keywords = ["chart", "graph", "plot", "visualize", "show", "bar", "line", "pie", "area"]
    is_visualization_request = any(keyword in query for keyword in chart_keywords)
    
    if is_visualization_request:
        return handle_visualization_request(query)
    else:
        return handle_text_request(query)


def handle_visualization_request(query: str) -> Dict[str, Any]:
    """
    Handles requests for data visualizations.
    Analyzes the query and returns appropriate chart data.
    """
    
    # Example: Sales by month
    if "sales" in query and "month" in query:
        return {
            "response": "Here's your monthly sales breakdown:",
            "chartData": {
                "type": "bar",
                "data": [
                    {"month": "January", "sales": 45000, "expenses": 28000},
                    {"month": "February", "sales": 52000, "expenses": 31000},
                    {"month": "March", "sales": 61000, "expenses": 35000},
                    {"month": "April", "sales": 58000, "expenses": 33000},
                ],
                "xKey": "month",
                "yKey": ["sales", "expenses"],
                "title": "Monthly Sales vs Expenses",
                "colors": ["#10b981", "#ef4444"]
            }
        }
    
    # Example: Revenue trend
    if "revenue" in query and ("trend" in query or "over time" in query):
        return {
            "response": "Your revenue shows a steady growth trend:",
            "chartData": {
                "type": "line",
                "data": [
                    {"week": "Week 1", "revenue": 42000, "forecast": 40000},
                    {"week": "Week 2", "revenue": 48000, "forecast": 45000},
                    {"week": "Week 3", "revenue": 55000, "forecast": 52000},
                    {"week": "Week 4", "revenue": 62000, "forecast": 60000},
                ],
                "xKey": "week",
                "yKey": ["revenue", "forecast"],
                "title": "Weekly Revenue Trend with Forecast",
                "colors": ["#3b82f6", "#f59e0b"]
            }
        }
    
    # Example: Expense distribution
    if "expense" in query and ("distribution" in query or "breakdown" in query or "pie" in query):
        return {
            "response": "Here's how your expenses are distributed:",
            "chartData": {
                "type": "pie",
                "data": [
                    {"name": "Salaries", "value": 150000},
                    {"name": "Operations", "value": 75000},
                    {"name": "Marketing", "value": 45000},
                    {"name": "Technology", "value": 30000},
                    {"name": "Other", "value": 20000},
                ],
                "yKey": "value",
                "title": "Expense Distribution",
                "colors": ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"]
            }
        }
    
    # Default visualization response
    return {
        "response": "I can create different visualizations for you. Try asking for 'sales chart', 'revenue trend', or 'expense breakdown'.",
        "chartData": None
    }


def handle_text_request(query: str) -> Dict[str, Any]:
    """
    Handles text-only requests without visualizations.
    """
    # Your existing text response logic here
    return {
        "response": "Processing your query... (implement your text response logic)"
    }
```

### 2. Query Analysis Function

```python
def analyze_query_for_visualization(query: str) -> Optional[Dict[str, str]]:
    """
    Analyzes user query to determine:
    - Chart type requested
    - Data to visualize
    - Time period
    """
    query_lower = query.lower()
    
    # Detect chart type
    chart_type = None
    if any(word in query_lower for word in ["bar", "column"]):
        chart_type = "bar"
    elif "line" in query_lower:
        chart_type = "line"
    elif "pie" in query_lower or "distribution" in query_lower:
        chart_type = "pie"
    elif "area" in query_lower or "cumulative" in query_lower:
        chart_type = "area"
    
    # Detect data type
    data_type = None
    if "sales" in query_lower:
        data_type = "sales"
    elif "revenue" in query_lower:
        data_type = "revenue"
    elif "expense" in query_lower or "cost" in query_lower:
        data_type = "expense"
    elif "profit" in query_lower:
        data_type = "profit"
    
    # Detect time period
    time_period = "month"  # default
    if "week" in query_lower:
        time_period = "week"
    elif "quarter" in query_lower:
        time_period = "quarter"
    elif "year" in query_lower:
        time_period = "year"
    elif "day" in query_lower:
        time_period = "day"
    
    return {
        "chart_type": chart_type,
        "data_type": data_type,
        "time_period": time_period
    }
```

### 3. Data Fetching Function

```python
def fetch_chart_data(data_type: str, time_period: str) -> List[Dict[str, Any]]:
    """
    Fetches data from your database based on requested type and period.
    """
    # Example: Query your database
    if data_type == "sales" and time_period == "month":
        # SELECT * FROM sales GROUP BY month ORDER BY date
        return [
            {"month": "Jan", "sales": 45000},
            {"month": "Feb", "sales": 52000},
            {"month": "Mar", "sales": 61000},
        ]
    
    # Add more conditions based on data_type and time_period
    return []
```

### 4. Complete Integration Example

```python
from datetime import datetime, timedelta

@router.post("/dashboard/query")
async def handle_query(query_data: dict):
    query = query_data.get("query", "").lower()
    
    # Analyze query
    analysis = analyze_query_for_visualization(query)
    
    # Check if visualization is requested
    is_chart_request = (
        analysis.get("chart_type") or 
        any(keyword in query for keyword in ["chart", "graph", "visualize", "show me"])
    )
    
    if is_chart_request:
        # Fetch data from database
        data = fetch_chart_data(
            analysis.get("data_type", "sales"),
            analysis.get("time_period", "month")
        )
        
        # Build chart response
        chart_type = analysis.get("chart_type", "bar")
        
        return {
            "response": f"Here's your {analysis.get('data_type', 'data')} visualization:",
            "chartData": {
                "type": chart_type,
                "data": data,
                "xKey": analysis.get("time_period", "month"),
                "yKey": analysis.get("data_type", "value"),
                "title": f"{analysis.get('data_type', 'Data')} by {analysis.get('time_period', 'Month')}"
            }
        }
    else:
        # Handle as text-only query
        # Your existing logic here
        return {
            "response": "Your text response here"
        }
```

## Database Query Examples

### Example 1: Monthly Sales Data

```sql
SELECT 
    DATE_TRUNC('month', created_at) as month,
    SUM(amount) as sales,
    COUNT(*) as transactions
FROM sales
WHERE created_at >= NOW() - INTERVAL '12 months'
GROUP BY DATE_TRUNC('month', created_at)
ORDER BY month;
```

### Example 2: Expense Breakdown

```sql
SELECT 
    category,
    SUM(amount) as value
FROM expenses
WHERE created_at >= NOW() - INTERVAL '1 year'
GROUP BY category
ORDER BY value DESC;
```

### Example 3: Revenue Forecast

```sql
SELECT 
    week,
    actual_revenue,
    forecast_revenue
FROM revenue_data
WHERE year = 2024
ORDER BY week;
```

## Response Format Validation

```python
def validate_chart_data(chart_data: dict) -> bool:
    """
    Validates that chart data has required fields.
    """
    required_fields = ["type", "data"]
    optional_fields = ["xKey", "yKey", "title", "colors"]
    
    # Check required fields
    for field in required_fields:
        if field not in chart_data:
            return False
    
    # Validate chart type
    valid_types = ["line", "bar", "pie", "area"]
    if chart_data.get("type") not in valid_types:
        return False
    
    # Check data is not empty
    if not chart_data.get("data") or len(chart_data["data"]) == 0:
        return False
    
    return True
```

## Error Handling

```python
@router.post("/dashboard/query")
async def handle_query(query_data: dict):
    try:
        query = query_data.get("query", "").lower()
        
        if not query:
            return {
                "response": "Please provide a query.",
                "error": "empty_query"
            }
        
        # ... rest of logic ...
        
    except Exception as e:
        return {
            "response": "An error occurred processing your query. Please try again.",
            "error": str(e)
        }
```

## Testing Your Implementation

### Test Case 1: Bar Chart Request
```bash
curl -X POST http://localhost:8000/dashboard/query \
  -H "Content-Type: application/json" \
  -d '{"query": "show me sales by month"}'
```

Expected response:
```json
{
  "response": "Here's your monthly sales...",
  "chartData": {
    "type": "bar",
    "data": [...],
    "xKey": "month",
    "yKey": "sales",
    "title": "Monthly Sales"
  }
}
```

### Test Case 2: Line Chart Request
```bash
curl -X POST http://localhost:8000/dashboard/query \
  -H "Content-Type: application/json" \
  -d '{"query": "visualize revenue trend"}'
```

### Test Case 3: Pie Chart Request
```bash
curl -X POST http://localhost:8000/dashboard/query \
  -H "Content-Type: application/json" \
  -d '{"query": "breakdown expenses by category"}'
```

## Performance Considerations

1. **Cache frequently requested charts** for faster response
2. **Limit data points** to reasonable amounts (100-500 per chart)
3. **Pre-aggregate data** in your database
4. **Use indexes** on commonly filtered columns

## Security Best Practices

1. Validate all user inputs
2. Use parameterized queries to prevent SQL injection
3. Implement proper authentication/authorization
4. Rate limit chart requests if needed
5. Log all visualization requests for audit trails
