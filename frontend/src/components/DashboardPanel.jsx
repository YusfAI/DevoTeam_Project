import { useEffect, useState } from 'react'
import VegaChart from './VegaChart'
import StatTile from './StatTile'
import DataTable from './DataTable'
import DevoteamLogo from './DevoteamLogo'

export default function DashboardPanel({ dashboard, theme, dashboardKey }) {
  const hasChart = Boolean(dashboard?.vega_spec)
  const hasTable = Array.isArray(dashboard?.table_rows)
  const isKpi = Boolean(dashboard) && dashboard.kpi_value !== undefined

  const [view, setView] = useState('chart')
  useEffect(() => {
    setView(hasChart ? 'chart' : 'table')
  }, [dashboard, hasChart])

  const title = dashboard?.goal || 'Analyse des opportunités'
  const subtitle = dashboard
    ? 'Données extraites de la base commerciale'
    : 'Visualisation interactive générée à la volée'

  const centered = !dashboard || isKpi

  return (
    <div className="dashboard-panel">
      <div className="dashboard-header">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {hasChart && hasTable && dashboard.table_rows.length > 0 && (
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

      <div className={`dashboard-body${centered ? '' : ' align-top'}`}>
        {!dashboard && (
          <div className="dashboard-placeholder">
            <DevoteamLogo size={72} className="placeholder-mark" />
            <p>Posez une question dans le chat pour générer un graphique.</p>
          </div>
        )}

        {dashboard && isKpi && (
          <StatTile
            key={dashboardKey}
            label={dashboard.kpi_label || 'Résultat'}
            value={dashboard.kpi_value_formatted}
            isNa={dashboard.kpi_value === null}
          />
        )}

        {dashboard && !isKpi && hasChart && view === 'chart' && (
          <div key={dashboardKey} className="dashboard-fade-in fill">
            <VegaChart spec={dashboard.vega_spec} theme={theme} />
          </div>
        )}

        {dashboard && !isKpi && ((hasChart && view === 'table') || (!hasChart && hasTable)) && (
          <div key={`${dashboardKey}-table`} className="dashboard-fade-in fill">
            <DataTable rows={dashboard.table_rows} />
          </div>
        )}
      </div>
    </div>
  )
}
