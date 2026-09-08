"""Le déploiement Docker (Dockerfile, docker-compose.yml).

Construit et vérifié en conditions réelles sur ce poste (voir Documentation/
INSTALLATION_DOCKER.md pour le détail) : image construite, les trois services
démarrés, `/health` répondant avec les vraies données du Sheet, une question posée
au chat qui compose un dashboard, et le tableau de bord rendu par un conteneur
SÉPARÉ du backend qui l'a écrit.

Ces tests-ci ne relancent pas Docker (trop lent pour la suite pytest, et Docker
n'est pas garanti disponible partout où la suite tourne) : ils tiennent les
propriétés STRUCTURELLES dont dépend tout ce qui précède, pour qu'une modification
future du Dockerfile ou du compose ne les défasse pas en silence.
"""
import pathlib

import yaml

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _dockerfile():
    return (RACINE / "Dockerfile").read_text(encoding="utf-8")


def _compose():
    return yaml.safe_load((RACINE / "docker-compose.yml").read_text(encoding="utf-8"))


def test_les_fichiers_existent():
    for nom in ("Dockerfile", "docker-compose.yml", ".dockerignore"):
        assert (RACINE / nom).exists(), nom


# ---------------------------------------------------------------------------
# Le montage unique — la propriété dont tout le reste dépend
# ---------------------------------------------------------------------------

def test_les_trois_services_partagent_un_seul_montage_du_depot():
    """`os.replace()` — l'écriture atomique des dashboards générés par le chat —
    n'est atomique qu'À L'INTÉRIEUR D'UN MÊME SYSTÈME DE FICHIERS.

    Vérifié empiriquement sur ce poste : deux montages Docker séparés vers des
    dossiers pourtant frères sur le même disque échouent quand même en EXDEV
    (« Invalid cross-device link »), malgré un `st_dev` identique des deux côtés
    — chaque `-v` crée son propre point de montage aux yeux du conteneur. Un seul
    montage couvrant tout `/app`, pour les TROIS services, est ce qui évite cette
    panne : `.dac_tmp/` (le fichier temporaire) et `dac/dashboards/` (la
    destination) se retrouvent alors sous le même point de montage.

    Une régression ici — un service qui monterait un sous-dossier séparément —
    ferait échouer silencieusement chaque dashboard composé par le chat, sans
    toucher aux tableaux de bord déjà écrits (accueil.yml et les sections), qui
    eux ne passent jamais par cette écriture atomique.
    """
    compose = _compose()

    for service in ("backend", "dac-light", "dac-dark"):
        volumes = compose["services"][service].get("volumes") or []
        assert volumes == [".:/app"], (
            "%s doit monter le dépôt ENTIER en un seul volume, pas un sous-dossier : "
            "%r" % (service, volumes))


def test_aucun_service_ne_monte_un_sous_dossier_a_part():
    """Le garde-fou inverse du précédent : même un DEUXIÈME volume sur le même
    service réintroduirait le problème pour tout ce qui n'est pas sous `/app`."""
    compose = _compose()

    for service in ("backend", "dac-light", "dac-dark"):
        volumes = compose["services"][service].get("volumes") or []
        assert len(volumes) == 1, (service, volumes)


# ---------------------------------------------------------------------------
# Les deux adresses de DAC — sonde interne vs adresse du navigateur
# ---------------------------------------------------------------------------

def test_le_backend_distingue_l_adresse_interne_et_l_adresse_publique_de_dac():
    """Le backend sonde DAC PAR NOM DE SERVICE (réseau Docker interne) ; le
    navigateur, qui tourne sur la machine hôte et charge le tableau de bord en
    iframe, a besoin de l'adresse PUBLIÉE sur l'hôte — un nom de service Docker
    ne lui dirait jamais rien. Confondre les deux ferait échouer soit la sonde de
    santé du backend, soit l'affichage du tableau de bord dans le navigateur.

    Cette distinction existait déjà dans backend/main.py pour l'accès par tunnel
    (DAC_URL vs DAC_PUBLIC_URL) — Docker en a simplement besoin pour la même
    raison : deux points de vue différents sur « où est DAC ».
    """
    env = _compose()["services"]["backend"]["environment"]

    assert env["DAC_URL"].startswith("http://dac-light:")
    assert env["DAC_DARK_URL"].startswith("http://dac-dark:")
    assert env["DAC_PUBLIC_URL"] == "http://127.0.0.1:8321"
    assert env["DAC_DARK_PUBLIC_URL"] == "http://127.0.0.1:8322"


def test_dac_light_et_dac_dark_ne_recoivent_pas_les_secrets():
    """Ils ne lisent que le fichier DuckDB local — jamais Google Sheets ni
    Gemini. Leur donner accès à .env élargirait sans raison la surface de ce qui
    peut fuiter si l'un de ces deux conteneurs est un jour compromis."""
    compose = _compose()
    for service in ("dac-light", "dac-dark"):
        assert "env_file" not in compose["services"][service]


# ---------------------------------------------------------------------------
# Les ports — même exposition que le lanceur bare-metal
# ---------------------------------------------------------------------------

def test_les_ports_ne_sont_publies_que_sur_127_0_0_1():
    """scripts/start_prod.bat lance uvicorn avec --host 127.0.0.1 : l'application
    n'est joignable QUE depuis cette machine. Publier un port Docker sans
    préciser l'hôte (juste "8000:8000") l'exposerait sur TOUTES les interfaces
    réseau de la machine — un changement de posture de sécurité qu'aucune
    demande n'a motivé."""
    compose = _compose()
    for service, port in [("backend", 8000), ("dac-light", 8321), ("dac-dark", 8322)]:
        ports = compose["services"][service]["ports"]
        assert ports == ["127.0.0.1:%d:%d" % (port, port)], (service, ports)


# ---------------------------------------------------------------------------
# Le répertoire de travail des serveurs DAC
# ---------------------------------------------------------------------------

def test_dac_light_et_dac_dark_travaillent_depuis_dac():
    """`--template themes/devoteam.yml` est un chemin relatif au répertoire de
    travail du PROCESSUS, pas à `--dir` — exactement comme le lanceur bare-metal,
    qui fait un `cd` explicite dans `dac/` avant d'invoquer `dac.exe serve`
    (scripts/start_prod.bat). Sans ce même `working_dir` ici, `--template`
    pointerait dans le vide."""
    compose = _compose()
    for service in ("dac-light", "dac-dark"):
        assert compose["services"][service]["working_dir"] == "/app/dac"


def test_les_deux_themes_sont_bien_distincts():
    compose = _compose()
    cmd_light = compose["services"]["dac-light"]["command"]
    cmd_dark = compose["services"]["dac-dark"]["command"]

    assert "themes/devoteam.yml" in cmd_light
    assert "themes/devoteam-dark.yml" in cmd_dark


# ---------------------------------------------------------------------------
# La compilation de l'interface
# ---------------------------------------------------------------------------

def test_le_backend_attend_que_l_interface_soit_compilee():
    """Servir frontend/dist avant qu'il n'existe ferait échouer FastAPI au tout
    premier chargement — StaticFiles refuse un dossier absent."""
    compose = _compose()
    depend = compose["services"]["backend"]["depends_on"]["frontend-build"]

    assert depend["condition"] == "service_completed_successfully"


def test_l_interface_est_toujours_recompilee_pas_conditionnellement():
    """Même comportement que scripts/start_prod.bat, qui recompile à CHAQUE
    lancement sans détection de changement — une heuristique par date de fichier
    serait de toute façon peu fiable ici : un `git pull` remet à peu près toutes
    les dates à la même heure."""
    commande = " ".join(_compose()["services"]["frontend-build"]["command"])

    assert "npm ci" in commande
    assert "npm run build" in commande


# ---------------------------------------------------------------------------
# L'image : le pilote DuckDB préchauffé une fois pour toutes
# ---------------------------------------------------------------------------

def test_le_pilote_duckdb_est_preinstalle_a_la_construction():
    """Sans ce préchauffage, plusieurs requêtes lancées en parallèle au tout
    premier démarrage tentent d'extraire le même pilote en même temps et se
    marchent dessus (constaté sous Windows avec duckdb.dll ; le mécanisme est
    identique ici). Baker le pilote dans l'image supprime la course : il n'y a
    plus rien à télécharger au premier lancement."""
    dockerfile = _dockerfile()

    assert "dac connections" in dockerfile


def test_git_init_precede_le_prechauffage():
    """`bruin` (invoqué par `dac` pour exécuter le SQL) refuse de fonctionner
    s'il ne trouve pas la racine d'un dépôt Git en remontant depuis le
    répertoire de travail du processus — constaté : « failed to find the git
    repository root » sans lui. Au runtime ce sera satisfait naturellement,
    /app étant le vrai clone (.git compris) ; seule cette étape de construction
    isolée en a besoin artificiellement."""
    dockerfile = _dockerfile()

    assert dockerfile.index("git init") < dockerfile.index("dac connections")


def test_les_dependances_python_sont_installees_avant_le_prechauffage():
    """Le préchauffage importe `duckdb` pour créer sa base jetable : sans les
    dépendances déjà installées à ce stade, cette étape échoue avec un
    ModuleNotFoundError avant même d'avoir pu tester quoi que ce soit."""
    dockerfile = _dockerfile()

    assert dockerfile.index("pip install") < dockerfile.index("dac connections")


# ---------------------------------------------------------------------------
# Les secrets ne doivent jamais entrer dans l'image
# ---------------------------------------------------------------------------

def test_l_image_ne_copie_ni_secrets_ni_code_applicatif():
    """Le code ET les secrets arrivent par le montage, jamais par COPY : une
    image qui embarquerait credentials/ ou .env graverait un secret dans une
    couche d'image, potentiellement partageable ou inspectable bien après que
    le fichier source a été supprimé."""
    dockerfile = _dockerfile()

    for motif in ("COPY .env", "COPY credentials", "COPY backend", "COPY dac "):
        assert motif not in dockerfile, motif


def test_dockerignore_exclut_les_secrets_et_l_etat_local():
    contenu = (RACINE / ".dockerignore").read_text(encoding="utf-8")

    for motif in (".env", "credentials/", ".git/", "dac/data/"):
        assert motif in contenu, motif


# ---------------------------------------------------------------------------
# Le raccourci Bureau (scripts/start_docker.bat)
#
# Sans lui, utiliser Docker demandait d'ouvrir un terminal et de taper
# "docker compose up -d" à chaque lancement — pas un geste raisonnable à
# demander à quelqu'un qui ne code pas. Testé en conditions réelles sur ce
# poste : `docker compose up -d` s'exécute, les trois conteneurs démarrent.
# ---------------------------------------------------------------------------

def _start_docker_bat():
    return (RACINE / "scripts" / "start_docker.bat").read_bytes()


def test_le_lanceur_docker_existe_et_porte_des_fins_de_ligne_windows():
    """Panne réellement rencontrée : écrit avec des fins de ligne LF (Unix) au
    lieu de CRLF, ce fichier échouait EN SILENCE sous cmd.exe — aucune sortie,
    aucun message d'erreur, juste rien. Tous les autres .bat du projet ont déjà
    des CRLF ; celui-ci doit les avoir aussi, sans quoi le défaut peut revenir
    à la moindre réécriture du fichier."""
    contenu = _start_docker_bat()

    assert b"\r\n" in contenu
    # Aucun LF qui ne soit pas précédé d'un CR — un mélange serait le signe
    # qu'une seule ligne a été rééditée sans respecter le reste du fichier.
    assert contenu.count(b"\n") == contenu.count(b"\r\n")


def test_le_lanceur_docker_ne_reconstruit_pas_l_image():
    """"docker compose up -d", jamais "--build" : l'image existe déjà après
    l'installation initiale. Reconstruire à chaque lancement ferait perdre
    plusieurs minutes pour rien à chaque double-clic.

    Le commentaire du fichier, lui, a le droit d'EXPLIQUER pourquoi --build
    n'y est pas — seule la ligne de COMMANDE réelle est concernée ici.
    """
    lignes_commande = [l for l in _start_docker_bat().decode("utf-8").splitlines()
                       if not l.strip().upper().startswith("REM")]
    contenu = "\n".join(lignes_commande)

    assert "docker compose up -d" in contenu
    assert "--build" not in contenu


def test_le_lanceur_docker_verifie_docker_avant_de_s_en_servir():
    contenu = _start_docker_bat().decode("utf-8")

    assert "where docker" in contenu


def test_creation_de_raccourcis_propose_desormais_trois_raccourcis():
    """Le troisième, pour Docker, ne doit pas remplacer les deux premiers — les
    trois méthodes d'installation restent utilisables côte à côte sur la même
    machine, chacune avec son propre raccourci."""
    contenu = (RACINE / "scripts" / "create_shortcut.ps1").read_text(encoding="utf-8")

    assert "start_dev.bat" in contenu
    assert "start_prod.bat" in contenu
    assert "start_docker.bat" in contenu
    assert contenu.count("Nom = 'DevoTeam Dashboard") == 3


# ---------------------------------------------------------------------------
# L'installateur en un clic (INSTALLER.bat, à la racine)
#
# Testé de bout en bout sur cette machine — trois exécutions réelles, la
# dernière propre : Docker vérifié, .env et les identifiants déjà en place
# détectés sans redemander, image construite, conteneurs démarrés, raccourci
# créé, puis les 15 contrôles de scripts/test_fonctionnel.py exécutés À
# L'INTÉRIEUR du conteneur backend — 15/15, sans Python local.
#
# Deux pannes trouvées PENDANT ces essais, toutes deux corrigées :
#   - une attente fixe (timeout /t 15) ne suffisait pas toujours après une
#     reconstruction complète ; remplacée par un sondage actif de /health ;
#   - timeout /t échoue silencieusement dès que l'entrée standard n'est pas un
#     vrai clavier (avéré y compris hors de ce projet — comportement documenté
#     de timeout.exe) ; ping -n, qui ne partage pas cette exigence, l'a
#     remplacé comme mécanisme d'attente dans les boucles de sondage.
# ---------------------------------------------------------------------------

def _installer_racine():
    return (RACINE / "INSTALLER.bat").read_bytes()


def test_l_installateur_racine_existe_et_porte_des_fins_de_ligne_windows():
    """Même panne que start_docker.bat, même garde-fou : un .bat écrit en LF
    échoue en silence sous cmd.exe — aucune sortie, aucune erreur, juste rien."""
    contenu = _installer_racine()

    assert b"\r\n" in contenu
    assert contenu.count(b"\n") == contenu.count(b"\r\n")


def test_l_installateur_racine_ne_demande_que_env_et_json():
    """La promesse faite à l'utilisateur : tout le reste est automatique."""
    contenu = _installer_racine().decode("utf-8")

    assert ".env" in contenu
    assert "google_service_account.json" in contenu
    assert "notepad" in contenu.lower()


def test_l_installateur_racine_verifie_docker_avant_tout():
    contenu = _installer_racine().decode("utf-8")

    assert "where docker" in contenu
    # Pas seulement présent : DÉMARRÉ. "docker" sur le PATH ne veut pas dire
    # que Docker Desktop est lancé — l'erreur la plus fréquente d'un premier
    # essai.
    assert "docker info" in contenu


def test_l_installateur_racine_construit_puis_demarre():
    contenu = _installer_racine().decode("utf-8")

    assert "docker compose up -d --build" in contenu


def test_l_installateur_racine_cree_le_raccourci_bureau():
    contenu = _installer_racine().decode("utf-8")

    assert "create_shortcut.ps1" in contenu


def test_l_installateur_racine_attend_activement_au_lieu_d_un_delai_fixe():
    """Panne trouvée en testant : un délai fixe de 15 s ne suffit pas toujours
    après une reconstruction complète de l'image. Remplacé par un sondage
    réel de /health, qui ne lance la vérification finale que lorsque
    l'application répond vraiment."""
    contenu = _installer_racine().decode("utf-8")

    assert "/health" in contenu
    assert "curl" in contenu
    assert "timeout /t 15" not in contenu


def test_l_installateur_racine_n_utilise_jamais_timeout_slash_t_pour_patienter():
    """Panne trouvée en testant : timeout.exe échoue immédiatement dès que
    l'entrée standard n'est pas un vrai clavier — un comportement documenté de
    l'outil, pas une particularité de ce projet. ping -n, qui n'a pas cette
    exigence, sert d'attente dans les boucles de sondage à la place."""
    contenu = _installer_racine().decode("utf-8")

    assert "timeout /t" not in contenu
    assert "ping -n" in contenu


def test_l_installateur_racine_verifie_sans_exiger_de_python_local():
    """C'est ce qui rend l'installateur VRAIMENT en un clic : la vérification
    finale tourne à l'intérieur du conteneur backend, qui a déjà tout —
    aucune installation Python supplémentaire n'est nécessaire sur le poste
    de destination pour prouver que les chiffres affichés sont justes."""
    contenu = _installer_racine().decode("utf-8")

    assert "docker compose exec" in contenu
    assert "test_fonctionnel.py" in contenu
    # DAC vit dans un conteneur séparé : depuis l'intérieur du conteneur
    # backend, 127.0.0.1 ne le joindrait pas — il faut son nom de service.
    assert "TEST_DAC_URL=http://dac-light:8321" in contenu
