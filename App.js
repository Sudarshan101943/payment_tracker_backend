import { useEffect, useState } from "react";
import axios from "axios";

function App() {
  const [tenants, setTenants] = useState([]);
  const [payments, setPayments] = useState([]);
  const [tenantId, setTenantId] = useState("");
  const [amount, setAmount] = useState("");

  useEffect(() => {
    fetchTenants();
  }, []);

  const fetchTenants = async () => {
    try {
      const res = await axios.get("http://127.0.0.1:8000/tenants");
      setTenants(res.data.tenants || []);
    } catch (err) {
      console.error(err);
    }
  };

  const markPaid = async () => {
    if(!tenantId || !amount) return alert("Enter tenant ID and amount");
    try {
      await axios.post("http://127.0.0.1:8000/payments/mark_paid", {
        tenant_id: tenantId,
        amount: parseFloat(amount)
      });
      setTenantId("");
      setAmount("");
      fetchTenants();
    } catch(err){
      console.error(err);
    }
  };

  return (
    <div style={{padding: "20px"}}>
      <h1>Owner Dashboard</h1>

      <h2>Tenants</h2>
      <table border="1" cellPadding="5">
        <thead>
          <tr>
            <th>Name</th>
            <th>Rent</th>
            <th>Paid</th>
            <th>Due</th>
            <th>Overdue Days</th>
          </tr>
        </thead>
        <tbody>
          {tenants.map(t => (
            <tr key={t.tenant_id}>
              <td>{t.name}</td>
              <td>{t.rent_amount}</td>
              <td>{t.paid_amount}</td>
              <td>{t.due_amount}</td>
              <td style={{color: t.overdue_days>0 ? "red":"black"}}>{t.overdue_days}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Mark Offline Payment</h2>
      <input placeholder="Tenant ID" value={tenantId} onChange={e=>setTenantId(e.target.value)} />
      <input placeholder="Amount" value={amount} onChange={e=>setAmount(e.target.value)} />
      <button onClick={markPaid}>Mark Paid</button>
    </div>
  );
}

export default App;

