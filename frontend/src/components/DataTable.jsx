function statusTagClass(value) {
  const s = String(value)
  if (s.includes('gagn')) return 'tag-won'
  if (s.includes('perdu')) return 'tag-lost'
  return 'tag-other'
}

function formatCell(col, val) {
  if (val === null || val === undefined || val === '') return ''
  if ((col === 'budget' || col === 'financial_offer') && typeof val === 'number') {
    return `${val.toLocaleString('fr-FR')} €`
  }
  if (col === 'days_remaining' && typeof val === 'number' && val < 0) {
    const days = Math.abs(val)
    return `Échéance dépassée depuis ${days} jour${days > 1 ? 's' : ''}`
  }
  return String(val)
}

export default function DataTable({ rows }) {
  if (!rows || rows.length === 0) {
    return <div className="dashboard-placeholder">Aucune donnée à afficher.</div>
  }

  const columns = Object.keys(rows[0])

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{col.replace(/_/g, ' ')}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => {
                const val = row[col]
                if (col === 'status') {
                  return (
                    <td key={col}>
                      <span className={`tag ${statusTagClass(val)}`}>{val}</span>
                    </td>
                  )
                }
                if (col === 'days_remaining' && typeof val === 'number') {
                  const className = val < 0 ? 'expired' : val < 7 ? 'urgent' : undefined
                  if (className) {
                    return <td key={col} className={className}>{formatCell(col, val)}</td>
                  }
                }
                return <td key={col}>{formatCell(col, val)}</td>
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
