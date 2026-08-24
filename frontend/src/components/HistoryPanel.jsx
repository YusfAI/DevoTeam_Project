// Historique des analyses, dans l'esprit du volet de conversations de Claude : une
// liste plein écran, groupée par jour, où chaque entrée est la demande telle qu'elle
// a été écrite et rouvre le tableau de bord qu'elle avait produit.
//
// Une liste déroulante (<select>) ne convenait pas : elle cache son contenu tant
// qu'on ne l'ouvre pas, tronque les intitulés longs — or ce sont des phrases
// entières — et ne peut porter ni date ni état courant. L'historique est un endroit
// où l'on RELIT ce qu'on a demandé, pas un sélecteur de valeur.

function groupLabel(timestamp) {
  if (!timestamp) return 'Plus ancien'
  const jour = new Date(timestamp)
  const aujourdhui = new Date()
  const memeJour = (a, b) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()

  if (memeJour(jour, aujourdhui)) return "Aujourd'hui"
  const hier = new Date(aujourdhui)
  hier.setDate(hier.getDate() - 1)
  if (memeJour(jour, hier)) return 'Hier'
  return jour.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

function heure(timestamp) {
  if (!timestamp) return ''
  return new Date(timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export default function HistoryPanel({ history, currentName, onOpen, onClose }) {
  // Les entrées arrivent de la plus récente à la plus ancienne ; les groupes suivent
  // donc le même ordre sans avoir à trier quoi que ce soit.
  const groupes = []
  for (const item of history) {
    const label = groupLabel(item.at)
    const dernier = groupes[groupes.length - 1]
    if (dernier && dernier.label === label) dernier.items.push(item)
    else groupes.push({ label, items: [item] })
  }

  return (
    <div className="history-panel" role="dialog" aria-label="Historique des analyses">
      <div className="history-header">
        <h2>Historique</h2>
        <button type="button" className="history-close" onClick={onClose} aria-label="Fermer l’historique">
          ✕
        </button>
      </div>

      {history.length === 0 ? (
        <p className="history-empty">
          Vos analyses apparaîtront ici. Posez une question pour commencer.
        </p>
      ) : (
        <div className="history-list">
          {groupes.map((groupe) => (
            <section key={groupe.label + groupe.items[0].id}>
              <h3 className="history-group">{groupe.label}</h3>
              {groupe.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`history-item${item.name === currentName ? ' active' : ''}`}
                  onClick={() => onOpen(item.name, item.question)}
                >
                  <span className="history-item-question">{item.question}</span>
                  <span className="history-item-meta">
                    {item.name === currentName ? 'Affiché' : heure(item.at)}
                  </span>
                </button>
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
