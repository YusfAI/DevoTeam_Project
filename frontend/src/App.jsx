import { useRef, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import DashboardPanel from './components/DashboardPanel'
import { useTheme } from './hooks/useTheme'
import { postDashboardQuery } from './api'

let nextMessageId = 1

const WELCOME_MESSAGE = {
  id: 0,
  type: 'system',
  text:
    'Bonjour ! Je suis votre assistant commercial. Que souhaitez-vous analyser ? ' +
    '(ex: "montre-moi le budget par pays pour Risk Advisory")',
}

export default function App() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [loading, setLoading] = useState(false)
  const [dashboard, setDashboard] = useState(null)
  const [dashboardKey, setDashboardKey] = useState(0)
  const [lastIntent, setLastIntent] = useState(null)
  const [theme, toggleTheme] = useTheme()
  const inputRef = useRef(null)

  async function handleSubmit(text) {
    setMessages((prev) => [...prev, { id: nextMessageId++, type: 'user', text }])
    setLoading(true)

    try {
      const data = await postDashboardQuery(text, lastIntent)
      setMessages((prev) => [
        ...prev,
        { id: nextMessageId++, type: 'system', text: data.ai_message || 'Voici le résultat de votre demande :' },
      ])
      if (data.kpi_value !== undefined || data.vega_spec || data.table_rows) {
        setDashboard(data)
        setDashboardKey((k) => k + 1)
      }
      // Seule une réponse résolue (pas une clarification) porte "intent" — un tour
      // raté ne doit jamais écraser le contexte utile du tour précédent.
      if (data.intent) {
        setLastIntent(data.intent)
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: nextMessageId++, type: 'error', text: err.message || 'Erreur de connexion au serveur.' },
      ])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="app">
      <ChatPanel
        messages={messages}
        loading={loading}
        onSubmit={handleSubmit}
        theme={theme}
        onToggleTheme={toggleTheme}
        inputRef={inputRef}
      />
      <DashboardPanel dashboard={dashboard} theme={theme} dashboardKey={dashboardKey} />
    </div>
  )
}
