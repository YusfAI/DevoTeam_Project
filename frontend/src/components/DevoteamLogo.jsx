// Recréation vectorielle du logo Devoteam (cercle corail + "d" surmonté d'un "+") —
// aucun fichier source du logo n'était disponible, reconstruit en SVG pour rester
// net à toute taille et suivre le thème clair/sombre via les jetons de marque.
export default function DevoteamLogo({ size = 34, glow = false, className = '' }) {
  return (
    <svg
      className={`devoteam-mark${glow ? ' glow' : ''} ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Devoteam"
    >
      <circle cx="50" cy="50" r="50" fill="var(--brand-primary)" />
      <text
        x="40"
        y="74"
        fontSize="58"
        fontWeight="700"
        fill="#ffffff"
        fontFamily="'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif"
        textAnchor="middle"
      >
        d
      </text>
      <g stroke="#ffffff" strokeWidth="8" strokeLinecap="round">
        <line x1="73" y1="20" x2="73" y2="42" />
        <line x1="62" y1="31" x2="84" y2="31" />
      </g>
    </svg>
  )
}
