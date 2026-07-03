/* ============================================================
   Banking API — API Service Layer
   ============================================================ */

const API = (() => {
  // Auto-détection : localhost en dev, Render en prod
  const BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:10000'
    : 'https://banking-api-mgyy.onrender.com';

  async function request(path, options = {}) {
    const url = `${BASE}${path}`;
    const config = {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    };
    if (config.body && typeof config.body === 'object') {
      config.body = JSON.stringify(config.body);
    }
    const res = await fetch(url, config);
    const data = res.headers.get('content-type')?.includes('application/json')
      ? await res.json()
      : await res.text();
    if (!res.ok) {
      const detail = data?.detail || data || `Erreur ${res.status}`;
      throw new Error(detail);
    }
    return data;
  }

  return {
    // Comptes
    getAccounts:       ()      => request('/comptes'),
    getAccount:        (num)   => request(`/comptes/${num}`),
    createAccount:     (data)  => request('/comptes', { method: 'POST', body: data }),
    deleteAccount:     (num)   => request(`/comptes/${num}`, { method: 'DELETE' }),

    // Opérations
    deposit:  (num, montant) => request(`/comptes/${num}/depot`,    { method: 'POST', body: { montant } }),
    withdraw: (num, montant) => request(`/comptes/${num}/retrait`,  { method: 'POST', body: { montant } }),
    transfer: (num, dest, montant) => request(`/comptes/${num}/virement`, { method: 'POST', body: { numero_compte_destination: dest, montant } }),

    // Transactions
    getTransactions: (num) => request(`/comptes/${num}/transactions`),
  };
})();
