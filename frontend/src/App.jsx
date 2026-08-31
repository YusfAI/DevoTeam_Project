import { useMemo, useRef, useState } from 'react'
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
  // Ouvert depuis l'en-tête du tableau de bord, affiché par-dessus le chat : l'état
  // est partagé par les deux panneaux, il vit donc ici plutôt que dans l'un d'eux.
  const [historyOpen, setHistoryOpen] = useState(false)
  const [theme, toggleTheme] = useTheme()
  const inputRef = useRef(null)

  // Toutes les demandes ayant produit un tableau de bord, de la plus récente à la
  // plus ancienne. Aucune n'est fusionnée : deux formulations qui aboutissent à la
  // même analyse restent deux entrées, parce que la liste retrace ce que
  // l'utilisateur a écrit — c'est par là qu'il retrouve une analyse, pas par le nom
  // que le backend lui a donné.
  const history = useMemo(
    () =>
      messages
        .filter((m) => m.dashboardName)
        .map((m) => ({
          id: m.id,
          at: m.at,
          name: m.dashboardName,
          question: m.question || m.dashboardName,
        }))
        .reverse(),
    [messages],
  )

  async function handleSubmit(text) {
    addMessage({ type: 'user', text })
    setLoading(true)

    try {
      const data = await postDashboardQuery(text, lastIntent)
      // La question est attachée à la réponse : c'est elle qu'affiche la liste
      // déroulante, et c'est le seul endroit où le lien question → dashboard existe.
      // dashboardName porte l'INSTANTANÉ, pas le dashboard de travail : ce dernier
      // sera réécrit par la question suivante, rouvrir une analyse passée doit
      // afficher ce qu'elle montrait alors, pas l'analyse en cours.
      addMessage({
        type: 'system',
        text: data.ai_message || 'Voici le résultat de votre demande :',
        dashboardName: data.dashboard_snapshot || data.dac_dashboard || null,
        question: text,
      })
      // dac_dashboard désigne le tableau de bord de travail, réécrit sur place par
      // cette question. Une réponse de clarification n'en a pas : on garde alors
      // l'affichage précédent plutôt que de le vider pour un tour sans résultat.
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

  // Passer d'une section à l'autre : c'est une NAVIGATION, pas une analyse. Le
  // contexte de la conversation reste intact — l'utilisateur regarde ailleurs, il ne
  // pose pas une nouvelle question.
  function handleOpenSection(name) {
    setDashboard({ dac_dashboard: name })
    setDashboardKey((k) => k + 1)
  }

  function handleOpenDashboard(name, question) {
    // « replay » distingue une analyse ROUVERTE du tableau de bord de travail : les
    // deux s'affichent dans le même cadre, mais l'une est figée et l'autre suit les
    // questions. Le sous-titre le dit, sinon rien ne les différencie à l'écran.
    setDashboard({ dac_dashboard: name, goal: question || name, replay: true })
    setDashboardKey((k) => k + 1)
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
          history={history}
          currentDashboardName={dashboard?.dac_dashboard || null}
          onOpenDashboard={handleOpenDashboard}
          onSubmit={handleSubmit}
          theme={theme}
          onToggleTheme={toggleTheme}
          onClearHistory={handleClearHistory}
          onSyncSheets={handleSyncSheets}
          syncingSheets={syncingSheets}
          inputRef={inputRef}
          historyOpen={historyOpen}
          onCloseHistory={() => setHistoryOpen(false)}
        />
        <DashboardPanel
          dashboard={dashboard}
          dashboardKey={dashboardKey}
          onOpenSection={handleOpenSection}
          historyOpen={historyOpen}
          onToggleHistory={() => setHistoryOpen((open) => !open)}
        />
      </div>
    </div>
  )
}
