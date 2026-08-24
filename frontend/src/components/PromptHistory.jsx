// Liste des questions déjà posées, chacune rouvrant le tableau de bord qu'elle avait
// produit. Sans elle, seule la dernière analyse restait atteignable : le dashboard de
// travail étant réécrit à chaque question, revenir à la précédente demandait de la
// reformuler — et de reconsommer un appel au modèle pour un résultat déjà calculé.
//
// Chaque demande y figure, y compris deux formulations qui ont abouti au même
// tableau de bord : la liste retrace ce que l'utilisateur a écrit, pas ce que le
// backend a produit. D'où la clé sur l'identifiant du message et non sur le nom du
// dashboard, qui, lui, peut se répéter.
//
// Un <select> natif plutôt qu'un menu maison : navigable au clavier, lisible par un
// lecteur d'écran et rendu par le système sur mobile, sans une ligne de JS à maintenir.
export default function PromptHistory({ history, currentName, onOpenDashboard }) {
  if (!history.length) return null

  // La liste est ordonnée du plus récent au plus ancien : la première entrée qui
  // correspond au dashboard affiché est donc la demande qui l'a produit en dernier.
  // Quand c'est le tableau de bord de travail qui est à l'écran, rien ne correspond
  // et le <select> reste sur son intitulé neutre — ce qui est exact.
  const courant = history.find((h) => h.name === currentName)

  return (
    <label className="prompt-history">
      <span className="prompt-history-label">Mes analyses</span>
      <select
        value={courant ? String(courant.id) : ''}
        onChange={(event) => {
          const item = history.find((h) => String(h.id) === event.target.value)
          if (item) onOpenDashboard(item.name, item.question)
        }}
      >
        <option value="">
          {history.length} demande{history.length > 1 ? 's' : ''} — en rouvrir une
        </option>
        {history.map((item) => (
          <option key={item.id} value={String(item.id)} title={item.question}>
            {item.question}
          </option>
        ))}
      </select>
    </label>
  )
}
