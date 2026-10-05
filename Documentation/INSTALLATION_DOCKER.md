# Installer avec Docker

**La méthode recommandée.** Au lieu d'installer Python, Node.js et le moteur de
tableaux de bord directement sur la machine, un seul outil (Docker Desktop) fait
tourner les trois services dans des conteneurs isolés. Ça élimine toute une
classe de pannes propres à Windows rencontrées avec l'installation native —
chemins avec espaces, `PATH` de `bruin` introuvable, PowerShell qui prend un
message de progression pour une erreur. (Alternative si Docker ne peut pas être
installé sur le poste : `setup\INSTALLER_NATIF.bat`.)

**Durée sur un poste neuf : compter 45 minutes à 1 h 30**, dont l'essentiel en
téléchargements sans surveillance (~9 Go au total : Docker Desktop ~600 Mo,
Ollama ~1,5 Go, le modèle de chat ~4,7 Go, les images Docker ~1,6 Go), plus un
redémarrage de Windows. Le build de l'image seul, sans aucun cache, a pris
6 min 40 lors de la vérification du 5 octobre 2026. Sur un poste où Docker et
Ollama sont déjà là, 10 minutes suffisent.

---

## Le poste de destination — à vérifier avant de se déplacer

`INSTALLER.bat` installe tous les logiciels lui-même ; il ne peut en revanche
rien contre ces cinq conditions. Chacune suffit à bloquer une installation.

| Condition | Pourquoi | Comment vérifier |
|---|---|---|
| **Windows 10 (22H2) ou 11, 64 bits** | Exigence de Docker Desktop | `winver` |
| **Droits administrateur** sur le poste (ou un technicien présent) | L'installation de Docker Desktop et de WSL2 demande une élévation (fenêtre UAC) | Clic droit sur un programme → « Exécuter en tant qu'administrateur » doit être possible |
| **Virtualisation activée** dans le BIOS/UEFI | Docker Desktop tourne sur WSL2, qui en dépend | Gestionnaire des tâches → Performances → Processeur → « Virtualisation : Activé » |
| **~20 Go libres** sur `C:` et **16 Go de RAM** conseillés | ~9 Go téléchargés, puis images et modèle décompressés ; le modèle occupe ~5 Go de RAM | Explorateur → Ce PC ; `INSTALLER.bat` affiche aussi la RAM détectée |
| **Accès Internet sans filtrage** vers `github.com`, `docker.com`, `docker.io`, `ollama.com`, `getbruin.com`, `pypi.org`, `npmjs.org`, `docs.google.com` | Un proxy d'entreprise qui bloque l'un d'eux fait échouer l'étape correspondante | Ouvrir ces sites dans le navigateur du poste |

> **Licence Docker Desktop** : gratuit pour un usage personnel, l'enseignement ou
> une entreprise de moins de 250 personnes **et** de moins de 10 M$ de chiffre
> d'affaires annuel ; au-delà, un abonnement Docker payant est exigé. Devoteam
> dépasse ces seuils : à faire valider par qui gère les licences logicielles
> avant d'installer sur un poste de l'entreprise.

### Recommandé : préparer WSL2 avant de lancer l'installateur

Sur un Windows neuf, l'installeur de Docker Desktop active les fonctionnalités
Windows nécessaires, mais pas toujours le **noyau** WSL2, qui se télécharge à
part : Docker Desktop refuse alors de démarrer (« unable to start »), constaté
sur un Windows 11 neuf. `INSTALLER.bat` sait le diagnostiquer, mais au prix d'un
aller-retour de plus. Le prévenir prend cinq minutes, dans une invite de
commandes **ouverte en administrateur** (menu Démarrer → `cmd` → clic droit →
« Exécuter en tant qu'administrateur ») :

```
wsl --install --no-distribution
```

puis **redémarrer** le poste. `--no-distribution` installe WSL2 sans y ajouter
de distribution Ubuntu, dont Docker n'a pas besoin. Si WSL2 est déjà présent, la
commande le signale simplement — sans risque à rejouer.

---

## En un clic : `INSTALLER.bat`

Après avoir récupéré le projet (étape 2 ci-dessous), **double-cliquer sur
`INSTALLER.bat`, à la racine**. Il enchaîne sept étapes, chacune vérifiant
d'abord si elle est déjà faite — le relancer après une interruption reprend
exactement là où il s'était arrêté :

| Étape | Ce qu'il fait | Ce qu'on fait soi-même |
|---|---|---|
| 1/7 | Vérifie que le dossier est un vrai clone Git (`.git`) ; affiche la RAM | Rien — s'il s'arrête ici, refaire le `git clone` |
| 2/7 | Installe **Docker Desktop** s'il manque : via `winget` s'il existe, sinon téléchargement direct de l'installeur officiel sur docker.com (`curl`, livré avec Windows) | Accepter la fenêtre UAC. Le script **s'arrête ensuite volontairement** : redémarrer si Windows le demande, **lancer Docker Desktop** une première fois (accepter ses conditions ; la connexion à un compte Docker peut être ignorée), puis **relancer `INSTALLER.bat`** |
| 3/7 | Attend jusqu'à une minute que Docker Desktop réponde ; sinon, distingue **WSL2 absent** (donne la commande `wsl --install`) de Docker simplement pas lancé | Le cas échéant : `wsl --install` dans une invite **administrateur**, redémarrer, relancer |
| 4/7 | Installe **Ollama** s'il manque (`winget`, sinon ollama.com), démarre son service, télécharge le modèle `qwen2.5:7b-instruct-q4_K_M` (~4,7 Go) | Attendre |
| 5/7 | Crée `.env` et **demande en console** l'identifiant (ou le lien complet) de la feuille, puis le nom de l'onglet | Coller le lien, taper le nom exact de l'onglet — Entrée conserve la valeur affichée entre crochets |
| 6/7 | Vérifie que les ports 8000/8321/8322 sont libres, construit l'image et démarre les trois services | Attendre (plusieurs minutes la première fois) |
| 7/7 | Crée les raccourcis du Bureau, attend que l'application réponde, ouvre le navigateur, puis exécute `scripts/test_fonctionnel.py` **à l'intérieur du conteneur** | Lire le dernier bloc : il doit afficher **« TOUT EST JUSTE »** |

Aucune clé API, aucun compte de service, aucun fichier JSON, aucun Python local.

**Vérifié de bout en bout le 5 octobre 2026** : clone neuf de la branche
`Version_2` depuis GitHub, image reconstruite **sans aucun cache**, puis
`INSTALLER.bat` réel — 7 étapes sur 7, **15 contrôles sur 15, « TOUT EST
JUSTE »**, et une génération réelle du modèle de chat depuis le conteneur via
`host.docker.internal`. Cette vérification a tourné sur un poste où Docker et
Ollama étaient déjà installés ; les branches « poste nu » (installation de
Docker Desktop et d'Ollama sans `winget`, diagnostic WSL2) ont été éprouvées
auparavant sur un Windows 11 Pro 25H2 neuf, en machine virtuelle (voir
`PROGRESS.md`, phases 47 et 48).

Les étapes 1 à 5 ci-dessous détaillent ce que ce fichier fait automatiquement —
utile pour comprendre ou dépanner, pas nécessaire à suivre à la main si
`INSTALLER.bat` s'est bien déroulé.

---

## Avant de commencer

Les mêmes choses que pour l'installation native — rien ne change ici. Fiche
détaillée avec les liens exacts : [`OBTENIR_LES_ACCES.md`](OBTENIR_LES_ACCES.md).

1. La feuille de calcul **partagée en Lecteur, à « toute personne disposant du
   lien »** — aucune clé API, aucun compte de service, aucun fichier JSON à
   déposer : la lecture se fait par le lien d'export public du Sheet.
2. **Le lien de la feuille** (ou son identifiant) et le **nom EXACT de son
   onglet** — un nom incorrect ne produit aucune erreur, il charge
   silencieusement le premier onglet de la feuille à la place.
3. **Git pour Windows** — le seul logiciel à installer à la main, avant tout le
   reste : [git-scm.com/download/win](https://git-scm.com/download/win), options
   par défaut (elles convertissent les fins de ligne au format Windows, dont les
   `.bat` ont besoin).
4. **Docker Desktop** et **Ollama** — rien à préparer à l'avance : `INSTALLER.bat`
   installe les deux automatiquement s'ils manquent (voir l'étape 1 et « Le
   modèle de chat » plus bas).

Voir `Documentation/INSTALLATION.md`, section « Avant le jour de l'installation »,
pour le détail des autres points.

## Étape 1 — Docker Desktop

`INSTALLER.bat` l'installe automatiquement s'il n'est pas déjà présent — via
`winget` quand il existe, sinon en téléchargeant l'installeur officiel
directement sur docker.com (`winget` peut tout simplement manquer : absent d'un
Windows 11 neuf, constaté en machine virtuelle, et souvent bloqué par stratégie
de groupe sur un poste d'entreprise). Pour l'installer vous-même avant de lancer
le script :

[docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

Au premier lancement, Docker Desktop demande d'activer WSL2 (Windows Subsystem for
Linux) si ce n'est pas déjà fait — suivre les instructions à l'écran, un
redémarrage peut être nécessaire. `INSTALLER.bat` le rappelle si l'installation
automatique vient de se terminer : redémarrer si demandé, lancer Docker Desktop
une première fois depuis le menu Démarrer, puis relancer le script.

> Licence : voir l'encadré « Licence Docker Desktop » en tête de page — à
> faire valider avant d'installer sur un poste de l'entreprise.

## Étape 2 — Récupérer le projet

Dans une invite de commandes (menu Démarrer → `cmd`), depuis un dossier
**hors OneDrive** — par exemple `C:\DevoTeam\` :

```
git clone --branch Version_2 https://github.com/YusfAI/DevoTeam_Project.git
cd DevoTeam_Project
```

> **La branche `Version_2` n'est pas un détail.** La branche par défaut du dépôt
> (`main`) est une version plus ancienne, antérieure au modèle de chat local :
> elle demande une clé d'API Google Gemini et ne suit pas cette procédure.
> `--branch Version_2` équivaut à `git clone` suivi de `git checkout Version_2` ;
> pour vérifier, `git branch` doit afficher `* Version_2`.
>
> **Hors OneDrive** : un dossier synchronisé peut verrouiller ou mettre en
> ligne-seulement des fichiers que l'application réécrit à chaque question.

> **`git clone` — surtout pas « Download ZIP ».** Le dossier `.git` n'est pas
> qu'un historique ici : le moteur de tableaux de bord (`dac`, qui appelle
> `bruin`) refuse de lancer la moindre requête s'il ne trouve pas de racine de
> dépôt Git. Vérifié en conditions réelles, à données et configuration
> identiques : avec `.git`, la connexion DuckDB répond « connected » ; sans
> `.git`, elle répond « bruin query failed ». Un dossier obtenu par le bouton
> « Download ZIP » de GitHub n'a pas de `.git` : l'application s'installerait et
> démarrerait normalement, mais **tous les tableaux de bord resteraient vides**.
> `INSTALLER.bat` s'arrête désormais dès l'étape 1/7 dans ce cas, avec la
> commande exacte à lancer.

## Étape 3 — Configurer

```
copy .env.example .env
```

Ouvrir `.env` dans un éditeur de texte et renseigner :

```ini
GOOGLE_SHEET_ID=           l'identifiant de la feuille
GOOGLE_SHEET_TAB=          le nom EXACT de l'onglet

# Facultatif — le rappel quotidien des échéances
GMAIL_SENDER=
GMAIL_APP_PASSWORD=
ALERT_RECIPIENT_EMAIL=

# Facultatif — vide = valeurs par défaut
OLLAMA_HOST=
OLLAMA_MODEL=
```

**Ne pas toucher** à `DAC_PUBLIC_URL` / `DAC_DARK_PUBLIC_URL`, ni à `OLLAMA_HOST` :
Docker les règle tout seul (voir la note technique en fin de page si la question
se pose — `OLLAMA_HOST` y est forcé vers `host.docker.internal`, l'adresse de la
machine hôte vue depuis un conteneur, peu importe ce qu'indique `.env`).

Aucun fichier à déposer, aucune clé API : la lecture du Sheet se fait par son
lien d'export public, à condition qu'il soit bien partagé en Lecteur (voir
« Avant de commencer » ci-dessus).

## Le modèle de chat (Ollama) — tourne sur l'hôte, pas dans Docker

Contrairement au reste, Ollama n'est **pas** conteneurisé : il tourne directement
sur la machine hôte, comme n'importe quel programme installé normalement.
`INSTALLER.bat` le vérifie et l'installe automatiquement à l'étape 4/7 — il
démarre aussi le service s'il est installé mais arrêté, et télécharge le modèle
s'il manque ; en
suivant les étapes manuelles ci-dessous, installez-le vous-même avant `docker
compose up` :

```
https://ollama.com/download
```

L'installeur d'Ollama pèse lui-même ~1,5 Go. Puis téléchargez le modèle (une
fois, ~4,7 Go) :

```
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Sans ça, tout le reste de l'application fonctionne normalement — seul le chat
répond « Impossible de joindre Ollama… » (ou « Modèle … introuvable
localement » si seul le modèle manque).

## Étape 4 — Lancer

```
docker compose up -d --build
```

La première fois, cette commande :
- construit l'image (installe Python, le moteur de tableaux de bord, et son
  pilote de base de données) — la partie la plus longue, plusieurs minutes ;
- compile l'interface ;
- démarre les trois services : l'application et les deux serveurs de tableaux
  de bord (clair, sombre).

Les fois suivantes, elle est presque instantanée : Docker ne reconstruit que ce
qui a changé.

### Un raccourci Bureau pour ne plus taper cette commande

`docker compose up -d --build` n'a besoin d'être tapé qu'une fois. Pour les
lancements suivants, un raccourci évite d'ouvrir un terminal à chaque fois :

```
powershell -ExecutionPolicy Bypass -File scripts\create_shortcut.ps1
```

Crée **« DevoTeam Dashboard (Docker) »** sur le Bureau — un double-clic démarre
les conteneurs (sans reconstruire l'image) et ouvre l'application dans le
navigateur. Les conteneurs continuent de tourner après la fermeture de la
fenêtre ; `docker compose down` les arrête.

## Étape 5 — Vérifier

Ouvrir **http://127.0.0.1:8000** dans un navigateur.

Puis, pour prouver que les CHIFFRES affichés sont justes — pas seulement que la
page s'ouvre — **sans avoir besoin d'un Python local** : le script calcule sa
propre vérité depuis la feuille avec pandas, donc il tourne à l'intérieur du
conteneur `backend`, qui a déjà tout ce qu'il lui faut.

```
docker compose exec -e TEST_DAC_URL=http://dac-light:8321 backend python scripts/test_fonctionnel.py
```

`INSTALLER.bat` lance déjà cette commande tout seul à la fin de l'installation —
elle n'est utile à taper à la main que pour revérifier plus tard, ou après une
mise à jour.

Tant que la sortie n'affiche pas **« TOUT EST JUSTE »**, ne pas présenter
l'application.

> **Pourquoi `TEST_DAC_URL` ?** Vu de l'intérieur du conteneur `backend`,
> `127.0.0.1` désigne ce conteneur lui-même — jamais celui des tableaux de bord
> (`dac-light`), qui vit à part et n'est joignable que par son nom de service
> sur le réseau Docker. Sans ce réglage, la moitié des contrôles échouerait en
> disant l'application injoignable, alors qu'elle tourne très bien.
>
> **Avec un Python local**, les deux formes se valent — depuis l'hôte,
> `127.0.0.1` atteint correctement les ports publiés par Docker :
> ```
> python scripts/verifier_installation.py
> python scripts/test_fonctionnel.py
> ```

---

## Les commandes utiles

| Besoin | Commande |
|---|---|
| Voir ce qui tourne | `docker compose ps` |
| Suivre les journaux | `docker compose logs -f backend` (ou `dac-light`, `dac-dark`) |
| Arrêter | `docker compose down` |
| Redémarrer après un `git pull` | `docker compose up -d --build` |
| Tout repartir de zéro | `docker compose down` puis relancer l'étape 4 |

## Mettre à jour

```
git pull
docker compose up -d --build
```

Les tableaux de bord versionnés (`dac/dashboards/*.yml`) sont lus directement
depuis le dépôt à chaque requête — un `git pull` suffit à les rafraîchir, sans
même relancer les conteneurs. Reconstruire l'image (`--build`) n'est nécessaire
que si une dépendance ou le moteur de tableaux de bord lui-même a changé.

---

## Pannes fréquentes

| Symptôme | Cause | Geste |
|---|---|---|
| `ports are not available` au lancement | Un port (8000/8321/8322) est déjà pris par une installation native encore active | Fermer les fenêtres de l'installation native, ou changer les ports publiés dans `docker-compose.yml` |
| Page blanche, `StaticFiles` en erreur dans les journaux | `frontend-build` a échoué | `docker compose logs frontend-build` |
| Tableaux de bord vides, aucune erreur | Statuts de la feuille non reconnus | Voir `Documentation/INSTALLATION.md`, section correspondante — identique en Docker |
| « Sheet introuvable (404) » dans les journaux backend | Identifiant de feuille mal recopié | Relancer `INSTALLER.bat` et coller le lien complet de la feuille depuis le navigateur |
| « Réponse inattendue de Google (pas du CSV) » dans les journaux backend | Feuille pas encore partagée en Lecteur, toute personne disposant du lien | Repartager depuis Google Sheets, puis `docker compose exec backend python scripts/verifier_installation.py` |
| Les chiffres semblent faux, aucune erreur affichée | `GOOGLE_SHEET_TAB` ne correspond à aucun onglet réel — Google charge silencieusement le premier onglet à la place | Vérifier l'orthographe exacte dans `.env` |
| Le chat répond mais aucun tableau de bord chat-généré ne s'affiche | Écriture atomique en échec (`EXDEV`) | Ne devrait plus arriver — signe que `docker-compose.yml` a été modifié pour monter un sous-dossier séparément (voir la note technique ci-dessous) |
| Le chat répond « Impossible de joindre Ollama… » ou « Service IA local indisponible » | Ollama pas installé ou pas démarré sur l'hôte | Lancer « Ollama » depuis le menu Démarrer (ou relancer `INSTALLER.bat`, qui démarre le service) — il tourne sur la machine hôte, jamais dans un conteneur |
| Le chat répond « Modèle … introuvable localement » | Le téléchargement du modèle n'a pas abouti | `ollama pull qwen2.5:7b-instruct-q4_K_M` |
| `'docker' n'est pas reconnu…` juste après l'installation de Docker | La fenêtre a été ouverte avant l'installation : son `PATH` est ancien | Fermer la fenêtre, redémarrer Windows si demandé, relancer `INSTALLER.bat` |
| `[ARRET] Docker Desktop ne repond toujours pas` + « WSL2 n'est pas installé », ou Docker Desktop qui affiche « WSL needs updating » / « unable to start » | Le noyau WSL2 manque ou est trop ancien (téléchargement à part de Docker) | `wsl --install --no-distribution` (ou `wsl --update` s'il est déjà installé) dans une invite **administrateur**, redémarrer, relancer `INSTALLER.bat` |
| Docker Desktop affiche « Virtualization support not detected » | Virtualisation désactivée dans le BIOS/UEFI | L'activer dans le BIOS (Intel VT-x / AMD-V, souvent « SVM Mode ») — geste d'un technicien sur un poste d'entreprise |
| `[ARRET] Un des ports 8000 / 8321 / 8322 est deja utilise` | Un autre programme (ou une installation native encore ouverte) occupe le port | `netstat -ano \| findstr "8000 8321 8322"` pour l'identifier, le fermer, relancer |
| Le téléchargement de Docker, d'Ollama ou de l'image échoue | Proxy ou pare-feu d'entreprise | Vérifier l'accès aux sites listés dans « Le poste de destination » ; relancer `INSTALLER.bat`, qui reprend là où il s'était arrêté |

---

## Note technique — pourquoi un seul montage pour tout `/app`

Ce point n'est pas nécessaire pour utiliser l'application ; il explique un choix
du fichier `docker-compose.yml`, pour qui voudrait le modifier.

`backend/dac_composer.py` écrit chaque dashboard généré par une question du chat
de façon atomique : un fichier temporaire (`.dac_tmp/`), puis un remplacement
(`os.replace()`) vers `dac/dashboards/`. Cette opération n'est atomique — et ne
fonctionne même tout court — qu'**à l'intérieur d'un même système de fichiers**.

Vérifié sur ce projet, empiriquement : monter `.dac_tmp/` et `dac/` séparément,
même vers deux dossiers frères sur le même disque, échoue avec `EXDEV`
(« Invalid cross-device link ») — chaque volume Docker (`-v`) crée son propre
point de montage aux yeux du conteneur, même si le disque sous-jacent est
identique.

La solution retenue : un seul volume, `.:/app`, partagé par les trois services.
`.dac_tmp/` et `dac/dashboards/` se retrouvent alors sous le même point de
montage, et l'écriture atomique fonctionne comme sur une installation native.

## Note technique — pourquoi `OLLAMA_HOST` est forcé dans `docker-compose.yml`

Même famille de piège que `DAC_URL`/`DAC_PUBLIC_URL` plus haut. Ollama tourne
sur l'hôte, jamais dans un conteneur : `localhost`/`127.0.0.1` lu par le backend
depuis `.env` désignerait le conteneur `backend` lui-même, qui n'a évidemment
aucun serveur Ollama dedans. `docker-compose.yml` force donc `OLLAMA_HOST` vers
`http://host.docker.internal:11434` — le nom que Docker Desktop résout vers
l'hôte depuis l'intérieur d'un conteneur (et que `extra_hosts` rend disponible
aussi sous Docker Engine/Linux, qui ne le fournit pas nativement) — quelle que
soit la valeur laissée dans `.env`.

C'est aussi ce choix qui fait que le CODE de l'application (pas seulement ses
données) vient du dépôt monté, jamais de l'image : un `git pull` suffit à mettre
à jour les dashboards versionnés sans reconstruire quoi que ce soit.
