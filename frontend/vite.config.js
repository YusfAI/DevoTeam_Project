import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Chaque préfixe d'API appelé par src/api.js doit figurer ici, sinon le serveur
    // de développement renvoie l'index.html du SPA à la place de la réponse JSON —
    // l'appelant reçoit alors « Unexpected token '<' ». Un test le vérifie
    // (tests/test_frontend_proxy.py) : l'oubli ne se voit qu'à l'exécution.
    proxy: {
      '/dashboard': 'http://127.0.0.1:8000',
      '/hot-deals': 'http://127.0.0.1:8000',
      '/alerts': 'http://127.0.0.1:8000',
      '/sheets': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/data': 'http://127.0.0.1:8000',
    },
  },
})
