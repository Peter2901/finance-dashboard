const API = "";  // Same origin on Railway — no need for full URL

const ICONS = {
  Groceries: "🛒", Food: "🍔", Transport: "🚗",
  Bills: "💡", Entertainment: "🎬", Health: "💊", Other: "💸"
};

let chartInstance = null;

async function load() {
  try {
    const res = await fetch(`${API}/api/dashboard`);
    const d = await res.json();
    renderDaily(d.today);
    renderAccounts(d.accounts);
    renderTransactions(d.recent_transactions);
    renderBudgets(d.budgets);
    renderLoans(d.upcoming_loans);
    renderChart(d.weekly_history);
  } catch(e) {
    console.error("Load failed", e);
  }
}

function fmt(n) {
  return parseFloat(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function renderDaily(t) {
  if (!t) return;
  document.getElementById("today-limit").textContent     = `₹${fmt(t.effective_limit)}`;
  document.getElementById("today-spent").textContent     = `₹${fmt(t.spent)} spent`;
  document.getElementById("today-remaining").textContent = `₹${fmt(t.remaining)} left`;

  const pct = t.effective_limit > 0 ? Math.min(100, (t.spent / t.effective_limit) * 100) : 0;
  const fill = document.getElementById("progress-fill");
  fill.style.width = pct + "%";
  fill.className = "progress-fill" + (pct > 90 ? " danger" : pct > 70 ? " warn" : "");

  const note = document.getElementById("rollover-note");
  if (t.rollover_from_prev > 0)
    note.textContent = `+₹${fmt(t.rollover_from_prev)} rolled over from yesterday`;
  else if (t.rollover_from_prev < 0)
    note.textContent = `₹${fmt(Math.abs(t.rollover_from_prev))} overspent yesterday — deducted today`;
  else
    note.textContent = `Base limit: ₹${fmt(t.base_limit)}/day`;
}

function renderAccounts(accounts) {
  if (!accounts?.length) return;
  document.getElementById("header-accounts").innerHTML =
    accounts.map(a => `${a.bank}: <strong>₹${fmt(a.balance)}</strong>`).join(" &nbsp;|&nbsp; ");
}

function renderTransactions(txs) {
  const el = document.getElementById("tx-list");
  if (!txs?.length) { el.innerHTML = `<div class="empty">No transactions yet.</div>`; return; }
  el.innerHTML = txs.map(tx => `
    <div class="tx-item">
      <div class="tx-icon">${ICONS[tx.category] || "💸"}</div>
      <div>
        <div class="tx-name">${tx.merchant}</div>
        <div class="tx-cat">${tx.category} · ${tx.date}</div>
      </div>
      <div class="tx-amt">-₹${fmt(tx.amount)}</div>
    </div>`).join("");
}

function renderBudgets(budgets) {
  const el = document.getElementById("budget-list");
  if (!budgets?.length) { el.innerHTML = `<div class="empty">No budgets set.</div>`; return; }
  el.innerHTML = budgets.map(b => {
    const pct = b.monthly_budget > 0 ? Math.min(100, (b.spent_this_month / b.monthly_budget) * 100) : 0;
    const color = pct > 90 ? "var(--red)" : pct > 70 ? "var(--yellow)" : "var(--accent)";
    return `
    <div class="budget-row">
      <div class="budget-header">
        <span>${b.category}</span>
        <span style="color:var(--muted)">₹${fmt(b.spent_this_month)} / ₹${fmt(b.monthly_budget)}</span>
      </div>
      <div class="budget-track">
        <div class="budget-fill" style="width:${pct}%;background:${color}"></div>
      </div>
    </div>`;
  }).join("");
}

function renderLoans(loans) {
  const el = document.getElementById("loan-list");
  if (!loans?.length) { el.innerHTML = `<div class="empty">No upcoming payments.</div>`; return; }
  el.innerHTML = loans.map(l => `
    <div class="loan-item">
      <div class="loan-lender">${l.lender}</div>
      <div class="loan-meta">Due: ${l.next_deduction_date}</div>
      <div class="loan-emi">₹${fmt(l.emi)} / month</div>
      ${l.foreclosure_amount ? `<div class="loan-meta">Foreclose: ₹${fmt(l.foreclosure_amount)}</div>` : ""}
    </div>`).join("");
}

function renderChart(history) {
  if (!history?.length) return;
  const ctx = document.getElementById("chart").getContext("2d");
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: history.map(r => r.date?.slice(5)),
      datasets: [
        {
          label: "Limit",
          data: history.map(r => r.effective_limit),
          backgroundColor: "rgba(124,111,247,0.3)",
          borderColor: "#7c6ff7",
          borderWidth: 1.5,
          borderRadius: 4,
        },
        {
          label: "Spent",
          data: history.map(r => r.spent),
          backgroundColor: "rgba(233,108,90,0.4)",
          borderColor: "#e96c5a",
          borderWidth: 1.5,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: "#8b8fa8", font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: "#8b8fa8" }, grid: { color: "rgba(255,255,255,0.04)" } },
        y: { ticks: { color: "#8b8fa8" }, grid: { color: "rgba(255,255,255,0.04)" } },
      },
    },
  });
}

// ── Actions ──────────────────────────────────────────────────────

async function addSpend() {
  const amount   = parseFloat(document.getElementById("qa-amount").value);
  const merchant = document.getElementById("qa-merchant").value.trim();
  const category = document.getElementById("qa-cat").value;
  if (!amount || !merchant) return alert("Enter amount and merchant");

  await fetch(`${API}/api/transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount, merchant, category }),
  });

  document.getElementById("qa-amount").value   = "";
  document.getElementById("qa-merchant").value = "";
  load();
}

async function syncSMS() {
  const btn = document.querySelector(".btn-sm");
  btn.textContent = "Syncing…";
  const res  = await fetch(`${API}/api/process-sms`, { method: "POST" });
  const data = await res.json();
  btn.textContent = "↻ Sync SMS";
  alert(`Done! Processed: ${data.processed} | Failed to parse: ${data.failed.length}`);
  load();
}

function toggleLoanForm() {
  const f = document.getElementById("loan-form");
  f.style.display = f.style.display === "none" ? "block" : "none";
}

async function saveLoan() {
  const body = {
    lender:               document.getElementById("lf-lender").value,
    principal:            parseFloat(document.getElementById("lf-principal").value),
    outstanding:          parseFloat(document.getElementById("lf-outstanding").value),
    emi:                  parseFloat(document.getElementById("lf-emi").value),
    next_deduction_date:  document.getElementById("lf-date").value,
    foreclosure_amount:   parseFloat(document.getElementById("lf-foreclosure").value) || 0,
  };
  if (!body.lender || !body.emi) return alert("Fill lender and EMI at minimum");
  await fetch(`${API}/api/loans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  toggleLoanForm();
  load();
}

async function runOCR(file) {
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  const res  = await fetch(`${API}/api/ocr`, { method: "POST", body: fd });
  const data = await res.json();
  const el   = document.getElementById("ocr-result");
  el.style.display = "block";
  el.textContent = data.error
    ? `Error: ${data.error}`
    : `Detected amounts: ₹${data.detected_amounts.join(", ₹") || "none"}\n\n${data.raw_text}`;
}

function handleDrop(e) {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file) runOCR(file);
}

// Init
load();
setInterval(load, 60000);
