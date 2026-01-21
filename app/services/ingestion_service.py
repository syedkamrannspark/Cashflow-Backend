import pandas as pd
import glob
import os
from sqlalchemy.orm import Session
from app.models.payment_history import PaymentHistory
from app.models.invoice import AppInvoice
from app.models.complex_models import BankTransaction, ForecastMetric
import numpy as np
import math

def ingest_data(db: Session, xlsx_dir: str):
    files = glob.glob(os.path.join(xlsx_dir, '*.xlsx'))
    
    for file_path in files:
        basename = os.path.basename(file_path)
        print(f"Processing {basename}...")
        
        try:
            # Determine file type
            if "Customer Payments History" in basename:
                ingest_payment_history(db, file_path)
            elif "AR  Records" in basename or "AR Records" in basename:
                ingest_ar_records(db, file_path)
            elif "Bank Statements" in basename:
                # Use dedicated function for Bank Statements
                ingest_bank_statement(db, file_path)
            elif "Forecast" in basename: 
                ingest_forecast_metrics(db, file_path)
            else:
                print(f"Skipping {basename} - No matching model.")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            db.rollback()


def ingest_payment_history(db: Session, file_path: str):
    # Read all sheets
    xls = pd.ExcelFile(file_path)
    target_sheet = 'Payment History'
    if target_sheet in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=target_sheet)
    else:
        df = pd.read_excel(file_path)
    
    count = 0
    # For PaymentHistory, we allow multiple entries per invoice (history)

    # For PaymentHistory, we allow multiple entries per invoice (history)
    # So we don't skip based on invoice_number alone.
    # Ideally check intersection of all fields, but for fresh ingestion, just insert.
    
    for _, row in df.iterrows():
        invoice_num = str(row['Invoice Number'])

        payment_date = row['Payment Date']
        if pd.isna(payment_date):
            payment_date = None
        
        payment_method = row['Payment Method']
        if pd.isna(payment_method):
            payment_method = None
            
        transaction_id = row['Transaction ID']
        if pd.isna(transaction_id):
            transaction_id = None

        # Safe date conversion
        billing_date = pd.to_datetime(row['Billing Date']) 
        due_date = pd.to_datetime(row['Due Date'])
        payment_date_obj = pd.to_datetime(payment_date) if payment_date else None

        db_item = PaymentHistory(
            account_number=str(row['Account Number']),
            customer_name=str(row['Customer Name']),
            account_type=str(row['Account Type']),
            invoice_number=invoice_num,
            billing_date=billing_date.date() if not pd.isna(billing_date) else None,
            due_date=due_date.date() if not pd.isna(due_date) else None,
            payment_date=payment_date_obj.date() if payment_date_obj else None,
            invoice_amount=float(row['Invoice Amount']),
            late_fee=float(row['Late Fee']),
            amount_paid=float(row['Amount Paid']),
            payment_method=str(payment_method) if payment_method else None,
            transaction_id=str(transaction_id) if transaction_id else None,
            days_late=int(row['Days Late']),
            payment_status=str(row['Payment Status']),
            on_time_payment=str(row['On-Time Payment'])
        )
        db.add(db_item)
        count += 1
        
        if count % 1000 == 0:
            db.commit()
    
    db.commit()
    print(f"Finished processing {os.path.basename(file_path)}")

def ingest_ar_records(db: Session, file_path: str):
    df = pd.read_excel(file_path)
    # Cache existing
    existing_ids = {r[0] for r in db.query(AppInvoice.invoice_number).all()}

    count = 0
    
    for _, row in df.iterrows():
        invoice_num = str(row['Invoice Number'])
        if invoice_num in existing_ids:
            continue
        existing_ids.add(invoice_num) # Update in-memory set

        due_date = pd.to_datetime(row['Due Date'])
        invoice_date = pd.to_datetime(row['Invoice Date'])
        
        db_item = AppInvoice(
            invoice_number=invoice_num,
            account_number=str(row['Account Number']) if not pd.isna(row['Account Number']) else None,
            customer_name=str(row['Customer Name']),
            due_date=due_date.date() if not pd.isna(due_date) else None,
            invoice_date=invoice_date.date() if not pd.isna(invoice_date) else None,
            total_amount=float(row['Total Invoice Amount']),
            amount_paid=float(row['Amount Paid']),
            balance_due=float(row['Balance Due']),
            status=str(row['Status']),
            days_past_due=int(row['Days Past Due']) if not pd.isna(row['Days Past Due']) else 0
        )
        db.add(db_item)
        count += 1
        
        # Periodic commit to avoid massive transaction
        if count % 1000 == 0:
             db.commit()
    
    db.commit()
    print(f"Finished processing {os.path.basename(file_path)}")

    print(f"Finished processing {os.path.basename(file_path)}")

def ingest_bank_statement(db: Session, file_path: str):
    xls = pd.ExcelFile(file_path)
    sheet_names = [s.strip() for s in xls.sheet_names]
    print(f"DEBUG: Sheets found in {os.path.basename(file_path)}: {sheet_names}")

    if 'Transaction Detail' in sheet_names:
        df = pd.read_excel(file_path, sheet_name='Transaction Detail')
        print(f"Found Transaction Detail sheet in {os.path.basename(file_path)}")
        
        count = 0
        for _, row in df.iterrows():
             try:
                date_val = row.get('Date')
                if pd.isna(date_val):
                    date_val = row.get('Transaction Date')
                
                desc = row.get('Description')
                if pd.isna(desc):
                    desc = row.get('Memo')

                if pd.isna(date_val) and pd.isna(desc): continue

                # Handle Debit/Credit explicitly
                debit_val = row.get('Debit')
                credit_val = row.get('Credit')
                
                # If they are not explicit columns, try 'Amount'
                if pd.isna(debit_val) and pd.isna(credit_val):
                     amt = row.get('Amount')
                     if not pd.isna(amt):
                         f_amt = float(amt)
                         debit_val = abs(f_amt) if f_amt < 0 else 0
                         credit_val = f_amt if f_amt > 0 else 0

                final_debit = float(debit_val) if not pd.isna(debit_val) else 0.0
                final_credit = float(credit_val) if not pd.isna(credit_val) else 0.0
                
                # Balance
                bal_val = row.get('Balance')
                final_bal = float(bal_val) if not pd.isna(bal_val) else 0.0

                db_item = BankTransaction(
                    date=pd.to_datetime(date_val).date() if not pd.isna(date_val) else None,
                    description=str(desc),
                    debits=final_debit,
                    credits=final_credit,
                    balance=final_bal
                )
                db.add(db_item)
                count += 1
             except Exception as e:
                 # print(f"Skipping row: {e}")
                 continue
        db.commit()
        print(f"Ingested {count} transactions from Detail sheet")
        return

    # Fallback to header search (no Detail sheet found)
    ingest_forecast_metrics(db, file_path)

def ingest_forecast_metrics(db: Session, file_path: str):
    # Iterate ALL sheets for metrics
    xls = pd.ExcelFile(file_path)
    count_total = 0
    
    basename = os.path.basename(file_path)
    category = "Unknown"
    if "Sales" in basename: category = "Sales"
    elif "Expense" in basename: category = "Expense"
    elif "Customer Payments" in basename: category = "CustomerPayment"
    elif "Bank Statements" in basename: category = "BankStatement"

    # Pre-fetch existing metrics to avoid duplicates (naive check)
    existing_metrics = set()
    for row in db.query(ForecastMetric.category, ForecastMetric.metric_name, ForecastMetric.period).all():
        existing_metrics.add((row.category, row.metric_name, row.period))

    for sheet in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet, header=None)
        
        count = 0
        for i, row in df.iterrows():
            # Look for pattern: String in col 0, value in col 1
            if len(row) < 2: continue
            
            col0 = row[0]
            col1 = row[1]
            
            if isinstance(col0, str) and not pd.isna(col1):
                val_str = str(col1)
                # Filter garbage
                if len(col0) > 100 or "Unnamed" in col0 or col0.strip() == "":
                    continue
                
                metric_name = f"{sheet} - {col0.strip()}" # Include sheet name in metric to differentiate
                period = "2025"
                
                if (category, metric_name, period) in existing_metrics:
                    continue

                db_item = ForecastMetric(
                    category=category,
                    metric_name=metric_name,
                    value_raw=val_str,
                    period=period 
                )
                db.add(db_item)
                existing_metrics.add((category, metric_name, period))
                count += 1
        
        if count > 0:
            db.commit()
            count_total += count

    print(f"Finished processing {os.path.basename(file_path)} ({count_total} new metrics from all sheets)")
