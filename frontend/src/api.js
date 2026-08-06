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
