"""Source de données unique de l'application : le Google Sheet, lu directement en
mémoire via pandas. Plus de base de données intermédiaire — le Sheet EST la base,
lue en direct, mise en cache, rafraîchie périodiquement. Le reste de l'application
(chat, graphiques, alertes) lit exclusivement via get_dataframe(), jamais le Sheet
directement.

Champs calculés à chaque chargement (jamais LUS depuis le Sheet, même s'ils y
figurent en colonne, toujours recalculés depuis les colonnes "brutes" pour ne
jamais en diverger) : deadline_month, deadline_year, days_remaining,
weighted_amount. Comme il n'y a plus de second store où "insérer" une ligne, la
distinction insert/update d'avant disparaît : une ligne sans id reçoit simplement
un id (max existant + 1), réécrit dans le Sheet pour rester stable d'un
chargement à l'autre.

Volontairement PAS de suppression : une ligne retirée du Sheet disparaît du
prochain chargement, ce qui est le comportement naturel d'une lecture en direct
(rien à supprimer explicitement quelque part).
"""
import logging
import os
import threading
from datetime import date, datetime

import gspread
import pandas as pd
from dotenv import load_dotenv

from .schema_and_whitelist import KNOWN_VALUES

# Chargé ici plutôt que de compter sur un autre module : data_store est la brique de
# base (lue par db_layer et alerts) et doit pouvoir fonctionner seule, y compris
# quand elle est importée directement par un script ou un test sans passer par main.py.
load_dotenv()

logger = logging.getLogger(__name__)

# Colonnes "brutes" attendues dans le Sheet (n'importe quel ordre, en-têtes exacts).
SHEET_COLUMNS = [
    "id", "country", "created_date", "deadline", "practice", "description",
    "buyer", "opp_type", "status", "budget", "funding_source", "partner",
    "financial_offer", "win_probability",
]

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

# Réécrites dans le Sheet après chaque chargement (si la colonne existe dans
# l'en-tête — elle n'est pas obligatoire, voir SHEET_COLUMNS) pour que l'utilisateur
# voie le résultat du calcul sans consulter les données brutes ; jamais LUES depuis
# le Sheet (_parse_row les recalcule toujours depuis les colonnes brutes).
_DERIVED_SHEET_COLUMNS = ("deadline_month", "deadline_year", "days_remaining", "weighted_amount")

_client = None
_worksheet = None
_cache_lock = threading.Lock()
_cached_df: "pd.DataFrame | None" = None
_last_refresh_summary: dict = {}


def _get_client():
    global _client
    if _client is None:
        creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials/google_service_account.json")
        _client = gspread.service_account(filename=creds_path)
    return _client


def _get_worksheet():
    # open_by_key() + worksheet() sont chacun un aller-retour réseau vers l'API
    # Sheets — le sheet_id/nom d'onglet sont fixes pour la durée du process, donc
    # pas besoin de les refaire à chaque chargement (toutes les 15 min, indéfiniment).
    # Seul get_all_values()/update_cells() doivent rester des appels frais à chaque
    # fois (données à jour).
    global _worksheet
    if _worksheet is None:
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        tab_name = os.getenv("GOOGLE_SHEET_TAB", "opportunities")
        if not sheet_id:
            raise ValueError("GOOGLE_SHEET_ID manquant dans .env")
        sh = _get_client().open_by_key(sheet_id)
        _worksheet = sh.worksheet(tab_name)
    return _worksheet


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


def _valeur_identique(brut: str, valeur) -> bool:
    """La cellule du Sheet porte-t-elle déjà cette valeur ?

    Comparaison NUMÉRIQUE quand les deux côtés sont des nombres : le Sheet rend
    « 72000 » là où Python écrit « 72000.0 », et une comparaison de texte conclurait
    à tort qu'il faut réécrire. En cas de doute, on renvoie False — réécrire une
    cellule déjà juste ne coûte qu'un peu de réseau, la laisser périmée fausserait
    ce que l'utilisateur lit dans son Sheet.
    """
    brut = (brut or "").strip()
    attendu = "" if valeur is None else str(valeur).strip()
    if brut == attendu:
        return True
    if not brut or not attendu:
        return False
    try:
        return abs(float(brut.replace(",", ".")) - float(attendu)) < 0.005
    except ValueError:
        return False


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
    """Lit le Sheet, valide chaque ligne, attribue un id aux nouvelles lignes et
    réécrit id + colonnes calculées dans le Sheet. Renvoie (lignes valides, résumé)."""
    # "errors" reste la liste lisible affichee a l'utilisateur ; "issues" en est la
    # version structuree, exploitee par backend/data_quality.py pour regrouper les
    # rejets par cause plutot que de reanalyser des phrases deja formatees.
    summary = {"total_rows": 0, "skipped": 0, "new_ids_assigned": 0, "errors": [],
               "issues": [], "repairs": []}

    ws = _get_worksheet()
    all_values = ws.get_all_values()
    if not all_values:
        return [], summary

    headers = all_values[0]
    missing_headers = [c for c in SHEET_COLUMNS if c not in headers]
    if missing_headers:
        msg = f"Colonnes manquantes dans l'en-tête du Sheet : {', '.join(missing_headers)}"
        logger.error("Chargement des données : %s", msg)
        summary["errors"].append(msg)
        return [], summary

    id_col_index = headers.index("id") + 1  # gspread est indexé à partir de 1
    derived_col_index = {c: headers.index(c) + 1 for c in _DERIVED_SHEET_COLUMNS if c in headers}

    parsed_rows: list[tuple[int, dict]] = []  # (row_number, row)
    # Texte BRUT des colonnes calculées, tel qu'il est actuellement dans le Sheet.
    # Sert à ne renvoyer que les cellules qui changent réellement (voir plus bas).
    brut_par_ligne: dict[int, dict] = {}
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

        cellules = dict(zip(headers, values))
        brut_par_ligne[row_number] = {c: cellules.get(c, "") for c in _DERIVED_SHEET_COLUMNS}
        parsed_rows.append((row_number, row))

    # Un id existant a priorité ; une ligne sans id en reçoit un nouveau (max + 1),
    # attribué dans l'ordre d'apparition — remplace l'AUTO_INCREMENT MySQL d'avant,
    # simplement pour donner une référence stable à une opportunité d'un chargement
    # à l'autre (plus de risque de doublon : il n'y a plus de second store à
    # dédupliquer, on relit tout depuis zéro à chaque fois).
    existing_ids = [int(r["id"]) for _, r in parsed_rows if r["id"].strip().isdigit()]
    next_id = (max(existing_ids) + 1) if existing_ids else 1

    pending_cells = []
    valid_rows: list[dict] = []

    for row_number, row in parsed_rows:
        if row["id"].strip().isdigit():
            row["id"] = int(row["id"])
        else:
            row["id"] = next_id
            next_id += 1
            summary["new_ids_assigned"] += 1
            pending_cells.append(gspread.Cell(row_number, id_col_index, row["id"]))

        for col_name, col_index in derived_col_index.items():
            value = row[col_name]
            if value is None:
                value = ""
            elif col_name == "weighted_amount":
                value = round(value, 2)  # cosmétique seulement — la valeur exacte reste dans les données
            # Seules les cellules qui CHANGENT sont renvoyées. Auparavant les quatre
            # colonnes calculées de chaque ligne repartaient à chaque chargement —
            # près de 1 500 cellules toutes les quinze minutes, pour un contenu le
            # plus souvent identique. Les valeurs brutes sont déjà en mémoire, la
            # comparaison ne coûte rien et supprime l'aller-retour réseau.
            if not _valeur_identique(brut_par_ligne.get(row_number, {}).get(col_name), value):
                pending_cells.append(gspread.Cell(row_number, col_index, value))

        valid_rows.append(row)

    summary["total_rows"] = len(valid_rows)

    if pending_cells:
        try:
            ws.update_cells(pending_cells, value_input_option="RAW")
        except Exception:
            # Les ids déjà attribués en mémoire restent valides pour ce chargement ;
            # seule leur réécriture dans le Sheet a échoué (cosmétique — ils seront
            # réattribués de façon cohérente au prochain chargement).
            logger.exception(
                "Chargement des données : échec de l'écriture retour de %d cellule(s) dans le Sheet.",
                len(pending_cells),
            )
            summary["errors"].append(
                "Id/valeurs calculées non réécrits dans le Sheet (le chargement en mémoire reste correct) — voir les logs."
            )

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
