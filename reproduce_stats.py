from typing import List, Dict, Any
import logging
from app.services.pandas_analytics_service import PandasAnalyticsService
from app.models.csv_document import CSVDocumentDetail
from datetime import datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Mock Data simulating the CSV contents
mock_bank_data = [
    {"Date": "2025-01-01", "Description": "Deposit", "Amount": "1000", "Net Amount": "1000.00"},
    {"Date": "2025-01-15", "Description": "Withdrawal", "Amount": "-500", "Net Amount": "500.00"},
    {"Date": "2025-01-30", "Description": "Deposit", "Amount": "2000", "Net Amount": "2100.00"},
] # Sum Net Amount = 3600

# 2. Mock Forecast Data (Monthly Forecast for Collections)
mock_monthly_collections = [
    {"Month": "Jan 2025", "Total Collections": "20000", "Collection Rate %": "75.5%"},
    {"Month": "Feb 2025", "Total Collections": "25000", "Collection Rate %": "78.0%"},
    {"Month": "Mar 2025", "Total Collections": "22000", "Collection Rate %": "76.2%"},
]

# 3. Mock Expense Data (Monthly Summary for Expenses)
mock_expense_data = [
    {"Month": "Jan 2025", "Total Expenses": "18000", "Estimated Revenue": "20000"},
    {"Month": "Feb 2025", "Total Expenses": "20000", "Estimated Revenue": "25000"},
    {"Month": "Mar 2025", "Total Expenses": "19000", "Estimated Revenue": "22000"},
]

# 4. Mock AR Data (Invoices)
mock_ar_data = [
    {
        "Invoice Number": "INV001", "Customer Name": "Customer A", 
        "Status": "Outstanding", "Days Past Due": "30", "Balance Due": "1000.00", "Due Date": "2025-01-01"
    },
    {
        "Invoice Number": "INV002", "Customer Name": "Customer B", 
        "Status": "Paid", "Days Past Due": "10", "Balance Due": "0.00", "Due Date": "2025-01-15"
    },
    {
        "Invoice Number": "INV003", "Customer Name": "Customer C", 
        "Status": "Partial Payment", "Days Past Due": "5", "Balance Due": "500.00", "Due Date": "2025-01-20"
    },
    {
        "Invoice Number": "INV004", "Customer Name": "Customer D", 
        "Status": "Outstanding", "Days Past Due": "0", "Balance Due": "2000.00", "Due Date": "2025-02-01"
    },
]

# 5. Mock Cash Flow Analysis (Net Cash Flow for 30 Day Forecast & Chart 1)
mock_cash_flow_analysis = [
    {"Month": "Dec 2024", "Net Cash Flow": "5000"},
    {"Month": "Jan 2025", "Net Cash Flow": "5350.50"}, 
    {"Month": "Feb 2025", "Net Cash Flow": "6000"},
]

def create_mock_doc(filename: str, data: List[Dict[str, Any]]) -> CSVDocumentDetail:
    return CSVDocumentDetail(
        id=1,
        filename=filename,
        preview=[],
        full_data=data,
        row_count=len(data),
        column_count=len(data[0]) if data else 0,
        is_described=False,
        upload_date=datetime.now()
    )

def test_pandas_analytics():
    print("Setting up mock documents...")
    documents = [
        create_mock_doc("Electricity Provider Bank Statements(Summary by Type).csv", mock_bank_data),
        create_mock_doc("Electricity Provider Customer Payments Forecast(Cash Flow Analysis).csv", mock_cash_flow_analysis),
        create_mock_doc("Electricity Provider Customer Payments Forecast(Monthly Forecast).csv", mock_monthly_collections),
        create_mock_doc("Electricity Provider Expense Forecast(Monthly Summary).csv", mock_expense_data),
        create_mock_doc("Electricity_Provider_AR  Records-02142026 2(Electricity AR Records).csv", mock_ar_data),
    ]
    
    print("\n--- Test 1: Calculate Stats ---")
    stats = PandasAnalyticsService.calculate_stats(documents)
    print(f"Current Cash Position: {stats['current']} (Expected: 3600.0)")
    print(f"30 Day Forecast: {stats['forecast30Day']} (Expected: 5350.5)")
    print(f"At Risk Invoices: {stats['atRiskInvoices']} (Expected: 1500.0)")
    
    assert abs(stats['current'] - 3600.0) < 0.01
    assert abs(stats['forecast30Day'] - 5350.5) < 0.01
    assert abs(stats['atRiskInvoices'] - 1500.0) < 0.01
    
    print("\n--- Test 2: Cash Forecast Data (Chart) ---")
    forecast_data = PandasAnalyticsService.get_cash_forecast_data(documents)
    labels = forecast_data.get("labels")
    datasets = forecast_data.get("datasets")
    print(f"Labels: {labels}")
    print(f"Datasets: {len(datasets)}")
    if datasets:
        print(f"Dataset 1 (Actual): {datasets[0]['data']}")
        print(f"Dataset 2 (Forecast): {datasets[1]['data']}")
        
    # Expected: 8 labels (Jan 1 to Feb 19)
    # Dataset 1: 4 values + 4 None
    # Dataset 2: 3 None + 1 overlap + 4 values
    assert len(labels) == 8
    assert len(datasets) == 2
    assert len(datasets[0]['data']) == 8
    
    print("\n--- Test 3: Cash Flow Data (Inflows vs Outflows) ---")
    flow_data = PandasAnalyticsService.get_cash_flow_data(documents)
    datasets = flow_data.get("datasets")
    inflows = next((d for d in datasets if d['label'] == 'Inflows'), None)
    outflows = next((d for d in datasets if d['label'] == 'Outflows'), None)
    
    # Jan 2025: In=20000, Out=18000
    print(f"Jan Inflows: {inflows['data'][0]} (Expected: 20000)")
    print(f"Jan Outflows: {outflows['data'][0]} (Expected: 18000)")
    
    assert inflows['data'][0] == 20000.0
    assert outflows['data'][0] == 18000.0
    
    print("\n--- Test 4: Scenario Analysis ---")
    scenario_data = PandasAnalyticsService.get_scenario_analysis(documents)
    datasets = scenario_data.get("datasets")
    opt = next((d for d in datasets if d['label'] == 'Optimistic'), None)
    exp = next((d for d in datasets if d['label'] == 'Expected'), None)
    pess = next((d for d in datasets if d['label'] == 'Pessimistic'), None)
    
    # Base: 3600
    # Jan Expected: 5600
    print(f"Jan Expected: {exp['data'][0]} (Expected: 5600)")
    assert abs(exp['data'][0] - 5600.0) < 0.01

    print("\n--- Test 5: Invoices Extraction & Stats ---")
    invoices = PandasAnalyticsService.get_invoices_data(documents)
    print(f"Extracted {len(invoices)} invoices")
    if invoices:
        print(f"Sample: {invoices[0]}")
    
    assert len(invoices) == 4
    
    # Test Stats
    # Mock data has 4 invoices.
    # Statuses: 'Outstanding' (active), 'Paid' (inactive), 'Partial' (active), 'Overdue' (inactive for calculation?)
    # Wait, 'Overdue' is NOT in notebook's definition of active invoices [Outstanding, Partial Payment].
    # Our mock data in reproduce_stats.py:
    # {"Invoice Number": "INV001", "Status": "Outstanding", "Balance Due": "1000", "Days Past Due": "45"},
    # {"Invoice Number": "INV002", "Status": "Paid", "Balance Due": "0", "Days Past Due": "0"},
    # {"Invoice Number": "INV003", "Status": "Partial Payment", "Balance Due": "500", "Days Past Due": "10"},
    # {"Invoice Number": "INV004", "Status": "Overdue", "Balance Due": "2000", "Days Past Due": "95"}
    
    # Active = INV001 (1000) + INV003 (500) = 1500
    # At Risk = INV001 (Days > 0) + INV003 (Days > 0) = 1500
    # Note: INV004 is 'Outstanding', so it is INCLUDED in Active/Receivables.
    
    # Collection Rate should be picked up from the global mock_monthly_collections
    
    inv_stats = PandasAnalyticsService.get_invoices_stats(documents)
    print(f"Invoice Stats: {inv_stats}")
    
    assert inv_stats["totalReceivables"] == 3500.0
    assert inv_stats["activeInvoiceCount"] == 3
    assert inv_stats["collectionRate"] == 75.5
    
    print("\n--- Test 6: Cash Shortfalls (Pessimistic Scenario) ---")
    # To test shortfalls, we need a negative running balance under Pessimistic assumptions.
    # Pessimistic: Collections * 0.85, Expenses * 1.10
    
    # Let's create a scenario where:
    # Current: 3600
    # Jan Collections: 10000 -> Pessimistic: 8500
    # Jan Expenses: 12000 -> Pessimistic: 13200
    # Jan Net Pessimistic: 8500 - 13200 = -4700
    # Running: 3600 - 4700 = -1100 -> Shortfall!
    
    mock_collections = [{"Month": "Jan 2025", "Total Collections": "10000"}]
    mock_expenses = [{"Month": "Jan 2025", "Total Expenses": "12000"}]
    
    docs_shortfall = [
        d for d in documents 
        if "MonthlyForecast" not in d.filename and "MonthlySummary" not in d.filename
    ]
    docs_shortfall.append(create_mock_doc("CustomerPaymentsForecast(MonthlyForecast).csv", mock_collections))
    docs_shortfall.append(create_mock_doc("ExpenseForecast(MonthlySummary).csv", mock_expenses))
    
    shortfall_result = PandasAnalyticsService.get_cash_shortfalls(docs_shortfall)
    print(f"Has Shortfalls: {shortfall_result['hasShortfalls']}")
    print(f"Total Shortfall: {shortfall_result['totalShortfall']}")
    print(f"Periods: {len(shortfall_result['periods'])}")
    
    if shortfall_result['hasShortfalls']:
        print(f"First Shortfall Amount: {shortfall_result['periods'][0]['shortfall']}")
    
    assert shortfall_result['hasShortfalls'] == True
    assert shortfall_result['totalShortfall'] > 1000
    assert len(shortfall_result['periods']) >= 1

    print("\n✅ Verification Successful!")

if __name__ == "__main__":
    test_pandas_analytics()
