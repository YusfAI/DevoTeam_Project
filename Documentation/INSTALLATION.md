# Installer l'application sur un autre poste

Procédure pour déployer DevoTeam Dashboard sur un poste Windows qui n'est pas celui
du développeur, avec **les clés et la feuille de calcul de ce poste-là**.

Compter une heure la première fois, dont l'essentiel est du téléchargement.

---

## Avant le jour de l'installation

Trois choses doivent être obtenues **à l'avance**. Ce sont elles qui font échouer une
installation faite dans l'urgence, parce qu'aucune ne dépend de vous seul.

### 1. Un compte de service Google, et le partage de la feuille

L'application ne se connecte pas avec un compte humain : elle utilise un **compte de
service**, dont l'identité est un fichier JSON.

- Si vous en avez déjà un, réutilisez-le. Sinon, en créer un sur
  [console.cloud.google.com](https://console.cloud.google.com) → *IAM et
  administration* → *Comptes de service* → *Créer*, puis *Clés* → *Ajouter une clé* →
  *JSON*.
- Activer l'**API Google Sheets** sur le projet concerné.
- Ouvrir le JSON et relever la ligne `client_email` — une adresse en
  `…iam.gserviceaccount.com`.
- **Partager la feuille de calcul avec cette adresse, en tant qu'Éditeur.**

> Le rôle Éditeur n'est pas un excès de précaution. L'application **écrit** dans la
> feuille : elle attribue un identifiant aux lignes qui n'en ont pas et y réinscrit
> les colonnes calculées. Partagée en Lecteur, tout fonctionne jusqu'au premier
> enregistrement — puis échoue sans que rien n'explique pourquoi.

### 2. Une clé Gemini

À générer sur [aistudio.google.com](https://aistudio.google.com) → *Get API key*.
L'offre gratuite suffit largement à l'usage.

### 3. L'identifiant de la feuille

Il est dans son URL, entre `/d/` et `/edit` :

```
https://docs.google.com/spreadsheets/d/IDENTIFIANT_DE_LA_FEUILLE/edit
```

Relever aussi le **nom de l'onglet** qui contient les données.

---

## Le jour de l'installation

### Étape 1 — Copier le dossier

Copier le dossier complet du projet sur le poste, par exemple dans
`C:\DevoTeam\devoteam_dashboard`.

Ce qu'il ne faut **pas** copier : `.venv`, `node_modules`, `frontend/dist`,
`__pycache__`. Ils sont propres à une machine et seront reconstruits. S'ils sont là,
l'installation les remplacera de toute façon.

Ne copiez **jamais** votre `.env` ni votre `credentials/` : ce poste utilisera ses
propres clés.

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
dépendances aux versions épinglées, compile l'interface et crée les raccourcis du
Bureau.

À un moment il ouvre le **Bloc-notes** sur le fichier `.env`. Remplir :

```ini
GOOGLE_API_KEY=            la clé Gemini de l'étape 2
GOOGLE_SHEET_ID=           l'identifiant relevé dans l'URL
GOOGLE_SHEET_TAB=          le nom de l'onglet

# Facultatif — l'email de rappel quotidien
GMAIL_SENDER=
GMAIL_APP_PASSWORD=
ALERT_RECIPIENT_EMAIL=
```

**Enregistrer**, puis fermer le Bloc-notes pour que l'installation reprenne.

> Les clés se saisissent ici, dans un fichier, et jamais dans une console : une clé
> tapée dans un terminal reste dans son historique. Le fichier `.env` est exclu du
> dépôt Git.

### Étape 5 — Déposer le compte de service

Copier le fichier JSON dans le dossier `credentials\` du projet, sous le nom :

```
credentials\google_service_account.json
```

### Étape 6 — Vérifier

```
.venv\Scripts\python.exe scripts\verifier_installation.py
```

C'est l'étape qui compte. Le script contrôle chaque maillon séparément et affiche un
verdict par point :

- Python, dépendances, interface compilée
- `.env` et chacune de ses variables
- le compte de service — **et il affiche l'adresse à qui partager la feuille**
- la feuille : lecture, **puis écriture réellement testée**
- les colonnes attendues, et les **valeurs inconnues** dans les colonnes de choix
- la clé Gemini, par un vrai appel
- `dac.exe`, `bruin.exe`, et les serveurs

Tant qu'il reste un point bloquant, l'application ne fonctionnera pas correctement.
Corriger, puis relancer le script — il ne modifie rien et peut être rejoué autant de
fois que nécessaire.

### Étape 7 — Lancer et tester

Double-cliquer sur **« DevoTeam Dashboard (Production) »** sur le Bureau, attendre une
quinzaine de secondes, puis :

```
.venv\Scripts\python.exe scripts	est_fonctionnel.py
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

### Étape 7 bis — Détail du lancement

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

---

## Pannes fréquentes

| Symptôme | Cause | Geste |
|---|---|---|
| Tous les visuels en erreur, la page s'affiche | `bruin.exe` absent ou hors du PATH | Refaire l'étape 3, relancer par le raccourci |
| « Serveur de dashboards injoignable » | DAC pas démarré | Relancer par le raccourci, ne pas fermer les fenêtres |
| Tableaux de bord vides, aucune erreur | Statuts non reconnus | Voir la section ci-dessus |
| Les données ne se rafraîchissent pas | Feuille partagée en Lecteur | Repartager en **Éditeur** |
| « GOOGLE_SHEET_ID manquant » | `.env` absent ou vide | Refaire l'étape 4 |
| `python` non reconnu | Case PATH décochée | Réinstaller Python en cochant la case |
| Le mode sombre reste clair | Second serveur DAC arrêté | Sans effet sur le reste — l'application retombe volontairement sur le thème clair |

---

## Mettre à jour ensuite

Remplacer les fichiers du projet — en gardant `.env` et `credentials/` — puis :

```
scripts\install.bat
```

Il recompile l'interface et remet les dépendances à niveau. Rien à défaire.
