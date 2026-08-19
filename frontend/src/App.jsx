import { useRef, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import DashboardPanel from './components/DashboardPanel'
import AlertBanner from './components/AlertBanner'
import { useTheme } from './hooks/useTheme'
import { useChatHistory } from './hooks/useChatHistory'
import { postDashboardQuery, postSheetsSync } from './api'

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
  const [syncingSheets, setSyncingSheets] = useState(false)
  const [dashboardKey, setDashboardKey] = useState(0)
  const [theme, toggleTheme] = useTheme()
  const inputRef = useRef(null)

  async function handleSubmit(text) {
    addMessage({ type: 'user', text })
    setLoading(true)

    try {
      const data = await postDashboardQuery(text, lastIntent)
      addMessage({ type: 'system', text: data.ai_message || 'Voici le résultat de votre demande :' })
      // dac_dashboard porte le dashboard multi-widgets généré pour cette question.
      // Une réponse de clarification n'en a pas : on garde alors le dashboard
      // précédent à l'écran plutôt que de le vider pour un tour sans résultat.
      if (data.dac_dashboard) {
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

  async function handleSyncSheets() {
    if (syncingSheets) return
    setSyncingSheets(true)
    try {
      const summary = await postSheetsSync()
      const parts = [
        `${summary.total_rows ?? 0} ligne(s) chargée(s)`,
        `${summary.new_ids_assigned ?? 0} nouvel(le)(s)`,
        `${summary.skipped ?? 0} ignorée(s)`,
      ]
      let text = `Synchronisation Google Sheets terminée : ${parts.join(', ')}.`
      if (summary.errors?.length) {
        text += ` ${summary.errors.length} ligne(s) à corriger — voir les logs serveur pour le détail.`
      }
      addMessage({ type: 'sync', text })
    } catch (err) {
      addMessage({ type: 'error', text: err.message || 'Échec de la synchronisation Google Sheets.' })
    } finally {
      setSyncingSheets(false)
    }
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
          onSyncSheets={handleSyncSheets}
          syncingSheets={syncingSheets}
          inputRef={inputRef}
        />
        <DashboardPanel dashboard={dashboard} dashboardKey={dashboardKey} />
      </div>
    </div>
  )
}
