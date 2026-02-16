
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models.csv_document import CSVDocument
from app.models.csv_metadata import CSVMetadata

# Mock dependencies before importing dashboard
with patch('app.repositories.csv_repository.CSVRepository') as MockCSVRepo, \
     patch('app.repositories.csv_metadata_repository.CSVMetadataRepository') as MockMetaRepo, \
     patch('app.services.llm_service.get_stats_from_openrouter') as MockGetStats, \
     patch('app.agents.nl2sql_agent.nl2sql_agent') as MockNL2SQLAgent:

    # Setup mocks
    mock_doc = MagicMock(spec=CSVDocument)
    mock_doc.id = 1
    mock_doc.filename = "test.xlsx"
    mock_doc.row_count = 1000
    mock_doc.column_count = 5
    mock_doc.upload_date = "2023-01-01"
    # Create fake full_data with 100 rows
    mock_doc.full_data = [{"Amount": i, "Date": "2023-01-01", "Status": "Paid"} for i in range(100)]
    
    mock_meta = MagicMock(spec=CSVMetadata)
    mock_meta.column_name = "Amount"
    mock_meta.is_target = True
    
    MockCSVRepo.list_documents_with_full_data = AsyncMock(return_value=[mock_doc])
    MockMetaRepo.list_metadata_by_document_ids = AsyncMock(return_value={1: [mock_meta]})
    
    # Mock NL2SQL response
    MockNL2SQLAgent.process_natural_query = AsyncMock(return_value={
        "success": True,
        "data_full": [{"status": "Paid", "count": 100, "sum": 5000}]
    })
    
    # Mock LLM service
    MockGetStats.return_value = {
        "current": 5000,
        "forecast30Day": 0,
        "atRiskInvoices": 0,
        "cashRunway": 0,
        "currentChangePercent": 0,
        "forecastChangePercent": 0,
        "overdueInvoicesCount": 0
    }

    # Import dashboard endpoint
    from app.api.v1.endpoints.dashboard import get_dashboard_stats, get_cash_forecast, get_cash_flow, get_data_visualization

    async def run_verification():
        print("Verifying /stats integration...")
        # Call the endpoint
        result = await get_dashboard_stats(db=MagicMock())
        
        # Verify NL2SQL was called
        MockNL2SQLAgent.process_natural_query.assert_called()
        print("✅ NL2SQL agent called for /stats")
        
        # Verify full_data was cleared in the object passed to get_stats_from_openrouter
        # We need to check the call args of MockGetStats
        call_args = MockGetStats.call_args
        dataset_arg = call_args[0][0]
        
        # Check if full_data is empty in the dataset passed to LLM
        full_data_len = len(dataset_arg["documents"][0]["full_data"])
        if full_data_len == 0:
            print(f"✅ full_data cleared! Length: {full_data_len}")
        else:
            print(f"❌ full_data NOT cleared! Length: {full_data_len}")

        print("\nVerifying /forecast integration...")
        MockNL2SQLAgent.process_natural_query.reset_mock()
        await get_cash_forecast(db=MagicMock())
        if MockNL2SQLAgent.process_natural_query.called:
             print("✅ NL2SQL agent called for /forecast")
        else:
             print("❌ NL2SQL agent NOT called for /forecast")

        print("\nVerifying /flow integration...")
        MockNL2SQLAgent.process_natural_query.reset_mock()
        await get_cash_flow(db=MagicMock())
        if MockNL2SQLAgent.process_natural_query.called:
             print("✅ NL2SQL agent called for /flow")
        else:
             print("❌ NL2SQL agent NOT called for /flow")

        print("\nVerifying /data-visualization integration...")
        # For viz, we don't call NL2SQL, we just limit rows.
        # But we can verify row count in dataset if we mock get_data_visualization_from_openrouter too.
        # Let's just check if it runs without error for now.
        await get_data_visualization(db=MagicMock())
        print("✅ /data-visualization ran successfully")

    # Run the async test
    asyncio.run(run_verification())
