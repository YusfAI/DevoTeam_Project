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

// Le serveur des dashboards en thème sombre. Un thème DAC est une carte de valeurs
// fixes, appliquée au lancement du serveur : il n'existe aucune bascule dans le
// fichier, d'où un SECOND processus plutôt qu'un second jeu de jetons. Son absence
// est prévue et sans gravité — le tableau de bord reprend alors le serveur clair.
export const DAC_DARK_BASE_URL =
  import.meta.env.VITE_DAC_DARK_BASE_URL || 'http://127.0.0.1:8322'

// Doit correspondre EXACTEMENT au champ `name:` de dac/dashboards/accueil.yml —
// DAC route ses dashboards par leur nom affiché, pas par leur nom de fichier.
export const OVERVIEW_DASHBOARD_NAME = "Vue d'ensemble commerciale"

// Le tableau de bord qui dit ce que les données NE contiennent pas : lignes chargées,
// cellules réparées, colonnes incomplètes et conséquence de chaque manque. Il existait,
// il était complet et honnête — et aucun chemin de l'interface n'y menait. Un
// utilisateur pouvait décider sur un montant pondéré sans jamais apprendre qu'il ne
// couvre que la moitié du portefeuille.
export const DATA_QUALITY_DASHBOARD_NAME = "Qualité des données"

// Les sections de la vue d'ensemble. DAC ne connaît pas la notion de page — son
// schéma refuse `pages` — donc chaque section est un tableau de bord à part entière,
// et c'est ici qu'on rétablit la navigation entre elles.
//
// Les noms doivent correspondre EXACTEMENT au champ `name:` de chaque fichier de
// dac/dashboards/ : DAC route par nom affiché. Ils sont produits par
// scripts/generate_accueil.py, et tests/test_sections_accueil.py vérifie que les
// deux listes ne divergent pas.
export const SECTIONS = [
  { nom: "Vue d'ensemble commerciale", onglet: 'Offres remises' },
  { nom: 'Affaires chaudes', onglet: 'Affaires chaudes' },
  { nom: 'Santé du portefeuille', onglet: 'Portefeuille' },
  { nom: 'Pipeline commercial', onglet: 'Pipeline' },
  { nom: 'Échéances à venir', onglet: 'Échéances' },
]

export function estUneSection(nom) {
  return SECTIONS.some((s) => s.nom === nom)
}

export function dacDashboardUrl(name, filters, racine) {
  // Les filtres d'un tableau de bord DAC vivent dans la chaîne de requête : la page
  // les y lit au chargement. C'est ce qui permet de RÉUTILISER la vue d'ensemble
  // pour une question qu'elle traite déjà — « budget pour Risk Advisory » l'ouvre
  // filtrée sur cette practice, sans qu'aucun tableau de bord soit écrit.
  //
  // `racine` désigne le serveur à interroger : le clair par défaut, le sombre quand
  // le thème sombre est actif ET que ce second serveur tourne. Omise, on retombe
  // sur le clair — un tableau de bord dans le mauvais thème vaut mieux qu'aucun.
  const base = `${racine || DAC_BASE_URL}/d/${encodeURIComponent(name)}`
  const entrees = Object.entries(filters || {}).filter(([, v]) => v != null && v !== '')
  if (entrees.length === 0) return base
  const params = new URLSearchParams()
  for (const [cle, valeur] of entrees) params.set(cle, String(valeur))
  return `${base}?${params.toString()}`
}
