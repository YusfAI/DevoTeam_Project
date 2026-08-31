// Délai au-delà duquel une requête est abandonnée. Sans lui, une réponse qui ne
// vient jamais laissait l'interface figée : champ désactivé, trois points animés,
// aucun bouton d'annulation, aucun moyen de taper autre chose. Le seul recours
// était de recharger la page — ce qui perd aussi le contexte de la conversation.
//
// 90 s, parce que l'attente longue est ici un cas NORMAL et non un cas limite : le
// quota du modèle est de ~16 requêtes/minute et le premier widget de tableau de bord
// coûte une dizaine de secondes à froid. Couper trop tôt transformerait une lenteur
// attendue en erreur.
const DELAI_MAX_MS = 90000

async function fetchAvecDelai(url, options = {}) {
  const controleur = new AbortController()
  const minuteur = setTimeout(() => controleur.abort(), DELAI_MAX_MS)
  try {
    return await fetch(url, { ...options, signal: controleur.signal })
  } catch (erreur) {
    if (erreur.name === 'AbortError') {
      throw new Error(
        `Le serveur n'a pas répondu en ${DELAI_MAX_MS / 1000} s. Réessayez : ` +
        'si cela se reproduit, le quota du modèle est peut-être atteint.',
      )
    }
    throw erreur
  } finally {
    clearTimeout(minuteur)
  }
}

export async function getHealth() {
  // Volontairement sans gestion d'erreur bruyante : si le backend lui-même ne répond
  // pas, l'appelant traite ça comme « indisponible » plutôt que de faire remonter une
  // exception dans l'interface.
  const response = await fetchAvecDelai('/health')
  if (!response.ok) throw new Error('Health check indisponible')
  return response.json()
}

export async function postSheetsSync() {
  const response = await fetchAvecDelai('/sheets/sync', { method: 'POST' })

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
  const response = await fetchAvecDelai('/dashboard', {
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
