import sqlite3
from datetime import datetime

DB = "rent_tracker.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Tenants table
    c.execute('''CREATE TABLE IF NOT EXISTS tenants (
        tenant_id TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        upi_id TEXT,
        email TEXT,
        rent_amount REAL,
        join_date TEXT
    )''')
    # Payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT,
        amount REAL,
        txn TEXT,
        date TEXT
    )''')
    conn.commit()
    conn.close()

def insert_tenant(tenant):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO tenants
                 (tenant_id,name,phone,upi_id,email,rent_amount,join_date)
                 VALUES (?,?,?,?,?,?,?)''',
              (tenant['tenant_id'], tenant['name'], tenant['phone'], tenant['upi_id'],
               tenant['email'], float(tenant['rent_amount']), tenant['join_date']))
    conn.commit()
    conn.close()

def insert_payment(payment):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''INSERT INTO payments (tenant_id, amount, txn, date)
                 VALUES (?,?,?,?)''',
              (payment['tenant_id'], payment['amount'], payment.get('txn','offline'),
               payment.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
    conn.commit()
    conn.close()

def get_tenants():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM tenants")
    rows = c.fetchall()
    tenants = []
    for r in rows:
        tenant_id = r[0]
        rent_amount = r[5]

        # Total paid
        c.execute("SELECT SUM(amount) FROM payments WHERE tenant_id=?", (tenant_id,))
        total_paid = c.fetchone()[0] or 0

        due_amount = rent_amount - total_paid

        # Overdue days
        join_date = datetime.strptime(r[6], "%Y-%m-%d")
        overdue_days = 0
        if due_amount > 0:
            overdue_days = (datetime.now() - join_date).days

        tenants.append({
            "tenant_id": tenant_id,
            "name": r[1],
            "phone": r[2],
            "upi_id": r[3],
            "email": r[4],
            "rent_amount": rent_amount,
            "join_date": r[6],
            "paid_amount": total_paid,
            "due_amount": due_amount,
            "overdue_days": overdue_days
        })
    conn.close()
    return tenants

def get_payments_for_tenant(tenant_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE tenant_id=? ORDER BY date DESC", (tenant_id,))
    rows = c.fetchall()
    payments = []
    for r in rows:
        payments.append({
            "tenant_id": r[1],
            "amount": r[2],
            "txn": r[3],
            "date": r[4]
        })
    conn.close()
    return payments

