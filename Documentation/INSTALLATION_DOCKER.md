# Installer avec Docker

Une alternative à `setup\INSTALLER.bat` : au lieu d'installer Python, Node.js et
le moteur de tableaux de bord directement sur la machine, un seul outil (Docker
Desktop) fait tourner les trois services dans des conteneurs isolés. Ça élimine
toute une classe de pannes propres à Windows rencontrées avec l'installation
native — chemins avec espaces, `PATH` de `bruin` introuvable, PowerShell qui
prend un message de progression pour une erreur.

Compter 5 à 10 minutes la première fois (téléchargement des images).

---

## Avant de commencer

Les mêmes trois choses que pour l'installation native — rien ne change ici. Fiche
détaillée avec les liens exacts : [`OBTENIR_LES_ACCES.md`](OBTENIR_LES_ACCES.md).

1. Un **compte de service Google**, dont la feuille de calcul est **partagée en
   Éditeur** avec son adresse `client_email`.
2. Une **clé Gemini** ([aistudio.google.com](https://aistudio.google.com)).
3. **L'identifiant de la feuille** et le **nom de son onglet**.

Voir `Documentation/INSTALLATION.md`, section « Avant le jour de l'installation »,
pour le détail de chaque point.

## Étape 1 — Installer Docker Desktop

[docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/)

Au premier lancement, Docker Desktop demande d'activer WSL2 (Windows Subsystem for
Linux) si ce n'est pas déjà fait — suivre les instructions à l'écran, un
redémarrage peut être nécessaire.

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
GOOGLE_API_KEY=            la clé Gemini
GOOGLE_SHEET_ID=           l'identifiant de la feuille
GOOGLE_SHEET_TAB=          le nom de l'onglet

# Facultatif — le rappel quotidien des échéances
GMAIL_SENDER=
GMAIL_APP_PASSWORD=
ALERT_RECIPIENT_EMAIL=
```

**Ne pas toucher** à `DAC_PUBLIC_URL` / `DAC_DARK_PUBLIC_URL` : Docker les règle
tout seul (voir la note technique en fin de page si la question se pose).

Déposer le fichier JSON du compte de service dans :

```
credentials\google_service_account.json
```

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

## Étape 5 — Vérifier

Ouvrir **http://127.0.0.1:8000** dans un navigateur.

Puis, pour prouver que les CHIFFRES affichés sont justes — pas seulement que la
page s'ouvre — depuis un Python local (voir la remarque plus bas si vous n'en
avez pas) :

```
python scripts/verifier_installation.py
python scripts/test_fonctionnel.py
```

Tant que le second n'affiche pas **« TOUT EST JUSTE »**, ne pas présenter
l'application.

> **Pourquoi un Python local, si le but est d'éviter d'installer des choses ?**
> Ces deux scripts calculent eux-mêmes la réponse attendue depuis la feuille
> (avec pandas) pour la comparer à ce que l'application répond — ils ont donc
> besoin des mêmes dépendances que l'application. Rien d'autre n'en a besoin :
> ni le moteur de tableaux de bord, ni Node.js, qui restent entièrement dans les
> conteneurs. Sans Python disponible, il reste la vérification manuelle : ouvrir
> la page, poser quelques questions, comparer à la feuille de calcul à l'œil.

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
| Le chat répond mais aucun tableau de bord chat-généré ne s'affiche | Écriture atomique en échec (`EXDEV`) | Ne devrait plus arriver — signe que `docker-compose.yml` a été modifié pour monter un sous-dossier séparément (voir la note technique ci-dessous) |
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

C'est aussi ce choix qui fait que le CODE de l'application (pas seulement ses
données) vient du dépôt monté, jamais de l'image : un `git pull` suffit à mettre
à jour les dashboards versionnés sans reconstruire quoi que ce soit.
