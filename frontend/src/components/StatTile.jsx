export default function StatTile({ label, value, isNa }) {
  return (
    <div className="stat-tile">
      <div className="label">{label}</div>
      <div className={`value${isNa ? ' na' : ''}`}>{value}</div>
    </div>
  )
}
