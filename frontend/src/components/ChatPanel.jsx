import { useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import TypingIndicator from './TypingIndicator'
import ThemeToggle from './ThemeToggle'
import DevoteamLogo from './DevoteamLogo'

export default function ChatPanel({
  messages, loading, onSubmit, theme, onToggleTheme, onClearHistory, onSyncSheets, syncingSheets, inputRef,
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
          <ChatMessage key={m.id} type={m.type} text={m.text} />
        ))}
        {loading && <TypingIndicator />}
        <div ref={endRef} />
      </div>
      <ChatInput inputRef={inputRef} loading={loading} onSubmit={onSubmit} />
    </div>
  )
}
