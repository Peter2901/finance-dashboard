const API = "";
const EMOJIS = ['🍔','🛒','🚗','💡','🎬','💊','✈️','👗','🏋️','📱','🏠','🎓','🍺','☕','🎮','💸','🐕','🌿'];
const CAT_ICONS = { Food:'🍔', Groceries:'🛒', Transport:'🚗', Bills:'💡', Entertainment:'🎬', Health:'💊', EMI:'🏦', 'Big Purchase':'🛍️', Other:'💸' };
let chartInstance = null;
let dashData = {};
let chatHistory = [];
let deferredPrompt = null;

// ── Init ──────────────────────────────────────────────────────────
window.addEventListener('load', () => {
  loadDashboard();
  registerSW();
  setInterval(loadDashboard, 60000);
  populateCatSelect();
});

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  document.getElementById('install-btn').style.display = 'block';
});

function installPWA() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => { deferredPrompt = null; });
  }
}

function registerSW() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

// ── Load dashboard ────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const res = await fetch(`${API}/api/dashboard`);
    dashData = await res.json();
    renderHero(dashData.today);
    renderBanks(dashData.accounts);
    renderStats(dashData);
    renderTxMini(dashData.recent_transactions);
    renderTxFull(dashData.recent_transactions);
    renderBudgetMini(dashData.budgets);
    renderBudgetEditor(dashData.budgets);
    renderLoans(dashData.upcoming_loans);
    renderChart(dashData.weekly_history);
    renderAccounts(dashData.accounts);
    renderAlerts(dashData.pending_alerts);
    populateCatSelect(dashData.budgets);
    updateSetterInfo(dashData.monthly_budget);
  } catch(e) {
    console.error('Dashboard load failed:', e);
  }
}

// ── Render functions ──────────────────────────────────────────────
function renderHero(today) {
  if (!today) return;
  const { effective_limit, spent, remaining, rollover_from_prev, base_limit } = today;
  document.getElementById('hero-amount').textContent = `₹${fmt(remaining)}`;
  document.getElementById('hero-spent').textContent  = `₹${fmt(spent)} spent`;
  document.getElementById('hero-limit').textContent  = `₹${fmt(effective_limit)} limit`;

  const pct  = effective_limit > 0 ? Math.min(100, (spent / effective_limit) * 100) : 0;
  const fill = document.getElementById('progress-fill');
  fill.style.width = pct + '%';
  fill.className   = 'progress-fill' + (pct > 90 ? ' danger' : pct > 70 ? ' warn' : '');

  const roll = document.getElementById('rollover-pill');
  if (rollover_from_prev > 0)
    roll.textContent = `+₹${fmt(rollover_from_prev)} rolled over from yesterday`;
  else if (rollover_from_prev < 0)
    roll.textContent = `₹${fmt(Math.abs(rollover_from_prev))} adjusted for overspend`;
  else
    roll.textContent = `Base limit: ₹${fmt(base_limit)}/day`;
}

function renderBanks(accounts) {
  if (!accounts?.length) return;
  document.getElementById('header-banks').innerHTML =
    accounts.map(a => `${a.bank}: <strong>₹${fmt(a.balance)}</strong>`).join('<br>');
}

function renderStats(d) {
  document.getElementById('stat-monthly').textContent    = d.monthly_budget ? `₹${fmt(d.monthly_budget)}` : 'Not set';
  document.getElementById('stat-daily').textContent      = `₹${fmt(d.base_daily)}/day`;
  document.getElementById('stat-month-spent').textContent = `₹${fmt(d.month_spent)}`;
  const nextLoan = d.upcoming_loans?.[0];
  document.getElementById('stat-emi').textContent = nextLoan ? nextLoan.next_deduction_date?.slice(5) : '—';
}

function renderTxMini(txs) { renderTxList('tx-mini', txs?.slice(0, 5)); }
function renderTxFull(txs) { renderTxList('tx-full', txs); }

function renderTxList(id, txs) {
  const el = document.getElementById(id);
  if (!txs?.length) { el.innerHTML = `<div style="color:var(--green-muted);font-size:12px;padding:8px 0">No transactions yet.</div>`; return; }
  el.innerHTML = txs.map(tx => `
    <div class="tx-item">
      <div class="tx-icon">${CAT_ICONS[tx.category] || '💸'}</div>
      <div>
        <div class="tx-name">${tx.merchant}</div>
        <div class="tx-cat">${tx.category} · ${tx.date}</div>
      </div>
      ${tx.category === 'Big Purchase' ? `<span class="tx-onetime">one-time</span>` : `<div class="tx-amt">-₹${fmt(tx.amount)}</div>`}
    </div>`).join('');
}

function renderBudgetMini(budgets) {
  const el = document.getElementById('budget-mini');
  if (!budgets?.length) { el.innerHTML = ''; return; }
  el.innerHTML = budgets.slice(0, 4).map(b => {
    const pct   = b.monthly_budget > 0 ? Math.min(100, Math.round((b.spent_this_month / b.monthly_budget) * 100)) : 0;
    const color = pct > 90 ? 'var(--red)' : pct > 70 ? 'var(--yellow)' : 'var(--green-mid)';
    return `
    <div class="budget-item">
      <div class="budget-row">
        <span class="budget-name">${b.category}</span>
        <span class="budget-amount">₹${fmt(b.spent_this_month)} / ₹${fmt(b.monthly_budget)}</span>
      </div>
      <div class="budget-track"><div class="budget-fill" style="width:${pct}%;background:${color}"></div></div>
    </div>`;
  }).join('');
}

function renderBudgetEditor(budgets) {
  const el = document.getElementById('cat-editor');
  if (!budgets?.length) return;
  el.innerHTML = budgets.map((b, i) => `
    <div class="cat-edit-row" id="cat-row-${i}">
      <div class="cat-emoji-btn" onclick="rotateEmoji(this)">${CAT_ICONS[b.category] || '💸'}</div>
      <input class="cat-name-input" value="${b.category}" oninput="recalcTotal()"/>
      <input class="cat-budget-input" type="number" value="${b.monthly_budget}" oninput="recalcTotal()"/>
      <button class="cat-del" onclick="this.closest('.cat-edit-row').remove();recalcTotal()">×</button>
    </div>`).join('');
  recalcTotal();
}

function renderLoans(loans) {
  const el = document.getElementById('loan-list');
  if (!loans?.length) { el.innerHTML = `<div style="color:var(--green-muted);font-size:12px">No upcoming EMIs.</div>`; return; }
  el.innerHTML = loans.map(l => `
    <div class="loan-card">
      <div class="loan-lender">${l.lender}</div>
      <div class="loan-meta">Due: ${l.next_deduction_date}</div>
      <div class="loan-emi">₹${fmt(l.emi)}/month</div>
      ${l.foreclosure_amount ? `<div class="loan-fore">Foreclosure: ₹${fmt(l.foreclosure_amount)}</div>` : ''}
    </div>`).join('');
}

function renderAccounts(accounts) {
  const el = document.getElementById('accounts-list');
  if (!accounts?.length) { el.innerHTML = ''; return; }
  el.innerHTML = accounts.map(a => `
    <div class="accounts-row">
      <div><div class="account-name">${a.bank}</div><div class="setting-sub">${a.account_name}</div></div>
      <div class="account-bal">₹${fmt(a.balance)}</div>
    </div>`).join('');
}

function renderChart(history) {
  if (!history?.length) return;
  const ctx = document.getElementById('chart').getContext('2d');
  if (chartInstance) chartInstance.destroy();
  chartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: history.map(r => r.date?.slice(5)),
      datasets: [
        { label: 'Limit', data: history.map(r => r.effective_limit), backgroundColor: 'rgba(134,239,172,0.3)', borderColor: '#86efac', borderWidth: 1.5, borderRadius: 4 },
        { label: 'Spent', data: history.map(r => r.spent), backgroundColor: 'rgba(220,38,38,0.35)', borderColor: '#dc2626', borderWidth: 1.5, borderRadius: 4 },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#6b7280', font: { size: 10 } } } },
      scales: {
        x: { ticks: { color: '#6b7280', font: { size: 9 } }, grid: { color: 'rgba(0,0,0,0.05)' } },
        y: { ticks: { color: '#6b7280', font: { size: 9 } }, grid: { color: 'rgba(0,0,0,0.05)' } },
      },
    },
  });
}

function renderAlerts(alerts) {
  const banner = document.getElementById('alert-banner');
  const inner  = document.getElementById('alert-inner');
  if (!alerts?.length) { banner.style.display = 'none'; return; }
  const alert = alerts[0];
  banner.style.display = 'block';
  inner.innerHTML = `
    <div style="font-weight:600;margin-bottom:4px">🤖 Groq AI: Unusual spend detected</div>
    <div>₹${fmt(alert.amount)} at <strong>${alert.merchant}</strong> — what is this expense?</div>
    <div class="alert-btns">
      <button class="alert-btn primary" onclick="resolveAlert('one-time', ${JSON.stringify(alert)})">One-time purchase</button>
      <button class="alert-btn" onclick="resolveAlert('emi', ${JSON.stringify(alert)})">EMI / Loan</button>
      <button class="alert-btn" onclick="resolveAlert('daily', ${JSON.stringify(alert)})">Daily expense</button>
      <button class="alert-btn" onclick="resolveAlert('skip', ${JSON.stringify(alert)})">Skip</button>
    </div>`;
}

// ── Actions ───────────────────────────────────────────────────────
async function addExpense() {
  const amount   = parseFloat(document.getElementById('qa-amount').value);
  const merchant = document.getElementById('qa-merchant').value.trim();
  const category = document.getElementById('qa-cat').value;
  const onetime  = document.getElementById('qa-onetime').checked;
  if (!amount || !merchant) { toast('Enter amount and merchant'); return; }

  await fetch(`${API}/api/transactions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, merchant, category, is_one_time: onetime }),
  });

  document.getElementById('qa-amount').value   = '';
  document.getElementById('qa-merchant').value = '';
  document.getElementById('qa-onetime').checked = false;
  toast(`✓ ₹${fmt(amount)} added${onetime ? ' (one-time)' : ''}`);
  loadDashboard();
}

async function syncSMS() {
  const btn = document.getElementById('sync-btn');
  btn.textContent = 'Syncing...';
  try {
    const res  = await fetch(`${API}/api/process-sms`, { method: 'POST' });
    const data = await res.json();
    let msg = `✓ Processed: ${data.processed}`;
    if (data.balance_updates?.length) msg += ` · Balances updated: ${data.balance_updates.length}`;
    toast(msg);
    loadDashboard();
  } catch(e) {
    toast('Sync failed');
  }
  btn.textContent = '↻ Sync';
}

async function resolveAlert(action, alertData) {
  await fetch(`${API}/api/sms/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sms_index: alertData.sms_index,
      action,
      amount:   alertData.amount,
      merchant: alertData.merchant,
      category: alertData.category,
    }),
  });
  document.getElementById('alert-banner').style.display = 'none';
  toast(`✓ Logged as ${action}`);
  loadDashboard();
}

async function setMonthly() {
  const val = parseFloat(document.getElementById('monthly-input').value);
  if (!val) { toast('Enter a monthly budget'); return; }
  await fetch(`${API}/api/budgets/monthly`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount: val }),
  });
  toast(`✓ ₹${fmt(val)}/month set`);
  updateSetterInfo(val);
  loadDashboard();
}

function updateSetterInfo(monthly) {
  if (!monthly) return;
  const days  = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate();
  const daily = (monthly / days).toFixed(2);
  const el    = document.getElementById('setter-info');
  if (el) el.textContent = `₹${fmt(monthly)} ÷ ${days} days = ₹${daily}/day · Over/underspend splits across remaining days`;
}

async function saveAllBudgets() {
  const rows   = document.querySelectorAll('.cat-edit-row');
  const budgets = [];
  rows.forEach(row => {
    const name   = row.querySelector('.cat-name-input')?.value.trim();
    const budget = parseFloat(row.querySelector('.cat-budget-input')?.value) || 0;
    if (name) budgets.push({ category: name, monthly_budget: budget, spent_this_month: 0 });
  });
  await fetch(`${API}/api/budgets/save-all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(budgets),
  });
  toast('✓ Budgets saved!');
  loadDashboard();
}

function addCatRow() {
  const el  = document.getElementById('cat-editor');
  const div = document.createElement('div');
  div.className = 'cat-edit-row';
  div.innerHTML = `
    <div class="cat-emoji-btn" onclick="rotateEmoji(this)">✨</div>
    <input class="cat-name-input" placeholder="Category name" oninput="recalcTotal()"/>
    <input class="cat-budget-input" type="number" placeholder="₹" oninput="recalcTotal()"/>
    <button class="cat-del" onclick="this.closest('.cat-edit-row').remove();recalcTotal()">×</button>`;
  el.appendChild(div);
}

function recalcTotal() {
  const inputs = document.querySelectorAll('.cat-budget-input');
  let total = 0;
  inputs.forEach(i => total += parseFloat(i.value) || 0);
  const monthly = parseFloat(document.getElementById('monthly-input')?.value) || dashData.monthly_budget || 0;
  const el = document.getElementById('total-allocated');
  if (el) {
    el.textContent  = `₹${fmt(total)}`;
    el.className    = 'total-val' + (total > monthly && monthly > 0 ? ' over' : '');
  }
}

function rotateEmoji(el) { el.textContent = EMOJIS[Math.floor(Math.random() * EMOJIS.length)]; }

function toggleLoanForm() {
  const f = document.getElementById('loan-form');
  f.style.display = f.style.display === 'none' ? 'flex' : 'none';
}

async function saveLoan() {
  const loan = {
    lender:              document.getElementById('lf-lender').value,
    principal:           parseFloat(document.getElementById('lf-principal').value) || 0,
    outstanding:         parseFloat(document.getElementById('lf-outstanding').value) || 0,
    emi:                 parseFloat(document.getElementById('lf-emi').value) || 0,
    next_deduction_date: document.getElementById('lf-date').value,
    foreclosure_amount:  parseFloat(document.getElementById('lf-foreclosure').value) || 0,
  };
  if (!loan.lender || !loan.emi) { toast('Enter lender and EMI'); return; }
  await fetch(`${API}/api/loans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(loan),
  });
  toggleLoanForm();
  toast('✓ Loan saved');
  loadDashboard();
}

async function updateBalance() {
  const bank    = document.getElementById('bank-name').value.trim();
  const balance = parseFloat(document.getElementById('bank-balance').value);
  if (!bank || !balance) { toast('Enter bank and balance'); return; }
  await fetch(`${API}/api/accounts/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bank, balance }),
  });
  document.getElementById('bank-name').value    = '';
  document.getElementById('bank-balance').value = '';
  toast(`✓ ${bank} updated to ₹${fmt(balance)}`);
  loadDashboard();
}

async function runOCR(file) {
  if (!file) return;
  const fd  = new FormData();
  fd.append('file', file);
  const res  = await fetch(`${API}/api/ocr`, { method: 'POST', body: fd });
  const data = await res.json();
  const el   = document.getElementById('ocr-result');
  el.style.display = 'block';
  el.textContent   = data.error
    ? `Error: ${data.error}`
    : `Amounts found: ₹${data.detected_amounts.join(', ₹') || 'none'}\n\n${data.raw_text}`;
}

function handleDrop(e) {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file) runOCR(file);
}

// ── AI Chat ───────────────────────────────────────────────────────
async function sendChat() {
  const input = document.getElementById('chat-input');
  const text  = input.value.trim();
  if (!text) return;
  input.value = '';

  addChatMsg(text, 'user');
  chatHistory.push({ role: 'user', content: text });
  showTyping();

  try {
    const res  = await fetch(`${API}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory }),
    });
    const data = await res.json();
    removeTyping();

    addChatMsg(data.reply, 'ai');
    chatHistory.push({ role: 'assistant', content: data.reply });

    if (data.action_result?.success) {
      addActionConfirm(data.action_result.message);
      loadDashboard(); // refresh data after action
    }
  } catch(e) {
    removeTyping();
    addChatMsg('Sorry, could not connect to Groq AI.', 'ai');
  }
}

function sendQuick(text) {
  document.getElementById('chat-input').value = text;
  switchTab('chat');
  setTimeout(sendChat, 100);
}

function addChatMsg(text, role) {
  const box = document.getElementById('chat-messages');
  if (role === 'user') {
    box.innerHTML += `<div class="msg-user"><div class="user-bubble"><p>${text}</p></div></div>`;
  } else {
    box.innerHTML += `<div class="msg-ai"><div class="ai-av">G</div><div class="ai-bubble"><p>${text}</p></div></div>`;
  }
  box.scrollTop = box.scrollHeight;
}

function addActionConfirm(msg) {
  const box = document.getElementById('chat-messages');
  box.innerHTML += `<div class="msg-ai"><div class="ai-av">G</div><div class="ai-bubble"><div class="action-bubble">✓ ${msg}</div></div></div>`;
  box.scrollTop = box.scrollHeight;
}

function showTyping() {
  const box = document.getElementById('chat-messages');
  box.innerHTML += `<div class="msg-ai" id="typing-indicator"><div class="ai-av">G</div><div class="ai-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div></div>`;
  box.scrollTop = box.scrollHeight;
}

function removeTyping() {
  document.getElementById('typing-indicator')?.remove();
}

// ── Navigation ────────────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.getElementById(`nav-${tab}`).classList.add('active');
}

// ── Helpers ───────────────────────────────────────────────────────
function fmt(n) {
  return parseFloat(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function populateCatSelect(budgets) {
  const sel  = document.getElementById('qa-cat');
  const cats = budgets?.map(b => b.category) || ['Food', 'Groceries', 'Transport', 'Bills', 'Entertainment', 'Health', 'Other'];
  const current = sel.value;
  sel.innerHTML = cats.map(c => `<option ${c === current ? 'selected' : ''}>${c}</option>`).join('');
}
