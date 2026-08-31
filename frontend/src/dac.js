// Adressage des dashboards servis par Bruin DAC (processus séparé, port 8321 —
// lancé par scripts/start_dev.bat ou scripts/start_prod.bat). L'iframe charge
// l'URL directement depuis le navigateur, donc aucun proxy Vite n'est nécessaire
// ici (contrairement aux appels fetch vers /dashboard ou /sheets/sync, qui eux
// passent par le proxy en développement).
//
// 127.0.0.1 plutôt que « localhost » : ce dernier résout d'abord en ::1 sur
// Windows, alors que DAC n'écoute que sur l'IPv4 (vérifié : netstat ne montre que
// 127.0.0.1:8321). Le navigateur y perdait le même délai que la sonde du backend,
// qui pour cette raison exacte est passée de 2,0 s à 0,003 s.
//
// Surchargeable à la COMPILATION (VITE_DAC_BASE_URL) : la valeur est figée dans le
// bundle par Vite, elle ne peut donc pas être changée après coup. Utile le jour où
// DAC ne tourne plus sur la même machine que le navigateur.
export const DAC_BASE_URL =
  import.meta.env.VITE_DAC_BASE_URL || 'http://127.0.0.1:8321'

// Doit correspondre EXACTEMENT au champ `name:` de dac/dashboards/accueil.yml —
// DAC route ses dashboards par leur nom affiché, pas par leur nom de fichier.
export const OVERVIEW_DASHBOARD_NAME = "Vue d'ensemble commerciale"

// Le tableau de bord qui dit ce que les données NE contiennent pas : lignes chargées,
// cellules réparées, colonnes incomplètes et conséquence de chaque manque. Il existait,
// il était complet et honnête — et aucun chemin de l'interface n'y menait. Un
// utilisateur pouvait décider sur un montant pondéré sans jamais apprendre qu'il ne
// couvre que la moitié du portefeuille.
export const DATA_QUALITY_DASHBOARD_NAME = "Qualité des données"

export function dacDashboardUrl(name, filters) {
  // Les filtres d'un tableau de bord DAC vivent dans la chaîne de requête : la page
  // les y lit au chargement. C'est ce qui permet de RÉUTILISER la vue d'ensemble
  // pour une question qu'elle traite déjà — « budget pour Risk Advisory » l'ouvre
  // filtrée sur cette practice, sans qu'aucun tableau de bord soit écrit.
  const base = `${DAC_BASE_URL}/d/${encodeURIComponent(name)}`
  const entrees = Object.entries(filters || {}).filter(([, v]) => v != null && v !== '')
  if (entrees.length === 0) return base
  const params = new URLSearchParams()
  for (const [cle, valeur] of entrees) params.set(cle, String(valeur))
  return `${base}?${params.toString()}`
}
