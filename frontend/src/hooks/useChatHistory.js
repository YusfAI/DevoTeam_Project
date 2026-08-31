import { useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'devoteam-chat-history'
// Borne la taille conservée — une conversation ne doit pas faire grossir indéfiniment
// le localStorage (limite ~5 Mo par origine dans la plupart des navigateurs).
//
// COUPLÉ à MAX_GENERATED_DASHBOARDS dans backend/dac_composer.py : une question
// occupe deux messages (la demande et la réponse), donc 100 messages = 50 analyses
// consultables. Le backend doit conserver au moins autant d'instantanés, sinon les
// entrées les plus anciennes de l'historique ouvrent un tableau de bord effacé.
const MAX_MESSAGES = 100

function loadPersisted() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || !Array.isArray(parsed.messages) || parsed.messages.length === 0) return null
    return parsed
  } catch {
    // JSON corrompu ou localStorage indisponible (navigation privée, quota…) —
    // on repart simplement d'une conversation vierge, jamais une erreur bloquante.
    return null
  }
}

export function useChatHistory(welcomeMessage) {
  const persistedRef = useRef(loadPersisted())
  const persisted = persistedRef.current

  const [messages, setMessages] = useState(persisted?.messages ?? [welcomeMessage])

  // Le tableau de bord affiché et le contexte de la dernière question ne sont PAS
  // restaurés : au rechargement de la page, on repart de la vue d'ensemble. Les
  // conserver rouvrait une analyse en cours sans que rien ne l'ait demandé, et
  // laissait une suite comme « en camembert » ajuster un tableau de bord que
  // l'utilisateur ne regardait plus. La conversation, elle, est bien conservée —
  // c'est par l'historique qu'on revient à une analyse passée.
  const [dashboard, setDashboard] = useState(null)
  const [lastIntent, setLastIntent] = useState(null)

  const nextIdRef = useRef(1 + Math.max(0, ...(persisted?.messages ?? []).map((m) => m.id)))

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ messages: messages.slice(-MAX_MESSAGES) }),
      )
    } catch {
      // Quota dépassée ou navigation privée — la persistance est un confort, pas une
      // garantie ; l'app continue de fonctionner normalement sans elle.
    }
  }, [messages])

  function addMessage(partial) {
    // Horodatage posé ici plutôt qu'à l'appel : l'historique groupe les analyses par
    // jour, et un seul endroit qui date les messages garantit qu'aucun n'y échappe.
    // Les conversations enregistrées avant cette version n'en ont pas — l'historique
    // les regroupe alors sous « Plus ancien » plutôt que d'afficher une fausse date.
    const message = { id: nextIdRef.current++, at: Date.now(), ...partial }
    setMessages((prev) => [...prev, message])
    return message
  }

  function clearHistory() {
    setMessages([welcomeMessage])
    setDashboard(null)
    setLastIntent(null)
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // rien à faire de plus si le storage est indisponible
    }
  }

  return { messages, addMessage, dashboard, setDashboard, lastIntent, setLastIntent, clearHistory }
}
