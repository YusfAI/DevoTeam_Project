# -*- coding: utf-8 -*-
"""L'application répond-elle JUSTE, sur les données de ce poste ?

`verifier_installation.py` répond à « tout est-il branché ? ». Ce script-ci répond à
la question suivante, et différente : « les chiffres affichés sont-ils les bons ? »

Une installation peut être parfaite et l'application répondre à côté — si les statuts
de la feuille ne sont pas ceux que les règles métier connaissent, les tableaux de
bord sont fonctionnels et vides, et le chat annonce des totaux qui ne veulent rien
dire. Rien n'échoue, rien ne s'affiche en rouge.

D'où le principe de ce script : il ne compare RIEN à des valeurs écrites d'avance.
Pour chaque question, il calcule la réponse attendue directement depuis les données
du poste avec pandas, puis pose la question à l'application et vérifie que le nombre
annoncé est celui-là. Il fonctionne donc sur n'importe quel jeu de données.

    python scripts/test_fonctionnel.py

L'application doit tourner (raccourci « DevoTeam Dashboard (Production) »).
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

API = "http://127.0.0.1:8000"
DAC = "http://127.0.0.1:8321"
DELAI = 120

_COULEUR = sys.platform != "win32" or __import__("os").environ.get("WT_SESSION")
VERT = "\033[32m" if _COULEUR else ""
ROUGE = "\033[31m" if _COULEUR else ""
JAUNE = "\033[33m" if _COULEUR else ""
FIN = "\033[0m" if _COULEUR else ""

_reussis, _echoues, _ignores = [], [], []


# ---------------------------------------------------------------------------

def _appeler(question):
    corps = json.dumps({"query": question}).encode("utf-8")
    requete = urllib.request.Request(
        API + "/dashboard", corps, {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
        return json.loads(reponse.read())


def _chiffres(texte):
    """Le texte sans rien qui puisse séparer les chiffres d'un même nombre.

    Les montants sont formatés « 103 900 001 DT », avec des espaces insécables selon
    la locale. Chercher la suite de chiffres nue évite d'avoir à reproduire ce
    formatage — et de faire échouer le test sur une différence de présentation qui
    n'intéresse personne.
    """
    return re.sub(r"[^\d]", "", texte or "")


def controler(libelle, question, attendu, unite=""):
    """Pose la question et vérifie que le nombre attendu figure dans la réponse."""
    try:
        reponse = _appeler(question)
    except urllib.error.URLError as e:
        _echoues.append((libelle, "application injoignable : %s" % e))
        print("  %sECHEC%s %s" % (ROUGE, FIN, libelle))
        print("        l'application ne répond pas — est-elle lancée ?")
        return

    message = reponse.get("ai_message") or ""
    if not message:
        _echoues.append((libelle, "aucune réponse"))
        print("  %sECHEC%s %s" % (ROUGE, FIN, libelle))
        print("        aucune réponse renvoyée pour : %s" % question)
        return

    cible = _chiffres("%d" % round(attendu))
    if cible and cible in _chiffres(message):
        _reussis.append(libelle)
        print("  %sOK%s    %-42s %s%s" % (VERT, FIN, libelle, "{:,}".format(round(attendu)).replace(",", " "), unite))
    else:
        _echoues.append((libelle, message[:150]))
        print("  %sECHEC%s %s" % (ROUGE, FIN, libelle))
        print("        attendu : %s%s" % ("{:,}".format(round(attendu)).replace(",", " "), unite))
        print("        obtenu  : %s" % message[:150].replace("\n", " "))


def titre(texte):
    print()
    print("  " + texte)
    print("  " + "-" * len(texte))


# ---------------------------------------------------------------------------
# La vérité, calculée depuis les données de CE poste
# ---------------------------------------------------------------------------

def verifier_les_reponses():
    from backend.business_rules import (
        LOST_STATUSES, SUBMITTED_STATUSES, WON_STATUSES, hot_deal_mask,
    )
    from backend.data_store import get_dataframe

    df = get_dataframe()
    if df is None or df.empty:
        print("  %sARRET%s aucune donnée chargée — vérifier la feuille." % (ROUGE, FIN))
        return False

    # Le périmètre par défaut de l'application : les affaires perdues sortent des
    # chiffres tant que la question ne les demande pas.
    actif = df[~df["status"].isin(LOST_STATUSES)]

    titre("Les totaux")
    controler("Budget total", "quel est le budget total ?",
              actif["budget"].sum(), " DT")
    controler("Montant pondéré", "quel est le montant pondéré ?",
              actif["weighted_amount"].sum(), " DT")
    controler("Nombre d'opportunités", "combien d'opportunités en tout ?",
              len(actif))

    titre("Les termes métier")
    controler("Offres gagnées", "combien d'offres gagnées ?",
              len(df[df["status"].isin(WON_STATUSES)]))
    controler("Affaires chaudes", "combien d'affaires chaudes ?",
              int(hot_deal_mask(actif).sum()))

    remises = df[df["status"].isin(SUBMITTED_STATUSES)]
    remises = remises[remises["days_remaining"] <= 0]
    controler("Offres remises", "combien d'offres a-t-on remises ?", len(remises))

    titre("Les répartitions")
    for axe, question, mot in [("country", "quel est le budget par pays ?", "pays"),
                               ("practice", "quel est le budget par practice ?", "practice")]:
        groupes = actif.groupby(axe)["budget"].sum()
        controler("Budget par %s — le total" % mot, question, groupes.sum(), " DT")

    titre("Un filtre")
    # La practice la plus représentée : la question a d'autant plus de sens qu'elle
    # porte sur une valeur qui existe vraiment dans CES données.
    if not actif.empty:
        principale = actif["practice"].value_counts().idxmax()
        controler("Budget filtré sur « %s »" % principale,
                  "quel est le budget pour %s ?" % principale,
                  actif[actif["practice"] == principale]["budget"].sum(), " DT")

    titre("Les échéances")
    from backend.alerts import EXCLUDED_STATUSES
    urgentes = df[(df["days_remaining"].between(0, 7))
                  & (~df["status"].isin(EXCLUDED_STATUSES))]
    controler("Opportunités urgentes", "quelles sont les opportunités urgentes ?",
              len(urgentes))
    return True


# ---------------------------------------------------------------------------
# Les tableaux de bord rendent-ils vraiment des chiffres ?
# ---------------------------------------------------------------------------

SECTIONS = [
    "Vue d'ensemble commerciale", "Affaires chaudes", "Santé du portefeuille",
    "Pipeline commercial", "Échéances à venir",
]


def verifier_les_tableaux():
    titre("Les tableaux de bord")

    for nom in SECTIONS:
        url = "%s/api/v1/dashboards/%s/data" % (DAC, urllib.parse.quote(nom))
        requete = urllib.request.Request(
            url, b"{}", {"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                widgets = (json.loads(reponse.read()) or {}).get("widgets") or {}
        except Exception as e:
            _echoues.append((nom, str(e)))
            print("  %sECHEC%s %-42s %s" % (ROUGE, FIN, nom, str(e)[:60]))
            continue

        # DAC accole « stderr: / stdout: » a chaque erreur ; sur trois lignes, le
        # message utile disparait dans le bruit.
        erreurs = [re.split(r"\s*std(?:err|out):", str(d["error"]))[0].strip()
                   for d in widgets.values() if d.get("error")]
        if erreurs:
            _echoues.append((nom, erreurs[0]))
            print("  %sECHEC%s %-42s %d widget(s) en erreur" % (ROUGE, FIN, nom, len(erreurs)))
            print("        %s" % erreurs[0][:120])
            continue

        # Un widget qui s'exécute sans rendre une seule ligne est le symptôme exact
        # d'une feuille dont les statuts ne sont pas ceux qu'attendent les règles
        # métier : la requête est juste, la page est vide, et rien ne le signale.
        vides = [n for n, d in widgets.items() if not (d.get("data") or d.get("rows"))]
        if vides:
            _ignores.append((nom, "%d widget(s) sans donnée" % len(vides)))
            print("  %sNOTE%s  %-42s %d widget(s) vide(s) sur %d"
                  % (JAUNE, FIN, nom, len(vides), len(widgets)))
        else:
            _reussis.append(nom)
            print("  %sOK%s    %-42s %d widgets" % (VERT, FIN, nom, len(widgets)))


# ---------------------------------------------------------------------------

def main():
    print()
    print("  ============================================================")
    print("    DevoTeam Dashboard - test fonctionnel")
    print("    Les reponses sont-elles justes sur CES donnees ?")
    print("  ============================================================")

    try:
        with urllib.request.urlopen(API + "/health", timeout=20) as r:
            sante = json.loads(r.read())
    except Exception:
        print()
        print("  %sARRET%s L'application ne repond pas sur %s" % (ROUGE, FIN, API))
        print("        La lancer par le raccourci \"DevoTeam Dashboard (Production)\",")
        print("        attendre une quinzaine de secondes, puis relancer ce script.")
        print()
        return 2

    if not (sante.get("dac") or {}).get("ok"):
        print()
        print("  %sNOTE%s  Le serveur de tableaux de bord signale un probleme :" % (JAUNE, FIN))
        print("        %s" % ((sante.get("dac") or {}).get("aide") or "")[:160])

    if not verifier_les_reponses():
        return 2
    verifier_les_tableaux()

    print()
    print("  ============================================================")
    print("    %d controle(s) reussi(s), %d echec(s)" % (len(_reussis), len(_echoues)))
    if _echoues:
        print()
        print("    ECHECS :")
        for libelle, detail in _echoues:
            print("      - %s" % libelle)
            print("        %s" % detail[:120])

        # Deux causes tres differentes, qu'il ne faut surtout pas confondre : un
        # widget qui ECHOUE est un probleme d'installation, un chiffre FAUX est un
        # probleme de donnees. Envoyer quelqu'un verifier les statuts de sa feuille
        # alors que « bruin » est hors du PATH lui fait perdre son apres-midi.
        installation = [l for l, d in _echoues
                        if "bruin" in d or "executable" in d or "injoignable" in d]
        print()
        if installation:
            print("    Cause : l'INSTALLATION, pas les donnees.")
            print("    « bruin » est introuvable dans le PATH du serveur DAC, ou")
            print("    celui-ci a ete lance a la main sans le PATH.")
            print("    -> Fermer les fenetres et relancer par le raccourci du Bureau.")
            print("    -> Puis : python scripts/verifier_installation.py")
        else:
            print("    Cause probable : les DONNEES de ce poste.")
            print("    Les chiffres sont calculables mais ne correspondent pas —")
            print("    le plus souvent, les statuts de la feuille ne sont pas ceux")
            print("    que connaissent les regles metier.")
            print("    -> Documentation/INSTALLATION.md, section \"Si les donnees")
            print("       de ce poste ne sont pas les votres\".")
    elif _ignores:
        print()
        print("    Points a connaitre :")
        for nom, detail in _ignores:
            print("      - %s : %s" % (nom, detail))
        print()
        print("    Des visuels vides signalent souvent des statuts non reconnus.")
    else:
        print()
        print("    TOUT EST JUSTE - l'application est prete a etre presentee.")
    print("  ============================================================")
    print()
    return 1 if _echoues else 0


if __name__ == "__main__":
    sys.exit(main())
