import { useEffect, useState } from 'react'
import { OVERVIEW_DASHBOARD_NAME, dacDashboardUrl } from '../dac'
import { getHealth } from '../api'
import DevoteamLogo from './DevoteamLogo'

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
  const frameUrl = dacDashboardUrl(currentName)

  // État du serveur de dashboards. null = vérification en cours ; false = injoignable,
  // auquel cas on affiche une consigne au lieu d'une iframe vide et muette — une
  // panne de DAC était jusqu'ici indiscernable d'une absence de données.
  const [dacStatus, setDacStatus] = useState(null)
  useEffect(() => {
    let cancelled = false
    getHealth()
      .then((h) => { if (!cancelled) setDacStatus(h.dac) })
      .catch(() => { if (!cancelled) setDacStatus({ ok: false, aide: 'Le serveur ne répond pas.' }) })
    return () => { cancelled = true }
  }, [dashboardKey])

  // Le premier affichage d'un widget déclenche un démarrage à froid du moteur de
  // requête (une douzaine de secondes) : sans ce voile, l'utilisateur fait face à un
  // cadre blanc qu'il interprète comme une panne.
  // Réinitialisé sur dashboardKey ET sur l'URL : reposer la même question régénère
  // le dashboard sans changer son nom, donc l'URL seule ne suffirait pas à détecter
  // qu'un nouveau chargement commence.
  const [frameLoaded, setFrameLoaded] = useState(false)
  useEffect(() => { setFrameLoaded(false) }, [frameUrl, dashboardKey])

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
        {dacStatus && !dacStatus.ok ? (
          <div className="dashboard-unavailable">
            <DevoteamLogo size={56} className="placeholder-mark" />
            <h3>Serveur de dashboards injoignable</h3>
            <p>{dacStatus.aide}</p>
            <button type="button" onClick={() => window.location.reload()}>
              Réessayer
            </button>
          </div>
        ) : (
          <>
            {!frameLoaded && (
              <div className="dac-skeleton" aria-hidden="true">
                <div className="dac-skeleton-row">
                  <span /><span /><span /><span />
                </div>
                <div className="dac-skeleton-row tall">
                  <span /><span />
                </div>
                <div className="dac-skeleton-caption">Préparation du tableau de bord…</div>
              </div>
            )}
            <iframe
              key={`${currentName}-${overviewVisible ? 'overview' : dashboardKey}`}
              className={`dac-frame${frameLoaded ? '' : ' loading'}`}
              src={frameUrl}
              title={currentName}
              onLoad={() => setFrameLoaded(true)}
            />
          </>
        )}
      </div>
    </div>
  )
}
