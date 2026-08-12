# DevoTeam Dashboard

Dashboard commercial conversationnel : l'utilisateur pose une question en langage
naturel dans un chat (ex. *"montre-moi le budget par pays pour Risk Advisory"*), un
LLM (Groq / Llama 3.3) extrait une intention structurée et validée, celle-ci est
traduite en requête SQL paramétrée sur MySQL, et le résultat est affiché sous forme
de graphique (Vega-Lite), de carte KPI ou de tableau. Une alerte quotidienne (email +
bannière) prévient aussi des opportunités dont l'échéance approche.

Stack : **FastAPI** (backend) + **MySQL/MariaDB via XAMPP** + **Groq** (LLM,
`llama-3.3-70b-versatile`) + **Vite/React** (frontend) + **APScheduler** (tâches
planifiées). Hébergement local uniquement.

## Fonctionnalités

- Chat en français libre, avec contexte multi-tour, dates relatives et requêtes de
  comparaison ("compare la France et le Maroc") ; l'historique de conversation persiste
  entre les rechargements de page (localStorage).
- 8 types de rendu au choix : barres, courbes, aires, camemberts, cartes KPI,
  tableaux, entonnoir de vente et carte de chaleur — voir `PROGRESS.md` pour le détail.
- Alertes deadlines : email quotidien (Gmail SMTP) + bannière dans le dashboard pour
  les opportunités actives (statuts clos exclus) à échéance ≤ 7 jours ; `days_remaining`
  recalculée chaque nuit depuis la deadline réelle. Rattrapée automatiquement au
  redémarrage si le serveur était éteint pile à l'heure planifiée.
- Thème clair/sombre, palette de couleurs validée pour l'accessibilité (daltonisme).
- Anti-hallucination : toute métrique/dimension/valeur de filtre non reconnue déclenche
  une demande de clarification plutôt qu'un résultat deviné.

## Prérequis

- Python 3.11+
- Node.js 18+ / npm
- [XAMPP](https://www.apachefriends.org/) avec MySQL démarré, base `devoteam_dashboard`
  déjà importée (voir `data/devoteam_dashboard_mysql.sql`)
- Une clé API [Groq](https://console.groq.com/)
- (Optionnel, pour les alertes email) un compte Gmail avec un
  [mot de passe d'application](https://myaccount.google.com/apppasswords)

## Installation

```bash
# Backend
pip install -r requirements.txt      # ou requirements-dev.txt pour lancer les tests

# Config
cp .env.example .env                 # remplir GROQ_API_KEY (les valeurs DB par défaut
                                      # correspondent à XAMPP : root, sans mot de passe)
                                      # + GMAIL_SENDER/GMAIL_APP_PASSWORD/ALERT_RECIPIENT_EMAIL
                                      # si tu veux activer les alertes email (sinon elles sont
                                      # simplement ignorées avec un avertissement dans les logs)
python init_tables.py                # crée les tables de log/cache (une seule fois)

# Frontend
cd frontend && npm install
```

## Lancer en développement (hot-reload)

Deux terminaux :

```bash
python -m uvicorn backend.main:app --reload          # API sur http://127.0.0.1:8000
```

```bash
cd frontend && npm run dev                 # UI sur http://127.0.0.1:5173 (proxy /dashboard -> :8000)
```

**Windows** : `scripts/start_dev.bat` démarre MySQL (XAMPP), l'API et le frontend en une
seule fois, puis ouvre le dashboard dans le navigateur — pratique en raccourci bureau
(icône fournie : `scripts/devoteam.ico`). Ne pas fermer les fenêtres de terminal qu'il ouvre.

## Lancer en local "prod" (un seul processus)

```bash
cd frontend && npm run build               # génère frontend/dist
cd .. && python -m uvicorn backend.main:app          # sert l'UI ET l'API sur http://127.0.0.1:8000
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/
```

La suite ne nécessite ni MySQL ni clé Groq réelle (le client Groq et la connexion DB
sont mockés dans les tests qui en ont besoin).

## Sécurité

`.env` contient des identifiants réels (clé Groq, mot de passe d'application Gmail) —
il est dans `.gitignore` et ne doit jamais être commité. Si une ancienne version de
`.env` a fini dans l'historique git, régénérez la clé Groq correspondante sur
console.groq.com et révoquez le mot de passe d'application Gmail sur
myaccount.google.com/apppasswords, plutôt que de compter sur sa suppression du dépôt.

## Structure

```
backend/              FastAPI, parsing LLM (Groq), couche SQL, génération Vega-Lite,
                       alertes deadlines (alerts.py) et maintenance (maintenance.py)
frontend/              Vite + React (build servi par FastAPI en local)
data/                  dump SQL de référence
tests/                 suite pytest (mock DB/Groq), 91 tests
Documentation/
  reports/              rapport professionnel + guide technique (.docx) et leur générateur
  planning/             brief initial et données sources du projet
```

Voir `PROGRESS.md` pour le détail des phases livrées et les limites connues.
