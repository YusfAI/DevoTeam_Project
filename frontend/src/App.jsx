import { useRef, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import DashboardPanel from './components/DashboardPanel'
import AlertBanner from './components/AlertBanner'
import { useTheme } from './hooks/useTheme'
import { useChatHistory } from './hooks/useChatHistory'
import { postDashboardQuery } from './api'

const WELCOME_MESSAGE = {
  id: 0,
  type: 'system',
  text:
    'Bonjour ! Je suis votre assistant commercial. Que souhaitez-vous analyser ? ' +
    '(ex: "montre-moi le budget par pays pour Risk Advisory")',
}

export default function App() {
  const { messages, addMessage, dashboard, setDashboard, lastIntent, setLastIntent, clearHistory } =
    useChatHistory(WELCOME_MESSAGE)
  const [loading, setLoading] = useState(false)
  const [dashboardKey, setDashboardKey] = useState(0)
  const [theme, toggleTheme] = useTheme()
  const inputRef = useRef(null)

  async function handleSubmit(text) {
    addMessage({ type: 'user', text })
    setLoading(true)

    try {
      const data = await postDashboardQuery(text, lastIntent)
      addMessage({ type: 'system', text: data.ai_message || 'Voici le résultat de votre demande :' })
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
      addMessage({ type: 'error', text: err.message || 'Erreur de connexion au serveur.' })
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  function handleClearHistory() {
    if (!window.confirm('Effacer tout l\'historique de conversation ?')) return
    clearHistory()
    setDashboardKey(0)
  }

  return (
    <div className="app-shell">
      <AlertBanner />
      <div className="app">
        <ChatPanel
          messages={messages}
          loading={loading}
          onSubmit={handleSubmit}
          theme={theme}
          onToggleTheme={toggleTheme}
          onClearHistory={handleClearHistory}
          inputRef={inputRef}
        />
        <DashboardPanel dashboard={dashboard} theme={theme} dashboardKey={dashboardKey} />
      </div>
    </div>
  )
}
