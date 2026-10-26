# Interface — DevoTeam Dashboard

Application Vite + React : le chat, l'historique des analyses et le cadre qui
affiche les tableaux de bord Bruin DAC (iframe, ports 8321 et 8322 pour le thème
sombre).

## Commandes

```
npm install          # une fois
npm run dev          # développement, http://127.0.0.1:5173 (proxy vers le backend :8000)
npm run build        # compile dans dist/, servi ensuite par le backend sur :8000
```

En installation Docker, rien à lancer ici : le service `frontend-build` de
`docker-compose.yml` compile l'interface à chaque démarrage.

## Organisation

```
src/
  App.jsx            disposition générale : chat à gauche, tableau de bord à droite
  api.js             appels au backend (/dashboard, /health, /sheets/sync)
  dac.js             adresses des tableaux de bord et passage des filtres par l'URL
  components/        chat, bandeau d'alertes, cadre du tableau de bord, historique, thème,
                     fenêtre « Source de données »
  components/ui/     briques communes : infobulle et bouton-icône, boîte de confirmation
  hooks/             historique de conversation persistant, thème clair/sombre
  styles/            jetons de design (tokens.css) et styles globaux
```

La palette de graphiques de `styles/tokens.css` doit rester identique à celle des
thèmes `dac/themes/*.yml` — un test (`tests/test_palette.py`) le vérifie.

## Bibliothèques d'interface

| Bibliothèque | Rôle |
|---|---|
| [Radix UI](https://www.radix-ui.com/primitives) | fenêtre « Source de données » (Dialog, Tabs), infobulles (Tooltip), confirmation d'effacement (AlertDialog) — focus, clavier et accessibilité pris en charge |
| [Lucide](https://lucide.dev) | toutes les icônes (aucun emoji dans l'interface) |
| [Motion](https://motion.dev) | animations discrètes : messages, suggestions, historique, bandeau d'alerte, bouton de thème |

Les composants Radix sont **sans style** : ils prennent l'apparence de
`styles/global.css` et des jetons de `styles/tokens.css`, clair comme sombre. Les
animations s'effacent quand Windows demande de les réduire (`MotionConfig
reducedMotion="user"` dans `App.jsx`, `prefers-reduced-motion` dans le CSS).
