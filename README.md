# DevoTeam Dashboard

**Tableau de bord commercial conversationnel.** On pose une question en français —
*« montre-moi le budget par pays pour Risk Advisory »* — et l'application répond
par un tableau de bord complet : chiffres clés, graphiques et détail, tous filtrés
sur la question. Les données viennent d'une feuille Google Sheets, lue en direct ;
le modèle de langage tourne **sur le poste**, sans clé d'API ni abonnement.

[▶ Voir la démonstration](https://app.arcade.software/flows/0JEAJAGmgCqMbVXfQo2R/view)
(sans rien installer — le lien est aussi dans `Demo video.url`)

---

## Sommaire

1. [Ce que fait l'application](#ce-que-fait-lapplication)
2. [Installation](#installation)
3. [Utilisation au quotidien](#utilisation-au-quotidien)
4. [La feuille Google Sheets](#la-feuille-google-sheets)
5. [Configuration](#configuration)
6. [Architecture](#architecture)
7. [Développement](#développement)
8. [Dépannage](#dépannage)
9. [Structure du dépôt](#structure-du-dépôt)
10. [Documentation](#documentation)
11. [Sécurité et limites connues](#sécurité-et-limites-connues)

---

## Ce que fait l'application

| | |
|---|---|
| **Un tableau de bord par question** | Chaque question compose 5 à 7 visuels cohérents — totaux, graphique principal, angle complémentaire, pipeline, détail — tous filtrés à l'identique. |
| **Cinq sections prêtes à l'emploi** | Offres remises, Affaires chaudes, Portefeuille, Pipeline, Échéances : 32 visuels versionnés, chacun avec sa phrase d'explication et ses filtres de période et de practice. |
| **Des retouches en toutes lettres** | « en camembert », « top 5 », « par practice », « ajoute le budget par pays »… modifient le tableau de bord affiché, et l'application dit ce qui a changé. |
| **Aucun chiffre inventé** | Le modèle de langage ne fait que *comprendre* la question ; le calcul est fait par du code. Une valeur inconnue, un axe inexistant ou une période hors des données sont signalés, jamais remplacés par une approximation. |
| **Alertes d'échéance** | Bandeau dans l'application et email quotidien (8 h) pour les opportunités actives dont l'échéance tombe dans les 7 jours. |
| **Santé des données** | Un bouton dit si la lecture du Google Sheet fonctionne, avec les chiffres clés, les cellules à corriger dans la feuille et un aperçu des lignes. |
| **Changer de feuille sans terminal** | Un bouton pour lier une autre feuille Google : ses onglets sont proposés, elle est testée avant d'être utilisée. |
| **Arrêt propre** | Une icône sur le Bureau arrête l'application et libère ses ports et la mémoire du modèle. |

Autres détails : historique des analyses (rouvrir une analyse passée), mode clair et
sombre jusque dans les graphiques, zoom du tableau de bord, ouverture dans un onglet
pour imprimer ou enregistrer en PDF, montants en dinars (DT), palette lisible par les
daltoniens.

---

## Installation

### Méthode recommandée : `INSTALLER.bat` (Docker)

Un seul fichier installe tout — Docker Desktop, le modèle de langage (Ollama),
l'application — puis vérifie que les chiffres affichés sont justes. Il ne demande
que le lien de la feuille Google et le nom de son onglet.

**Avant de commencer**, sur le poste :

- Windows 11 23H2 ou plus récent (ou Windows 10 22H2), 64 bits ;
- droits administrateur, virtualisation activée dans le BIOS ;
- ~20 Go libres, 16 Go de RAM conseillés ;
- un accès Internet non filtré (≈ 9 Go à télécharger) ;
- une licence Docker Desktop si l'entreprise dépasse 250 personnes ou 10 M$ de CA ;
- **Git pour Windows** ([git-scm.com](https://git-scm.com/download/win), options par défaut) ;
- la feuille Google partagée en **Lecteur — « toute personne disposant du lien »**.

**Puis :**

```
cd C:\
mkdir DevoTeam && cd DevoTeam
git clone --branch Version_2 https://github.com/YusfAI/DevoTeam_Project.git
```

Double-cliquer sur **`DevoTeam_Project\INSTALLER.bat`** et suivre ses sept étapes.
Il s'arrête volontairement après avoir installé Docker Desktop : redémarrer Windows,
ouvrir Docker Desktop une fois (et cocher *Settings › General › Start Docker Desktop
when you sign in*), puis le relancer — il reprend là où il s'était arrêté.
L'installation est terminée quand il affiche **« TOUT EST JUSTE »**.

> - **`--branch Version_2` est indispensable** : la branche `main` est une version
>   antérieure.
> - **`git clone`, jamais « Download ZIP »** : le dossier `.git` est nécessaire au
>   moteur des tableaux de bord ; sans lui, ils restent vides.
> - **Hors de OneDrive** : un dossier synchronisé peut verrouiller les fichiers que
>   l'application réécrit.

Compter 45 minutes à 1 h 30 sur un poste neuf. Guide pas à pas, avec captures des
messages et dépannage : **[`Installing DevoTeam Dashboard.pdf`](Installing%20DevoTeam%20Dashboard.pdf)**
(en anglais) ou [`Documentation/INSTALLATION_DOCKER.md`](Documentation/INSTALLATION_DOCKER.md).

### Alternative sans Docker

Si Docker ne peut pas être installé : **`setup\INSTALLER_NATIF.bat`** installe
Python, les dépendances, l'interface et le moteur des tableaux de bord directement
sur le poste. Voir [`setup/README.md`](setup/README.md) et
[`Documentation/INSTALLATION.md`](Documentation/INSTALLATION.md).

---

## Utilisation au quotidien

### Démarrer, arrêter

| Action | Comment |
|---|---|
| **Démarrer** | Raccourci **« DevoTeam Dashboard (Docker) »** sur le Bureau — l'application s'ouvre sur http://127.0.0.1:8000. Docker Desktop doit tourner (il démarre avec Windows si le réglage a été coché). |
| **Arrêter** | Raccourci **« Arrêter DevoTeam Dashboard »** (icône marche/arrêt) : arrête l'application, libère les ports 8000 / 8321 / 8322 et la mémoire du modèle (~5 Go). Docker Desktop et Ollama restent en arrière-plan ; un nouveau démarrage prend une dizaine de secondes. |
| **Vérifier** | Bouton **« 🩺 Santé des données »** dans l'application (voir plus bas), ou, pour un contrôle complet des chiffres : `docker compose exec -e TEST_DAC_URL=http://dac-light:8321 backend python scripts/test_fonctionnel.py` → « TOUT EST JUSTE ». |

### Poser des questions

Taper la question dans le champ en haut du chat. Quelques formulations :

| Question | Réponse |
|---|---|
| « Budget par practice » | répartition du budget, graphique et détail |
| « Top 5 des pays par budget » | classement des cinq premiers pays |
| « Combien d'offres gagnées ? » | nombre d'offres gagnées ou signées |
| « Que sont devenues les offres remises ? » | gagnées / perdues / en attente |
| « Compare la France et le Maroc » | comparaison des deux pays |
| « Combien d'offres remises depuis janvier 2026 ? » | période en mois nommés |
| « Liste des opportunités urgentes (< 7 jours) » | échéances proches, en tableau |
| « en camembert », « par statut », « sans filtre » | retouche du tableau de bord affiché |

Les questions courantes reçoivent une réponse immédiate ; les formulations plus
libres passent par le modèle de langage — quelques secondes, plusieurs dizaines sans
carte graphique, la première étant la plus lente (chargement du modèle).

### Les boutons de l'interface

| Bouton | Où | Rôle |
|---|---|---|
| 🔗 **Lier une feuille Google** | en-tête du chat | Choisir la feuille lue par l'application (voir ci-dessous). |
| 🗑️ | en-tête du chat | Effacer la conversation. |
| ☀️ / 🌙 | en-tête du chat | Mode clair ou sombre. |
| 🩺 **Santé des données** | en-tête du tableau de bord | État de la lecture du Google Sheet, chiffres clés, cellules à corriger, aperçu des lignes, et « Relire la feuille maintenant ». |
| 🕘 **Historique** | en-tête du tableau de bord | Toutes les analyses, groupées par jour ; chacune rouvre son tableau de bord. |
| ⧉ **Ouvrir en grand** | en-tête du tableau de bord | Le tableau de bord dans un onglet — pour l'imprimer ou l'enregistrer en PDF. |
| − 100 % + | en-tête du tableau de bord | Taille d'affichage des graphiques. |
| ← **Tableau de bord principal** | en-tête du tableau de bord | Revenir à la vue d'ensemble depuis une analyse. |

### Santé des données

Le bouton **🩺 Santé des données** répond à la question « la lecture du Google Sheet
marche-t-elle ? » :

- **un verdict** : la lecture fonctionne / fonctionne avec des points à vérifier /
  échoue — avec la cause en clair et le geste à faire (feuille non partagée, lien
  erroné, connexion…) ;
- **la source** : lien vers la feuille, onglet, date et durée de la dernière lecture,
  état du moteur des tableaux de bord ;
- **les chiffres clés** : lignes chargées et ignorées, cellules à corriger, colonnes
  reconnues, période couverte, nombre de pays et de practices, budget total ;
- **les cellules à corriger dans la feuille** (ligne, colonne, valeur) — une valeur
  non reconnue garde sa ligne mais compte pour « Non renseigné » ;
- **un aperçu** des cinq premières lignes.

« Relire la feuille maintenant » relance la lecture sans attendre le rafraîchissement
automatique (toutes les 15 minutes). Si une lecture échoue, l'application continue
d'afficher les données de la lecture précédente — et l'écran le signale.

### Lier une autre feuille Google

Le bouton **🔗 Lier une feuille Google** remplace toute manipulation de fichier ou
de terminal :

1. partager la feuille en **Lecteur — « toute personne disposant du lien »** ;
2. ouvrir l'onglet des opportunités, copier l'adresse du navigateur, la coller ;
3. choisir l'onglet dans la liste — l'onglet du lien collé est présélectionné ;
4. **① Tester la lecture** : la feuille est lue exactement comme l'application la
   lira, avec le même diagnostic que « Santé des données » ;
5. **② Utiliser cette feuille** : activé seulement si le test a réussi. La feuille
   est enregistrée dans `.env` et chargée aussitôt — chat, alertes et tableaux de bord.

Un onglet inexistant, des colonnes obligatoires absentes ou un onglet vide bloquent
la liaison. Le changement n'est accepté que depuis l'application elle-même, sur le
poste qui l'héberge.

### Mettre à jour l'application

```
cd C:\DevoTeam\DevoTeam_Project
git pull
docker compose up -d --build
```

La configuration (`.env`) n'est jamais écrasée par une mise à jour. Ne modifier
aucun fichier suivi par Git sur un poste d'utilisation : `git pull` refuserait de
mettre à jour.

---

## La feuille Google Sheets

L'application la **lit seulement** — par son lien d'export public, sans clé d'API ni
compte de service — et ne peut rien y modifier. Elle est relue au démarrage, toutes
les 15 minutes, et à la demande.

### Colonnes

La première ligne porte les en-têtes, dans n'importe quel ordre et sans distinction
de majuscules. Les intitulés français de la feuille métier sont reconnus :

| Colonne | Intitulés acceptés | Obligatoire |
|---|---|:-:|
| `id` | id | non — attribué à la lecture s'il manque |
| `country` | Pays | oui |
| `created_date` | Date de création | oui |
| `deadline` | Deadline | oui |
| `practice` | Practice | oui |
| `description` | Description, Description de la prestation | oui |
| `buyer` | Acheteur, Lead (acheteur) | oui |
| `opp_type` | Type, Types | oui |
| `status` | Statut | oui |
| `budget` | Budget | oui |
| `funding_source` | Financement | oui |
| `partner` | Partenaire | oui |
| `financial_offer` | Offre financière | oui |
| `win_probability` | Pondéré à | oui |

`deadline_month`, `deadline_year`, `days_remaining` et `weighted_amount` sont
recalculés à chaque lecture : inutile de les tenir à jour dans la feuille.

### Valeurs reconnues

`practice`, `opp_type` et `status` prennent leurs valeurs dans une liste fermée
([`backend/schema_and_whitelist.py`](backend/schema_and_whitelist.py)) — par exemple
Digital Transformation, Risk Advisory, Data Management pour les practices. Une cellule
non reconnue (ou une date, un montant illisible) **ne fait pas perdre la ligne** : la
valeur devient « Non renseigné » et la cellule apparaît dans *Santé des données ›
À corriger dans la feuille*.

### Règles métier appliquées aux chiffres

- **Affaires perdues exclues par défaut** (Offre perdue, Infructueux, NO GO, Hors
  scope, Non shortlisté) — sauf si la question porte explicitement sur un statut.
  C'est pourquoi le budget total des tableaux de bord est inférieur à celui de
  *Santé des données*, qui compte toutes les lignes.
- **Offres remises** : les offres effectivement déposées (offre remise, en attente,
  gagnée, signée ou perdue) dont l'échéance est passée.
- **Affaires chaudes** : statut « Offre remise », ou probabilité de gain entre 80 %
  inclus et 100 % exclu.
- **Alertes** : opportunités actives (statuts clos exclus) à échéance dans les 7 jours.

---

## Configuration

Le fichier `.env` à la racine (créé par l'installateur depuis `.env.example`,
jamais versionné) :

| Variable | Rôle | Défaut |
|---|---|---|
| `GOOGLE_SHEET_ID` | Lien ou identifiant de la feuille — modifiable par le bouton « Lier une feuille Google » | *(obligatoire)* |
| `GOOGLE_SHEET_TAB` | Nom exact de l'onglet | `opportunities` |
| `OLLAMA_MODEL` | Modèle de langage | `qwen2.5:7b-instruct-q4_K_M` |
| `OLLAMA_HOST` | Adresse d'Ollama (imposée par Docker : `host.docker.internal`) | `http://localhost:11434` |
| `GMAIL_SENDER` | Compte Gmail qui envoie l'alerte quotidienne | *(facultatif)* |
| `GMAIL_APP_PASSWORD` | [Mot de passe d'application](https://myaccount.google.com/apppasswords) de ce compte | *(facultatif)* |
| `ALERT_RECIPIENT_EMAIL` | Destinataire(s), séparés par une virgule | *(facultatif)* |
| `DAC_PUBLIC_URL`, `DAC_DARK_PUBLIC_URL` | Adresse des tableaux de bord vue par un navigateur distant (accès par tunnel uniquement) | *(vide)* |

Sans les trois variables Gmail, tout fonctionne sauf l'email quotidien. Après une
modification manuelle de `.env` : `docker compose up -d --force-recreate` (la
feuille liée par le bouton de l'interface, elle, s'applique immédiatement).

---

## Architecture

```
 Navigateur ── http://127.0.0.1:8000 ──►  backend  (FastAPI, conteneur)
     │                                      │  ├─ lit le Google Sheet (lien d'export public)
     │                                      │  ├─ comprend la question ──► Ollama (sur le poste, :11434)
     │                                      │  ├─ calcule les chiffres (pandas) et compose le tableau de bord (YAML)
     │                                      │  └─ projette les données dans DuckDB
     └── iframe http://127.0.0.1:8321 ──►  dac-light / dac-dark (:8321 / :8322, conteneurs)
                                           exécutent le SQL des tableaux de bord sur DuckDB
```

| Brique | Technologie | Rôle |
|---|---|---|
| Interface | Vite + React | chat, tableau de bord en iframe, fenêtres de données |
| API | FastAPI (Python) | questions, alertes, santé, source de données |
| Données | Google Sheets + pandas | source unique, chargée en mémoire |
| Compréhension | Ollama · Qwen2.5-7B-Instruct | transforme la question en *intention* structurée |
| Tableaux de bord | Bruin DAC + DuckDB | tableaux de bord « as code » (YAML versionné) |
| Tâches planifiées | APScheduler | relecture toutes les 15 min, alerte à 8 h |
| Déploiement | Docker Compose | trois services + compilation de l'interface |

**Le modèle de langage n'écrit jamais de SQL ni de chiffre.** Il produit une intention
(métrique, axe, filtres, type de graphique), validée contre une liste blanche puis
traduite par du code. Le chat et les tableaux de bord lisent les mêmes données : ils
ne peuvent pas se contredire. Le trajet complet d'une question est décrit dans
[`Documentation/WORKFLOW.md`](Documentation/WORKFLOW.md).

### API

| Méthode | Route | Rôle |
|---|---|---|
| `POST` | `/dashboard` | Répond à une question et compose son tableau de bord |
| `GET` | `/alerts/deadlines` | Opportunités à échéance dans les 7 jours |
| `GET` | `/health` | État des données et du moteur des tableaux de bord |
| `GET` | `/data/quality` | Lignes rejetées et cellules remplacées |
| `GET` | `/data/source` | Santé des données : lecture, chiffres clés, aperçu |
| `POST` | `/data/source/onglets` | Onglets d'une feuille Google |
| `POST` | `/data/source/test` | Teste une feuille sans rien modifier |
| `POST` | `/data/source` | Lie une feuille (testée, puis enregistrée dans `.env`) |
| `POST` | `/sheets/sync` | Relit la feuille immédiatement |

---

## Développement

### Installation native

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
cd frontend && npm install && cd ..
curl -LsSf https://getbruin.com/install/dac | sh     # bruin + dac, dans ~/.local/bin (Git Bash)
ollama pull qwen2.5:7b-instruct-q4_K_M
copy .env.example .env                               # puis renseigner GOOGLE_SHEET_ID
```

`setup\INSTALLER_NATIF.bat` fait tout cela de façon assistée.

### Lancer

| Mode | Lanceur | Adresse | Particularités |
|---|---|---|---|
| Développement | `scripts\start_dev.bat` | http://localhost:5173 | rechargement à chaud, interface servie par Vite |
| Production native | `scripts\start_prod.bat` | http://127.0.0.1:8000 | interface compilée, un seul worker |
| Docker | `scripts\start_docker.bat` | http://127.0.0.1:8000 | ce qu'utilise un poste installé par `INSTALLER.bat` |
| Accès distant | `scripts\start_public.bat` | URL du tunnel | voir `DAC_PUBLIC_URL` |

Les raccourcis du Bureau se recréent avec
`powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1` — ceux des
modes développement et production seulement si l'installation native existe.

### Tests

```bash
pytest tests/          # 680 tests
```

Presque tous tournent hors ligne (modèle et Google Sheet simulés). Exceptions :
neuf tests comparent les deux moteurs de calcul sur la feuille réelle (`.env` et
accès Internet requis), dont cinq lisent aussi la projection DuckDB créée au premier
démarrage de l'application ; un fichier exige l'interface compilée (`frontend/dist`).
Sur un poste où l'application a tourné une fois, tous passent.

### Tâches de maintenance

| Besoin | Commande |
|---|---|
| Régénérer les cinq sections du tableau de bord principal | `python scripts/generate_accueil.py` |
| Vérifier la structure des tableaux de bord | `cd dac && dac validate --dir .` |
| Exécuter réellement chaque requête des tableaux de bord | `cd dac && dac check --dir .` |
| Régénérer le rapport, le guide technique et le guide d'installation (Word, PDF) | `python Documentation/reports/generate_docs.py` |
| Diagnostic de l'installation, maillon par maillon | `python scripts/verifier_installation.py` |

Conventions à respecter :

- les sections `dac/dashboards/accueil.yml` et `section_*.yml` sont **générées** :
  modifier `scripts/generate_accueil.py`, pas le YAML ;
- la palette de graphiques existe en deux exemplaires
  (`frontend/src/styles/tokens.css` et `dac/themes/*.yml`), qui doivent rester
  identiques — un test le vérifie ;
- les `.bat` gardent des fins de ligne Windows (`.gitattributes`) et n'affichent que
  de l'ASCII : cmd.exe rend les accents en caractères parasites.

---

## Dépannage

| Symptôme | Cause probable | Que faire |
|---|---|---|
| Le raccourci affiche « Le démarrage a échoué » | Docker Desktop n'est pas lancé | Ouvrir Docker Desktop, attendre son démarrage, relancer le raccourci |
| *Santé des données* : « Google refuse l'accès » | Feuille non partagée | Partager › Accès général › « Toute personne disposant du lien », Lecteur |
| *Santé des données* : « Colonnes obligatoires absentes » | Mauvais onglet ou en-têtes renommés | Vérifier l'onglet et la première ligne (voir [Colonnes](#colonnes)) |
| Des chiffres « Non renseigné » | Valeurs non reconnues dans la feuille | *Santé des données › À corriger dans la feuille* donne ligne et colonne |
| Le chat répond « Impossible de joindre Ollama » | Ollama arrêté | Le lancer depuis le menu Démarrer |
| Tableaux de bord vides, aucune erreur | Dossier obtenu par « Download ZIP » (pas de `.git`) | Récupérer le projet par `git clone` |
| « Un des ports 8000 / 8321 / 8322 est déjà utilisé » | Autre programme, ou instance précédente | Raccourci « Arrêter DevoTeam Dashboard », puis relancer |

Dépannage détaillé de l'installation :
[`Documentation/INSTALLATION_DOCKER.md`](Documentation/INSTALLATION_DOCKER.md#pannes-fréquentes).

---

## Structure du dépôt

```
INSTALLER.bat                       installation complète en un clic (Docker)
Installing DevoTeam Dashboard.pdf   guide d'installation pas à pas (anglais)
README.md                           ce document
Demo video.url                      démonstration en ligne
Dockerfile, docker-compose.yml      image d'exécution et services
requirements.txt                    dépendances Python, versions épinglées
requirements-dev.txt                + tests et génération des documents
.env.example                        modèle de configuration

backend/
  main.py                application FastAPI : routes, planificateur
  data_store.py          lecture du Google Sheet -> DataFrame pandas (source unique)
  data_source.py         santé des données et liaison d'une feuille (boutons de l'interface)
  llm.py                 appel au modèle local, validation, anti-hallucination
  intent_refiner.py      compréhension rapide sans modèle, dates relatives, retouches
  schema_and_whitelist.py  métriques, axes et valeurs autorisés
  db_layer.py            calculs pandas pour les réponses du chat
  sql_builder.py         intention validée -> SQL DuckDB
  dac_composer.py        composition des tableaux de bord -> YAML
  duckdb_export.py       projection des données vers DuckDB
  overview_match.py      réutilise une section quand elle répond déjà à la question
  business_rules.py      règles métier (affaires perdues, offres remises, affaires chaudes)
  response_builder.py    phrases de réponse du chat
  alerts.py              alertes d'échéance (bandeau, email)
  data_quality.py        rapport des cellules et lignes rejetées
dac/
  dashboards/            sections versionnées (générées) + tableaux de bord du chat (ignorés par Git)
  themes/                thèmes clair et sombre
frontend/src/
  App.jsx, api.js        assemblage et appels au backend
  components/            chat, tableau de bord, historique, fenêtre « Source de données »…
  styles/                jetons de design et styles
scripts/
  start_docker.bat       démarrage (raccourci « DevoTeam Dashboard (Docker) »)
  stop.bat, stop.ps1     arrêt (raccourci « Arrêter DevoTeam Dashboard »)
  start_dev.bat, start_prod.bat, start_public.bat   lancements sans Docker
  install.bat            installation native, appelée par setup/
  test_fonctionnel.py    « les chiffres sont-ils justes ? » — 15 contrôles
  verifier_installation.py  diagnostic de l'installation
  generate_accueil.py    génère les cinq sections du tableau de bord principal
  create_shortcut.ps1, maj_env.ps1, devoteam.ico   outils de l'installateur
setup/                   installation native assistée (INSTALLER_NATIF.bat)
tests/                   suite pytest — 680 tests
Documentation/           guides, rapports, journal de développement
```

---

## Documentation

| Document | Pour qui |
|---|---|
| [`Installing DevoTeam Dashboard.pdf`](Installing%20DevoTeam%20Dashboard.pdf) | la personne qui installe — pas à pas, en anglais |
| [`Documentation/OBTENIR_LES_ACCES.md`](Documentation/OBTENIR_LES_ACCES.md) | ce qu'il faut préparer avant l'installation |
| [`Documentation/INSTALLATION_DOCKER.md`](Documentation/INSTALLATION_DOCKER.md) | installation recommandée, en détail, et dépannage |
| [`Documentation/INSTALLATION.md`](Documentation/INSTALLATION.md) | installation sans Docker |
| [`Documentation/WORKFLOW.md`](Documentation/WORKFLOW.md) | le trajet d'une question, du chat au tableau de bord |
| [`Documentation/PROGRESS.md`](Documentation/PROGRESS.md) | journal de développement, phase par phase |
| [`Documentation/reports/`](Documentation/reports/) | rapport professionnel et guide technique (Word) |

Index complet : [`Documentation/README.md`](Documentation/README.md).

---

## Sécurité et limites connues

**Sécurité**

- Les services n'écoutent que sur la boucle locale (`127.0.0.1`) : l'application
  n'est joignable que depuis le poste qui l'héberge.
- `.env` (mot de passe d'application Gmail) est exclu de Git. Un secret qui aurait
  été versionné par le passé doit être **révoqué**, pas seulement supprimé.
- La feuille Google est lue par lien public : elle est lisible par quiconque obtient
  ce lien. Y placer uniquement des données compatibles avec ce mode de partage.
- Le changement de feuille refuse les requêtes venant d'un autre site que
  l'application elle-même.

**Limites connues**

- Pas d'authentification ni de gestion multi-utilisateurs : l'application est
  conçue pour un poste et un utilisateur. Le tableau de bord de travail est unique.
- Les questions au superlatif sans « par » sont lues comme un total : préférer
  « Top 5 des pays par budget » à « Quel pays a le plus gros budget ? ».
- Sans carte graphique, les questions qui passent par le modèle prennent plusieurs
  dizaines de secondes.
- Les versions de `bruin` et `dac` ne sont pas épinglées : chaque construction de
  l'image prend leur dernière version publiée.
