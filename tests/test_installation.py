"""L'installation sur un poste qui n'est pas celui du développeur.

Une installation ratée ne se signale pas : l'application démarre, la page s'ouvre, et
les tableaux de bord restent vides ou pleins d'erreurs. Clé absente, feuille non
partagée, `bruin` hors du PATH, interface jamais compilée — toutes ces causes
produisent à peu près le même symptôme.

Ces tests tiennent le script de vérification qui les distingue, et les lanceurs qui
doivent employer l'environnement isolé créé par l'installation.
"""
import pathlib
import socket
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = RACINE / "scripts"

sys.path.insert(0, str(SCRIPTS))
import verifier_installation as verif  # noqa: E402


# ---------------------------------------------------------------------------
# La sonde de port
# ---------------------------------------------------------------------------

def test_un_port_qui_ecoute_est_bien_vu():
    """Le défaut d'origine : la sonde disait « éteint » sur un serveur vivant.

    `settimeout()` passe la socket en mode NON BLOQUANT ; sous Windows `connect_ex`
    renvoie alors 10035 (WSAEWOULDBLOCK) avant d'avoir conclu, y compris sur un port
    parfaitement ouvert. Le diagnostic annonçait donc une panne là où il n'y en avait
    pas — pire qu'inutile un jour d'installation.
    """
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen(1)
    port = serveur.getsockname()[1]
    try:
        assert verif._port_ecoute(port) is True
    finally:
        serveur.close()


def test_un_port_ferme_est_bien_vu():
    # Un port qu'on vient de libérer : rien n'écoute plus dessus.
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    port = serveur.getsockname()[1]
    serveur.close()

    assert verif._port_ecoute(port) is False


# ---------------------------------------------------------------------------
# La forme des données — le point qui fait rater une démonstration en silence
# ---------------------------------------------------------------------------

def _valeurs(lignes):
    """Reconstruit ce que `get_all_values()` renvoie : l'en-tête puis les lignes."""
    return [["status", "practice"]] + lignes


def test_un_statut_inconnu_est_signale(capsys):
    """Une feuille aux libellés différents donne des tableaux justes, et VIDES.

    Les règles métier nomment des statuts français précis. Rien n'échoue si la
    feuille en utilise d'autres : les lignes tombent simplement en « Non renseigné »
    et disparaissent des chiffres. C'est exactement ce qu'il faut dire tout haut le
    jour de l'installation.
    """
    verif._echecs.clear()
    verif._avertissements.clear()

    verif.verifier_valeurs(_valeurs([
        ["Prospect", "Risk Advisory"],
        ["Offre remise", "Risk Advisory"],
    ]))

    sortie = capsys.readouterr().out
    assert "Prospect" in sortie
    assert "status" in sortie
    # Signalé, mais non bloquant : la feuille reste exploitable, seulement amputée.
    assert not verif._echecs
    assert verif._avertissements


def test_des_statuts_connus_ne_declenchent_rien(capsys):
    verif._echecs.clear()
    verif._avertissements.clear()

    verif.verifier_valeurs(_valeurs([
        ["Offre remise", "Risk Advisory"],
        ["Offre gagnée", "Data Management"],
    ]))

    assert not verif._echecs
    assert not verif._avertissements


def test_une_colonne_absente_est_bloquante(capsys):
    """Sans ses colonnes, le chargement rejette toutes les lignes."""
    verif._echecs.clear()
    verif._avertissements.clear()

    verif.verifier_colonnes(["id", "country", "status"])

    sortie = capsys.readouterr().out
    assert "budget" in sortie
    assert verif._echecs


def test_toutes_les_colonnes_attendues_passent():
    from backend.data_store import SHEET_COLUMNS

    verif._echecs.clear()
    verif.verifier_colonnes(list(SHEET_COLUMNS))

    assert not verif._echecs


# ---------------------------------------------------------------------------
# Le script vérifie ce qu'il annonce
# ---------------------------------------------------------------------------

def test_l_ecriture_dans_la_feuille_est_reellement_testee():
    """Lire ne prouve pas qu'on peut écrire.

    L'application attribue les identifiants manquants et réinscrit les colonnes
    calculées. Une feuille partagée en Lecteur laisse tout fonctionner jusqu'au
    premier enregistrement — donc jusqu'au premier vrai usage.
    """
    source = (SCRIPTS / "verifier_installation.py").read_text(encoding="utf-8")

    assert "update_acell" in source
    # Idempotent : la cellule est réécrite avec SA PROPRE valeur, jamais autre chose.
    assert 'update_acell("A1", valeurs[0][0])' in source


def test_l_adresse_du_compte_de_service_est_affichee():
    # C'est l'information qu'on cherche le jour de l'installation, et elle ne se
    # devine pas : sans elle, impossible de savoir à qui partager la feuille.
    source = (SCRIPTS / "verifier_installation.py").read_text(encoding="utf-8")

    assert "client_email" in source
    assert "partagée" in source


# ---------------------------------------------------------------------------
# Les lanceurs et l'environnement isolé
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", ["start_dev.bat", "start_prod.bat"])
def test_les_lanceurs_preferent_l_environnement_isole(nom):
    """install.bat crée un .venv ; le lancer avec le Python du système passerait à
    côté des versions épinglées, et l'application démarrerait sur autre chose que ce
    qui a été installé."""
    contenu = (SCRIPTS / nom).read_text(encoding="utf-8", errors="surrogateescape")

    assert r".venv\Scripts\python.exe" in contenu, nom
    # Un seul niveau de guillemets autour du chemin : le doublement précédent
    # empêchait tout démarrage dès qu'un dossier du chemin contenait une espace.
    assert '""%PY%" -m uvicorn' in contenu, nom
    # Et le repli : un poste configuré avant l'existence du .venv doit continuer
    # de démarrer.
    assert 'set "PY=python"' in contenu, nom


def test_l_environnement_isole_n_est_pas_versionne():
    # Des binaires propres à une machine et à une version de Python.
    assert ".venv/" in (RACINE / ".gitignore").read_text(encoding="utf-8")


def test_l_installeur_ne_demande_aucun_secret_en_console():
    """Une clé tapée dans une console reste dans son historique.

    L'installeur ouvre donc le Bloc-notes sur le fichier .env plutôt que de lire les
    valeurs au clavier.
    """
    contenu = (SCRIPTS / "install.bat").read_text(encoding="utf-8",
                                                  errors="surrogateescape")

    assert "notepad" in contenu.lower()
    for secret in ("GOOGLE_API_KEY", "GMAIL_APP_PASSWORD"):
        assert "set /p %s" % secret not in contenu


def test_l_installeur_termine_par_la_verification():
    # Une installation qu'on croit finie est le vrai risque : le script doit dire
    # lui-même si elle l'est.
    contenu = (SCRIPTS / "install.bat").read_text(encoding="utf-8",
                                                  errors="surrogateescape")

    assert "verifier_installation.py" in contenu


def test_la_procedure_documente_le_partage_en_editeur():
    """Le piège le plus coûteux, parce qu'il ne se voit qu'à l'usage."""
    texte = (RACINE / "Documentation" / "INSTALLATION.md").read_text(encoding="utf-8")

    assert "Éditeur" in texte
    assert "Add python.exe to PATH" in texte
    assert "getbruin.com/install/dac" in texte


# ---------------------------------------------------------------------------
# Les dépendances déclarées suffisent-elles vraiment ?
# ---------------------------------------------------------------------------

def test_toute_dependance_importee_est_declaree():
    """Le défaut qui aurait bloqué l'installation sur un poste neuf.

    `yaml` était importé par backend/dac_composer.py sans figurer dans
    requirements.txt. Sur la machine de développement il arrivait par ricochet, tiré
    par un autre paquet ; dans l'environnement isolé créé par install.bat il était
    absent, et l'application ne démarrait pas du tout — ModuleNotFoundError au tout
    premier import, avant même la moindre requête.

    Une liste de dépendances ne vaut que si elle est COMPLÈTE. Ce test la compare aux
    imports réels plutôt qu'à ce qu'on croit y avoir mis.
    """
    import ast
    import sys

    declares = set()
    for ligne in (RACINE / "requirements.txt").read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#"):
            declares.add(ligne.split("==")[0].strip().lower())

    # Le nom du paquet et celui du module diffèrent parfois : la correspondance ne se
    # devine pas, elle s'écrit.
    module_vers_paquet = {
        "dotenv": "python-dotenv", "yaml": "pyyaml", "google": "google-genai",
        "apscheduler": "apscheduler",
    }

    importes = set()
    for dossier in ("backend", "scripts"):
        for fichier in (RACINE / dossier).rglob("*.py"):
            arbre = ast.parse(fichier.read_text(encoding="utf-8"))
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    importes.update(a.name.split(".")[0] for a in noeud.names)
                elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                    importes.add(noeud.module.split(".")[0])

    locaux = {"backend", "scripts", "tests"}
    manquants = sorted(
        module for module in importes
        if module not in sys.stdlib_module_names
        and module not in locaux
        and module_vers_paquet.get(module, module).lower() not in declares)

    assert not manquants, (
        "Ces modules sont importés mais absents de requirements.txt : %s. "
        "L'application ne démarrera pas dans un environnement neuf."
        % ", ".join(manquants))


# ---------------------------------------------------------------------------
# L'accès public (tunnel)
# ---------------------------------------------------------------------------

def test_l_adresse_des_tableaux_de_bord_est_reglable_a_l_execution():
    """Elle était figée à la compilation du frontend, et ne pouvait pas l'être.

    L'iframe est chargée par le NAVIGATEUR : lui transmettre « 127.0.0.1:8321 »
    revient à lui faire interroger SA PROPRE machine. Derrière un tunnel, tous les
    tableaux de bord restent vides et aucune requête n'échoue — la panne est donc
    difficile à rattacher à sa cause.

    Une URL de tunnel change à chaque session : la régler à l'exécution est la seule
    forme utilisable.
    """
    source = (RACINE / "backend" / "main.py").read_text(encoding="utf-8")

    assert 'DAC_PUBLIC_URL = os.getenv("DAC_PUBLIC_URL") or DAC_URL' in source
    assert 'DAC_DARK_PUBLIC_URL = os.getenv("DAC_DARK_PUBLIC_URL") or DAC_DARK_URL' in source
    # C'est bien l'adresse PUBLIQUE qui part au navigateur.
    assert '"url": DAC_PUBLIC_URL,' in source


def test_le_backend_continue_de_sonder_l_adresse_locale():
    """Les deux adresses ont deux usages, et les confondre casserait les sondes.

    Le backend sonde DAC pour lui-même : il doit continuer d'employer l'adresse
    locale, même quand le navigateur reçoit celle du tunnel.
    """
    source = (RACINE / "backend" / "main.py").read_text(encoding="utf-8")

    # La sonde de présence et celle d'exécution visent DAC_URL / DAC_DARK_URL.
    assert "urllib.request.urlopen(DAC_DARK_URL" in source
    assert "racine = racine or DAC_URL" in source


def test_le_frontend_prend_l_origine_dans_la_sante():
    js = (RACINE / "frontend" / "src" / "components"
          / "DashboardPanel.jsx").read_text(encoding="utf-8")

    assert "const racineClaire = dacStatus?.url || undefined" in js
    # Et rien ne se charge avant de connaître l'origine : un cadre lancé trop tôt
    # viserait le 127.0.0.1 du visiteur et échouerait bruyamment.
    assert "if (dacStatus === null) return" in js


def test_le_lanceur_public_ouvre_bien_deux_tunnels():
    """Un seul tunnel ne suffit pas, et l'erreur est silencieuse.

    DAC ne sait pas servir sous un préfixe de chemin — « dac serve » n'a aucune
    option de base path et ses ressources sont en chemins absolus. Il lui faut donc
    sa propre origine.
    """
    contenu = (SCRIPTS / "start_public.bat").read_text(encoding="utf-8",
                                                       errors="surrogateescape")

    assert "ngrok http 8321" in contenu
    assert "ngrok http 8000" in contenu
    assert "DAC_PUBLIC_URL" in contenu
    # L'avertissement de sécurité : l'URL donne accès aux données commerciales.
    assert "basic_auth" in contenu


# ---------------------------------------------------------------------------
# Un chemin de projet contenant une espace
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", ["start_dev.bat", "start_prod.bat"])
def test_les_lanceurs_survivent_a_une_espace_dans_le_chemin(nom):
    """Le défaut constaté sur un poste réel : rien ne démarrait, rien ne le disait.

    Le projet y vivait dans « D:\...\DevoTeam Project\DevoTeam_Project ». Les
    fenêtres s'ouvraient et se refermaient aussitôt ; aucun message, aucun journal.
    Reproduit sur un banc, puis corrigé.

    La forme fautive doublait les guillemets — `cmd /k "cd /d ""%ROOT%"" && ""%PY%""
    args"`. C'est un usage répandu, mais `cmd /k` ne le résout pas de façon
    déterministe dès qu'un dossier du chemin contient une espace.

    La forme retenue : `/D` fixe le répertoire de travail, `/s` rend le traitement
    des guillemets déterministe (cmd retire le premier et le dernier, garde le
    reste tel quel), et il ne subsiste qu'un seul niveau d'imbrication.
    """
    contenu = (SCRIPTS / nom).read_text(encoding="utf-8", errors="surrogateescape")

    lignes = [l for l in contenu.splitlines()
              if l.strip().startswith('start "DevoTeam')]
    assert lignes, nom

    for ligne in lignes:
        # Le doublement de guillemets est précisément ce qui échouait.
        assert '""' not in ligne.replace('cmd /s /k ""', 'cmd /s /k <<'), ligne
        assert "cmd /s /k" in ligne or "http" in ligne, ligne
        assert "/D " in ligne, ligne


@pytest.mark.parametrize("nom", ["start_dev.bat", "start_prod.bat"])
def test_les_lanceurs_ne_reglent_plus_le_path_dans_la_fenetre_fille(nom):
    """Le PATH s'hérite ; le régler à nouveau dans la commande fille rajoutait un
    niveau de guillemets là où ils étaient déjà le problème.

    Le lanceur ajoute %BRUIN_BIN% au PATH avant tout `start` : les processus lancés
    en héritent. Vérifié en exécutant depuis un chemin à espaces — les quinze
    contrôles du test fonctionnel passent, donc `bruin` est bien trouvé.
    """
    contenu = (SCRIPTS / nom).read_text(encoding="utf-8", errors="surrogateescape")

    # Le PATH est bien préparé une fois, en amont.
    assert 'set "PATH=%PATH%;%BRUIN_BIN%"' in contenu, nom
    # Et plus jamais à l'intérieur d'une commande lancée.
    for ligne in contenu.splitlines():
        if ligne.strip().startswith('start "DevoTeam'):
            assert "set " not in ligne, ligne


# ---------------------------------------------------------------------------
# Le pilote DuckDB, installé une fois et une seule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", ["start_dev.bat", "start_prod.bat"])
def test_le_pilote_est_prechauffe_avant_tout_demarrage(nom):
    """La panne du premier lancement sur un poste neuf.

    `bruin` installe le pilote ADBC de DuckDB à sa première requête. L'application
    en lance aussitôt des dizaines en parallèle — une par widget, sur deux serveurs :
    toutes constatent l'absence du pilote et tentent de l'installer en même temps.

        could not create file duckdb.dll:
        The process cannot access the file because it is being used by another process

    Le symptôme est trompeur : CERTAINS widgets s'affichent, d'autres non, en clair
    comme en sombre, sans logique apparente — ce sont ceux qui ont perdu la course.

    `dac connections` ouvre la connexion dans UN SEUL processus et installe le
    pilote. Reproduit puis vérifié en supprimant %APPDATA%\ADBC\Drivers : sans
    l'étape, une partie des widgets échoue ; avec elle, les trente-deux passent.
    """
    contenu = (SCRIPTS / nom).read_text(encoding="utf-8", errors="surrogateescape")

    assert "dac.exe\" connections" in contenu, nom

    # ET il doit venir AVANT le premier serveur : après, la course a déjà eu lieu.
    prechauffage = contenu.index('dac.exe" connections')
    premier_serveur = contenu.index('start "DevoTeam DAC"')
    assert prechauffage < premier_serveur, (
        "%s : le préchauffage doit précéder le démarrage des serveurs" % nom)


def test_le_prechauffage_ne_bloque_pas_le_lancement():
    """Un préchauffage en échec ne doit pas empêcher l'application de démarrer.

    La base peut être absente au tout premier lancement — le fichier DuckDB n'est
    écrit qu'au premier rafraîchissement des données. Refuser de démarrer pour cela
    empêcherait précisément le rafraîchissement qui le crée.
    """
    contenu = (SCRIPTS / "start_prod.bat").read_text(encoding="utf-8",
                                                     errors="surrogateescape")
    bloc = contenu[contenu.index("Preparation du moteur"):]
    bloc = bloc[:bloc.index("popd")]

    assert "exit /b" not in bloc, "le préchauffage ne doit jamais interrompre le lanceur"
