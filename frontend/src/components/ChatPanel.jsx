import { useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
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

export default function ChatPanel({
  messages, loading, onSubmit, theme, onToggleTheme, onClearHistory, onSyncSheets,
  syncingSheets, inputRef, onOpenDashboard,
}) {
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, loading])

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
      <div className="chat-messages">
        {messages.map((m) => (
          <ChatMessage
            key={m.id}
            type={m.type}
            text={m.text}
            dashboardName={m.dashboardName}
            onOpenDashboard={onOpenDashboard}
          />
        ))}

        {/* Affichées tant que la conversation n'a produit aucune réponse : une fois
            l'utilisateur lancé, elles n'ont plus lieu d'être et laissent la place. */}
        {!loading && !messages.some((m) => m.dashboardName) && (
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
      <ChatInput inputRef={inputRef} loading={loading} onSubmit={onSubmit} />
    </div>
  )
}
