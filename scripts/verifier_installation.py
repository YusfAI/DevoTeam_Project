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

Ne modifie rien : la lecture du Sheet se fait par une clé API (lecture seule, aucun
accès en écriture possible avec ce mode d'authentification).
"""
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
                           ("requests", "requests"),
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
             "l'application ne saura pas quelle feuille lire",
             "Copier .env.example en .env, puis le remplir")
        return False

    from dotenv import load_dotenv
    load_dotenv(chemin)
    dire(OK, "Fichier .env présent")

    # GOOGLE_SHEET_ID est indispensable. Le modèle (Ollama, local) n'a pas de clé
    # à renseigner — il est vérifié séparément (section 4, service + modèle
    # présents), et la lecture du Sheet non plus (lien d'export public, aucune
    # clé). Les trois variables d'email ne sont pas indispensables non plus :
    # sans elles l'alerte quotidienne ne part pas, et c'est tout — l'application
    # reste pleinement utilisable.
    for cle, role in [("GOOGLE_SHEET_ID", "la lecture des données")]:
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


# ---------------------------------------------------------------------------
# 3. La feuille : lecture (lien d'export public, aucune clé) et FORME des données
# ---------------------------------------------------------------------------

def verifier_feuille():
    titre("3. Google Sheet")

    try:
        from backend import data_store
        valeurs = data_store.fetch_sheet_values()
    except Exception as e:
        message = str(e)
        if "404" in message:
            geste = "Vérifier GOOGLE_SHEET_ID dans .env"
        elif "partagé" in message:
            geste = "Partager la feuille en « Lecteur — toute personne disposant du lien »"
        else:
            geste = "Vérifier GOOGLE_SHEET_ID et GOOGLE_SHEET_TAB dans .env"
        dire(KO, "Feuille inaccessible", message[:160], geste)
        return

    if not valeurs:
        dire(KO, "Feuille vide", "aucune ligne, pas même l'en-tête")
        return

    dire(OK, "Lecture", "%d ligne(s), onglet « %s »"
         % (len(valeurs) - 1, os.getenv("GOOGLE_SHEET_TAB", "opportunities")))
    dire(INFO, "Un nom d'onglet incorrect ne produit PAS d'erreur ici",
         "Google charge alors silencieusement le premier onglet de la feuille",
         "Vérifier que « %s » est bien le nom affiché en bas de la feuille"
         % os.getenv("GOOGLE_SHEET_TAB", "opportunities"))

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
    titre("4. Modèle local (Ollama)")

    import requests
    host = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    modele = os.getenv("OLLAMA_MODEL") or "qwen2.5:7b-instruct-q4_K_M"

    try:
        reponse = requests.get(f"{host}/api/tags", timeout=5)
        reponse.raise_for_status()
    except requests.exceptions.ConnectionError:
        dire(KO, "Ollama injoignable", host,
             "Démarrer Ollama (`ollama serve`, ou l'application Ollama)")
        return
    except Exception as e:
        dire(KO, "Ollama injoignable", str(e)[:160],
             "Vérifier OLLAMA_HOST dans .env et que le service tourne")
        return

    dire(OK, "Service Ollama joignable", host)

    noms = {m.get("name", "") for m in reponse.json().get("models", [])}
    # Le tag peut être présent sans son suffixe de quantification (ex: pull d'un
    # tag legerement different) — on accepte un préfixe correspondant plutôt que de
    # forcer une correspondance caractère pour caractère sur la quantification exacte.
    if any(n == modele or n.startswith(modele.split(":")[0] + ":") for n in noms):
        dire(OK, "Modèle « %s » présent" % modele)
    else:
        dire(KO, "Modèle « %s » absent" % modele, "",
             "Exécuter : ollama pull %s" % modele)


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
    """Le moteur de tableaux de bord — natif (bruin.exe local) ou en conteneur.

    Sous Docker, `bruin`/`dac` vivent DANS l'image, jamais sur cette machine : les
    chercher à un chemin Windows natif échouerait toujours, sur une installation
    par ailleurs parfaitement saine. Ce qui compte réellement n'est pas OÙ vivent
    ces binaires, mais si le serveur RÉPOND et EXÉCUTE ses requêtes — ce test-là
    est vrai quelle que soit la manière dont l'application a été installée, et
    c'est donc lui qui décide du verdict. La présence locale des binaires reste
    vérifiée, mais seulement à titre indicatif.
    """
    titre("5. Moteur de tableaux de bord (Bruin DAC)")

    dossier = Path(os.environ.get("USERPROFILE", Path.home())) / ".local" / "bin"
    binaires_locaux = all((dossier / b).exists() for b in ("dac.exe", "bruin.exe"))
    if binaires_locaux:
        dire(OK, "dac.exe et bruin.exe", "installation native, %s" % dossier)

    try:
        from backend.main import _dac_query_failure
    except Exception:
        _dac_query_failure = None

    for port, nom, service_docker in [(8321, "clair", "dac-light"), (8322, "sombre", "dac-dark")]:
        racine = "http://127.0.0.1:%d" % port
        if not _port_ecoute(port):
            if port == 8321:
                if binaires_locaux:
                    dire(AVERTIR, "Serveur clair (port 8321) éteint",
                         "normal si l'application n'est pas lancée",
                         "Il démarre avec le raccourci du Bureau")
                else:
                    dire(KO, "Serveur clair (port 8321) injoignable",
                         "ni binaires locaux, ni serveur démarré",
                         "Installer via setup\\INSTALLER_NATIF.bat, ou lancer "
                         "« docker compose up -d --build »")
            else:
                dire(AVERTIR, "Serveur sombre (port 8322) éteint",
                     "facultatif — sans lui, le tableau de bord reste en clair")
            continue

        erreur = _dac_query_failure(racine) if _dac_query_failure else None
        if erreur is None:
            dire(OK, "Serveur %s (port %d)" % (nom, port), "répond et exécute ses requêtes")
        else:
            dire(KO, "Serveur %s (port %d) répond mais échoue sur ses requêtes" % (nom, port),
                 erreur[:160],
                 "Voir les journaux du conteneur : docker compose logs %s" % service_docker)


def verifier_frontend():
    titre("6. Interface compilée")

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
    if env_ok:
        verifier_feuille()
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
