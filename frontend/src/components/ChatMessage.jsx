export default function ChatMessage({ type, text, dashboardName, question, onOpenDashboard }) {
  // Une réponse qui a produit un dashboard devient cliquable : sans ça, seul le
  // dernier résultat restait accessible et les analyses précédentes étaient perdues.
  const replayable = Boolean(dashboardName && onOpenDashboard)

  if (!replayable) {
    return <div className={`message ${type}`}>{text}</div>
  }

  return (
    <div className={`message ${type} replayable`}>
      {text}
      <button
        type="button"
        className="message-replay"
        onClick={() => onOpenDashboard(dashboardName, question)}
        title="Réafficher ce tableau de bord"
      >
        ↗ Revoir ce tableau de bord
      </button>
    </div>
  )
}
