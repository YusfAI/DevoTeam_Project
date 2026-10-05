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
  components/        chat, bandeau d'alertes, cadre du tableau de bord, historique, thème
  hooks/             historique de conversation persistant, thème clair/sombre
  styles/            jetons de design (tokens.css) et styles globaux
```

La palette de graphiques de `styles/tokens.css` doit rester identique à celle des
thèmes `dac/themes/*.yml` — un test (`tests/test_palette.py`) le vérifie.
