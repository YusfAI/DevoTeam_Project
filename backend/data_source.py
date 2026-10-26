"""La source de données vue depuis l'interface : est-elle lue correctement, et
comment en changer sans passer par une invite de commandes.

Deux boutons s'appuient sur ce module :
  - « Santé des données » (`etat_actuel`) : la dernière lecture a-t-elle réussi,
    que contient la feuille, et un aperçu de ses lignes ;
  - « Lier une feuille Google » (`onglets_de`, `diagnostiquer`, `enregistrer_source`) :
    lister les onglets d'une feuille, la tester EXACTEMENT comme l'application la
    lira, puis l'inscrire dans .env si — et seulement si — le test est concluant.

Rien ici ne modifie les données en service tant qu'une feuille n'est pas
enregistrée : le test d'une feuille candidate passe par `analyser_valeurs`, qui
ne touche pas au cache de data_store.
"""
import math
import os
import re
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from .data_store import (
    DATA_COLUMNS, ENV_PATH, SHEET_COLUMNS, UNKNOWN, SourceError,
    _extraire_identifiant, analyser_valeurs, expliquer_echec, fetch_sheet_values,
    get_dataframe, get_last_refresh_summary,
)

ONGLET_PAR_DEFAUT = "opportunities"

# Un identifiant de feuille Google : 44 caractères en pratique, jamais moins de 20.
_MOTIF_IDENTIFIANT = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_MOTIF_GID = re.compile(r"[#&?]gid=(\d+)")

# Les onglets d'une feuille partagée par lien, tels que les liste sa page publique
# « htmlview » : `items.push({name: "opportunities", pageUrl: "…&gid=1698513051"…`.
# Google n'expose aucune liste d'onglets sans clé d'API ; cette page-là est la seule
# source publique. Si son format change, `lister_onglets` renvoie None et l'interface
# retombe sur un nom d'onglet saisi à la main — rien ne casse.
_MOTIF_ONGLET = re.compile(
    r'items\.push\(\{name: "((?:[^"\\]|\\.)*)", pageUrl: "((?:[^"\\]|\\.)*)"')
_HTMLVIEW_TIMEOUT_SECONDS = 15

# Un onglet dont le nom ne peut exister : demandé à Google, il renvoie le premier
# onglet de la feuille. Sert à reconnaître ce repli silencieux quand la liste des
# onglets n'a pas pu être lue.
_ONGLET_INEXISTANT = "__devoteam_onglet_inexistant__"

# Les intitulés de la feuille métier (voir data_store._ALIAS_COLONNES), pour parler
# à la personne avec les mots qu'elle voit dans sa feuille.
LIBELLES = {
    "id": "id", "country": "Pays", "created_date": "Date de création",
    "deadline": "Deadline", "practice": "Practice", "description": "Description",
    "buyer": "Acheteur", "opp_type": "Type", "status": "Statut", "budget": "Budget",
    "funding_source": "Financement", "partner": "Partenaire",
    "financial_offer": "Offre financière", "win_probability": "Pondéré à",
}

# L'aperçu : de quoi reconnaître sa feuille d'un coup d'œil, pas toutes ses colonnes.
_COLONNES_APERCU = ["country", "practice", "status", "buyer", "budget", "deadline"]
_LIGNES_APERCU = 5
_CORRECTIONS_MONTREES = 10


def url_feuille(sheet_id: str) -> str:
    return "https://docs.google.com/spreadsheets/d/%s/edit" % sheet_id if sheet_id else ""


def identifiant_depuis(saisie: str) -> str:
    """L'identifiant d'une feuille, depuis son lien complet ou l'identifiant nu."""
    identifiant = _extraire_identifiant((saisie or "").strip())
    if not _MOTIF_IDENTIFIANT.match(identifiant):
        raise SourceError(
            "Identifiant de feuille invalide : %r" % saisie,
            "Ce n'est pas un lien de feuille Google Sheets. Copiez l'adresse complète "
            "depuis la barre du navigateur : elle contient « /spreadsheets/d/ ».")
    return identifiant


def _decoder_chaine_js(texte: str) -> str:
    texte = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), texte)
    texte = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), texte)
    return re.sub(r"\\(.)", r"\1", texte)


def lister_onglets(sheet_id: str) -> list[dict] | None:
    """Les onglets de la feuille — [{"name", "gid"}] — ou None si on ne peut pas les lire."""
    try:
        reponse = requests.get(
            "https://docs.google.com/spreadsheets/d/%s/htmlview" % sheet_id,
            timeout=_HTMLVIEW_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None
    if reponse.status_code != 200:
        return None
    onglets = []
    for nom, page in _MOTIF_ONGLET.findall(reponse.text):
        gid = _MOTIF_GID.search(_decoder_chaine_js(page))
        onglets.append({"name": _decoder_chaine_js(nom), "gid": gid.group(1) if gid else None})
    return onglets or None


def onglets_de(saisie: str) -> dict:
    """Pour le formulaire : identifiant, onglets, et l'onglet désigné par le lien.

    Un lien copié pendant qu'on regarde un onglet porte son `gid` : c'est l'onglet
    que la personne a sous les yeux, donc celui qu'elle veut — on le présélectionne
    plutôt que de lui faire retrouver son nom dans une liste.
    """
    try:
        sheet_id = identifiant_depuis(saisie)
    except SourceError as exc:
        return {"sheet_id": None, "onglets": None, "onglet_du_lien": None, "erreur": exc.aide}
    onglets = lister_onglets(sheet_id)
    gid = _MOTIF_GID.search(saisie or "")
    du_lien = None
    if gid and onglets:
        du_lien = next((o["name"] for o in onglets if o["gid"] == gid.group(1)), None)
    return {
        "sheet_id": sheet_id,
        "onglets": [o["name"] for o in onglets] if onglets else None,
        "onglet_du_lien": du_lien,
        "erreur": None,
    }


# ---------------------------------------------------------------------------
# Mesures communes au diagnostic d'une feuille candidate et à l'état en service
# ---------------------------------------------------------------------------

def _valeur_json(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, float) and math.isnan(valeur):
        return None
    if isinstance(valeur, date):
        return valeur.isoformat()
    if hasattr(valeur, "item"):  # scalaires numpy
        return _valeur_json(valeur.item())
    return valeur


def _apercu(df: pd.DataFrame) -> dict:
    lignes = [
        [_valeur_json(ligne[c]) for c in _COLONNES_APERCU]
        for _, ligne in df.head(_LIGNES_APERCU).iterrows()
    ]
    return {"colonnes": [LIBELLES[c] if c != "budget" else "Budget (DT)" for c in _COLONNES_APERCU],
            "lignes": lignes}


def _indicateurs(df: pd.DataFrame) -> dict:
    """Ce qu'il y a dans les données : de quoi reconnaître qu'il s'agit des bonnes."""
    if df.empty:
        return {"periode": None, "pays": 0, "practices": 0, "budget_total": 0}
    echeances = df["deadline"].dropna()

    def renseignes(colonne: str) -> int:
        valeurs = df[colonne]
        return valeurs[valeurs.notna() & (valeurs != UNKNOWN)].nunique()

    budget = pd.to_numeric(df["budget"], errors="coerce").sum()
    return {
        "periode": {"debut": _valeur_json(echeances.min()), "fin": _valeur_json(echeances.max())}
        if not echeances.empty else None,
        "pays": int(renseignes("country")),
        "practices": int(renseignes("practice")),
        "budget_total": _valeur_json(float(budget)),
    }


def _mesures(summary: dict, df: pd.DataFrame) -> dict:
    return {
        "lignes": {
            "chargees": int(summary.get("total_rows", 0)),
            "ignorees": int(summary.get("skipped", 0)),
            "cellules_corrigees": len(summary.get("repairs") or []),
            "ids_attribues": int(summary.get("new_ids_assigned", 0)),
        },
        "colonnes": {
            "attendues": [LIBELLES[c] for c in SHEET_COLUMNS],
            "trouvees": [LIBELLES[c] for c in summary.get("columns_found") or []],
            "manquantes": [LIBELLES[c] for c in summary.get("columns_missing") or []],
            "non_reconnues": list(summary.get("columns_unrecognized") or []),
        },
        "indicateurs": _indicateurs(df),
        "apercu": _apercu(df),
        # Ce qu'il faudrait corriger DANS la feuille : la cellule est tolérée (la
        # ligne est gardée), mais elle compte pour « Non renseigné » partout.
        "a_corriger": [
            {"ligne": r.get("row"), "colonne": LIBELLES.get(r.get("field"), r.get("field")),
             "valeur": r.get("value")}
            for r in (summary.get("repairs") or [])[:_CORRECTIONS_MONTREES]
        ],
    }


def _erreur_de_structure(summary: dict, lignes: int) -> str | None:
    manquantes = summary.get("columns_missing") or []
    if manquantes:
        return ("Colonnes obligatoires absentes de l'onglet : %s. Vérifiez qu'il s'agit "
                "du bon onglet et que sa première ligne contient bien les en-têtes."
                % ", ".join(LIBELLES.get(c, c) for c in manquantes))
    if lignes == 0:
        return "L'onglet ne contient aucune ligne de données sous ses en-têtes."
    return None


def _points_a_verifier(summary: dict) -> list[str]:
    """Pourquoi une lecture réussie mérite quand même un coup d'œil — dit en clair,
    sans quoi « des points à vérifier » laisse chercher lesquels."""
    points = []
    corrigees = len(summary.get("repairs") or [])
    if corrigees:
        points.append("%d cellule(s) non reconnue(s) dans la feuille — détail dans "
                      "« À corriger dans la feuille » ci-dessous." % corrigees)
    if summary.get("skipped"):
        points.append("%d ligne(s) illisible(s) ignorée(s) — détail dans « Qualité "
                      "détaillée »." % summary["skipped"])
    return points


def _statut(erreur: str | None, summary: dict, avertissements: list) -> str:
    if erreur:
        return "erreur"
    if summary.get("skipped") or summary.get("repairs") or avertissements:
        return "attention"
    return "ok"


# ---------------------------------------------------------------------------
# « Lier une feuille Google »
# ---------------------------------------------------------------------------

def diagnostiquer(saisie: str, onglet: str | None = None) -> dict:
    """Lit une feuille candidate comme l'application la lirait, sans rien changer.

    Le statut est « erreur » dès que la lier donnerait une application vide ou
    fausse : feuille illisible, onglet inexistant, colonnes manquantes, aucune ligne.
    """
    resultat = {"statut": "erreur", "erreur": None, "avertissements": [],
                "source": None, "onglets": None}
    try:
        sheet_id = identifiant_depuis(saisie)
    except SourceError as exc:
        resultat["erreur"] = exc.aide
        return resultat

    onglets = lister_onglets(sheet_id)
    noms = [o["name"] for o in onglets] if onglets else None
    onglet = (onglet or "").strip()
    if not onglet:
        gid = _MOTIF_GID.search(saisie or "")
        du_lien = next((o["name"] for o in onglets or [] if gid and o["gid"] == gid.group(1)), None)
        onglet = du_lien or (noms[0] if noms else ONGLET_PAR_DEFAUT)

    resultat["onglets"] = noms
    resultat["source"] = {"sheet_id": sheet_id, "tab": onglet, "url": url_feuille(sheet_id)}

    # Le piège principal : Google ne signale PAS un onglet inexistant, il renvoie le
    # premier onglet à la place. Avec la liste des onglets, on le tranche net ; la
    # comparaison est insensible à la casse, comme Google, et c'est le nom EXACT
    # qui est retenu.
    if noms:
        exact = next((n for n in noms if n.casefold() == onglet.casefold()), None)
        if exact is None:
            resultat["erreur"] = ("L'onglet « %s » n'existe pas dans cette feuille. "
                                  "Onglets disponibles : %s." % (onglet, ", ".join(noms)))
            return resultat
        onglet = exact
        resultat["source"]["tab"] = exact

    try:
        valeurs = fetch_sheet_values(sheet_id, onglet)
    except Exception as exc:  # noqa: BLE001 — tout échec doit se dire à l'écran
        resultat["erreur"] = expliquer_echec(exc)
        return resultat

    if noms is None:
        # Sans la liste, seul le repli lui-même trahit un nom faux : un onglet qui
        # ne peut pas exister renvoie la même chose que celui demandé.
        try:
            if fetch_sheet_values(sheet_id, _ONGLET_INEXISTANT) == valeurs:
                resultat["avertissements"].append(
                    "Le contenu lu est celui du PREMIER onglet de la feuille. Si « %s » "
                    "n'est pas le premier onglet, son nom est mal saisi : Google renvoie "
                    "alors le premier onglet sans signaler d'erreur." % onglet)
        except Exception:  # noqa: BLE001 — simple vérification de confort
            pass

    lignes, summary = analyser_valeurs(valeurs)
    df = pd.DataFrame(lignes, columns=list(DATA_COLUMNS))
    erreur = _erreur_de_structure(summary, len(lignes))
    resultat.update(_mesures(summary, df))
    resultat["erreur"] = erreur
    if not erreur:
        resultat["avertissements"] += _points_a_verifier(summary)
    resultat["statut"] = _statut(erreur, summary, resultat["avertissements"])
    return resultat


def _valeur_env(valeur: str) -> str:
    """Une valeur sûre pour .env, lu par python-dotenv ET par docker compose.

    Sans guillemets tant que c'est possible — c'est ainsi qu'INSTALLER.bat écrit, et
    qu'il relit ses valeurs par défaut. Entre guillemets dès qu'un caractère serait
    mal lu : un « # » précédé d'une espace ouvre un commentaire, et la fin d'un nom
    d'onglet comme « Pipeline #2 » disparaîtrait en silence.
    """
    if re.search(r'[#"\'\\]', valeur) or valeur != valeur.strip():
        return '"%s"' % valeur.replace("\\", "\\\\").replace('"', '\\"')
    return valeur


def enregistrer_source(sheet_id: str, onglet: str, chemin: Path = ENV_PATH) -> None:
    """Inscrit la feuille dans .env et la met en service pour ce processus.

    Ne touche à AUCUNE autre ligne du fichier (même règle que scripts/maj_env.ps1) :
    commentaires, alertes email et réglages Ollama restent tels quels. Écriture
    atomique (fichier temporaire puis remplacement) : un .env à moitié écrit ferait
    perdre la configuration entière, pas seulement la feuille.
    """
    valeurs = {"GOOGLE_SHEET_ID": sheet_id, "GOOGLE_SHEET_TAB": onglet}
    # newline="" : sans lui, Python convertit \r\n en \n à la lecture, et le fichier
    # (écrit en CRLF par INSTALLER.bat) était réécrit en LF sans qu'on le décide.
    try:
        with open(chemin, encoding="utf-8-sig", newline="") as f:
            texte = f.read()
    except FileNotFoundError:
        texte = ""
    fin_de_ligne = "\r\n" if "\r\n" in texte else "\n"

    sortie, vues = [], set()
    for ligne in texte.splitlines():
        cle = ligne.split("=", 1)[0].strip()
        if cle in valeurs and "=" in ligne and not ligne.lstrip().startswith("#"):
            sortie.append("%s=%s" % (cle, _valeur_env(valeurs[cle])))
            vues.add(cle)
        else:
            sortie.append(ligne)
    for cle, valeur in valeurs.items():
        if cle not in vues:
            sortie.append("%s=%s" % (cle, _valeur_env(valeur)))

    contenu = fin_de_ligne.join(sortie) + fin_de_ligne
    descripteur, provisoire = tempfile.mkstemp(dir=chemin.parent, prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8", newline="") as f:
            f.write(contenu)
        os.replace(provisoire, chemin)
    except BaseException:
        if os.path.exists(provisoire):
            os.remove(provisoire)
        raise

    os.environ.update(valeurs)


# ---------------------------------------------------------------------------
# « Santé des données »
# ---------------------------------------------------------------------------

def etat_actuel() -> dict:
    """La feuille en service, la dernière lecture, et ce qu'elle a produit.

    Deux choses distinctes sont rapportées, parce qu'elles peuvent diverger : le
    statut de la DERNIÈRE lecture, et les données EN SERVICE. Une lecture qui échoue
    ne vide pas l'application — elle garde les données de la lecture précédente — et
    l'écran doit le dire plutôt que d'afficher des chiffres sans dire leur âge.
    """
    df = get_dataframe()  # charge au premier appel, si le planificateur n'a pas encore tourné
    summary = get_last_refresh_summary() or {}
    source = summary.get("source") or {
        "sheet_id": _extraire_identifiant(os.getenv("GOOGLE_SHEET_ID") or ""),
        "tab": os.getenv("GOOGLE_SHEET_TAB") or ONGLET_PAR_DEFAUT,
    }

    erreur = summary.get("fatal_error") or _erreur_de_structure(summary, int(summary.get("total_rows", 0)))
    etat = {
        "statut": _statut(erreur, summary, []),
        "erreur": erreur,
        "avertissements": [],
        "source": {**source, "url": url_feuille(source.get("sheet_id"))},
        "lecture": {
            "at": summary.get("at"),
            "duree_ms": summary.get("duration_ms"),
            "duckdb_exporte": summary.get("duckdb_exported"),
        },
        "donnees_en_service": int(len(df)),
    }
    etat.update(_mesures(summary, df))
    if not erreur:
        etat["avertissements"] += _points_a_verifier(summary)
    if summary.get("fatal_error") and len(df):
        etat["avertissements"].append(
            "L'application continue d'afficher les données de la lecture précédente "
            "(%d lignes) : elles ne sont plus à jour tant que la lecture échoue." % len(df))
    return etat
