# Installer l'application sur un autre poste

Procédure pour déployer DevoTeam Dashboard sur un poste Windows qui n'est pas celui
du développeur, avec **les clés et la feuille de calcul de ce poste-là**.

Compter une heure la première fois, dont l'essentiel est du téléchargement.

---

> Pour voir l'application avant de l'installer :
> [démonstration guidée](https://app.arcade.software/flows/0JEAJAGmgCqMbVXfQo2R/view) (aussi dans `Demo video.url`, à la racine du projet).

> **Plus rapide :** `setup\INSTALLER_NATIF.bat` fait tout ce qui suit automatiquement et
> ne vous demande que la clé API et la feuille. Cette page reste la référence si vous
> préférez procéder à la main, ou pour comprendre ce que l'assistant fait.
>
> **Sans rien installer sur la machine que Docker Desktop** (pas de Python, Node,
> ni moteur de tableaux de bord à poser directement sur le poste) :
> `Documentation/INSTALLATION_DOCKER.md`.

## Avant le jour de l'installation

Deux choses doivent être obtenues **à l'avance**. Ce sont elles qui font échouer une
installation faite dans l'urgence, parce qu'aucune ne dépend de vous seul. Aucune
n'est un secret à protéger comme un mot de passe : la clé Sheets est en lecture
seule, et le modèle de chat tourne en local, sans clé du tout.

> Fiche à garder, avec les liens exacts et le détail de chaque étape :
> [`OBTENIR_LES_ACCES.md`](OBTENIR_LES_ACCES.md).

### 1. Une clé API Google Sheets, en lecture seule

L'application ne se connecte pas avec un compte de service ni un fichier JSON : une
simple clé API suffit, parce qu'elle ne fait jamais que LIRE le Sheet.

- Sur [console.cloud.google.com](https://console.cloud.google.com) → *API et
  services* → *Bibliothèque* → activer **Google Sheets API**.
- *API et services* → *Identifiants* → *Créer des identifiants* → **Clé API**.
- *(Recommandé)* Restreindre la clé à *Google Sheets API* uniquement.
- **Partager la feuille de calcul** → Accès général → **« Toute personne disposant
  du lien »**, rôle **Lecteur**.

> Une clé API n'a pas d'identité Google propre : elle ne peut lire que ce qui est
> déjà accessible par lien, quel que soit son propriétaire — d'où l'absence d'une
> adresse précise à qui partager, contrairement à un compte de service. C'est aussi
> pourquoi le rôle Lecteur suffit : une clé API ne permet jamais d'écrire, donc rien
> ne peut échouer plus tard faute d'un rôle Éditeur qu'on aurait oublié.
>
> À peser côté entreprise : « toute personne disposant du lien » est un partage
> plus large qu'un compte de service ciblé. Si ce n'est pas acceptable pour cette
> feuille, il faut soit y limiter les données sensibles, soit revenir à une
> authentification par compte de service (non couverte par ce guide).

### 2. L'identifiant de la feuille

Il est dans son URL, entre `/d/` et `/edit` :

```
https://docs.google.com/spreadsheets/d/IDENTIFIANT_DE_LA_FEUILLE/edit
```

Relever aussi le **nom de l'onglet** qui contient les données.

### Le modèle de chat (Ollama) — rien à préparer

Aucune clé, aucun compte : `scripts\install.bat` détecte Ollama, dit où
l'installer s'il manque ([ollama.com/download](https://ollama.com/download)), et
télécharge automatiquement le modèle (`qwen2.5:7b-instruct-q4_K_M`, ~4,7 Go) s'il
n'est pas déjà présent. Ça peut prendre plusieurs minutes selon la connexion.

---

## Le jour de l'installation

### Étape 1 — Copier le dossier

Copier le dossier complet du projet sur le poste, par exemple dans
`C:\DevoTeam\devoteam_dashboard`.

Ce qu'il ne faut **pas** copier : `.venv`, `node_modules`, `frontend/dist`,
`__pycache__`. Ils sont propres à une machine et seront reconstruits. S'ils sont là,
l'installation les remplacera de toute façon.

Ne copiez **jamais** votre `.env` : ce poste utilisera sa propre clé.

### Étape 2 — Installer les prérequis

Trois logiciels, à prendre dans cet ordre :

| Logiciel | Où | Remarque |
|---|---|---|
| **Python 3.11+** | [python.org](https://www.python.org/downloads/) | Cocher **« Add python.exe to PATH »** pendant l'installation |
| **Node.js LTS** | [nodejs.org](https://nodejs.org/) | Sert à compiler l'interface, une seule fois |
| **Git pour Windows** | [git-scm.com](https://git-scm.com/download/win) | Fournit Git Bash, nécessaire à l'étape suivante |

La case « Add python.exe to PATH » est le piège classique : sans elle, tout le reste
échoue avec un message qui ne la mentionne jamais.

### Étape 3 — Installer le moteur de tableaux de bord

Ouvrir **Git Bash** et lancer :

```bash
curl -LsSf https://getbruin.com/install/dac | sh
```

Cela installe `dac.exe` et `bruin.exe` dans `%USERPROFILE%\.local\bin`.

> L'installeur **n'ajoute pas** ce dossier au PATH du système, et ce n'est pas un
> problème : les lanceurs de l'application s'en chargent. En revanche, si vous lancez
> `dac` à la main un jour, il faudra le faire vous-même — sinon le serveur démarre
> normalement et chaque visuel affiche une erreur.

### Étape 4 — Lancer l'installation

Double-cliquer sur **`scripts\install.bat`**.

Il vérifie les prérequis, crée un environnement Python isolé, installe les
dépendances aux versions épinglées, compile l'interface, **vérifie Ollama et
télécharge le modèle de chat s'il manque**, et crée les raccourcis du Bureau.

À un moment il ouvre le **Bloc-notes** sur le fichier `.env`. Remplir :

```ini
GOOGLE_SHEETS_API_KEY=     la clé API de l'étape 1 (lecture seule)
GOOGLE_SHEET_ID=           l'identifiant relevé dans l'URL
GOOGLE_SHEET_TAB=          le nom de l'onglet

# Facultatif — l'email de rappel quotidien
GMAIL_SENDER=
GMAIL_APP_PASSWORD=
ALERT_RECIPIENT_EMAIL=     une adresse, ou plusieurs séparées par une virgule

# Facultatif — vide = valeurs par défaut (http://localhost:11434, qwen2.5:7b-instruct-q4_K_M)
OLLAMA_HOST=
OLLAMA_MODEL=
```

**Enregistrer**, puis fermer le Bloc-notes pour que l'installation reprenne.

> La clé se saisit ici, dans un fichier, et jamais dans une console : une clé
> tapée dans un terminal reste dans son historique. Le fichier `.env` est exclu du
> dépôt Git.

### Étape 5 — Vérifier

```
.venv\Scripts\python.exe scripts\verifier_installation.py
```

C'est l'étape qui compte. Le script contrôle chaque maillon séparément et affiche un
verdict par point :

- Python, dépendances, interface compilée
- `.env` et chacune de ses variables
- la feuille : lecture par clé API (aucune écriture à tester — une clé API n'écrit
  jamais)
- les colonnes attendues, et les **valeurs inconnues** dans les colonnes de choix
- le modèle local — service Ollama joignable, modèle bien téléchargé
- `dac.exe`, `bruin.exe`, et les serveurs

Tant qu'il reste un point bloquant, l'application ne fonctionnera pas correctement.
Corriger, puis relancer le script — il ne modifie rien et peut être rejoué autant de
fois que nécessaire.

### Étape 6 — Lancer et tester

Double-cliquer sur **« DevoTeam Dashboard (Production) »** sur le Bureau, attendre une
quinzaine de secondes, puis :

```
.venv\Scripts\python.exe scripts\test_fonctionnel.py
```

C'est le test qui répond à la vraie question : **les chiffres sont-ils justes sur les
données de ce poste ?** Il ne compare rien à des valeurs écrites d'avance — pour
chaque question, il calcule la réponse attendue depuis la feuille avec pandas, la pose
à l'application, et vérifie que le nombre annoncé est celui-là. Il fonctionne donc sur
n'importe quel jeu de données.

Il contrôle les totaux, les termes métier (offres gagnées, remises, affaires
chaudes), les répartitions, un filtre, les échéances, et que les cinq sections rendent
bien des chiffres.

Tant qu'il n'affiche pas **« TOUT EST JUSTE »**, ne pas présenter l'application.

### Étape 6 bis — Détail du lancement

Double-cliquer sur **« DevoTeam Dashboard (Production) »** sur le Bureau.

Trois fenêtres s'ouvrent et doivent rester ouvertes : le backend et les deux serveurs
de tableaux de bord. Le navigateur s'ouvre seul sur `http://127.0.0.1:8000` après une
quinzaine de secondes — le temps que le moteur de requêtes démarre à froid.

---

## Si les données de ce poste ne sont pas les vôtres

C'est le point qui peut faire rater une démonstration **sans qu'aucune erreur ne
s'affiche**.

Les règles métier nomment des statuts français précis — `Offre remise`,
`Offre gagnée`, `Offre signée`, `Offre perdue`. Une feuille qui utilise d'autres
libellés produit des tableaux de bord parfaitement fonctionnels, et **vides**.

`verifier_installation.py` le signale explicitement :

```
NOTE Valeurs inconnues en colonne « status »
     Prospect, Signé, Abandonné
     -> Ces lignes seront comptées comme « Non renseigné ».
```

Deux réponses possibles :

1. **Aligner la feuille** sur les libellés attendus — le plus simple si elle est
   modifiable.
2. **Aligner le code** : ajouter les libellés dans `backend/schema_and_whitelist.py`
   (`KNOWN_VALUES`), et les rattacher aux bons groupes dans
   `backend/business_rules.py` — `SUBMITTED_STATUSES`, `WON_STATUSES`,
   `LOST_STATUSES`. Relancer `pytest tests/ -q` ensuite.

Il en va de même pour les **practices** et les **types d'opportunité**.

### Le nom des colonnes, distinct de leur contenu

Un point différent de celui ci-dessus : ce n'est plus la VALEUR d'une cellule qui
peut différer, mais le nom même d'une colonne. Une feuille métier réelle porte
souvent ses propres intitulés français — `Pays`, `Statut`, `Lead (Acheteur)`,
`Deadline` — plutôt que les noms internes anglais que le code cherche par défaut
(`country`, `status`, `buyer`, `deadline`).

L'application reconnaît déjà les intitulés suivants, en plus des noms internes, et
**sans distinction de majuscule** :

| Colonne de la feuille | Colonne interne |
|---|---|
| Pays | `country` |
| Date de création | `created_date` |
| Deadline / Practice / Budget | *(déjà identiques, à la casse près)* |
| Lead (Acheteur) | `buyer` |
| Types | `opp_type` |
| Statut | `status` |
| Financement | `funding_source` |
| Partenaire | `partner` |
| Offre financière | `financial_offer` |
| Pondéré à | `win_probability` |
| Description de la prestation | `description` |
| Année Deadline, Jours Rest., Pondération | colonnes calculées, affichées dans les tableaux de bord — jamais lues ni réécrites dans le Sheet |

**La colonne `id` est la seule totalement facultative.** Une feuille métier qui n'en
a jamais eu n'a besoin d'aucun ajout : l'application attribue un identifiant à
chaque ligne en mémoire à chaque chargement. Une limite honnête à connaître : la
lecture se fait par clé API, qui ne permet jamais d'écrire — cet identifiant n'est
donc **jamais réécrit dans le Sheet**, contrairement à l'ancien compte de service.
Il reste stable d'un chargement à l'autre si le Sheet porte sa propre colonne
`id` ; sinon, il n'est valable que pour le chargement en cours (attribué dans
l'ordre des lignes). Sans conséquence pour l'usage courant (rien dans
l'application ne s'appuie sur sa stabilité), mais à savoir si vous comptiez vous y
référer d'une session à l'autre.

Si la feuille porte un intitulé qui n'est reconnu ni comme nom interne ni comme
alias, il est simplement ignoré comme une colonne en trop — la liste des alias se
trouve dans `backend/data_store.py` (`_ALIAS_COLONNES`), à compléter au besoin de
la même façon que les statuts ci-dessus.

---

## Rendre l'application accessible à distance (ngrok)

Pour la faire essayer depuis un autre poste sans rien installer chez le testeur.

### Il faut DEUX tunnels, pas un

C'est le point qui surprend, et son échec est silencieux. Le tableau de bord est
chargé en `<iframe>` **par le navigateur du visiteur**. Lui transmettre
`127.0.0.1:8321` revient à lui faire interroger *sa propre* machine : le chat
répondrait normalement et **tous les tableaux de bord resteraient vides**, sans
qu'une seule requête n'échoue.

Un proxy sous préfixe ne règle rien : `dac serve` n'a aucune option de chemin de
base et sert ses ressources en chemins absolus. Il lui faut sa propre origine.

### La procédure

```
scripts\start_public.bat
```

Il ouvre le tunnel des tableaux de bord, vous demande son URL, redémarre le backend
en lui transmettant cette adresse, puis ouvre le tunnel de l'application. L'URL à
partager est celle du port 8000.

À la main, si vous préférez :

```
ngrok http 8321                          puis relever l'URL sur http://127.0.0.1:4040
set DAC_PUBLIC_URL=https://xxxx.ngrok-free.app
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
ngrok http 8000
```

`DAC_PUBLIC_URL` est lu à l'**exécution**, pas à la compilation : une URL de tunnel
change à chaque session, et recompiler l'interface pour cela n'aurait aucun sens.

### Deux choses à savoir

**La page d'avertissement ngrok.** À la première visite, ngrok affiche un
interstitiel. Dans une iframe, il s'affiche *à la place* du tableau de bord et
ressemble à une panne. Ouvrez d'abord l'URL de DAC dans un onglet, cliquez
« Visit Site », puis rechargez l'application.

**L'URL n'est pas secrète.** Elle donne accès aux données commerciales à quiconque
la possède, et elle est publique sur Internet. Protégez-la, et coupez les tunnels dès
l'essai terminé :

```yaml
# ngrok.yml
tunnels:
  app:
    addr: 8000
    proto: http
    basic_auth: ["devoteam:un-mot-de-passe-solide"]
  dac:
    addr: 8321
    proto: http
    basic_auth: ["devoteam:un-mot-de-passe-solide"]
```

---

## Pannes fréquentes

| Symptôme | Cause | Geste |
|---|---|---|
| **Une partie** des visuels en erreur au 1er lancement (`could not create file duckdb.dll`) | Plusieurs requêtes installaient le pilote DuckDB en même temps | Mettre à jour (`git pull`) : le lanceur l'installe désormais une fois, seul |
| Tous les visuels en erreur, la page s'affiche | `bruin.exe` absent ou hors du PATH | Refaire l'étape 3, relancer par le raccourci |
| « Serveur de dashboards injoignable » | DAC pas démarré | Relancer par le raccourci, ne pas fermer les fenêtres |
| Tableaux de bord vides, aucune erreur | Statuts non reconnus | Voir la section ci-dessus |
| « Accès refusé (403) » à la lecture du Sheet | Feuille pas encore partagée en « Lecteur, toute personne disposant du lien » | Repartager depuis Google Sheets (voir étape 1) |
| Erreur « 429 » ou 403 intermittent sur la lecture du Sheet | Quota gratuit de l'API Sheets dépassé (nombreuses requêtes rapprochées) | Attendre une minute ; sans rapport avec la clé ou le partage |
| « GOOGLE_SHEETS_API_KEY manquant » ou « GOOGLE_SHEET_ID manquant » | `.env` absent ou vide | Refaire l'étape 4 |
| Les fenêtres s'ouvrent puis se referment, rien ne démarre | Lanceur antérieur à la correction des chemins à espaces | Mettre le projet à jour (`git pull`) |
| `python` non reconnu | Case PATH décochée | Réinstaller Python en cochant la case |
| Tableaux vides derrière une URL ngrok | Un seul tunnel, ou `DAC_PUBLIC_URL` non renseignée | Voir la section « accessible à distance » |
| Une page « You are about to visit… » à la place des visuels | Interstitiel ngrok dans l'iframe | Ouvrir l'URL de DAC dans un onglet, cliquer « Visit Site » |
| Le mode sombre reste clair | Second serveur DAC arrêté | Sans effet sur le reste — l'application retombe volontairement sur le thème clair |

---

## Mettre à jour ensuite

Remplacer les fichiers du projet — en gardant `.env` — puis :

```
scripts\install.bat
```

Il recompile l'interface et remet les dépendances à niveau. Rien à défaire.
