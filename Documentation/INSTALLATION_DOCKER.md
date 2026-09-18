# Installer avec Docker

**La méthode recommandée.** Au lieu d'installer Python, Node.js et le moteur de
tableaux de bord directement sur la machine, un seul outil (Docker Desktop) fait
tourner les trois services dans des conteneurs isolés. Ça élimine toute une
classe de pannes propres à Windows rencontrées avec l'installation native —
chemins avec espaces, `PATH` de `bruin` introuvable, PowerShell qui prend un
message de progression pour une erreur. (Alternative si Docker ne peut pas être
installé sur le poste : `setup\INSTALLER_NATIF.bat`.)

Compter 5 à 10 minutes la première fois (téléchargement des images).

---

## En un clic : `INSTALLER.bat`

Après avoir récupéré le projet (étape 2 ci-dessous), **double-cliquer sur
`INSTALLER.bat`, à la racine** : c'est tout, il installe même Docker Desktop et
Ollama tout seul (via `winget`) s'ils manquent — vérifie/installe **Docker
Desktop**, vérifie/installe **Ollama** (le modèle de chat, qui tourne sur la
machine hôte — voir plus bas) et télécharge son modèle, **demande en console**
(pas de Bloc-notes, aucune clé API) l'identifiant de la feuille et son onglet,
construit l'image, démarre les trois services, crée le raccourci du Bureau,
puis **exécute `scripts/test_fonctionnel.py` directement à l'intérieur du
conteneur** — la preuve que les chiffres affichés sont justes, sans qu'aucun
Python ne soit installé sur ce poste.

> Seule exception qui reste manuelle : si Windows demande un **redémarrage**
> pour activer WSL2 (nécessaire à Docker), il faut le faire, puis lancer Docker
> Desktop une première fois depuis le menu Démarrer (accepter les conditions
> d'utilisation) avant de relancer `INSTALLER.bat`. Il reprend alors exactement
> là où il s'était arrêté.

Testé de bout en bout sur ce dépôt : trois exécutions réelles, la dernière
propre — 15 contrôles sur 15, « TOUT EST JUSTE ».

Les étapes 1 à 5 ci-dessous détaillent ce que ce fichier fait automatiquement —
utile pour comprendre ou dépanner, pas nécessaire à suivre à la main si
`INSTALLER.bat` s'est bien déroulé.

---

---

## Avant de commencer

Les mêmes choses que pour l'installation native — rien ne change ici. Fiche
détaillée avec les liens exacts : [`OBTENIR_LES_ACCES.md`](OBTENIR_LES_ACCES.md).

1. La feuille de calcul **partagée en Lecteur, à « toute personne disposant du
   lien »** — aucune clé API, aucun compte de service, aucun fichier JSON à
   déposer : la lecture se fait par le lien d'export public du Sheet.
2. **L'identifiant de la feuille** et le **nom EXACT de son onglet** — un nom
   incorrect ne produit aucune erreur, il charge silencieusement le premier
   onglet de la feuille à la place.
3. **Docker Desktop** et **Ollama** — rien à préparer à l'avance : `INSTALLER.bat`
   installe les deux automatiquement s'ils manquent (voir l'étape 1 et « Le
   modèle de chat » plus bas).

Voir `Documentation/INSTALLATION.md`, section « Avant le jour de l'installation »,
pour le détail des autres points.

## Étape 1 — Docker Desktop

`INSTALLER.bat` l'installe automatiquement (via `winget`) s'il n'est pas déjà
présent — rien à faire à l'avance dans la plupart des cas. Pour l'installer
vous-même avant de lancer le script (ou si `winget` n'est pas disponible sur ce
poste) :

[docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

Au premier lancement, Docker Desktop demande d'activer WSL2 (Windows Subsystem for
Linux) si ce n'est pas déjà fait — suivre les instructions à l'écran, un
redémarrage peut être nécessaire. `INSTALLER.bat` le rappelle si l'installation
automatique vient de se terminer : redémarrer si demandé, lancer Docker Desktop
une première fois depuis le menu Démarrer, puis relancer le script.

> Docker Desktop est gratuit pour un usage personnel ou dans une petite
> entreprise ; au-delà d'un certain effectif, Docker facture un abonnement. À
> vérifier auprès de qui gère les licences logicielles de l'entreprise avant de
> déployer sur le poste d'un tiers.

## Étape 2 — Récupérer le projet

```
git clone https://github.com/<votre-organisation>/DevoTeam_Project.git
cd DevoTeam_Project
```

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
`INSTALLER.bat` le vérifie et l'installe automatiquement à l'étape 3/6 ; en
suivant les étapes manuelles ci-dessous, installez-le vous-même avant `docker
compose up` :

```
https://ollama.com/download
```

Puis téléchargez le modèle (une fois, ~4,7 Go) :

```
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Sans ça, tout le reste de l'application fonctionne normalement — seul le chat
répond « Ollama injoignable ».

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
| « Réponse inattendue de Google (pas du CSV) » dans les journaux backend | Feuille pas encore partagée en Lecteur, toute personne disposant du lien | Repartager depuis Google Sheets, puis `docker compose exec backend python scripts/verifier_installation.py` |
| Les chiffres semblent faux, aucune erreur affichée | `GOOGLE_SHEET_TAB` ne correspond à aucun onglet réel — Google charge silencieusement le premier onglet à la place | Vérifier l'orthographe exacte dans `.env` |
| Le chat répond mais aucun tableau de bord chat-généré ne s'affiche | Écriture atomique en échec (`EXDEV`) | Ne devrait plus arriver — signe que `docker-compose.yml` a été modifié pour monter un sous-dossier séparément (voir la note technique ci-dessous) |
| Le chat répond « Ollama injoignable » | Ollama pas installé, pas démarré, ou modèle non téléchargé sur l'hôte | `ollama serve` doit tourner sur la machine hôte (pas dans un conteneur), et `ollama pull qwen2.5:7b-instruct-q4_K_M` doit avoir réussi |
| `docker: command not found` dans un terminal | Docker Desktop pas démarré | Le lancer depuis le menu Démarrer, attendre l'icône verte dans la zone de notification |

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
