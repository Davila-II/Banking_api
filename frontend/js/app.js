/* BK Bank — Application */
const App = (() => {
  // ── State ──────────────────────────────────────────────
  let accounts = [];
  let selectedAccount = null;
  let transactions = [];
  let currentView = 'dashboard';
  let pendingDeleteNumero = null;
  let currentOp = null; // 'depot' | 'retrait'

  // ── Init ───────────────────────────────────────────────
  async function init() {
    await refresh();
    // Navigation clicks
    document.querySelectorAll('.nav-item').forEach(a => {
      a.addEventListener('click', e => {
        e.preventDefault();
        const v = a.dataset.view;
        if (v) navigate(v);
      });
    });
    // Escape key for modals
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeAllModals();
    });
    // Overlay click to close
    document.addEventListener('click', e => {
      if (e.target.classList.contains('modal-overlay')) closeAllModals();
    });
  }

  async function refresh() {
    try {
      accounts = await API.getAccounts();
      renderCurrentView();
    } catch (e) {
      toast(e.message, 'error');
    }
  }

  // ── Navigation ─────────────────────────────────────────
  function navigate(view, data = null) {
    currentView = view;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const el = document.getElementById('view-' + view);
    if (el) el.classList.add('active');

    // Update nav
    document.querySelectorAll('.nav-item').forEach(a => a.classList.remove('active'));
    const navItem = document.querySelector(`.nav-item[data-view="${view}"]`);
    if (navItem) navItem.classList.add('active');

    // Close mobile sidebar
    document.getElementById('sidebar').classList.remove('open');

    if (data) selectedAccount = data;
    if (view === 'account-detail' && selectedAccount) {
      loadAndRenderAccountDetail();
    } else if (view === 'transfers') {
      renderTransferPage();
    } else {
      selectedAccount = null;
    }
    renderCurrentView();
  }

  function renderCurrentView() {
    switch (currentView) {
      case 'dashboard': renderDashboard(); break;
      case 'accounts': renderAccountsList(); break;
      case 'transfers': renderTransferPage(); break;
    }
  }

  // ── Sidebar toggle (mobile) ────────────────────────────
  function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
  }

  // ── Dashboard ──────────────────────────────────────────
  function renderDashboard() {
    renderDashboardCards();
    renderRecentTransactions();
  }

  function renderDashboardCards() {
    const container = document.getElementById('dashboard-cards');
    if (!accounts.length) {
      container.innerHTML = `
        <div class="empty-dash">
          <div class="empty-icon"><svg width="56" height="56" viewBox="0 0 56 56" fill="none"><circle cx="28" cy="28" r="26" stroke="#2a2a35" stroke-width="2"/><path d="M28 20v16M20 28h16" stroke="#2a2a35" stroke-width="2" stroke-linecap="round"/></svg></div>
          <h3>Bienvenue chez BK Bank</h3>
          <p>Ouvrez votre premier compte pour commencer à gérer vos finances.</p>
          <button class="btn btn-gold" onclick="App.openModal('create-account')">Ouvrir un compte</button>
        </div>`;
      document.getElementById('recent-txns-section').style.display = 'none';
      return;
    }
    container.innerHTML = accounts.map(c => bankCardHTML(c)).join('');
  }

  function bankCardHTML(c) {
    const nc = c.numero_compte;
    const formatted = nc.substr(3,4) + ' ' + nc.substr(7);
    const soldeClass = c.solde < 0 ? ' negative' : '';
    const safe = esc(JSON.stringify(c));
    return `
      <div class="bank-card" onclick="App.navigate('account-detail', App.findAccount('${c.numero_compte}'))">
        <div class="card-top">
          <div class="card-chip"></div>
          <div class="card-type">BK Bank</div>
        </div>
        <div class="card-number">${formatted}</div>
        <div class="card-bottom">
          <div>
            <div class="card-holder-label">Titulaire</div>
            <div class="card-holder">${esc(c.nom_titulaire)}</div>
          </div>
          <div>
            <div class="card-balance-label">Solde</div>
            <div class="card-balance${soldeClass}">${fmtEur(c.solde)}</div>
          </div>
        </div>
        <div class="card-quick-actions" onclick="event.stopPropagation()">
          <button class="btn btn-success btn-sm" onclick="App.openOpModal('depot', App.findAccount('${c.numero_compte}'))">+ Dépôt</button>
          <button class="btn btn-danger btn-sm" onclick="App.openOpModal('retrait', App.findAccount('${c.numero_compte}'))">− Retrait</button>
          <button class="btn btn-outline btn-sm" onclick="App.navigate('transfers')">⇄ Virer</button>
        </div>
      </div>`;
  }

  function findAccount(numero) {
    return accounts.find(c => c.numero_compte === numero) || null;
  }

  function renderRecentTransactions() {
    const section = document.getElementById('recent-txns-section');
    const feed = document.getElementById('recent-txns');
    if (!accounts.length) { section.style.display = 'none'; return; }

    // Collect all transactions across all accounts
    const allTxns = [];
    accounts.forEach(acc => {
      if (acc._txns) allTxns.push(...acc._txns.map(t => ({ ...t, _account: acc.numero_compte })));
    });

    if (!allTxns.length) {
      section.style.display = 'none';
      return;
    }

    allTxns.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    const recent = allTxns.slice(0, 10);

    section.style.display = 'block';
    feed.innerHTML = recent.map(t => {
      const { icon, label, meta, amount, cssClass } = txnDisplay(t);
      return `
        <div class="txn-item">
          <div class="txn-icon ${icon}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">${txnIconPath(icon)}</svg>
          </div>
          <div class="txn-info">
            <div class="txn-label">${label}</div>
            <div class="txn-meta">${meta} · ${fmtDate(t.date)}</div>
          </div>
          <div class="txn-amount ${cssClass}">${amount}</div>
        </div>`;
    }).join('');
  }

  // ── Accounts List ──────────────────────────────────────
  function renderAccountsList() {
    const container = document.getElementById('accounts-list');
    const counter = document.getElementById('accounts-count');
    counter.textContent = `${accounts.length} compte${accounts.length !== 1 ? 's' : ''}`;

    if (!accounts.length) {
      container.innerHTML = `
        <div class="empty-dash">
          <div class="empty-icon"><svg width="56" height="56" viewBox="0 0 56 56" fill="none"><circle cx="28" cy="28" r="26" stroke="#2a2a35" stroke-width="2"/><path d="M28 20v16M20 28h16" stroke="#2a2a35" stroke-width="2" stroke-linecap="round"/></svg></div>
          <h3>Aucun compte</h3>
          <p>Ouvrez votre premier compte bancaire.</p>
          <button class="btn btn-gold" onclick="App.openModal('create-account')">Ouvrir un compte</button>
        </div>`;
      return;
    }

    container.innerHTML = accounts.map(c => {
      const soldeClass = c.solde < 0 ? ' negative' : '';
      const safe = esc(JSON.stringify(c));
      return `
        <div class="account-row" onclick="App.navigate('account-detail', App.findAccount('${c.numero_compte}'))">
          <div class="acct-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
          </div>
          <div class="acct-info">
            <div class="acct-name">${esc(c.nom_titulaire)}</div>
            <div class="acct-number">${esc(c.numero_compte)}</div>
          </div>
          <div class="acct-balance${soldeClass}">${fmtEur(c.solde)}</div>
          <div class="acct-actions" onclick="event.stopPropagation()">
            <button class="btn btn-success btn-sm" onclick="App.openOpModal('depot', App.findAccount('${c.numero_compte}'))">+</button>
            <button class="btn btn-danger btn-sm" onclick="App.openOpModal('retrait', App.findAccount('${c.numero_compte}'))">−</button>
            <button class="btn btn-outline btn-sm" onclick="App.navigate('transfers')">⇄</button>
          </div>
        </div>`;
    }).join('');
  }

  // ── Account Detail ─────────────────────────────────────
  async function loadAndRenderAccountDetail() {
    const content = document.getElementById('account-detail-content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div>Chargement...</div>';

    try {
      const [compte, txns] = await Promise.all([
        API.getAccount(selectedAccount.numero_compte),
        API.getTransactions(selectedAccount.numero_compte)
      ]);
      selectedAccount = compte;
      transactions = txns;
      // Cache transactions on account for dashboard
      const idx = accounts.findIndex(a => a.numero_compte === compte.numero_compte);
      if (idx >= 0) accounts[idx]._txns = txns;
      renderAccountDetail();
    } catch (e) {
      content.innerHTML = `<div class="empty-dash"><p>Erreur : ${esc(e.message)}</p></div>`;
      toast(e.message, 'error');
    }
  }

  function renderAccountDetail() {
    const c = selectedAccount;
    const soldeClass = c.solde < 0 ? ' negative' : '';

    const txnRows = transactions.length ? transactions.map(t => {
      const { icon, label, meta, amount, cssClass } = txnDisplay(t);
      return `
        <div class="txn-item">
          <div class="txn-icon ${icon}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">${txnIconPath(icon)}</svg>
          </div>
          <div class="txn-info">
            <div class="txn-label">${label}</div>
            <div class="txn-meta">${meta} · ${fmtDate(t.date)}</div>
          </div>
          <div class="txn-amount ${cssClass}">${amount}</div>
        </div>`;
    }).join('') : '<div class="no-txns">Aucune transaction pour ce compte</div>';

    document.getElementById('account-detail-content').innerHTML = `
      <div class="detail-card">
        <div class="detail-hero">
          <div class="detail-number">${esc(c.numero_compte)}</div>
          <div class="detail-holder">${esc(c.nom_titulaire)}</div>
          <div class="detail-balance-row">
            <div class="detail-balance${soldeClass}">${fmtEur(c.solde)}</div>
            <div class="detail-balance-label">solde actuel</div>
          </div>
        </div>
        <div class="detail-actions">
          <button class="btn btn-success" onclick="App.openOpModal('depot', App.findAccount('${c.numero_compte}'))">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 2v12M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> Dépôt
          </button>
          <button class="btn btn-danger" onclick="App.openOpModal('retrait', App.findAccount('${c.numero_compte}'))">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> Retrait
          </button>
          <button class="btn btn-outline" onclick="App.navigate('transfers')">
            <svg width="14" height="14" viewBox="0 0 16 16"><polyline points="12 3 15 6 12 9"/><path d="M2 10V9a4 4 0 014-4h9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg> Virement
          </button>
          <button class="btn btn-ghost" style="color:var(--danger)" onclick="App.openModal('delete', App.findAccount('${c.numero_compte}'))">
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M13 4l-.8 9.2a1 1 0 01-1 .8H4.8a1 1 0 01-1-.8L3 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Fermer
          </button>
        </div>
        <div class="detail-body">
          <h3>Historique des transactions</h3>
          <div class="txn-feed">${txnRows}</div>
        </div>
      </div>`;
  }

  // ── Transfer Page ───────────────────────────────────────
  function renderTransferPage() {
    const source = document.getElementById('tf-source');
    const dest = document.getElementById('tf-dest');

    const options = accounts.map(c =>
      `<option value="${c.numero_compte}">${esc(c.numero_compte)} — ${esc(c.nom_titulaire)} (${fmtEur(c.solde)})</option>`
    ).join('');

    const currentSource = source.value;
    const currentDest = dest.value;

    source.innerHTML = options;
    dest.innerHTML = '<option value="">Sélectionner...</option>' + options;

    if (currentSource && accounts.some(c => c.numero_compte === currentSource)) source.value = currentSource;
    if (currentDest && accounts.some(c => c.numero_compte === currentDest)) dest.value = currentDest;
  }

  async function handleTransferPage(e) {
    e.preventDefault();
    const source = document.getElementById('tf-source').value;
    let dest = document.getElementById('tf-dest').value;
    const montant = parseFloat(document.getElementById('tf-montant').value);

    if (!dest) { toast('Sélectionnez un compte destinataire', 'error'); return; }
    if (source === dest) { toast('Impossible de virer vers le même compte', 'error'); return; }

    try {
      await API.transfer(source, dest, montant);
      toast(`Virement de ${fmtEur(montant)} effectué`, 'success');
      document.getElementById('tf-montant').value = '';
      await refresh();
      renderTransferPage();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  // ── Transaction display helper ─────────────────────────
  function txnDisplay(t) {
    const isSource = t.compte_source === (selectedAccount?.numero_compte || t._account);
    if (t.type === 'depot') {
      return {
        icon: 'depot', label: 'Dépôt', meta: esc(t.compte_source),
        amount: '+ ' + fmtEur(t.montant), cssClass: 'positive'
      };
    } else if (t.type === 'retrait') {
      return {
        icon: 'retrait', label: 'Retrait', meta: esc(t.compte_source),
        amount: '− ' + fmtEur(t.montant), cssClass: 'negative'
      };
    } else {
      if (isSource) {
        return {
          icon: 'virement-out', label: 'Virement envoyé', meta: 'vers ' + esc(t.compte_destination || '—'),
          amount: '− ' + fmtEur(t.montant), cssClass: 'negative'
        };
      } else {
        return {
          icon: 'virement-in', label: 'Virement reçu', meta: 'de ' + esc(t.compte_source || '—'),
          amount: '+ ' + fmtEur(t.montant), cssClass: 'positive'
        };
      }
    }
  }

  function txnIconPath(icon) {
    switch (icon) {
      case 'depot': return '<path d="M12 5v14M5 12h14"/>';
      case 'retrait': return '<path d="M5 12h14"/>';
      case 'virement-in': return '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>';
      default: return '<polyline points="1 6 10.5 15.5 15.5 10.5 23 18"/><polyline points="17 18 23 18 23 12"/>';
    }
  }

  // ── Modals ─────────────────────────────────────────────
  function openModal(name, data = null) {
    closeAllModals(); // close any existing first
    const el = document.getElementById('modal-' + name);
    if (!el) return;
    el.classList.add('active');

    if (name === 'delete' && data) {
      pendingDeleteNumero = data.numero_compte;
      document.getElementById('delete-compte-label').textContent = data.numero_compte;
    }
  }

  function openOpModal(type, compte) {
    currentOp = type;
    const el = document.getElementById('modal-operation');
    const title = document.getElementById('modal-op-title');
    const btn = document.getElementById('modal-op-btn');
    const lbl = document.getElementById('modal-op-compte');
    const solde = document.getElementById('modal-op-solde');

    title.textContent = type === 'depot' ? 'Dépôt' : 'Retrait';
    btn.className = 'btn ' + (type === 'depot' ? 'btn-success' : 'btn-danger');
    btn.textContent = type === 'depot' ? 'Déposer' : 'Retirer';
    lbl.textContent = compte.numero_compte;
    solde.textContent = 'Solde actuel : ' + fmtEur(compte.solde);
    document.getElementById('op-montant').value = '';

    el.classList.add('active');
  }

  function closeModal(name) {
    const el = document.getElementById('modal-' + name);
    if (el) el.classList.remove('active');
    if (name === 'delete') pendingDeleteNumero = null;
    if (name === 'operation') currentOp = null;
  }

  function closeAllModals() {
    document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    pendingDeleteNumero = null;
    currentOp = null;
  }

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
      toast(`Compte ${compte.numero_compte} ouvert avec succès`, 'success');
      await refresh();
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function handleOperation(e) {
    e.preventDefault();
    const montant = parseFloat(document.getElementById('op-montant').value);
    const numero = document.getElementById('modal-op-compte').textContent;

    try {
      if (currentOp === 'depot') {
        await API.deposit(numero, montant);
        toast(`Dépôt de ${fmtEur(montant)} effectué`, 'success');
      } else {
        await API.withdraw(numero, montant);
        toast(`Retrait de ${fmtEur(montant)} effectué`, 'success');
      }
      closeModal('operation');
      await refresh();
      if (currentView === 'account-detail' && selectedAccount) {
        await loadAndRenderAccountDetail();
      }
    } catch (err) {
      toast(err.message, 'error');
    }
  }

  async function handleDelete() {
    if (!pendingDeleteNumero) return;
    try {
      await API.deleteAccount(pendingDeleteNumero);
      closeModal('delete');
      toast(`Compte ${pendingDeleteNumero} fermé`, 'info');
      navigate('dashboard');
      await refresh();
    } catch (err) {
      toast(err.message, 'error');
    }
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
    }, 3800);
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
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }) +
      ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  // ── Public ─────────────────────────────────────────────
  return {
    init, refresh, navigate, toggleSidebar,
    openModal, openOpModal, closeModal,
    handleCreateAccount, handleOperation, handleTransferPage, handleDelete,
    findAccount, toast
  };
})();

document.addEventListener('DOMContentLoaded', () => App.init());
