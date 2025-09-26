import os, re, pickle, base64
import pandas as pd
from fpdf import FPDF
from datetime import datetime, timedelta
from decimal import Decimal
from dateutil import parser as dateparser
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

TENANT_XLSX = "tenant_reference.xlsx"
OWNER_EMAIL = "sudarshanreddy0825@gmail.com"
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.send']

# Trusted senders (banks / UPI platforms)
TRUSTED_SENDERS = [
    'upi@phonepe.com', 'noreply@paytm.com', 'noreply@googlepay.com', 
    'noreply@sbi.co.in', 'noreply@icicibank.com', 'noreply@hdfcbank.com'
]

# ---------------- Gmail Auth ----------------
def gmail_service(credentials_path='credentials.json', token_path='token.pickle'):
    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as f:
            pickle.dump(creds, f)
    return build('gmail', 'v1', credentials=creds)

def list_messages(service, query, max_results=10):
    resp = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    return resp.get('messages', [])

def get_message(service, msg_id):
    return service.users().messages().get(userId='me', id=msg_id, format='full').execute()

def get_message_body(msg):
    payload = msg['payload']
    parts = payload.get('parts') or []
    body = ''
    if parts:
        for p in parts:
            mime = p.get('mimeType','')
            data = p['body'].get('data')
            if data and (mime == 'text/plain' or mime == 'text/html'):
                body = base64.urlsafe_b64decode(data.encode('UTF-8')).decode('utf-8')
                return body
    else:
        data = payload.get('body', {}).get('data')
        if data:
            body = base64.urlsafe_b64decode(data.encode('UTF-8')).decode('utf-8')
    return body

# ---------------- Parse Transaction ----------------
RE_AMOUNT = re.compile(r'₹?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{1,2})?|[0-9]+(?:\.\d{1,2})?)')
RE_UPI = re.compile(r'([a-zA-Z0-9.\-_]{3,}@[a-zA-Z]{2,})')
RE_PHONE = re.compile(r'(?<!\d)(?:\+91[\-\s]?)?([6-9]\d{9})(?!\d)')
RE_TXN = re.compile(r'\b(txn|tx|utr|ref)[\s:]*([A-Za-z0-9\-\/]+)', re.I)

def parse_transaction_email(text):
    text = text.replace('\xa0',' ').strip()
    upi = (RE_UPI.search(text).group(1).lower()
           if RE_UPI.search(text) else None)
    phone = (RE_PHONE.search(text).group(1)
             if RE_PHONE.search(text) else None)
    amounts = [a.replace(',','') for a in RE_AMOUNT.findall(text)]
    amounts = [Decimal(a) for a in amounts if a and float(a) > 0]
    amount = max(amounts) if amounts else None
    txn = (RE_TXN.search(text).group(2)
           if RE_TXN.search(text) else None)
    return {'upi': upi, 'phone': phone,
            'amount': float(amount) if amount else None,
            'txn': txn, 'raw': text[:200]}

# ---------------- Match Tenant ----------------
def match_to_tenant(parsed, df_tenants):
    if parsed['upi']:
        rows = df_tenants[df_tenants['upi_id'].str.lower() == parsed['upi']]
        if not rows.empty: return rows.iloc[0].to_dict()
    if parsed['phone']:
        rows = df_tenants[df_tenants['phone'].str.contains(parsed['phone'], na=False)]
        if not rows.empty: return rows.iloc[0].to_dict()
    if parsed['amount']:
        candidates = df_tenants[df_tenants['rent_amount'] == parsed['amount']]
        if len(candidates) == 1: return candidates.iloc[0].to_dict()
    return None

# ---------------- Invoice PDF ----------------
def generate_invoice_pdf(tenant, parsed, out_path):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 10, "Rent Receipt", ln=True, align='C')
    pdf.ln(5)
    pdf.cell(0, 8, f"Tenant: {tenant['name']} ({tenant['tenant_id']})", ln=True)
    pdf.cell(0, 8, f"Email: {tenant.get('email','')}", ln=True)
    pdf.cell(0, 8, f"UPI: {tenant.get('upi_id','')}", ln=True)
    pdf.cell(0, 8, f"Phone: {tenant.get('phone','')}", ln=True)
    pdf.ln(5)
    pdf.cell(0, 8, f"Amount received: ₹{parsed['amount']}", ln=True)
    pdf.cell(0, 8, f"Transaction ref: {parsed.get('txn','')}", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(10)
    pdf.multi_cell(0, 6, "Thank you for the payment. This is an auto generated receipt.")
    pdf.output(out_path)
    return out_path

# ---------------- Send Mail ----------------
def send_email_with_attachment(service, to_email, subject, body_text, attachment_path=None):
    message = MIMEMultipart()
    message['to'] = to_email
    message['subject'] = subject
    message.attach(MIMEText(body_text, 'html'))

    if attachment_path:
        with open(attachment_path, 'rb') as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
        message.attach(part)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    sent = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print(f"Sent email to {to_email}, msgId: {sent['id']}")

# ---------------- Summary Mail ----------------
def send_summary(service, df_tenants, payments_today):
    # Compute overdue, balance tenants
    df_tenants['rent_amount'] = pd.to_numeric(df_tenants['rent_amount'])
    df_tenants['due_date'] = pd.to_datetime(df_tenants['join_date']).apply(lambda d: d.replace(day=25))  # example due day: 25th
    today = datetime.now().date()
    summary_rows = []

    for idx, row in df_tenants.iterrows():
        tenant_id = row['tenant_id']
        paid = tenant_id in payments_today
        amount_due = row['rent_amount'] if not paid else 0
        overdue_days = (today - row['due_date'].date()).days if today > row['due_date'].date() and not paid else 0
        summary_rows.append({
            'tenant': row['name'],
            'paid': paid,
            'amount_due': amount_due,
            'overdue_days': overdue_days
        })

    # Build HTML table
    html = "<h2>Daily Rent Summary</h2>"
    html += "<table border='1' cellpadding='5' cellspacing='0'>"
    html += "<tr><th>Tenant</th><th>Status</th><th>Amount Due (₹)</th><th>Overdue Days</th></tr>"
    for row in summary_rows:
        status = "Paid" if row['paid'] else "Pending"
        html += f"<tr><td>{row['tenant']}</td><td>{status}</td><td>{row['amount_due']}</td><td>{row['overdue_days']}</td></tr>"
    html += "</table>"

    send_email_with_attachment(service, OWNER_EMAIL, "Daily Rent Summary", html)

# ---------------- Main ----------------
def main():
    df = pd.read_excel(TENANT_XLSX, dtype=str)
    df['upi_id'] = df['upi_id'].str.lower().fillna('')
    df['phone'] = df['phone'].str.replace(r'\D','', regex=True).fillna('')
    df['rent_amount'] = pd.to_numeric(df['rent_amount'])

    service = gmail_service()

    # Gmail query: only trusted senders
    query = 'in:inbox (' + ' OR '.join([f'from:{s}' for s in TRUSTED_SENDERS]) + ')'
    msgs = list_messages(service, query=query, max_results=20)
    if not msgs:
        print("No messages found.")
        return

    os.makedirs("invoices", exist_ok=True)
    payments_today = set()

    for m in msgs:
        msg = get_message(service, m['id'])
        sender = msg['payload']['headers']
        sender_email = next((h['value'] for h in sender if h['name'].lower() == 'from'), '')
        sender_email = sender_email.lower()
        if not any(trusted in sender_email for trusted in TRUSTED_SENDERS):
            continue  # Skip non-trusted senders

        body = get_message_body(msg)
        parsed = parse_transaction_email(body)
        tenant = match_to_tenant(parsed, df)
        if tenant:
            pdf_path = f"invoices/{tenant['tenant_id']}_{parsed.get('txn','auto')}.pdf"
            generate_invoice_pdf(tenant, parsed, pdf_path)
            if tenant.get('email'):
                send_email_with_attachment(service, tenant['email'],
                                           "Rent Receipt",
                                           f"Hello {tenant['name']},<br><br>Please find attached your rent receipt.",
                                           pdf_path)
            print("Processed payment for", tenant['name'], parsed)
            payments_today.add(tenant['tenant_id'])
        else:
            print("Unmatched transaction:", parsed)

    # Send summary to owner
    send_summary(service, df, payments_today)

if __name__ == "__main__":
    main()

