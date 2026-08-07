import { useEffect, useRef, useState } from 'react'

const STORAGE_KEY = 'devoteam-chat-history'
// Borne la taille conservée — une conversation ne doit pas faire grossir indéfiniment
// le localStorage (limite ~5 Mo par origine dans la plupart des navigateurs).
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
  const [dashboard, setDashboard] = useState(persisted?.dashboard ?? null)
  const [lastIntent, setLastIntent] = useState(persisted?.lastIntent ?? null)

  const nextIdRef = useRef(1 + Math.max(0, ...(persisted?.messages ?? []).map((m) => m.id)))

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ messages: messages.slice(-MAX_MESSAGES), dashboard, lastIntent }),
      )
    } catch {
      // Quota dépassée ou navigation privée — la persistance est un confort, pas une
      // garantie ; l'app continue de fonctionner normalement sans elle.
    }
  }, [messages, dashboard, lastIntent])

  function addMessage(partial) {
    const message = { id: nextIdRef.current++, ...partial }
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
