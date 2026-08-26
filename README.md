# DevoTeam Dashboard

Dashboard commercial conversationnel : l'utilisateur pose une question en langage
naturel dans un chat (ex. *"montre-moi le budget par pays pour Risk Advisory"*), un
LLM (Google Gemini) extrait une intention structurée et validée, celle-ci est
traduite en requête sur les données chargées depuis Google Sheets, et la réponse
s'affiche sous forme d'un **dashboard complet** (plusieurs graphiques, KPI et
tableaux partageant les filtres de la question), rendu par Bruin DAC. Une alerte
quotidienne (email + bannière) prévient aussi des opportunités dont l'échéance
approche.

Stack : **FastAPI** (backend) + **Google Sheets + pandas** (source de données,
chargée en mémoire) + **Google Gemini** (LLM, `gemini-flash-lite-latest`) +
**Bruin DAC + DuckDB** (dashboards « as code ») + **Vite/React** (frontend) +
**APScheduler** (tâches planifiées). Hébergement local uniquement, sans base de
données à installer.

## Fonctionnalités

- Chat en français libre, avec contexte multi-tour, dates relatives et requêtes de
  comparaison ("compare la France et le Maroc") ; l'historique de conversation persiste
  entre les rechargements de page (localStorage).
- **Un seul tableau de bord, jamais deux pages** : il s'ouvre sur la vue d'ensemble
  et chaque question le transforme (5 à 7 widgets — totaux du périmètre, graphique
  principal, angle complémentaire, pipeline, détail, tous filtrés à l'identique). Au
  rechargement de la page, retour à la vue d'ensemble. Voir
  `Documentation/WORKFLOW.md` pour le traçage complet.
- **Transitions en fondu** : deux cadres se superposent le temps d'un changement, le
  nouveau ne devenant visible qu'une fois chargé. L'écran n'est jamais vidé ; un fil
  d'attente en tête indique le travail en cours.
- **« Ajoute … » complète au lieu de remplacer** : « ajoute le budget par pays »
  place un widget de plus sur le tableau de bord affiché. Un ajout déjà présent est
  signalé comme tel plutôt qu'annoncé à tort.
- **Tout se pilote par la phrase tapée** : « en camembert », « top 5 », « par
  practice », « sans filtre » ajustent le dashboard affiché en héritant du contexte,
  sans appel au modèle et sans bouton à cliquer. Une demande dont un seul mot n'est
  pas compris repart par le chemin complet plutôt que d'hériter d'un filtre que
  l'utilisateur n'a pas redemandé. L'application dit à chaque fois ce qui a changé
  (« axe : pays → practice ; filtres retirés »), ou que la demande n'a rien changé.
- **Historique des analyses** : ouvert depuis l'en-tête du tableau de bord, un volet
  groupé par jour rassemble toutes les questions posées et signale celle qui est
  affichée ; chacune rouvre le tableau de bord qu'elle avait produit.
- **Affaires perdues exclues par défaut** : les statuts d'échec (Offre perdue,
  Infructueux, NO GO, Hors scope, Non shortlisté) — 66 M€ sur 164 M€ — sortent de tous
  les chiffres et de tous les graphiques, sauf si la question porte explicitement sur
  un statut. Un « budget total » incluant les affaires mortes n'aide pas à décider.
- **Type de graphique arbitré sur les données**, pas sur les mots : un camembert
  demandé sur 19 pays devient des barres, et l'explication s'affiche sous le
  graphique. Une moyenne ne forme jamais des parts d'un tout.
- **Vue d'ensemble versionnée** : la page d'accueil est un dashboard YAML relu en
  revue (`dac/dashboards/accueil.yml`), avec filtres interactifs de période et de
  practice. Elle répond d'abord aux trois questions du métier — combien d'offres
  remises sur la période, comment elles se répartissent par practice, et ce qu'elles
  sont devenues (gagnées / perdues / en attente) — puis donne l'état du portefeuille,
  le pipeline et les échéances urgentes. 19 widgets.
- **Affaires chaudes** : les offres remises encore en jeu dont la probabilité de
  gain atteint 80 % — le pipeline le plus proche de se concrétiser. Trois KPI, un
  graphique par practice et le détail opportunité par opportunité sur la vue
  d'ensemble. « Affaire chaude » et « offre pondérée » sont deux noms du même
  concept et résolvent vers la même définition (`business_rules.HOT_DEAL_STATUSES`).
- **« Offre remise » est un terme métier, pas un statut** : le statut décrit l'état
  *courant*, donc une offre partie chez le client et gagnée depuis n'y figure plus.
  Compter ce seul statut donnait 4 offres là où 57 avaient été déposées. La
  définition (`business_rules.SUBMITTED_STATUSES`) vaut aussi bien pour le dashboard
  que pour le chat.
- 9 types de rendu : barres, courbes, aires, camemberts (pourcentage affiché sur
  chaque part), cartes KPI, tableaux, entonnoir de vente, nuage de points et carte de
  chaleur. Les catégories d'un graphique ont chacune leur couleur, la même d'un
  graphique à l'autre du même tableau de bord.
- Alertes deadlines : email quotidien (Gmail SMTP) + bannière dans le dashboard pour
  les opportunités actives (statuts clos exclus) à échéance ≤ 7 jours. Rattrapée
  automatiquement au redémarrage si le serveur était éteint pile à l'heure planifiée.
- Anti-hallucination : toute métrique/dimension/valeur de filtre non reconnue déclenche
  une demande de clarification plutôt qu'un résultat deviné. **Le LLM n'écrit jamais
  de SQL** — il ne produit qu'une intention validée, traduite ensuite par du code.
- Google Sheets comme source de données unique : l'application lit directement le
  Sheet (via pandas), en mémoire, rafraîchi toutes les 15 minutes + au démarrage +
  sur demande (`POST /sheets/sync`). Le Sheet sert aussi de formulaire d'ajout/
  modification d'opportunités — plus simple à éditer qu'une base de données. Une
  cellule illisible (statut inconnu, date invalide, montant non numérique) coûte la
  cellule, jamais la ligne : elle est remplacée par « Non renseigné » et l'opportunité
  est conservée avec son budget, son échéance et son client. Chaque remplacement est
  recensé — colonne, valeur d'origine, numéro de ligne — dans `GET /data/quality` et
  le dashboard « Qualité des données », sans quoi tolérer reviendrait à corrompre les
  données en silence.

## Prérequis

- Python 3.11+
- Node.js 18+ / npm
- Une clé API [Google AI Studio](https://aistudio.google.com/apikey)
- Un compte de service Google avec accès au Sheet source (voir "Google Sheets"
  ci-dessous — obligatoire, l'application ne fonctionne pas sans données)
- (Optionnel, pour les alertes email) un compte Gmail avec un
  [mot de passe d'application](https://myaccount.google.com/apppasswords)

## Installation

```bash
# Backend
pip install -r requirements.txt      # ou requirements-dev.txt pour lancer les tests

# Config
cp .env.example .env                 # remplir GOOGLE_API_KEY, GOOGLE_SHEET_ID (voir
                                      # "Google Sheets" ci-dessous) + GMAIL_SENDER/
                                      # GMAIL_APP_PASSWORD/ALERT_RECIPIENT_EMAIL si tu
                                      # veux activer les alertes email (sinon elles sont
                                      # simplement ignorées avec un avertissement dans les logs)

# Frontend
cd frontend && npm install
```

## Google Sheets (source de données)

1. [console.cloud.google.com](https://console.cloud.google.com) → un projet → activer
   **"Google Sheets API"**.
2. IAM et administration → Comptes de service → créer un compte de service (aucun rôle
   GCP requis) → onglet "Clés" → Ajouter une clé → JSON → télécharge le fichier.
3. Place ce fichier dans `credentials/google_service_account.json` (dossier gitignoré —
   ne le commit jamais).
4. Ouvre ton Google Sheet → **Partager** → ajoute l'email du compte de service
   (`....iam.gserviceaccount.com`, visible dans le JSON) en **Éditeur** (pas juste
   lecteur — l'application réécrit l'id généré des nouvelles lignes dans le Sheet).
5. Renseigne `GOOGLE_SHEET_ID` (dans l'URL du Sheet) et `GOOGLE_SHEET_TAB` (le nom de
   l'onglet) dans `.env`.
6. La première ligne du Sheet doit contenir ces en-têtes exacts (n'importe quel
   ordre) : `id, country, created_date, deadline, practice, description, buyer,
   opp_type, status, budget, funding_source, partner, financial_offer,
   win_probability`. Ligne avec `id` vide = nouvelle opportunité (un id est généré et
   réécrit dans le Sheet au chargement suivant).
7. `deadline_month`, `deadline_year`, `days_remaining` et `weighted_amount` sont
   **toujours recalculés** depuis les colonnes ci-dessus — inutile (et sans effet) de
   les éditer dans le Sheet.
8. `practice`, `opp_type` et `status` doivent correspondre exactement aux valeurs
   whitelistées dans `backend/schema_and_whitelist.py` (insensible à la casse) —
   sinon la ligne est ignorée et journalisée, sans bloquer les autres.

## Dashboards « as code » (Bruin DAC)

La vue d'ensemble affichée à l'ouverture n'est pas codée en dur dans le frontend :
c'est un dashboard **versionné en YAML** (`dac/dashboards/accueil.yml`), rendu par
[Bruin DAC](https://getbruin.com/docs/dac/) — 21 types de graphiques, filtres
interactifs, grille 12 colonnes. L'UI React l'affiche en iframe (port 8321).

Installation (une seule fois, dans Git Bash sous Windows) :

```bash
curl -LsSf https://getbruin.com/install/dac | sh   # installe bruin + dac dans ~/.local/bin
```

⚠️ **L'installeur n'ajoute pas `~/.local/bin` au PATH système.** C'est indispensable :
`dac` délègue l'exécution du SQL à `bruin`, qu'il cherche dans le PATH. Sans ça, DAC
démarre normalement mais chaque widget affiche
`bruin query failed: executable file not found in %PATH%`.

`scripts/start_dev.bat` s'en charge automatiquement. Pour lancer `dac` à la main,
ajoute le dossier au PATH de ton terminal :

```bash
export PATH="$PATH:$HOME/.local/bin"     # Git Bash
```
```powershell
$env:PATH += ";$env:USERPROFILE\.local\bin"   # PowerShell
```

DAC interroge un fichier **DuckDB** (`dac/data/devoteam.db`) qui est une simple
projection en lecture seule du DataFrame de l'application, réécrite à chaque
rafraîchissement depuis le Google Sheet (`backend/duckdb_export.py`) — les données
affichées sont donc toujours les mêmes que celles du chat.

```bash
cd dac && dac validate --dir .   # vérifie la structure des dashboards
cd dac && dac check --dir .      # exécute réellement chaque requête widget
```

Les dashboards portent l'identité Devoteam via `dac/themes/devoteam.yml`, passé au
serveur avec `--template`. Ce fichier reprend les mêmes jetons que
`frontend/src/styles/tokens.css`, palette de graphiques comprise (validée pour la
vision daltonienne) : **toute modification de couleur doit être faite des deux
côtés**, sinon le chat et les dashboards divergent visuellement.

## Lancer en développement (hot-reload)

Trois terminaux (ou `scripts/start_dev.bat` sous Windows, qui lance les trois) :

```bash
python -m uvicorn backend.main:app --reload          # API sur http://127.0.0.1:8000
```

```bash
cd dac && dac serve --dir . --port 8321 --template themes/devoteam.yml
                                           # dashboards DAC sur http://localhost:8321
                                           # (PATH doit contenir ~/.local/bin — voir ci-dessus)
```

```bash
cd frontend && npm run dev                 # UI sur http://127.0.0.1:5173 (proxy /dashboard -> :8000)
```

**Windows** : `scripts/start_dev.bat` démarre l'API et le frontend en une seule fois,
puis ouvre le dashboard dans le navigateur — pratique en raccourci bureau (icône
fournie : `scripts/devoteam.ico`). Ne pas fermer les fenêtres de terminal qu'il ouvre.

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

La suite ne nécessite ni Google Sheet ni clé Google AI Studio réelle (le client
Gemini et la lecture du Sheet sont mockés dans les tests qui en ont besoin).

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
backend/
  data_store.py          chargement Google Sheet -> DataFrame pandas (source de vérité)
  db_layer.py            requêtage pandas (chat, message texte)
  llm.py                 appel Gemini, validation Pydantic, anti-hallucination
  intent_refiner.py      parseur rapide, dates relatives, garde-fous déterministes
  sql_builder.py         intention validée -> SQL DuckDB (jamais écrit par le LLM)
  dac_composer.py        composition du dashboard multi-widgets -> YAML
  duckdb_export.py       projection du DataFrame vers DuckDB (pour DAC)
  alerts.py              alertes deadlines (email + endpoint)
  response_builder.py    messages texte déterministes
  business_rules.py      règles métier indépendantes de l'affichage : ordre du pipeline,
                         exclusion des affaires perdues, choix du type de graphique
  data_quality.py        rapport des lignes rejetées et des valeurs manquantes
dac/
  .bruin.yml             connexion DuckDB (aucun secret, versionnée volontairement)
  themes/devoteam.yml    thème aux couleurs de l'application (palette CVD comprise)
  dashboards/accueil.yml vue d'ensemble versionnée, PRODUITE par
                         scripts/generate_accueil.py (étapes du pipeline et statuts
                         dérivés de business_rules.py) — ne pas éditer à la main
  dashboards/qualite.yml  dashboard de qualité des données, versionné
  dashboards/_principal.yml tableau de bord de travail, réécrit à chaque question (gitignoré)
  dashboards/_analyse_*.yml instantanés par question, pour les rouvrir (gitignorés)
  data/devoteam.db       projection DuckDB (gitignorée, régénérée)
frontend/              Vite + React (build servi par FastAPI en local)
credentials/           clé de compte de service Google (gitignoré, absent par défaut)
data/                  scheduler_state.json (état local, gitignoré) ; dump SQL
                       historique de l'ancienne base MySQL, conservé pour référence
tests/                 suite pytest (mock Gemini/Sheets), 218 tests
Documentation/
  WORKFLOW.md            traçage concret d'une question, du prompt au dashboard affiché
  reports/              rapport professionnel + guide technique (.docx) et leur générateur
  planning/             brief initial et données sources du projet
```

Voir `PROGRESS.md` pour le détail des phases livrées et les limites connues.
