"""Synchronisation Google Sheets -> MySQL : le Sheet sert de formulaire d'ajout et
de modification d'opportunités (plus simple à éditer que la base directement). Sens
UNIQUE — l'application continue de LIRE depuis MySQL comme avant (chat, graphiques,
alertes) ; ce module importe seulement les changements du Sheet vers la base.

Champs calculés automatiquement à chaque synchronisation (jamais lus depuis le
Sheet, même s'ils y figurent en colonne) : deadline_month, deadline_year,
days_remaining, weighted_amount — dérivés des colonnes "brutes" pour ne jamais
diverger d'elles (voir backend/maintenance.py pour le même principe sur
days_remaining).
"""
import logging
import os
from datetime import date, datetime

import gspread

from .db import get_connection
from .schema_and_whitelist import KNOWN_VALUES

logger = logging.getLogger(__name__)

# Colonnes "brutes" attendues dans le Sheet (n'importe quel ordre, en-têtes exacts).
# id vide/absent = nouvelle opportunité (insérée, puis son id est réécrit dans le
# Sheet) ; id renseigné = mise à jour de la ligne MySQL correspondante.
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

_UPSERT_COLUMNS = (
    "country", "created_date", "deadline", "deadline_month", "deadline_year",
    "days_remaining", "practice", "description", "buyer", "opp_type", "status",
    "budget", "funding_source", "partner", "financial_offer", "win_probability",
    "weighted_amount",
)

# Volontairement PAS de suppression automatique : une ligne retirée du Sheet ne
# supprime jamais l'opportunité correspondante en base. Une synchro automatique,
# non surveillée (toutes les 15 min + au démarrage) est le mauvais endroit pour une
# opération destructive et irréversible — une lecture partielle, un mauvais onglet,
# ou un Sheet vidé par erreur pourrait effacer de vraies données sans que personne
# ne le voie venir. Ajout/modification seulement.

_client = None
_worksheet = None


def _get_client():
    global _client
    if _client is None:
        creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials/google_service_account.json")
        _client = gspread.service_account(filename=creds_path)
    return _client


def _get_worksheet():
    # open_by_key() + worksheet() sont chacun un aller-retour réseau vers l'API
    # Sheets (~1.6s mesuré à eux deux) — le seul sur les quatre du sheet_id/nom
    # d'onglet fixes pour la durée du process, donc pas besoin de les refaire à
    # chaque synchro (toutes les 15 min, indéfiniment). Seul get_all_values()/
    # update_cell() doivent rester des appels frais à chaque fois (données à jour).
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
    seulement journalisée et sautée (voir sync_sheet_to_mysql)."""


def _parse_date(raw: str, field: str) -> date:
    raw = (raw or "").strip()
    if not raw:
        raise RowError(f"{field} est vide")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise RowError(f"{field}='{raw}' n'est pas une date valide (attendu AAAA-MM-JJ)")


def _parse_float(raw: str, field: str):
    raw = (raw or "").strip().replace(",", ".").replace(" ", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise RowError(f"{field}='{raw}' n'est pas un nombre valide")


def _parse_win_probability(raw: str):
    value = _parse_float(raw, "win_probability")
    if value is None:
        return None
    # Tolère les deux saisies naturelles : "0.8" (déjà une fraction, comme stocké en
    # base) ou "80" (un pourcentage tapé tel quel) — jamais > 1 stocké en base.
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
    raise RowError(f"{field}='{raw}' non reconnu — valeurs attendues : {', '.join(known)}")


def _parse_row(headers: list, values: list) -> dict:
    """Transforme une ligne brute du Sheet en dict validé, champs dérivés déjà
    calculés. Lève RowError (message précis) si la ligne est invalide."""
    raw = dict(zip(headers, values))

    def get(field):
        # L'export CSV -> Sheets écrit parfois les NULL MySQL comme le texte littéral
        # "NULL" au lieu d'une cellule vide — sans ce nettoyage, "NULL" finirait
        # stocké tel quel comme valeur de chaîne (ex: partner = "NULL").
        value = (raw.get(field) or "").strip()
        if value.upper() in ("NULL", "NONE", "N/A", "#N/A"):
            return ""
        return value

    row = {"id": get("id")}

    row["country"] = get("country") or None
    if not row["country"]:
        raise RowError("country est vide")

    row["created_date"] = _parse_date(get("created_date"), "created_date")
    row["deadline"] = _parse_date(get("deadline"), "deadline")

    row["practice"] = _normalize_choice(get("practice"), "practice")
    row["opp_type"] = _normalize_choice(get("opp_type"), "opp_type")
    row["status"] = _normalize_choice(get("status"), "status")

    row["description"] = get("description") or None
    row["buyer"] = get("buyer") or None
    row["funding_source"] = get("funding_source") or None
    row["partner"] = get("partner") or None

    row["budget"] = _parse_float(get("budget"), "budget")
    row["financial_offer"] = _parse_float(get("financial_offer"), "financial_offer")
    row["win_probability"] = _parse_win_probability(get("win_probability"))

    # --- Champs dérivés — jamais lus depuis le Sheet, toujours recalculés ---
    row["deadline_month"] = row["deadline"].strftime("%Y-%m")
    row["deadline_year"] = row["deadline"].year
    row["days_remaining"] = (row["deadline"] - date.today()).days
    if row["financial_offer"] is not None and row["win_probability"] is not None:
        row["weighted_amount"] = row["financial_offer"] * row["win_probability"]
    else:
        row["weighted_amount"] = None

    return row


def _insert_opportunity(cur, row: dict) -> int:
    columns = ", ".join(_UPSERT_COLUMNS)
    placeholders = ", ".join(["%s"] * len(_UPSERT_COLUMNS))
    cur.execute(
        f"INSERT INTO opportunities ({columns}) VALUES ({placeholders})",
        tuple(row[c] for c in _UPSERT_COLUMNS),
    )
    return cur.lastrowid


def _update_opportunity(cur, opp_id: int, row: dict) -> None:
    assignments = ", ".join(f"{c} = %s" for c in _UPSERT_COLUMNS)
    cur.execute(
        f"UPDATE opportunities SET {assignments} WHERE id = %s",
        tuple(row[c] for c in _UPSERT_COLUMNS) + (opp_id,),
    )
    # Ne PAS utiliser cur.rowcount pour détecter si la ligne existe : PyMySQL (sans
    # CLIENT_FOUND_ROWS) renvoie le nombre de lignes RÉELLEMENT MODIFIÉES, pas le
    # nombre de lignes trouvées — un UPDATE qui ne change aucune valeur (le cas
    # courant si le Sheet est déjà identique à la base) renvoie rowcount=0 même sur
    # un id existant. D'où le pré-chargement des ids existants dans sync_sheet_to_mysql().


def sync_sheet_to_mysql() -> dict:
    """Point d'entrée : lit le Sheet, met à jour/insère dans MySQL, écrit l'id des
    nouvelles lignes dans le Sheet. Une ligne invalide est journalisée et sautée,
    jamais bloquante pour les autres lignes."""
    summary = {"inserted": 0, "updated": 0, "skipped": 0, "errors": []}

    try:
        ws = _get_worksheet()
        all_values = ws.get_all_values()
    except Exception:
        logger.exception("Synchronisation Sheets : impossible de lire le Sheet.")
        summary["errors"].append("Lecture du Sheet impossible — voir les logs.")
        return summary

    if not all_values:
        return summary

    headers = all_values[0]
    missing_headers = [c for c in SHEET_COLUMNS if c not in headers]
    if missing_headers:
        msg = f"Colonnes manquantes dans l'en-tête du Sheet : {', '.join(missing_headers)}"
        logger.error("Synchronisation Sheets : %s", msg)
        summary["errors"].append(msg)
        return summary
    id_col_index = headers.index("id") + 1  # gspread est indexé à partir de 1

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Pré-chargé une seule fois : sert à distinguer "id existant" d'"id
            # inconnu" sans dépendre de cur.rowcount (non fiable pour ça, voir
            # _update_opportunity).
            cur.execute("SELECT id FROM opportunities")
            existing_ids = {r["id"] for r in cur.fetchall()}

            for offset, values in enumerate(all_values[1:], start=1):
                row_number = offset + 1  # +1 pour la ligne d'en-tête
                if not any(v.strip() for v in values):
                    continue  # ligne totalement vide — ignorée silencieusement

                try:
                    row = _parse_row(headers, values)
                except RowError as e:
                    logger.warning("Synchronisation Sheets : ligne %d ignorée — %s", row_number, e)
                    summary["skipped"] += 1
                    summary["errors"].append(f"Ligne {row_number} : {e}")
                    continue

                if row["id"]:
                    try:
                        opp_id = int(row["id"])
                    except ValueError:
                        logger.warning("Synchronisation Sheets : ligne %d — id='%s' invalide.", row_number, row["id"])
                        summary["skipped"] += 1
                        summary["errors"].append(f"Ligne {row_number} : id '{row['id']}' invalide")
                        continue
                    if opp_id not in existing_ids:
                        logger.warning("Synchronisation Sheets : ligne %d — id=%d introuvable en base.", row_number, opp_id)
                        summary["skipped"] += 1
                        summary["errors"].append(f"Ligne {row_number} : id {opp_id} introuvable en base")
                        continue
                    _update_opportunity(cur, opp_id, row)
                    summary["updated"] += 1
                else:
                    new_id = _insert_opportunity(cur, row)
                    summary["inserted"] += 1
                    try:
                        ws.update_cell(row_number, id_col_index, new_id)
                    except Exception:
                        # L'insertion MySQL a déjà réussi ; seule l'écriture retour a échoué.
                        # Sans elle, cette ligne serait réinsérée au prochain passage —
                        # signalé bruyamment pour une correction manuelle si besoin.
                        logger.exception(
                            "Synchronisation Sheets : id %d inséré mais échec de l'écriture "
                            "retour dans le Sheet (ligne %d) — risque de doublon au prochain sync.",
                            new_id, row_number,
                        )
                        summary["errors"].append(
                            f"Ligne {row_number} : insérée (id {new_id}) mais écriture de "
                            "l'id dans le Sheet a échoué — corrige-la manuellement."
                        )
        conn.commit()

    logger.info(
        "Synchronisation Sheets : %d insérée(s), %d mise(s) à jour, %d ignorée(s).",
        summary["inserted"], summary["updated"], summary["skipped"],
    )
    return summary
