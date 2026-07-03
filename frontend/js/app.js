/* ============================================================
   Banking API — Application UI
   ============================================================ */

const App = (() => {
  // ── State ──────────────────────────────────────────────
  let accounts = [];
  let selectedAccount = null;
  let transactions = [];
  let currentView = 'dashboard';
  let pendingDeleteNumero = null;

  // ── Init ───────────────────────────────────────────────
  async function init() {
    await refresh();
  }

  async function refresh() {
    try {
      accounts = await API.getAccounts();
      renderDashboard();
      updateAccountCount();
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  // ── Navigation ─────────────────────────────────────────
  function navigate(view, data = null) {
    currentView = view;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const el = document.getElementById(`view-${view}`);
    if (el) el.classList.add('active');

    if (view === 'dashboard') {
      selectedAccount = null;
      renderDashboard();
    } else if (view === 'account') {
      selectedAccount = data;
      loadAndRenderAccount();
    }
  }

  // ── Dashboard ──────────────────────────────────────────
  function renderDashboard() {
    const grid = document.getElementById('accounts-grid');
    if (!accounts.length) {
      grid.innerHTML = `
        <div class="empty-state">
          <svg width="48" height="48" viewBox="0 0 48 48"><rect x="8" y="12" width="32" height="26" rx="4" stroke="#30363d" stroke-width="2" fill="none"/><path d="M16 28h16" stroke="#30363d" stroke-width="2" stroke-linecap="round"/><path d="M16 34h10" stroke="#30363d" stroke-width="2" stroke-linecap="round"/></svg>
          <p>Aucun compte pour le moment</p>
          <button class="btn btn-primary" onclick="App.openModal('create-account')">Créer un premier compte</button>
        </div>`;
      return;
    }

    grid.innerHTML = accounts.map(c => {
      const soldeClass = c.solde < 0 ? 'negative' : '';
      return `
        <div class="account-card" onclick="App.navigate('account', ${JSON.stringify(c).replace(/"/g, '&quot;')})">
          <div class="card-number">${esc(c.numero_compte)}</div>
          <div class="card-holder">${esc(c.nom_titulaire)}</div>
          <div class="card-email">${esc(c.email)}</div>
          <div class="card-balance ${soldeClass}">${fmtEur(c.solde)}</div>
          <div class="card-date">Créé le ${fmtDate(c.date_creation)}</div>
          <div class="card-actions" onclick="event.stopPropagation()">
            <button class="btn btn-success btn-sm" onclick="App.openModal('deposit', ${JSON.stringify(c).replace(/"/g, '&quot;')})">+ Dépôt</button>
            <button class="btn btn-danger btn-sm" onclick="App.openModal('withdraw', ${JSON.stringify(c).replace(/"/g, '&quot;')})">− Retrait</button>
            <button class="btn btn-primary btn-sm" onclick="App.openModal('transfer', ${JSON.stringify(c).replace(/"/g, '&quot;')})">⇄ Virer</button>
          </div>
        </div>`;
    }).join('');
  }

  function updateAccountCount() {
    const el = document.getElementById('account-count');
    if (el) el.textContent = `${accounts.length} compte${accounts.length !== 1 ? 's' : ''}`;
  }

  // ── Account Detail ─────────────────────────────────────
  async function loadAndRenderAccount() {
    const content = document.getElementById('account-detail-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div>Chargement…</div>';

    try {
      const [compte, txns] = await Promise.all([
        API.getAccount(selectedAccount.numero_compte),
        API.getTransactions(selectedAccount.numero_compte)
      ]);
      selectedAccount = compte;
      transactions = txns;
      renderAccountDetail();
    } catch (e) {
      content.innerHTML = `<div class="empty-state"><p>Erreur : ${esc(e.message)}</p></div>`;
      toast(e.message, 'error');
    }
  }

  function renderAccountDetail() {
    const c = selectedAccount;
    const soldeClass = c.solde < 0 ? 'negative' : '';

    const html = `
      <div class="account-detail">
        <div class="detail-header">
          <div class="detail-number">${esc(c.numero_compte)}</div>
          <div class="detail-holder">${esc(c.nom_titulaire)}</div>
          <div class="detail-email">${esc(c.email)}</div>
          <div class="detail-balance ${soldeClass}">${fmtEur(c.solde)}</div>
          <div class="detail-balance-label">Solde actuel</div>
        </div>

        <div class="detail-actions">
          <button class="btn btn-success" onclick="App.openModal('deposit', ${JSON.stringify(c).replace(/"/g, '&quot;')})">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 2v12M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            Dépôt
          </button>
          <button class="btn btn-danger" onclick="App.openModal('withdraw', ${JSON.stringify(c).replace(/"/g, '&quot;')})">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
            Retrait
          </button>
          <button class="btn btn-primary" onclick="App.openModal('transfer', ${JSON.stringify(c).replace(/"/g, '&quot;')})">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M4 5l4-4 4 4M4 11l4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Virement
          </button>
          <button class="btn btn-ghost" style="color:var(--danger);border-color:var(--danger)" onclick="App.openModal('delete', ${JSON.stringify(c).replace(/"/g, '&quot;')})">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M13 4l-.8 9.2a1 1 0 01-1 .8H4.8a1 1 0 01-1-.8L3 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            Supprimer
          </button>
        </div>

        <div class="detail-body">
          <h3>Historique des transactions</h3>
          ${renderTransactions()}
        </div>
      </div>`;

    document.getElementById('account-detail-content').innerHTML = html;
  }

  function renderTransactions() {
    if (!transactions.length) {
      return '<div class="no-transactions">Aucune transaction pour ce compte</div>';
    }

    const rows = transactions.map(t => {
      let typeLabel, typeClass, amountClass, amountPrefix;
      if (t.type === 'depot') {
        typeLabel = 'Dépôt'; typeClass = 'depot'; amountClass = 'positive'; amountPrefix = '+';
      } else if (t.type === 'retrait') {
        typeLabel = 'Retrait'; typeClass = 'retrait'; amountClass = 'negative'; amountPrefix = '−';
      } else {
        typeLabel = 'Virement'; typeClass = 'virement';
        if (t.compte_source === selectedAccount.numero_compte) {
          amountClass = 'negative'; amountPrefix = '−';
        } else {
          amountClass = 'positive'; amountPrefix = '+';
        }
      }

      const dest = t.compte_destination
        ? (t.compte_destination === selectedAccount.numero_compte ? t.compte_source : t.compte_destination)
        : '—';

      return `
        <tr>
          <td><span class="txn-type ${typeClass}">${typeLabel}</span></td>
          <td class="txn-amount ${amountClass}">${amountPrefix} ${fmtEur(t.montant)}</td>
          <td>${esc(dest)}</td>
          <td>${fmtDate(t.date)}</td>
        </tr>`;
    }).join('');

    return `
      <table class="txn-table">
        <thead><tr><th>Type</th><th>Montant</th><th>Contrepartie</th><th>Date</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  // ── Modals ─────────────────────────────────────────────
  function openModal(name, data = null) {
    const el = document.getElementById(`modal-${name}`);
    if (!el) return;
    el.classList.add('active');

    // Pre-fill context
    if (name === 'deposit' && data) {
      document.getElementById('deposit-compte-label').textContent = data.numero_compte;
      document.getElementById('deposit-montant').value = '';
    }
    if (name === 'withdraw' && data) {
      document.getElementById('withdraw-compte-label').textContent = data.numero_compte;
      document.getElementById('withdraw-montant').value = '';
    }
    if (name === 'transfer' && data) {
      document.getElementById('transfer-source-label').textContent = data.numero_compte;
      document.getElementById('transfer-dest').value = '';
      document.getElementById('transfer-montant').value = '';
    }
    if (name === 'delete' && data) {
      pendingDeleteNumero = data.numero_compte;
      document.getElementById('delete-compte-label').textContent = data.numero_compte;
    }
  }

  function closeModal(name) {
    const el = document.getElementById(`modal-${name}`);
    if (!el) return;
    el.classList.remove('active');
    if (name === 'delete') pendingDeleteNumero = null;
  }

  // Close modal on overlay click
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
      e.target.classList.remove('active');
      if (e.target.id === 'modal-delete') pendingDeleteNumero = null;
    }
  });

  // Close modal on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => {
        m.classList.remove('active');
        if (m.id === 'modal-delete') pendingDeleteNumero = null;
      });
    }
  });

  // ── Handlers ───────────────────────────────────────────
  async function handleCreateAccount(e) {
    e.preventDefault();
    const nom = document.getElementById('create-nom').value.trim();
    const email = document.getElementById('create-email').value.trim();
    try {
      const compte = await API.createAccount({ nom_titulaire: nom, email });
      closeModal('create-account');
      document.getElementById('create-nom').value = '';
      document.getElementById('create-email').value = '';
      toast(`Compte ${compte.numero_compte} créé`, 'success');
      await refresh();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function handleDeposit(e) {
    e.preventDefault();
    const montant = parseFloat(document.getElementById('deposit-montant').value);
    const numero = document.getElementById('deposit-compte-label').textContent;
    try {
      await API.deposit(numero, montant);
      closeModal('deposit');
      toast(`Dépôt de ${fmtEur(montant)} effectué`, 'success');
      await refreshCurrentView();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function handleWithdraw(e) {
    e.preventDefault();
    const montant = parseFloat(document.getElementById('withdraw-montant').value);
    const numero = document.getElementById('withdraw-compte-label').textContent;
    try {
      await API.withdraw(numero, montant);
      closeModal('withdraw');
      toast(`Retrait de ${fmtEur(montant)} effectué`, 'success');
      await refreshCurrentView();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function handleTransfer(e) {
    e.preventDefault();
    const dest = document.getElementById('transfer-dest').value.trim();
    const montant = parseFloat(document.getElementById('transfer-montant').value);
    const source = document.getElementById('transfer-source-label').textContent;
    try {
      await API.transfer(source, dest, montant);
      closeModal('transfer');
      toast(`Virement de ${fmtEur(montant)} vers ${dest}`, 'success');
      await refreshCurrentView();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function handleDelete() {
    if (!pendingDeleteNumero) return;
    try {
      await API.deleteAccount(pendingDeleteNumero);
      closeModal('delete');
      toast(`Compte ${pendingDeleteNumero} supprimé`, 'info');
      navigate('dashboard');
      await refresh();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function refreshCurrentView() {
    if (currentView === 'account' && selectedAccount) {
      await loadAndRenderAccount();
    }
    await refresh();
  }

  // ── Toast ──────────────────────────────────────────────
  function toast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(20px)';
      el.style.transition = 'all 0.2s';
      setTimeout(() => el.remove(), 200);
    }, 3500);
  }

  // ── Helpers ────────────────────────────────────────────
  function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  function fmtEur(value) {
    const v = typeof value === 'number' ? value : parseFloat(value);
    if (isNaN(v)) return '0,00 €';
    return v.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }) +
      ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  // ── Public API ─────────────────────────────────────────
  return {
    init, refresh, navigate, refreshCurrentView,
    openModal, closeModal,
    handleCreateAccount, handleDeposit, handleWithdraw, handleTransfer, handleDelete,
    toast
  };
})();

// ── Boot ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => App.init());
