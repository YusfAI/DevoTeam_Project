import { useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import PromptHistory from './PromptHistory'
import TypingIndicator from './TypingIndicator'
import ThemeToggle from './ThemeToggle'
import DevoteamLogo from './DevoteamLogo'

// Questions d'amorce : un chat vide ne dit pas ce qu'on peut lui demander. Chacune
// exerce une capacité différente (filtre, comparaison, pipeline, urgence), pour que
// l'utilisateur découvre l'étendue de l'outil en cliquant plutôt qu'en devinant.
const SUGGESTIONS = [
  'Budget par pays pour Risk Advisory',
  'Compare le budget entre la France et le Maroc',
  "Montre-moi l'entonnoir de vente",
  'Liste des opportunités urgentes (< 7 jours)',
]

// Retouches applicables au tableau de bord affiché. Elles ne sont proposées qu'une
// fois une analyse à l'écran : c'est là qu'elles ont un sens, et c'est ce qui rend
// visible que l'assistant sait MODIFIER le dashboard, pas seulement en créer un.
const ADJUSTMENTS = ['En camembert', 'Top 5', 'Par practice', 'Sans filtre']

export default function ChatPanel({
  messages, loading, onSubmit, theme, onToggleTheme, onClearHistory, onSyncSheets,
  syncingSheets, inputRef, onOpenDashboard, history, currentDashboardName,
}) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, loading])

  const hasAnalysis = history.length > 0

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
          chaque interaction, et il ne doit pas se déplacer avec la conversation ni
          demander de faire défiler pour être atteint. La liste des analyses est
          juste en dessous, au même endroit — poser une question et rouvrir une
          question posée sont la même intention. */}
      <div className="chat-composer">
        <ChatInput inputRef={inputRef} loading={loading} onSubmit={onSubmit} />
        {hasAnalysis && (
          <div className="chat-adjustments">
            {ADJUSTMENTS.map((a) => (
              <button
                key={a}
                type="button"
                className="chat-adjustment"
                disabled={loading}
                onClick={() => onSubmit(a)}
                title="Modifier le tableau de bord affiché"
              >
                {a}
              </button>
            ))}
          </div>
        )}
        <PromptHistory
          history={history}
          currentName={currentDashboardName}
          onOpenDashboard={onOpenDashboard}
        />
      </div>

      <div className="chat-messages">
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
        {!loading && !hasAnalysis && (
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
    </div>
  )
}
