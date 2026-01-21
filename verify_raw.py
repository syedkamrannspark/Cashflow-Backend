
import os
import psycopg2
from app.core.config import settings

print(f"Connecting to: {settings.DB_HOST}:{settings.DB_PORT} / {settings.DB_NAME}")

try:
    conn = psycopg2.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM payment_history;")
    ph_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM invoices;")
    inv_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM bank_transactions;")
    bt_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM forecast_metrics;")
    fm_count = cur.fetchone()[0]
    
    print(f"PaymentHistory: {ph_count}")
    print(f"Invoices: {inv_count}")
    print(f"BankTransactions: {bt_count}")
    print(f"ForecastMetrics: {fm_count}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
