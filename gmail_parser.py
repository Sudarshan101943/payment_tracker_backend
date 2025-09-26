from your_existing_rent_tracker import gmail_service, list_messages, get_message_body, parse_transaction_email, match_to_tenant

def fetch_payments_from_gmail(df_tenants):
    service = gmail_service()
    msgs = list_messages(service, query='in:inbox (UPI OR credited OR payment OR txn)', max_results=5)
    payments = []
    for m in msgs:
        body = get_message_body(service, m['id'])
        parsed = parse_transaction_email(body)
        tenant = match_to_tenant(parsed, df_tenants)
        if tenant:
            payments.append({
                "tenant_id": tenant["tenant_id"],
                "amount": parsed["amount"],
                "txn": parsed.get("txn") or "online",
                "date": str(pd.Timestamp.now())
            })
    return payments

