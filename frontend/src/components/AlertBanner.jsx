import { useEffect, useState } from 'react'

// L'unité des montants, ici comme partout ailleurs (backend/labels.py::DEVISE).
// Ce bandeau était resté en euros après le passage au dinar : les mêmes budgets
// s'affichaient donc en € dans l'alerte et en DT dans le tableau de bord.
const DEVISE = 'DT'

// Repli si l'API ne dit rien : c'est aussi la valeur par défaut de
// backend/alerts.py::ALERT_WINDOW_DAYS.
const FENETRE_PAR_DEFAUT = 7

function formatBudget(value) {
  if (value === null || value === undefined) return 'N/A'
  return `${Number(value).toLocaleString('fr-FR')} ${DEVISE}`
}

export default function AlertBanner() {
  const [opportunities, setOpportunities] = useState([])
  // La fenêtre vient de l'API : elle y est déjà, et l'écrire en dur dans la phrase
  // faisait annoncer « 7 prochains jours » quelle que soit la valeur réellement
  // appliquée par le backend.
  const [fenetre, setFenetre] = useState(FENETRE_PAR_DEFAUT)
  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch('/alerts/deadlines')
      .then((res) => (res.ok ? res.json() : { opportunities: [] }))
      .then((data) => {
        if (cancelled) return
        setOpportunities(data.opportunities || [])
        if (data.window_days) setFenetre(data.window_days)
      })
      .catch(() => {
        // Le panneau reste silencieux si l'API est injoignable — ce n'est qu'un
        // rappel, pas une fonctionnalité bloquante pour le reste du dashboard.
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (dismissed || opportunities.length === 0) return null

  return (
    <div className="alert-banner">
      <button className="alert-banner-summary" onClick={() => setExpanded((v) => !v)}>
        <span className="alert-banner-icon">⚠</span>
        <span>
          {opportunities.length} opportunité{opportunities.length > 1 ? 's' : ''} à échéance dans les {fenetre}{' '}
          prochains jours
        </span>
        <span className="alert-banner-chevron">{expanded ? '▲' : '▼'}</span>
      </button>
      <button
        className="alert-banner-dismiss"
        onClick={() => setDismissed(true)}
        aria-label="Masquer l'alerte"
        title="Masquer"
      >
        ✕
      </button>
      {expanded && (
        <div className="alert-banner-list">
          {opportunities.map((opp) => (
            <div key={opp.id} className="alert-banner-row">
              <span className={`alert-days ${opp.days_left <= 3 ? 'critical' : 'warning'}`}>
                {opp.days_left} j
              </span>
              <span className="alert-buyer">{opp.buyer || 'Client non renseigné'}</span>
              <span className="alert-meta">
                {opp.country} · {opp.practice}
              </span>
              <span className="alert-meta">{opp.status}</span>
              <span className="alert-budget">{formatBudget(opp.budget)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
