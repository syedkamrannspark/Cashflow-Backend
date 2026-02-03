#!/usr/bin/env python3
"""
Script to seed the database with dummy data for testing purposes.
Run with: python3 seed_database.py
"""

from datetime import datetime, timedelta
from app.core.database import SessionLocal, engine, Base
from app.models.invoice import AppInvoice
from app.models.payment_history import PaymentHistory
from app.models.complex_models import BankTransaction, ForecastMetric

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Initialize database session
db = SessionLocal()

def clear_database():
    """Clear existing data from all tables"""
    print("Clearing existing data...")
    db.query(AppInvoice).delete()
    db.query(PaymentHistory).delete()
    db.query(BankTransaction).delete()
    db.query(ForecastMetric).delete()
    db.commit()
    print("Database cleared.")

def seed_invoices():
    """Seed invoices table with dummy data"""
    print("Seeding invoices...")
    
    customer_names = [
        "Acme Corporation", "TechStart Inc", "Global Enterprises", "Innovation Labs",
        "Future Systems", "Digital Solutions", "Creative Agency", "Enterprise Plus",
        "CloudTech Systems", "Data Analytics Co", "Financial Services Inc", "Retail Group Ltd",
        "Manufacturing Corp", "Healthcare Solutions", "Education Plus", "Media Networks",
        "Tech Ventures", "Smart Industries", "Advanced Tech", "Global Logistics",
        "Software House", "Consulting Firm", "Marketing Agency", "Design Studio",
        "E-Commerce Hub", "Logistics Pro", "Real Estate Group", "Insurance Plus",
        "Financial Tech", "Supply Chain Co", "Distribution Center", "Trading Partners",
        "Investment Group", "Venture Capital", "Startup Hub", "Tech Incubator",
        "Business Solutions", "Management Consulting", "Strategic Partners", "Growth Partners",
        "Innovation Hub", "Digital Transformation", "Enterprise Software", "Cloud Services",
        "Data Engineering", "AI Solutions", "Mobile Apps", "Web Development",
        "IT Infrastructure", "Network Solutions", "Security Services", "Support Services",
        "Professional Services", "Training Academy", "Research Institute", "Development Labs",
    ]
    
    statuses = ["Paid", "Overdue", "Partial", "Outstanding"]
    invoices = []
    base_date = datetime(2024, 10, 1).date()
    
    for i in range(60):
        invoice_date = base_date + timedelta(days=i*2)
        due_date = invoice_date + timedelta(days=30)
        today = datetime.now().date()
        days_past_due = (today - due_date).days
        days_past_due = max(0, days_past_due)
        
        # Vary amounts between 2000-25000
        total = round(2000 + (i * 382.5), 2)
        
        # Randomize payment status
        status = statuses[i % 4]
        if status == "Paid":
            amount_paid = total
            balance = 0.0
        elif status == "Partial":
            amount_paid = round(total * 0.5, 2)
            balance = total - amount_paid
        elif status == "Overdue":
            amount_paid = 0.0
            balance = total
        else:  # Outstanding
            amount_paid = 0.0
            balance = total
        
        invoices.append(AppInvoice(
            invoice_number=f"INV-2025-{i+1:05d}",
            account_number=f"ACC-{1000 + (i % 50)}",
            customer_name=customer_names[i % len(customer_names)],
            invoice_date=invoice_date,
            due_date=due_date,
            total_amount=total,
            amount_paid=amount_paid,
            balance_due=balance,
            status=status,
            days_past_due=days_past_due if status == "Overdue" else 0
        ))
    
    db.add_all(invoices)
    db.commit()
    print(f"✓ Added {len(invoices)} invoices")

def seed_payment_history():
    """Seed payment history table with dummy data"""
    print("Seeding payment history...")
    
    customer_names = [
        "Acme Corporation", "TechStart Inc", "Global Enterprises", "Innovation Labs",
        "Future Systems", "Digital Solutions", "Creative Agency", "Enterprise Plus",
        "CloudTech Systems", "Data Analytics Co", "Financial Services Inc", "Retail Group Ltd",
        "Manufacturing Corp", "Healthcare Solutions", "Education Plus", "Media Networks",
        "Tech Ventures", "Smart Industries", "Advanced Tech", "Global Logistics",
        "Software House", "Consulting Firm", "Marketing Agency", "Design Studio",
        "E-Commerce Hub", "Logistics Pro", "Real Estate Group", "Insurance Plus",
        "Financial Tech", "Supply Chain Co", "Distribution Center", "Trading Partners",
        "Investment Group", "Venture Capital", "Startup Hub", "Tech Incubator",
        "Business Solutions", "Management Consulting", "Strategic Partners", "Growth Partners",
        "Innovation Hub", "Digital Transformation", "Enterprise Software", "Cloud Services",
        "Data Engineering", "AI Solutions", "Mobile Apps", "Web Development",
        "IT Infrastructure", "Network Solutions", "Security Services", "Support Services",
        "Professional Services", "Training Academy", "Research Institute", "Development Labs",
    ]
    
    account_types = ["Business", "Enterprise", "Startup", "SMB", "Corporation"]
    payment_methods = ["Bank Transfer", "Credit Card", "ACH", "Wire Transfer", "Check"]
    payment_statuses = ["Paid", "Overdue", "Partial", "Outstanding"]
    
    payments = []
    base_date = datetime(2024, 10, 1).date()
    
    for i in range(60):
        invoice_date = base_date + timedelta(days=i*2)
        due_date = invoice_date + timedelta(days=30)
        
        # Randomize payment behavior
        payment_status = payment_statuses[i % 4]
        
        if payment_status == "Paid":
            payment_date = due_date - timedelta(days=1 + (i % 10))
            amount_paid = round(5000 + (i * 286.6), 2)
            days_late = -1
            late_fee = 0.0
            on_time = "Yes"
        elif payment_status == "Overdue":
            payment_date = None
            amount_paid = 0.0
            days_late = 20 + (i % 40)
            late_fee = round(amount_paid * 0.05, 2) if amount_paid > 0 else 0.0
            on_time = "No"
        elif payment_status == "Partial":
            payment_date = due_date + timedelta(days=5 + (i % 15))
            total_invoice = round(5000 + (i * 286.6), 2)
            amount_paid = round(total_invoice * 0.6, 2)
            days_late = 5 + (i % 10)
            late_fee = round((total_invoice - amount_paid) * 0.05, 2)
            on_time = "No"
        else:  # Outstanding
            payment_date = None
            total_invoice = round(5000 + (i * 286.6), 2)
            amount_paid = 0.0
            days_late = 5 + (i % 20)
            late_fee = round(total_invoice * 0.02, 2)
            on_time = "No"
        
        invoice_amount = round(5000 + (i * 286.6), 2)
        
        payments.append(PaymentHistory(
            account_number=f"ACC-{1000 + (i % 50)}",
            customer_name=customer_names[i % len(customer_names)],
            account_type=account_types[i % len(account_types)],
            invoice_number=f"INV-2025-{i+1:05d}",
            billing_date=invoice_date,
            due_date=due_date,
            payment_date=payment_date,
            invoice_amount=invoice_amount,
            late_fee=late_fee,
            amount_paid=amount_paid,
            payment_method=payment_methods[i % len(payment_methods)] if payment_status == "Paid" else None,
            transaction_id=f"TXN-2025-{i+1:05d}" if payment_status == "Paid" else None,
            days_late=days_late,
            payment_status=payment_status,
            on_time_payment=on_time
        ))
    
    db.add_all(payments)
    db.commit()
    print(f"✓ Added {len(payments)} payment history records")

def seed_bank_transactions():
    """Seed bank transactions table with dummy data"""
    print("Seeding bank transactions...")
    
    expense_descriptions = [
        "Operating Expense - Utilities", "Payroll", "Office Supplies", "Rent",
        "Equipment Purchase", "Insurance Payment", "Software License", "Consulting Fee",
        "Marketing Expense", "Travel Reimbursement", "Professional Development", "Maintenance",
        "Supplies", "Shipping", "Customer Service", "Sales Commission", "Training",
        "Legal Fee", "Accounting", "IT Support", "Advertising", "Event", "Membership",
        "Subscription", "Hosting Fee", "Cloud Services", "Database", "API Access",
        "Library Purchase", "Audit", "Inspection", "Repair", "Upgrade", "Renewal"
    ]
    
    revenue_descriptions = [
        "Customer Payment - Invoice", "Service Revenue", "Contract Payment",
        "Monthly Subscription", "Consulting Income", "License Fee", "Support Fee",
        "Training Fee", "Product Sale", "Professional Service", "Maintenance Fee",
        "Technical Support", "Implementation Service", "Customization Fee", "Premium Service"
    ]
    
    transactions = []
    base_date = datetime(2024, 10, 1).date()
    running_balance = 500000.0
    
    for i in range(60):
        date = base_date + timedelta(days=i)
        
        # Alternate between debits and credits with some variety
        if i % 3 == 0:  # Revenue/Credit
            amount = round(5000 + (i * 250), 2)
            description = revenue_descriptions[i % len(revenue_descriptions)]
            debits = None
            credits = amount
            running_balance += amount
        else:  # Expense/Debit
            amount = round(2000 + (i * 150), 2)
            description = expense_descriptions[i % len(expense_descriptions)]
            debits = amount
            credits = None
            running_balance -= amount
        
        transactions.append(BankTransaction(
            date=date,
            description=description,
            debits=debits,
            credits=credits,
            balance=round(running_balance, 2)
        ))
    
    db.add_all(transactions)
    db.commit()
    print(f"✓ Added {len(transactions)} bank transactions")

def seed_forecast_metrics():
    """Seed forecast metrics table with dummy data"""
    print("Seeding forecast metrics...")
    
    metrics = []
    periods = [
        "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07",
        "2025-08", "2025-09", "2025-10", "2025-11", "2025-12"
    ]
    
    # Sales metrics (12-15 entries)
    for i, period in enumerate(periods[:15]):
        revenue = 100000 + (i * 15000)
        metrics.append(ForecastMetric(
            category="Sales",
            metric_name="Monthly Revenue",
            value_raw=f"${revenue:,}",
            period=period
        ))
    
    # Average Monthly Revenue (aggregate)
    for i in range(5):
        avg_revenue = 1200000 + (i * 200000)
        metrics.append(ForecastMetric(
            category="Sales",
            metric_name="Average Monthly Revenue",
            value_raw=f"${avg_revenue:,}",
            period=f"Q{i+1} 2025"
        ))
    
    # Expense metrics (12-15 entries)
    for i, period in enumerate(periods[:15]):
        expense = 45000 + (i * 5000)
        metrics.append(ForecastMetric(
            category="Expense",
            metric_name="Operating Cost",
            value_raw=f"${expense:,}",
            period=period
        ))
    
    # Average Monthly Expenses (aggregate)
    for i in range(5):
        avg_expense = 500000 + (i * 50000)
        metrics.append(ForecastMetric(
            category="Expense",
            metric_name="Average Monthly Expenses",
            value_raw=f"${avg_expense:,}",
            period=f"Q{i+1} 2025"
        ))
    
    # Customer Payment metrics (12-15 entries)
    for i, period in enumerate(periods[:15]):
        collections = 80000 + (i * 12000)
        metrics.append(ForecastMetric(
            category="CustomerPayment",
            metric_name="Expected Collections",
            value_raw=f"${collections:,}",
            period=period
        ))
    
    # Payment performance metrics
    metrics.extend([
        ForecastMetric(
            category="CustomerPayment",
            metric_name="On-Time Payment Rate",
            value_raw="65%",
            period="2025 Q1"
        ),
        ForecastMetric(
            category="CustomerPayment",
            metric_name="Average Days to Payment",
            value_raw="18 days",
            period="2025 Q1"
        ),
        ForecastMetric(
            category="CustomerPayment",
            metric_name="Write-off Rate",
            value_raw="2.5%",
            period="2025 Q1"
        ),
    ])
    
    # Cash position metrics
    metrics.extend([
        ForecastMetric(
            category="CashPosition",
            metric_name="Current Cash Balance",
            value_raw="$450,000",
            period="2025-01-30"
        ),
        ForecastMetric(
            category="CashPosition",
            metric_name="Cash Runway Days",
            value_raw="45 days",
            period="2025-01-30"
        ),
        ForecastMetric(
            category="CashPosition",
            metric_name="Days Sales Outstanding",
            value_raw="32 days",
            period="2025 Q1"
        ),
    ])
    
    db.add_all(metrics)
    db.commit()
    print(f"✓ Added {len(metrics)} forecast metrics")

def main():
    """Main function to seed all tables"""
    try:
        print("=" * 50)
        print("Starting database seeding...")
        print("=" * 50)
        
        clear_database()
        seed_invoices()
        seed_payment_history()
        seed_bank_transactions()
        seed_forecast_metrics()
        
        print("=" * 50)
        print("✓ Database seeding completed successfully!")
        print("=" * 50)
    except Exception as e:
        print(f"✗ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
