import { useEffect, useState } from 'react'

function formatBudget(value) {
  if (value === null || value === undefined) return 'N/A'
  return `${Number(value).toLocaleString('fr-FR')} €`
}

export default function AlertBanner() {
  const [opportunities, setOpportunities] = useState([])
  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch('/alerts/deadlines')
      .then((res) => (res.ok ? res.json() : { opportunities: [] }))
      .then((data) => {
        if (!cancelled) setOpportunities(data.opportunities || [])
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
          {opportunities.length} opportunité{opportunities.length > 1 ? 's' : ''} à échéance dans les 7 prochains
          jours
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
