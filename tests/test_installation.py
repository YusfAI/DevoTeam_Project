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
    assert '""%PY%"" -m uvicorn' in contenu, nom
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
