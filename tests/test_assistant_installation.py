"""L'assistant d'installation (dossier setup/).

Il conduit une installation complète sur un poste neuf en ne demandant que ce qui
ne peut pas être deviné. Ces tests tiennent les propriétés qui comptent : qu'il ne
duplique pas les scripts existants, qu'aucun secret ne transite par un endroit
inattendu, et qu'il reste rejouable.
"""
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
SETUP = RACINE / "setup"


def _assistant():
    # Le fichier porte un BOM UTF-8 (voir le test dédié) : utf-8-sig le retire.
    return (SETUP / "assistant.ps1").read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# Le dossier
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", ["INSTALLER.bat", "assistant.ps1",
                                 "sonde_feuille.py", "README.md"])
def test_le_dossier_est_complet(nom):
    assert (SETUP / nom).exists(), nom


def test_l_assistant_porte_un_bom_utf8():
    """Sans BOM, PowerShell 5.1 lit un .ps1 en ANSI.

    Tous les accents de l'assistant sortiraient alors en caractères parasites —
    y compris dans les messages qu'on lit précisément quand ça bloque.
    """
    debut = (SETUP / "assistant.ps1").read_bytes()[:3]

    assert debut == b"\xef\xbb\xbf"


def test_le_lanceur_ne_modifie_pas_les_reglages_de_la_machine():
    """-ExecutionPolicy Bypass ne vaut que pour ce processus.

    Set-ExecutionPolicy, lui, modifierait durablement le poste — inacceptable sur
    une machine qui n'est pas la nôtre et qu'on doit rendre telle qu'on l'a trouvée.
    """
    contenu = (SETUP / "INSTALLER.bat").read_text(encoding="utf-8",
                                                  errors="surrogateescape")

    assert "-ExecutionPolicy Bypass" in contenu
    # Les lignes REM expliquent justement pourquoi Set-ExecutionPolicy est écarté :
    # les inclure ferait échouer ce test sur son propre commentaire.
    commandes = [l for l in contenu.splitlines()
                 if not l.strip().upper().startswith("REM")]
    assert not [l for l in commandes if "Set-ExecutionPolicy" in l]


# ---------------------------------------------------------------------------
# Il ne réimplémente rien
# ---------------------------------------------------------------------------

def test_l_assistant_reutilise_les_scripts_existants():
    """Deux chemins d'installation finiraient par diverger.

    L'assistant pose les questions ; l'installation elle-même reste celle de
    scripts/install.bat, et le verdict celui de verifier_installation.py.
    """
    s = _assistant()

    assert r"scripts\install.bat" in s
    assert r"scripts\verifier_installation.py" in s
    # Et il ne refait pas le travail à sa façon.
    for commande in ("python -m venv", "pip install", "npm run build"):
        assert commande not in s, commande


# ---------------------------------------------------------------------------
# Les secrets
# ---------------------------------------------------------------------------

def test_les_secrets_se_saisissent_en_aveugle():
    s = _assistant()

    assert "-AsSecureString" in s
    # La clé et le mot de passe passent bien par la saisie masquée.
    assert "LireSecret 'Cle Gemini" in s
    assert "LireSecret \"Mot de passe d'application" in s


def test_les_espaces_d_un_mot_de_passe_sont_retires():
    """Google affiche les mots de passe d'application en quatre groupes de quatre.

    Collés tels quels, ils font échouer l'authentification SMTP avec un
    « Username and Password not accepted » — constaté sur un poste réel.
    """
    s = _assistant()

    assert "-replace '\s', ''" in s


def test_aucun_secret_n_est_affiche():
    """Un `Write-Host` sur une valeur saisie la ferait apparaître à l'écran, et
    dans toute capture ou partage d'écran fait pendant l'installation."""
    s = _assistant()

    for interdit in ("Write-Host $cle", "Write-Host $valeur",
                     "Write-Host $config['GOOGLE_API_KEY']"):
        assert interdit not in s, interdit


# ---------------------------------------------------------------------------
# Ce qui rend l'assistant utile
# ---------------------------------------------------------------------------

def test_l_identifiant_est_extrait_d_un_lien_colle():
    # Demander « la partie entre /d/ et /edit » est une manipulation inutile, et
    # une source d'erreur de plus le jour de l'installation.
    s = _assistant()

    assert "IdentifiantDeFeuille" in s
    assert "/d/([A-Za-z0-9_-]{20,})" in s


def test_l_assistant_attend_le_partage_au_lieu_d_echouer():
    """Partager la feuille est un geste qui se fait ailleurs, chez Google.

    Échouer dessus obligerait à tout relancer ; l'assistant affiche l'adresse et
    revérifie à la demande.
    """
    s = _assistant()

    assert "AttendreLePartage" in s
    assert "sonde_feuille.py" in s
    assert "EDITEUR" in s


def test_la_sonde_verifie_l_ecriture_et_pas_seulement_la_lecture():
    """Un partage en Lecteur laisse tout fonctionner jusqu'au premier
    enregistrement — c'est-à-dire jusqu'au premier usage réel."""
    s = (SETUP / "sonde_feuille.py").read_text(encoding="utf-8")

    assert "update_acell" in s
    assert "get_all_values" in s
    # Idempotent : la cellule est réécrite avec sa propre valeur.
    assert 'update_acell("A1", valeurs[0][0])' in s


def test_l_assistant_est_rejouable():
    """Relancer après correction ne doit rien défaire ni tout redemander."""
    s = _assistant()

    # Une entrée vide conserve la valeur existante.
    assert "Entree pour la garder" in s
    # Et le fichier d'identifiants déjà en place n'est pas redemandé.
    assert "Test-Path $Identifiants" in s
