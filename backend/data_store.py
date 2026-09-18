"""Source de données unique de l'application : le Google Sheet, lu directement en
mémoire via pandas. Plus de base de données intermédiaire — le Sheet EST la base,
lue en direct, mise en cache, rafraîchie périodiquement. Le reste de l'application
(chat, graphiques, alertes) lit exclusivement via get_dataframe(), jamais le Sheet
directement.

Lecture SEULE, via le lien d'export public du Sheet (aucune clé API, aucun fichier
de compte de service, aucun OAuth) : le Sheet doit être partagé en « Lecteur —
toute personne disposant du lien ». Champs calculés à chaque chargement (jamais LUS
depuis le Sheet, même
s'ils y figurent en colonne, toujours recalculés depuis les colonnes "brutes" pour
ne jamais en diverger) : deadline_month, deadline_year, days_remaining,
weighted_amount — affichés dans les tableaux de bord, jamais réécrits dans le
Sheet (un lien d'export public ne permet de toute façon pas l'écriture). Une ligne sans
id en reçoit un (max existant + 1) pour la durée de CE chargement ; sans colonne
"id" dans le Sheet, cet id n'est stable d'un chargement à l'autre que si l'ordre
des lignes ne change pas.

Volontairement PAS de suppression : une ligne retirée du Sheet disparaît du
prochain chargement, ce qui est le comportement naturel d'une lecture en direct
(rien à supprimer explicitement quelque part).
"""
import csv
import io
import logging
import os
import re
import threading
from datetime import date, datetime

import pandas as pd
import requests
from dotenv import load_dotenv

from .schema_and_whitelist import KNOWN_VALUES

# Chargé ici plutôt que de compter sur un autre module : data_store est la brique de
# base (lue par db_layer et alerts) et doit pouvoir fonctionner seule, y compris
# quand elle est importée directement par un script ou un test sans passer par main.py.
load_dotenv()

logger = logging.getLogger(__name__)

# Colonnes "brutes" attendues dans le Sheet (n'importe quel ordre, en-têtes exacts
# UNE FOIS PASSÉS PAR _nom_canonique — voir juste en dessous).
SHEET_COLUMNS = [
    "id", "country", "created_date", "deadline", "practice", "description",
    "buyer", "opp_type", "status", "budget", "funding_source", "partner",
    "financial_offer", "win_probability",
]

# En-têtes français déjà en usage sur une vraie feuille métier (celle dont ce projet
# est parti), acceptés en plus des noms internes anglais — insensible à la casse.
#
# Sans cette table, intégrer la feuille RÉELLE d'une utilisatrice demanderait de
# renommer les colonnes de son outil de travail pour satisfaire le code, ce qui
# n'est pas une demande raisonnable à lui faire. Les clés sont déjà en minuscules :
# _nom_canonique() met l'en-tête reçu en minuscules avant de chercher ici.
_ALIAS_COLONNES = {
    "pays": "country",
    "date de création": "created_date",
    "date de creation": "created_date",
    "lead (acheteur)": "buyer",
    "acheteur": "buyer",
    "types": "opp_type",
    "type": "opp_type",
    "statut": "status",
    "financement": "funding_source",
    "partenaire": "partner",
    "offre financière": "financial_offer",
    "offre financiere": "financial_offer",
    "pondéré à": "win_probability",
    "pondere a": "win_probability",
    "description de la prestation": "description",
}


def _nom_canonique(entete: str) -> str:
    """Le nom interne correspondant à cet en-tête de colonne du Sheet.

    Insensible à la casse : une feuille réelle porte ses propres intitulés
    ("Pays", "Statut", "Deadline"...), et seule la CASSE diffère déjà pour les
    noms qui coïncident par ailleurs avec le nom interne ("Practice" vs
    "practice"). Un en-tête non reconnu (ni nom interne, ni alias connu) est
    renvoyé tel quel, en minuscules : il ne correspondra à aucune colonne
    attendue et sera simplement ignoré, sans faire échouer le chargement.
    """
    normalise = entete.strip().lower()
    return _ALIAS_COLONNES.get(normalise, normalise)

_CHOICE_FIELDS = {
    "practice": KNOWN_VALUES["practice"],
    "opp_type": KNOWN_VALUES["opp_type"],
    "status": KNOWN_VALUES["status"],
}

# Colonnes du DataFrame final, dans cet ordre — colonnes brutes + calculées.
DATA_COLUMNS = (
    "id", "country", "created_date", "deadline", "deadline_month", "deadline_year",
    "days_remaining", "practice", "description", "buyer", "opp_type", "status",
    "budget", "funding_source", "partner", "financial_offer", "win_probability",
    "weighted_amount",
)

_cache_lock = threading.Lock()
_cached_df: "pd.DataFrame | None" = None
_last_refresh_summary: dict = {}

_SHEETS_EXPORT_TIMEOUT_SECONDS = 20

# GOOGLE_SHEET_ID accepte aussi bien l'identifiant nu que le lien complet collé
# depuis le navigateur — recopier "la partie entre /d/ et /edit" est une
# manipulation inutile à demander, et une source d'erreur de plus le jour de
# l'installation (même logique que setup/assistant.ps1::IdentifiantDeFeuille).
_MOTIF_LIEN_SHEET = re.compile(r"/d/([A-Za-z0-9_-]{20,})")


def _extraire_identifiant(valeur: str) -> str:
    correspondance = _MOTIF_LIEN_SHEET.search(valeur)
    return correspondance.group(1) if correspondance else valeur.strip()


def fetch_sheet_values() -> list[list[str]]:
    """Lit toutes les valeurs de l'onglet configuré via le lien d'export CSV public
    du Sheet (le même mécanisme que Fichier > Télécharger > CSV, exposé en URL).

    Lecture seule, sans clé API ni fichier de compte de service : le Sheet doit
    être partagé en « Lecteur — toute personne disposant du lien », faute de quoi
    Google répond une page de connexion (HTML) plutôt que le CSV attendu.

    Limite connue et acceptée : un nom d'onglet INCORRECT ne produit PAS d'erreur —
    Google retombe silencieusement sur le premier onglet de la feuille. Rien ne
    permet de le détecter depuis ce seul appel ; la vérification des colonnes
    attendues (_load_from_sheet, juste après) reste le seul filet de sécurité
    contre un onglet mal nommé qui ressemblerait quand même au bon.
    """
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    tab_name = os.getenv("GOOGLE_SHEET_TAB", "opportunities")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID manquant dans .env")
    sheet_id = _extraire_identifiant(sheet_id)

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
    resp = requests.get(
        url, params={"tqx": "out:csv", "sheet": tab_name},
        timeout=_SHEETS_EXPORT_TIMEOUT_SECONDS,
    )
    if resp.status_code == 404:
        raise ValueError(
            "Sheet introuvable (404) — vérifier GOOGLE_SHEET_ID dans .env."
        )
    resp.raise_for_status()

    # Un Sheet privé (ou l'identifiant d'un document qui n'est pas un Sheet) ne
    # renvoie pas d'erreur HTTP franche : Google sert une page de connexion HTML,
    # avec un code 200. Le Content-Type est le seul signal fiable observé pour
    # distinguer ce cas du CSV attendu.
    content_type = resp.headers.get("Content-Type", "")
    if "text/csv" not in content_type:
        raise ValueError(
            "Réponse inattendue de Google (pas du CSV) — le Sheet doit être "
            "partagé en « Lecteur, toute personne disposant du lien » ; vérifier "
            "aussi GOOGLE_SHEET_ID dans .env."
        )

    texte = resp.content.decode("utf-8")
    return list(csv.reader(io.StringIO(texte)))


class RowError(ValueError):
    """Ligne de Sheet invalide — jamais laissée corrompre les lignes suivantes,
    seulement journalisée et sautée (voir _load_from_sheet).

    Porte la colonne et la valeur fautives en plus du message : c'est ce qui permet
    au rapport de qualité (backend/data_quality.py) de regrouper les erreurs par
    cause réelle, plutôt que de devoir réanalyser des phrases déjà formatées."""

    def __init__(self, message: str, field: str | None = None, value: str | None = None):
        super().__init__(message)
        self.field = field
        self.value = value


def _parse_date(raw: str, field: str) -> date:
    raw = (raw or "").strip()
    if not raw:
        raise RowError(f"{field} est vide")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise RowError(f"{field}='{raw}' n'est pas une date valide (attendu AAAA-MM-JJ)",
                    field=field, value=raw)


def _parse_float(raw: str, field: str):
    raw = (raw or "").strip().replace(",", ".").replace(" ", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise RowError(f"{field}='{raw}' n'est pas un nombre valide", field=field, value=raw)


def _parse_win_probability(raw: str):
    value = _parse_float(raw, "win_probability")
    if value is None:
        return None
    # Tolère les deux saisies naturelles : "0.8" (déjà une fraction) ou "80" (un
    # pourcentage tapé tel quel) — jamais > 1 stocké.
    if value > 1:
        value = value / 100
    if not 0 <= value <= 1:
        raise RowError(f"win_probability='{raw}' hors intervalle (0 à 1, ou 0 à 100 en %)")
    return value


def _normalize_choice(raw: str, field: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise RowError(f"{field} est vide")
    known = _CHOICE_FIELDS[field]
    for candidate in known:
        if candidate.lower() == raw.lower():
            return candidate
    raise RowError(f"{field}='{raw}' non reconnu — valeurs attendues : {', '.join(known)}",
                    field=field, value=raw)


# Valeur inscrite à la place d'une cellule vide ou illisible.
#
# Le principe du projet reste de ne rien deviner : « Non renseigné » n'invente aucune
# donnée, il DIT que la donnée manque. Mais rejeter la ligne entière pour une seule
# cellule fautive faisait disparaître une opportunité complète — budget, échéance,
# client — à cause d'un statut mal tapé. Le coût de l'élimination dépasse largement
# celui d'une catégorie explicitement inconnue, visible telle quelle dans les
# graphiques et recensée cellule par cellule dans le rapport de qualité.
UNKNOWN = "Non renseigné"


def _repair(repairs: list, field: str, value: str, remplacement) -> None:
    """Enregistre une cellule réparée. C'est la contrepartie NON NÉGOCIABLE de la
    tolérance : sans cette trace, réparer au lieu de rejeter reviendrait à corrompre
    les données en silence — exactement ce que le rejet servait à éviter."""
    repairs.append({"field": field, "value": value, "replacement": remplacement})


def _choice_or_unknown(raw: str, field: str, repairs: list) -> str:
    try:
        return _normalize_choice(raw, field)
    except RowError:
        _repair(repairs, field, (raw or "").strip(), UNKNOWN)
        return UNKNOWN


def _date_or_none(raw: str, field: str, repairs: list):
    try:
        return _parse_date(raw, field)
    except RowError:
        _repair(repairs, field, (raw or "").strip(), None)
        return None


def _float_or_none(raw: str, field: str, repairs: list):
    try:
        return _parse_float(raw, field)
    except RowError:
        _repair(repairs, field, (raw or "").strip(), None)
        return None


def _probability_or_none(raw: str, repairs: list):
    try:
        return _parse_win_probability(raw)
    except RowError:
        _repair(repairs, "win_probability", (raw or "").strip(), None)
        return None



def _parse_row(headers: list, values: list) -> tuple[dict, list]:
    """Transforme une ligne brute du Sheet en dict, champs dérivés déjà calculés.

    Ne rejette JAMAIS la ligne : chaque cellule illisible est remplacée par une
    valeur explicitement inconnue et consignée dans la liste de réparations
    renvoyée, que le rapport de qualité restitue cellule par cellule.
    """
    raw = dict(zip(headers, values))
    repairs: list = []

    def get(field):
        # L'export CSV -> Sheets écrit parfois les NULL comme le texte littéral
        # "NULL" au lieu d'une cellule vide — sans ce nettoyage, "NULL" finirait
        # stocké tel quel comme valeur de chaîne (ex: partner = "NULL").
        value = (raw.get(field) or "").strip()
        if value.upper() in ("NULL", "NONE", "N/A", "#N/A"):
            return ""
        return value

    row = {"id": get("id")}

    row["country"] = get("country") or None
    if not row["country"]:
        _repair(repairs, "country", "", UNKNOWN)
        row["country"] = UNKNOWN

    row["created_date"] = _date_or_none(get("created_date"), "created_date", repairs)
    row["deadline"] = _date_or_none(get("deadline"), "deadline", repairs)

    row["practice"] = _choice_or_unknown(get("practice"), "practice", repairs)
    row["opp_type"] = _choice_or_unknown(get("opp_type"), "opp_type", repairs)
    row["status"] = _choice_or_unknown(get("status"), "status", repairs)

    row["description"] = get("description") or None
    row["buyer"] = get("buyer") or None
    row["funding_source"] = get("funding_source") or None
    row["partner"] = get("partner") or None

    row["budget"] = _float_or_none(get("budget"), "budget", repairs)
    row["financial_offer"] = _float_or_none(get("financial_offer"), "financial_offer", repairs)
    row["win_probability"] = _probability_or_none(get("win_probability"), repairs)

    # --- Champs dérivés — jamais lus depuis le Sheet, toujours recalculés ---
    # Tous dépendent de l'échéance : sans elle ils restent vides, et la ligne sort
    # naturellement des analyses temporelles sans fausser les autres (son budget
    # continue de compter dans les totaux, ce qui est bien le but).
    if row["deadline"] is not None:
        row["deadline_month"] = row["deadline"].strftime("%Y-%m")
        row["deadline_year"] = row["deadline"].year
        row["days_remaining"] = (row["deadline"] - date.today()).days
    else:
        row["deadline_month"] = None
        row["deadline_year"] = None
        row["days_remaining"] = None

    if row["financial_offer"] is not None and row["win_probability"] is not None:
        row["weighted_amount"] = row["financial_offer"] * row["win_probability"]
    else:
        row["weighted_amount"] = None

    return row, repairs


def _load_from_sheet() -> tuple[list[dict], dict]:
    """Lit le Sheet (lecture seule, clé API) et valide chaque ligne, en attribuant
    un id aux lignes qui n'en ont pas. Renvoie (lignes valides, résumé)."""
    # "errors" reste la liste lisible affichee a l'utilisateur ; "issues" en est la
    # version structuree, exploitee par backend/data_quality.py pour regrouper les
    # rejets par cause plutot que de reanalyser des phrases deja formatees.
    summary = {"total_rows": 0, "skipped": 0, "new_ids_assigned": 0, "errors": [],
               "issues": [], "repairs": []}

    all_values = fetch_sheet_values()
    if not all_values:
        return [], summary

    headers = [_nom_canonique(h) for h in all_values[0]]
    # "id" est la SEULE colonne facultative : une feuille métier réelle n'en a pas
    # forcément une (elle n'a jamais eu besoin de s'auto-numéroter). Toutes les
    # autres restent obligatoires — les rendre facultatives masquerait une vraie
    # feuille mal formée derrière des colonnes silencieusement vides.
    missing_headers = [c for c in SHEET_COLUMNS if c != "id" and c not in headers]
    if missing_headers:
        msg = f"Colonnes manquantes dans l'en-tête du Sheet : {', '.join(missing_headers)}"
        logger.error("Chargement des données : %s", msg)
        summary["errors"].append(msg)
        return [], summary

    parsed_rows: list[dict] = []
    for offset, values in enumerate(all_values[1:], start=1):
        row_number = offset + 1  # +1 pour la ligne d'en-tête
        if not any(v.strip() for v in values):
            continue  # ligne totalement vide — ignorée silencieusement

        try:
            row, repairs = _parse_row(headers, values)
        except Exception as e:
            # _parse_row ne rejette plus rien : n'arrive ici qu'un défaut imprévu du
            # code lui-même. On saute la ligne plutôt que de faire échouer les 361
            # autres, mais on le journalise comme l'anomalie que c'est.
            logger.exception("Chargement des données : ligne %d illisible malgré la tolérance.", row_number)
            summary["skipped"] += 1
            summary["errors"].append(f"Ligne {row_number} : {e}")
            summary["issues"].append({
                "row": row_number, "field": "?", "value": "", "message": str(e),
            })
            continue

        for repair in repairs:
            summary["repairs"].append({"row": row_number, **repair})
        if repairs:
            logger.info(
                "Chargement des données : ligne %d conservée, %d cellule(s) remplacée(s) par « %s » (%s).",
                row_number, len(repairs), UNKNOWN,
                ", ".join(r["field"] for r in repairs),
            )

        parsed_rows.append(row)

    # Un id existant a priorité ; une ligne sans id en reçoit un nouveau (max + 1),
    # attribué dans l'ordre d'apparition. Lecture seule (clé API) : jamais réécrit
    # dans le Sheet — stable pour la durée de CE chargement, et d'un chargement à
    # l'autre seulement si le Sheet a sa propre colonne "id" ou si l'ordre des
    # lignes ne change pas.
    existing_ids = [int(r["id"]) for r in parsed_rows if r["id"].strip().isdigit()]
    next_id = (max(existing_ids) + 1) if existing_ids else 1

    valid_rows: list[dict] = []
    for row in parsed_rows:
        if row["id"].strip().isdigit():
            row["id"] = int(row["id"])
        else:
            row["id"] = next_id
            next_id += 1
            summary["new_ids_assigned"] += 1
        valid_rows.append(row)

    summary["total_rows"] = len(valid_rows)

    logger.info(
        "Chargement des données : %d ligne(s) chargée(s), %d ignorée(s), %d cellule(s) réparée(s), "
        "%d nouvel(aux) id(s) attribué(s).",
        summary["total_rows"], summary["skipped"], len(summary["repairs"]),
        summary["new_ids_assigned"],
    )
    return valid_rows, summary


def refresh_dataframe() -> dict:
    """Recharge le DataFrame depuis le Sheet et remplace le cache. Appelé au
    démarrage, toutes les 15 minutes (scheduler), et à la demande (POST /sheets/sync).
    Renvoie un résumé du chargement pour affichage (frontend, logs)."""
    global _cached_df, _last_refresh_summary
    try:
        rows, summary = _load_from_sheet()
    except Exception:
        logger.exception("Chargement des données : impossible de lire le Sheet.")
        summary = {"total_rows": 0, "skipped": 0, "new_ids_assigned": 0, "issues": [],
                    "repairs": [],
                    "errors": ["Lecture du Sheet impossible — voir les logs."]}
        _last_refresh_summary = summary
        return summary

    df = pd.DataFrame(rows, columns=list(DATA_COLUMNS))
    with _cache_lock:
        _cached_df = df
        _last_refresh_summary = summary
    return summary


def get_dataframe() -> pd.DataFrame:
    """DataFrame actuellement en cache — chargement synchrone au tout premier appel
    si le scheduler n'a pas encore tourné (ex: appel direct en test).

    Renvoie toujours un DataFrame, jamais None : si le chargement échoue (Sheet
    injoignable), un DataFrame vide aux bonnes colonnes permet aux appelants de
    filtrer/grouper normalement et de retomber sur "aucune donnée" plutôt que de
    devoir gérer un cas None séparément.
    """
    if _cached_df is None:
        refresh_dataframe()
    if _cached_df is None:
        return pd.DataFrame(columns=list(DATA_COLUMNS))
    return _cached_df


def get_last_refresh_summary() -> dict:
    return _last_refresh_summary
