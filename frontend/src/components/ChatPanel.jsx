import { useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import HistoryPanel from './HistoryPanel'
import TypingIndicator from './TypingIndicator'
import ThemeToggle from './ThemeToggle'
import DevoteamLogo from './DevoteamLogo'

// Questions d'amorce : un chat vide ne dit pas ce qu'on peut lui demander. Chacune
// exerce une capacité différente (filtre, comparaison, pipeline, urgence), pour que
// l'utilisateur découvre l'étendue de l'outil en cliquant plutôt qu'en devinant.
// Elles disparaissent dès la première réponse : passé ce point, c'est la phrase
// tapée qui pilote le tableau de bord, pas des boutons.
// Les trois premières sont celles que la direction pose réellement, dans l'ordre où
// elle les pose : le volume déposé et son issue, puis la répartition par practice,
// puis la période. Elles ouvrent la liste parce que ce sont elles qu'on cherche.
const SUGGESTIONS = [
  'Sur le total des offres remises, combien gagnées, perdues, et en attente ?',
  'Quelle est la répartition par practice ?',
  "Combien d'offres a-t-on remis entre novembre 2025 et à date actuelle ?",
  'Budget par pays pour Risk Advisory',
  'Compare le budget entre la France et le Maroc',
  "Montre-moi l'entonnoir de vente",
  'Liste des opportunités urgentes (< 7 jours)',
]

export default function ChatPanel({
  messages, loading, onSubmit, theme, onToggleTheme, onClearHistory, onSyncSheets,
  syncingSheets, inputRef, onOpenDashboard, history, currentDashboardName,
  historyOpen, onCloseHistory,
}) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, loading])

  function handleOpenFromHistory(name, question) {
    onOpenDashboard(name, question)
    onCloseHistory()
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div className="chat-header-brand">
          <DevoteamLogo size={36} glow />
          <div>
            <h1>DevoTeam Assistant</h1>
            <p className="tagline">Dashboard commercial</p>
          </div>
        </div>
        <div className="chat-header-actions">
          <button
            className={`theme-toggle${syncingSheets ? ' syncing' : ''}`}
            onClick={onSyncSheets}
            disabled={syncingSheets}
            title="Synchroniser Google Sheets"
            aria-label="Synchroniser Google Sheets"
            type="button"
          >
            🔄
          </button>
          <button
            className="theme-toggle"
            onClick={onClearHistory}
            title="Effacer la conversation"
            aria-label="Effacer la conversation"
            type="button"
          >
            🗑️
          </button>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>

      {/* La zone de saisie est en tête de panneau : c'est le point de départ de
          chaque interaction, et elle ne doit pas se déplacer avec la conversation ni
          demander de faire défiler pour être atteinte. C'est aussi le SEUL moyen de
          modifier le tableau de bord affiché — décrire le changement en toutes
          lettres plutôt que le choisir dans une liste de retouches préparées. */}
      <div className="chat-composer">
        <ChatInput inputRef={inputRef} loading={loading} onSubmit={onSubmit} />
      </div>

      {/* `aria-live` ici, et pas seulement sur le pourcentage de zoom : un lecteur
          d'écran n'annonçait jamais la réponse de l'assistant, alors qu'il annonçait
          « 110 % » à chaque clic de zoom. La priorité était exactement inversée.
          `polite` plutôt que `assertive` : la réponse ne doit pas couper l'utilisateur
          en train de taper. */}
      <div className="chat-messages" role="log" aria-live="polite" aria-relevant="additions">
        {messages.map((m) => (
          <ChatMessage
            key={m.id}
            type={m.type}
            text={m.text}
            dashboardName={m.dashboardName}
            question={m.question}
            onOpenDashboard={onOpenDashboard}
          />
        ))}

        {/* Affichées tant que la conversation n'a produit aucune réponse : une fois
            l'utilisateur lancé, elles n'ont plus lieu d'être et laissent la place. */}
        {!loading && history.length === 0 && (
          <div className="chat-suggestions">
            <span className="chat-suggestions-label">Essayez :</span>
            {SUGGESTIONS.map((q) => (
              <button key={q} type="button" className="chat-suggestion" onClick={() => onSubmit(q)}>
                {q}
              </button>
            ))}
          </div>
        )}

        {loading && <TypingIndicator />}
        <div ref={endRef} />
      </div>

      {historyOpen && (
        <HistoryPanel
          history={history}
          currentName={currentDashboardName}
          onOpen={handleOpenFromHistory}
          onClose={onCloseHistory}
        />
      )}
    </div>
  )
}
