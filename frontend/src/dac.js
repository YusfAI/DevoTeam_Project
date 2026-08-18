// Adressage des dashboards servis par Bruin DAC (processus séparé, port 8321 —
// lancé par scripts/start_dev.bat). L'iframe charge l'URL directement depuis le
// navigateur, donc aucun proxy Vite n'est nécessaire ici (contrairement aux appels
// fetch vers /dashboard ou /sheets/sync, qui eux passent par le proxy).
export const DAC_BASE_URL = 'http://localhost:8321'

// Doit correspondre EXACTEMENT au champ `name:` de dac/dashboards/accueil.yml —
// DAC route ses dashboards par leur nom affiché, pas par leur nom de fichier.
export const OVERVIEW_DASHBOARD_NAME = "Vue d'ensemble commerciale"

export function dacDashboardUrl(name) {
  return `${DAC_BASE_URL}/d/${encodeURIComponent(name)}`
}
