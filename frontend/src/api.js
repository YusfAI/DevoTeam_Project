export async function getHealth() {
  // Volontairement sans gestion d'erreur bruyante : si le backend lui-même ne répond
  // pas, l'appelant traite ça comme « indisponible » plutôt que de faire remonter une
  // exception dans l'interface.
  const response = await fetch('/health')
  if (!response.ok) throw new Error('Health check indisponible')
  return response.json()
}

export async function postSheetsSync() {
  const response = await fetch('/sheets/sync', { method: 'POST' })

  let data = {}
  try {
    data = await response.json()
  } catch {
    // réponse non-JSON (ex: serveur injoignable) -> on retombe sur le message générique ci-dessous
  }

  if (!response.ok) {
    throw new Error(data.detail || data.error || 'Erreur de connexion au serveur.')
  }
  return data
}

export async function postDashboardQuery(query, previousIntent) {
  const response = await fetch('/dashboard', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, previous_intent: previousIntent || null }),
  })

  let data = {}
  try {
    data = await response.json()
  } catch {
    // réponse non-JSON (ex: serveur injoignable) -> on retombe sur le message générique ci-dessous
  }

  if (!response.ok) {
    throw new Error(data.detail || data.error || 'Erreur de connexion au serveur.')
  }
  return data
}

export async function getHotDeals() {
  // Le tableau des affaires chaudes est rendu par l'application, pas par DAC, faute
  // de défilement vertical dans le tableau de DAC (voir HotDealsTable.jsx).
  const response = await fetch('/hot-deals')
  if (!response.ok) throw new Error('Liste des affaires chaudes indisponible.')

  // Une réponse HTML là où on attend du JSON a une cause précise et récurrente : le
  // serveur de développement a répondu l'index.html du SPA parce que le préfixe
  // manque dans le proxy Vite. Laisser remonter « Unexpected token '<' » n'aide
  // personne à le comprendre. (tests/test_frontend_proxy.py empêche le cas.)
  const brut = await response.text()
  try {
    return JSON.parse(brut)
  } catch {
    throw new Error(
      'Réponse inattendue du serveur pour /hot-deals — vérifiez que le backend tourne ' +
        'et que le préfixe figure bien dans le proxy de vite.config.js.',
    )
  }
}
