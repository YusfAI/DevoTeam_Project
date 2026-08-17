# DevoTeam Dashboard

Dashboard commercial conversationnel : l'utilisateur pose une question en langage
naturel dans un chat (ex. *"montre-moi le budget par pays pour Risk Advisory"*), un
LLM (Google Gemini) extrait une intention structurée et validée, celle-ci est
traduite en requête SQL paramétrée sur MySQL, et le résultat est affiché sous forme
de graphique (Vega-Lite), de carte KPI ou de tableau. Une alerte quotidienne (email +
bannière) prévient aussi des opportunités dont l'échéance approche.

Stack : **FastAPI** (backend) + **MySQL/MariaDB via XAMPP** + **Google Gemini** (LLM,
`gemini-flash-lite-latest`) + **Vite/React** (frontend) + **APScheduler** (tâches
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
- Synchronisation Google Sheets → MySQL : ajouter/modifier des opportunités depuis un
  Sheet plutôt qu'en éditant la base directement. Sens unique (le Sheet ne fait
  qu'alimenter la base) ; toutes les 15 minutes + au démarrage + sur demande
  (`POST /sheets/sync`) ; une ligne invalide (statut inconnu, date illisible…) est
  journalisée et sautée sans bloquer les autres.

## Prérequis

- Python 3.11+
- Node.js 18+ / npm
- [XAMPP](https://www.apachefriends.org/) avec MySQL démarré, base `devoteam_dashboard`
  déjà importée (voir `data/devoteam_dashboard_mysql.sql`)
- Une clé API [Google AI Studio](https://aistudio.google.com/apikey)
- (Optionnel, pour les alertes email) un compte Gmail avec un
  [mot de passe d'application](https://myaccount.google.com/apppasswords)
- (Optionnel, pour la synchro Google Sheets) voir "Synchronisation Google Sheets"
  ci-dessous

## Installation

```bash
# Backend
pip install -r requirements.txt      # ou requirements-dev.txt pour lancer les tests

# Config
cp .env.example .env                 # remplir GOOGLE_API_KEY (les valeurs DB par défaut
                                      # correspondent à XAMPP : root, sans mot de passe)
                                      # + GMAIL_SENDER/GMAIL_APP_PASSWORD/ALERT_RECIPIENT_EMAIL
                                      # si tu veux activer les alertes email (sinon elles sont
                                      # simplement ignorées avec un avertissement dans les logs)
python init_tables.py                # crée les tables de log/cache (une seule fois)

# Frontend
cd frontend && npm install
```

## Synchronisation Google Sheets (optionnel)

Le Sheet devient un formulaire d'ajout/modification d'opportunités ; l'appli continue
de lire depuis MySQL comme d'habitude (voir `backend/sheets_sync.py`).

1. [console.cloud.google.com](https://console.cloud.google.com) → un projet → activer
   **"Google Sheets API"**.
2. IAM et administration → Comptes de service → créer un compte de service (aucun rôle
   GCP requis) → onglet "Clés" → Ajouter une clé → JSON → télécharge le fichier.
3. Place ce fichier dans `credentials/google_service_account.json` (dossier gitignoré —
   ne le commit jamais).
4. Ouvre ton Google Sheet → **Partager** → ajoute l'email du compte de service
   (`....iam.gserviceaccount.com`, visible dans le JSON) en **Éditeur** (pas juste
   lecteur — la synchro écrit l'id généré des nouvelles lignes dans le Sheet).
5. Renseigne `GOOGLE_SHEET_ID` (dans l'URL du Sheet) et `GOOGLE_SHEET_TAB` (le nom de
   l'onglet) dans `.env`.
6. La première ligne du Sheet doit contenir ces en-têtes exacts (n'importe quel
   ordre) : `id, country, created_date, deadline, practice, description, buyer,
   opp_type, status, budget, funding_source, partner, financial_offer,
   win_probability`. Ligne avec `id` vide = nouvelle opportunité (l'id généré est
   réécrit dans le Sheet après import) ; `id` renseigné = mise à jour de la ligne
   MySQL correspondante.
7. `deadline_month`, `deadline_year`, `days_remaining` et `weighted_amount` sont
   **toujours recalculés** depuis les colonnes ci-dessus — inutile (et sans effet) de
   les éditer dans le Sheet.
8. `practice`, `opp_type` et `status` doivent correspondre exactement aux valeurs
   whitelistées dans `backend/schema_and_whitelist.py` (insensible à la casse) —
   sinon la ligne est ignorée et journalisée, sans bloquer les autres.

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

La suite ne nécessite ni MySQL ni clé Google AI Studio réelle (le client Gemini et la
connexion DB sont mockés dans les tests qui en ont besoin).

## Sécurité

`.env` contient des identifiants réels (clé Google AI Studio, mot de passe d'application
Gmail) — il est dans `.gitignore` et ne doit jamais être commité. Si une ancienne version
de `.env` a fini dans l'historique git, régénérez la clé sur aistudio.google.com/apikey
et révoquez le mot de passe d'application Gmail sur myaccount.google.com/apppasswords,
plutôt que de compter sur sa suppression du dépôt.

`credentials/` (clé de compte de service Google Sheets) est gitignoré au niveau du
dossier entier — jamais de fichier `.json` de credentials commité, quel que soit son nom.

## Structure

```
backend/              FastAPI, parsing LLM (Gemini), couche SQL, génération Vega-Lite,
                       alertes deadlines (alerts.py), maintenance (maintenance.py)
                       et synchro Google Sheets (sheets_sync.py)
frontend/              Vite + React (build servi par FastAPI en local)
credentials/           clé de compte de service Google (gitignoré, absent par défaut)
data/                  dump SQL de référence
tests/                 suite pytest (mock DB/Gemini/Sheets), 143 tests
Documentation/
  WORKFLOW.md            traçage concret d'une question, du prompt au graphique affiché
  reports/              rapport professionnel + guide technique (.docx) et leur générateur
  planning/             brief initial et données sources du projet
```

Voir `PROGRESS.md` pour le détail des phases livrées et les limites connues.
