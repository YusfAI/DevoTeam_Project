export default function TypingIndicator() {
  // Trois points animés ne disent rien à qui ne les voit pas. `role="status"` et le
  // texte lu par les seuls lecteurs d'écran signalent qu'une requête est en cours —
  // information d'autant plus utile ici que l'attente peut durer une dizaine de
  // secondes au démarrage à froid du moteur de requête.
  return (
    <div className="typing" role="status" aria-live="polite">
      <span className="sr-only">Analyse en cours…</span>
      <div className="dot" aria-hidden="true" />
      <div className="dot" aria-hidden="true" />
      <div className="dot" aria-hidden="true" />
    </div>
  )
}
