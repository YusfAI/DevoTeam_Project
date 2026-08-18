import { useEffect, useState } from 'react'
import VegaChart from './VegaChart'
import StatTile from './StatTile'
import DataTable from './DataTable'
import { OVERVIEW_DASHBOARD_NAME, dacDashboardUrl } from '../dac'

export default function DashboardPanel({ dashboard, theme, dashboardKey }) {
  const hasChart = Boolean(dashboard?.vega_spec)
  const hasTable = Array.isArray(dashboard?.table_rows)
  const isKpi = Boolean(dashboard) && dashboard.kpi_value !== undefined

  const [view, setView] = useState('chart')
  useEffect(() => {
    setView(hasChart ? 'chart' : 'table')
  }, [dashboard, hasChart])

  // Tant qu'aucune question n'a été posée, on affiche la vue d'ensemble DAC
  // (dac/dashboards/accueil.yml) plutôt qu'un placeholder vide. Une réponse du chat
  // reprend la main sur le panneau ; le bouton « Vue d'ensemble » y ramène.
  const [showOverview, setShowOverview] = useState(true)
  useEffect(() => {
    if (dashboard) setShowOverview(false)
  }, [dashboardKey, dashboard])

  const overviewVisible = !dashboard || showOverview

  const title = overviewVisible
    ? 'Vue d’ensemble commerciale'
    : dashboard?.goal || 'Analyse des opportunités'
  const subtitle = overviewVisible
    ? 'Dashboard versionné (Bruin DAC) — filtres interactifs, données à jour'
    : 'Données extraites du portefeuille d’opportunités'

  const centered = !overviewVisible && isKpi

  return (
    <div className="dashboard-panel">
      <div className="dashboard-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <div className="dashboard-header-actions">
          {dashboard && (
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
                Résultat
              </button>
            </div>
          )}
          {!overviewVisible && hasChart && hasTable && dashboard.table_rows.length > 0 && (
            <div className="view-toggle">
              <button
                type="button"
                className={view === 'chart' ? 'active' : ''}
                onClick={() => setView('chart')}
              >
                Graphique
              </button>
              <button
                type="button"
                className={view === 'table' ? 'active' : ''}
                onClick={() => setView('table')}
              >
                Tableau
              </button>
            </div>
          )}
        </div>
      </div>

      <div className={`dashboard-body${centered ? '' : ' align-top'}`}>
        {overviewVisible && (
          <iframe
            className="dac-frame"
            src={dacDashboardUrl(OVERVIEW_DASHBOARD_NAME)}
            title="Vue d’ensemble commerciale"
          />
        )}

        {!overviewVisible && isKpi && (
          <StatTile
            key={dashboardKey}
            label={dashboard.kpi_label || 'Résultat'}
            value={dashboard.kpi_value_formatted}
            isNa={dashboard.kpi_value === null}
          />
        )}

        {!overviewVisible && !isKpi && hasChart && view === 'chart' && (
          <div key={dashboardKey} className="dashboard-fade-in fill">
            <VegaChart spec={dashboard.vega_spec} theme={theme} />
          </div>
        )}

        {!overviewVisible && !isKpi && ((hasChart && view === 'table') || (!hasChart && hasTable)) && (
          <div key={`${dashboardKey}-table`} className="dashboard-fade-in fill">
            <DataTable rows={dashboard.table_rows} />
          </div>
        )}
      </div>
    </div>
  )
}
