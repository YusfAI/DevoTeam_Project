import { useMemo, useRef, useState } from 'react'
import ChatPanel from './components/ChatPanel'
import DashboardPanel from './components/DashboardPanel'
import AlertBanner from './components/AlertBanner'
import DataSourcePanel from './components/DataSourcePanel'
import { useTheme } from './hooks/useTheme'
import { useChatHistory } from './hooks/useChatHistory'
import { postDashboardQuery } from './api'

// Le compte rendu d'une relecture du Sheet, tel qu'il s'affiche dans le chat. Une
// lecture en échec dit POURQUOI (feuille non partagée, connexion…) au lieu de
// renvoyer aux journaux du serveur, que personne ne lit devant l'écran.
function messageDeLecture(resume) {
  if (resume.fatal_error) return `Lecture du Google Sheet impossible : ${resume.fatal_error}`
  const parts = [
    `${resume.total_rows ?? 0} ligne(s) chargée(s)`,
    `${resume.new_ids_assigned ?? 0} nouvel(le)(s)`,
    `${resume.skipped ?? 0} ignorée(s)`,
  ]
  let texte = `Synchronisation Google Sheets terminée : ${parts.join(', ')}.`
  const aCorriger = resume.repairs?.length || 0
  if (aCorriger) {
    texte += ` ${aCorriger} cellule(s) à corriger dans la feuille — voir « Santé des données ».`
  }
  return texte
}

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
  // La fenêtre « Source de données » : fermée (null), ou ouverte sur l'un de ses deux
  // onglets — 'sante' depuis l'en-tête du tableau de bord, 'lier' depuis le chat.
  const [dataPanel, setDataPanel] = useState(null)
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

  // Une relecture (« Relire la feuille maintenant ») : compte rendu dans le chat, et
  // le tableau de bord affiché est rechargé pour montrer les nouvelles valeurs.
  function handleSheetReread(resume) {
    addMessage({ type: resume.fatal_error ? 'error' : 'sync', text: messageDeLecture(resume) })
    setDashboardKey((k) => k + 1)
  }

  // Une autre feuille vient d'être liée. Le contexte de conversation est abandonné :
  // ses filtres (un pays, un client…) désignaient des valeurs de l'ANCIENNE feuille.
  // Retour à la vue d'ensemble, recalculée sur les nouvelles données.
  function handleSourceChanged({ diagnostic, etat }) {
    const lignes = etat?.lignes?.chargees ?? diagnostic?.lignes?.chargees ?? 0
    addMessage({
      type: 'sync',
      text:
        `Nouvelle feuille liée — onglet « ${diagnostic.source.tab} », ${lignes} ligne(s) chargée(s). ` +
        'Le chat, les alertes et les tableaux de bord utilisent désormais cette feuille.',
    })
    setLastIntent(null)
    setDashboard(null)
    setDashboardKey((k) => k + 1)
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
          onOpenLinkSheet={() => setDataPanel('lier')}
          inputRef={inputRef}
          historyOpen={historyOpen}
          onCloseHistory={() => setHistoryOpen(false)}
        />
        <DashboardPanel
          dashboard={dashboard}
          dashboardKey={dashboardKey}
          theme={theme}
          onOpenSection={handleOpenSection}
          historyOpen={historyOpen}
          onToggleHistory={() => setHistoryOpen((open) => !open)}
          onOpenDataHealth={() => setDataPanel('sante')}
        />
      </div>
      {dataPanel && (
        <DataSourcePanel
          vue={dataPanel}
          onChangerVue={setDataPanel}
          onClose={() => setDataPanel(null)}
          onRelu={handleSheetReread}
          onSourceChangee={handleSourceChanged}
        />
      )}
    </div>
  )
}
