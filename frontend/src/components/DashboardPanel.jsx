import { useEffect, useState } from 'react'
import { OVERVIEW_DASHBOARD_NAME, dacDashboardUrl } from '../dac'

export default function DashboardPanel({ dashboard, dashboardKey }) {
  // Nom du dashboard DAC généré pour la dernière question (backend/dac_composer.py).
  // Absent tant qu'aucune question n'a été posée, ou si sa génération a échoué —
  // dans ce cas on retombe simplement sur la vue d'ensemble.
  const generatedName = dashboard?.dac_dashboard || null

  const [showOverview, setShowOverview] = useState(true)
  useEffect(() => {
    if (generatedName) setShowOverview(false)
  }, [dashboardKey, generatedName])

  const overviewVisible = !generatedName || showOverview
  const currentName = overviewVisible ? OVERVIEW_DASHBOARD_NAME : generatedName

  const title = overviewVisible ? 'Vue d’ensemble commerciale' : dashboard?.goal || 'Analyse'
  const subtitle = overviewVisible
    ? 'Dashboard versionné (Bruin DAC) — filtres interactifs, données à jour'
    : 'Dashboard généré à partir de votre question — mêmes filtres sur tous les widgets'

  return (
    <div className="dashboard-panel">
      <div className="dashboard-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {generatedName && (
          <div className="dashboard-header-actions">
            <div className="view-toggle">
              <button
                type="button"
                className={overviewVisible ? 'active' : ''}
                onClick={() => setShowOverview(true)}
              >
                Vue d’ensemble
              </button>
              <button
                type="button"
                className={!overviewVisible ? 'active' : ''}
                onClick={() => setShowOverview(false)}
              >
                Ma question
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="dashboard-body align-top">
        {/* key = dashboardKey : force le remontage de l'iframe à chaque nouvelle
            réponse, pour que DAC recharge le dashboard même si son nom est
            identique (question reposée après un rafraîchissement des données). */}
        <iframe
          key={`${currentName}-${overviewVisible ? 'overview' : dashboardKey}`}
          className="dac-frame"
          src={dacDashboardUrl(currentName)}
          title={currentName}
        />
      </div>
    </div>
  )
}
