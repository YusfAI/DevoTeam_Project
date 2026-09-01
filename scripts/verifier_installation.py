# -*- coding: utf-8 -*-
"""Vérifie qu'une installation est complète, et dit précisément ce qui manque.

Écrit pour l'installation sur un poste qui n'est pas celui du développeur. Sur une
machine neuve, une installation ratée ne se signale pas : l'application démarre, la
page s'ouvre, et les tableaux de bord restent vides ou pleins d'erreurs. Chacune des
causes possibles — clé absente, feuille non partagée, `bruin` hors du PATH, frontend
jamais compilé — produit à peu près le même symptôme.

Ce script les distingue. Il vérifie chaque maillon séparément et affiche un verdict
par point, avec le geste exact à faire quand ça bloque.

    python scripts/verifier_installation.py

Il ne modifie rien, à une exception près, volontaire : il réécrit la cellule A1 de
la feuille AVEC SA PROPRE VALEUR. C'est le seul moyen de prouver l'accès en
ÉCRITURE, dont l'application a besoin — elle réinscrit les identifiants manquants et
les colonnes calculées. Un partage en lecture seule laisserait tout fonctionner
jusqu'au premier enregistrement, puis échouerait sans que personne comprenne
pourquoi.
"""
import json
import os
import socket
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

# La console Windows francaise est en page de code 850 : tous les accents de ce
# script y sortiraient en "?" — precisement le texte qu'on lit quand quelque chose
# ne va pas. `reconfigure` existe depuis Python 3.7 et ne coute rien.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

# Les couleurs ANSI passent sur les terminaux Windows récents ; ailleurs elles
# s'affichent comme du texte parasite, d'où le repli sur des marqueurs en clair.
_COULEUR = os.environ.get("TERM") or os.environ.get("WT_SESSION") or os.name != "nt"
OK, KO, AVERTIR, INFO = (
    ("\033[32mOK  \033[0m", "\033[31mKO  \033[0m", "\033[33mNOTE\033[0m", "    ")
    if _COULEUR else ("OK  ", "KO  ", "NOTE", "    ")
)

_echecs = []
_avertissements = []


def dire(etat, titre, detail="", geste=""):
    print("  %s %s" % (etat, titre))
    if detail:
        print("       %s" % detail)
    if geste:
        print("       -> %s" % geste)
    if etat is KO:
        _echecs.append(titre)
    elif etat is AVERTIR:
        _avertissements.append(titre)


def titre(texte):
    print()
    print("  " + texte)
    print("  " + "-" * len(texte))


# ---------------------------------------------------------------------------
# 1. Le socle : Python, dépendances, fichiers de configuration
# ---------------------------------------------------------------------------

def verifier_python():
    titre("1. Python et dépendances")

    if sys.version_info < (3, 11):
        dire(KO, "Version de Python", "trouvée : %d.%d" % sys.version_info[:2],
             "Installer Python 3.11 ou plus récent depuis python.org")
    else:
        dire(OK, "Python %d.%d" % sys.version_info[:2])

    manquants = []
    for module, paquet in [("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
                           ("pandas", "pandas"), ("duckdb", "duckdb"),
                           ("gspread", "gspread"), ("google.genai", "google-genai"),
                           ("apscheduler", "APScheduler"), ("dotenv", "python-dotenv")]:
        try:
            __import__(module)
        except ImportError:
            manquants.append(paquet)

    if manquants:
        dire(KO, "Dépendances Python", "absentes : " + ", ".join(manquants),
             "python -m pip install -r requirements.txt")
    else:
        dire(OK, "Dépendances Python installées")


def verifier_env():
    titre("2. Fichier .env")

    chemin = RACINE / ".env"
    if not chemin.exists():
        dire(KO, "Fichier .env absent",
             "l'application ne saura ni quelle feuille lire, ni quelle clé utiliser",
             "Copier .env.example en .env, puis le remplir")
        return False

    from dotenv import load_dotenv
    load_dotenv(chemin)
    dire(OK, "Fichier .env présent")

    # GOOGLE_SHEET_ID et la clé du modèle sont indispensables. Les trois variables
    # d'email ne le sont pas : sans elles l'alerte quotidienne ne part pas, et c'est
    # tout — l'application reste pleinement utilisable.
    for cle, role in [("GOOGLE_API_KEY", "l'interprétation des questions"),
                      ("GOOGLE_SHEET_ID", "la lecture des données")]:
        if not (os.getenv(cle) or "").strip():
            dire(KO, "%s vide" % cle, "requise pour %s" % role,
                 "Renseigner cette valeur dans .env")
        else:
            dire(OK, "%s renseignée" % cle)

    email = [c for c in ("GMAIL_SENDER", "GMAIL_APP_PASSWORD", "ALERT_RECIPIENT_EMAIL")
             if not (os.getenv(c) or "").strip()]
    if email:
        dire(AVERTIR, "Alertes email non configurées",
             "absentes : " + ", ".join(email),
             "Facultatif — sans elles, seul le mail quotidien ne part pas")
    else:
        dire(OK, "Alertes email configurées")
    return True


def verifier_credentials():
    titre("3. Compte de service Google")

    chemin = RACINE / os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH",
                                "credentials/google_service_account.json")
    if not chemin.exists():
        dire(KO, "Fichier d'identifiants absent", str(chemin),
             "Déposer le JSON du compte de service à cet emplacement")
        return None

    try:
        infos = json.loads(chemin.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        dire(KO, "Fichier d'identifiants illisible", str(e),
             "Retélécharger le JSON depuis la console Google Cloud")
        return None

    adresse = infos.get("client_email")
    if not adresse:
        dire(KO, "Fichier d'identifiants incomplet", "client_email absent",
             "Ce n'est pas une clé de compte de service — en générer une")
        return None

    dire(OK, "Compte de service lu")
    print("       adresse à qui la feuille doit être partagée (en Éditeur) :")
    print("       %s" % adresse)
    return adresse


# ---------------------------------------------------------------------------
# 4. La feuille : lecture, écriture, et FORME des données
# ---------------------------------------------------------------------------

def verifier_feuille(adresse_service):
    titre("4. Google Sheet")

    if not adresse_service:
        dire(KO, "Feuille non vérifiée", "identifiants indisponibles")
        return

    try:
        from backend import data_store
        feuille = data_store._get_worksheet()
    except Exception as e:
        message = str(e)
        if "PERMISSION_DENIED" in message or "403" in message:
            geste = ("Partager la feuille avec %s en tant qu'ÉDITEUR" % adresse_service)
        elif "404" in message or "not found" in message.lower():
            geste = "Vérifier GOOGLE_SHEET_ID dans .env (l'identifiant est dans l'URL)"
        else:
            geste = "Vérifier GOOGLE_SHEET_ID et GOOGLE_SHEET_TAB dans .env"
        dire(KO, "Feuille inaccessible", message[:160], geste)
        return

    try:
        valeurs = feuille.get_all_values()
    except Exception as e:
        dire(KO, "Lecture de la feuille en échec", str(e)[:160],
             "Partager la feuille avec %s" % adresse_service)
        return

    if not valeurs:
        dire(KO, "Feuille vide", "aucune ligne, pas même l'en-tête")
        return

    dire(OK, "Lecture", "%d ligne(s), onglet « %s »"
         % (len(valeurs) - 1, os.getenv("GOOGLE_SHEET_TAB", "opportunities")))

    # --- L'écriture, prouvée et non supposée -------------------------------
    # L'application réinscrit les identifiants manquants et les colonnes calculées.
    # Un partage en lecture seule laisse tout fonctionner jusqu'au premier
    # enregistrement — c'est-à-dire jusqu'au premier vrai usage.
    try:
        feuille.update_acell("A1", valeurs[0][0])
        dire(OK, "Écriture", "la feuille est bien partagée en Éditeur")
    except Exception as e:
        dire(KO, "Écriture refusée", str(e)[:160],
             "Repartager la feuille avec %s en ÉDITEUR (et non Lecteur)"
             % adresse_service)

    verifier_colonnes(valeurs[0])
    verifier_valeurs(valeurs)


def verifier_colonnes(entete):
    from backend.data_store import SHEET_COLUMNS

    entete = [c.strip() for c in entete]
    absentes = [c for c in SHEET_COLUMNS if c not in entete]
    if absentes:
        dire(KO, "Colonnes manquantes dans la feuille", ", ".join(absentes),
             "Renommer les colonnes de la feuille pour qu'elles correspondent")
    else:
        dire(OK, "Colonnes attendues toutes présentes")


def verifier_valeurs(valeurs):
    """La FORME des données, et non plus seulement leur présence.

    C'est le point qui fait rater une démonstration sans rien casser. Les règles
    métier nomment des statuts français précis — « Offre remise », « Offre gagnée »,
    « Offre signée ». Une feuille qui en utilise d'autres produit des tableaux de
    bord parfaitement fonctionnels, et vides.
    """
    from backend.schema_and_whitelist import KNOWN_VALUES

    entete = [c.strip() for c in valeurs[0]]
    lignes = valeurs[1:]

    for colonne, connues in KNOWN_VALUES.items():
        if colonne not in entete:
            continue
        i = entete.index(colonne)
        vues = {(l[i] or "").strip() for l in lignes if i < len(l)}
        vues.discard("")
        inconnues = sorted(v for v in vues if v not in connues)
        if inconnues:
            dire(AVERTIR, "Valeurs inconnues en colonne « %s »" % colonne,
                 ", ".join(inconnues[:6]) + (" …" if len(inconnues) > 6 else ""),
                 "Ces lignes seront comptées comme « Non renseigné ». Si ce sont "
                 "de vrais statuts, les ajouter à backend/schema_and_whitelist.py")
        else:
            dire(OK, "Valeurs de « %s » toutes reconnues" % colonne)


# ---------------------------------------------------------------------------
# 5. Le modèle
# ---------------------------------------------------------------------------

def verifier_modele():
    titre("5. Clé du modèle (Gemini)")

    cle = (os.getenv("GOOGLE_API_KEY") or "").strip()
    if not cle:
        dire(KO, "Clé absente", "", "Renseigner GOOGLE_API_KEY dans .env")
        return

    try:
        # La bibliotheque imprime un avertissement sur l'appel de fonctions
        # automatique, sans rapport avec ce qu'on verifie. Sur un ecran
        # d'installation, un pave rouge qui ne concerne pas l'utilisateur lui fait
        # croire a une panne.
        import logging
        logging.getLogger("google_genai").setLevel(logging.ERROR)
        logging.getLogger("google_genai.models").setLevel(logging.ERROR)

        from google import genai
        client = genai.Client(api_key=cle)
        # La question la plus courte possible : on vérifie que la clé est acceptée,
        # pas la qualité du modèle. Inutile de dépenser du quota pour ça.
        client.models.generate_content(model="gemini-flash-lite-latest", contents="ok")
        dire(OK, "Clé acceptée par l'API")
    except Exception as e:
        message = str(e)
        if "API_KEY_INVALID" in message or "API key not valid" in message:
            geste = "La clé est refusée — en générer une sur aistudio.google.com"
        elif "quota" in message.lower() or "429" in message:
            geste = "Quota atteint pour aujourd'hui — la clé est valide, réessayer plus tard"
            dire(AVERTIR, "Quota du modèle atteint", message[:120], geste)
            return
        else:
            geste = "Vérifier la connexion réseau et la clé"
        dire(KO, "Clé refusée", message[:160], geste)


# ---------------------------------------------------------------------------
# 6. Les tableaux de bord et l'interface
# ---------------------------------------------------------------------------

def _port_ecoute(port):
    """Vrai si quelque chose écoute sur ce port.

    `create_connection` plutôt que `connect_ex` sur une socket configurée avec
    `settimeout` : cette dernière passe la socket en mode NON BLOQUANT, et sous
    Windows `connect_ex` renvoie alors 10035 (WSAEWOULDBLOCK) avant même d'avoir
    conclu — y compris sur un port parfaitement vivant. La sonde annonçait donc
    « éteint » sur une installation qui tournait, c'est-à-dire exactement l'inverse
    de ce qu'on lui demande.
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def verifier_dac():
    titre("6. Moteur de tableaux de bord (Bruin DAC)")

    dossier = Path(os.environ.get("USERPROFILE", Path.home())) / ".local" / "bin"
    for binaire, role in [("dac.exe", "sert les tableaux de bord"),
                          ("bruin.exe", "exécute leurs requêtes")]:
        if (dossier / binaire).exists():
            dire(OK, binaire, role)
        else:
            dire(KO, "%s introuvable" % binaire, str(dossier / binaire),
                 "Dans Git Bash : curl -LsSf https://getbruin.com/install/dac | sh")

    for port, nom in [(8321, "clair"), (8322, "sombre")]:
        if _port_ecoute(port):
            dire(OK, "Serveur %s (port %d) démarré" % (nom, port))
        elif port == 8321:
            dire(AVERTIR, "Serveur clair (port 8321) éteint",
                 "normal si l'application n'est pas lancée",
                 "Il démarre avec le raccourci du Bureau")
        else:
            dire(AVERTIR, "Serveur sombre (port 8322) éteint",
                 "facultatif — sans lui, le tableau de bord reste en clair")


def verifier_frontend():
    titre("7. Interface compilée")

    index = RACINE / "frontend" / "dist" / "index.html"
    if index.exists():
        dire(OK, "frontend/dist présent")
    else:
        dire(KO, "Interface jamais compilée", str(index),
             "Dans frontend/ : npm install puis npm run build")

    if (RACINE / "frontend" / "node_modules").exists():
        dire(OK, "node_modules présent")
    else:
        dire(AVERTIR, "node_modules absent",
             "sans lui, impossible de recompiler l'interface",
             "Dans frontend/ : npm install")


# ---------------------------------------------------------------------------

def main():
    print()
    print("  ============================================================")
    print("    DevoTeam Dashboard - verification de l'installation")
    print("  ============================================================")

    verifier_python()
    env_ok = verifier_env()
    adresse = verifier_credentials() if env_ok else None
    if env_ok:
        verifier_feuille(adresse)
        verifier_modele()
    verifier_dac()
    verifier_frontend()

    print()
    print("  ============================================================")
    if _echecs:
        print("    %d POINT(S) BLOQUANT(S) :" % len(_echecs))
        for e in _echecs:
            print("      - %s" % e)
        print()
        print("    L'application ne fonctionnera pas correctement en l'etat.")
    else:
        print("    INSTALLATION COMPLETE - tout est en place.")
    if _avertissements:
        print()
        print("    %d point(s) a connaitre (non bloquants) :" % len(_avertissements))
        for a in _avertissements:
            print("      - %s" % a)
    print("  ============================================================")
    print()
    return 1 if _echecs else 0


if __name__ == "__main__":
    sys.exit(main())
