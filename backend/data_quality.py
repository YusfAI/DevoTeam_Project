"""Rapport de qualité des données du Google Sheet.

Le principe du projet est de ne jamais deviner : une ligne dont le statut n'est pas
reconnu est rejetée plutôt que rattachée au hasard à une valeur voisine. Ce module
rend ces rejets VISIBLES au lieu de les laisser dans les logs — une donnée écartée
silencieusement est un chiffre faux qui s'ignore.

Il ne corrige rien : décider qu'« AMI » saisi dans `status` doit devenir un
`opp_type`, ou qu'« En attente du plan de charge » est un statut légitime à ajouter
à la liste blanche, relève du métier, pas du code.
"""
import logging

import pandas as pd

from .data_store import get_dataframe, get_last_refresh_summary
from .schema_and_whitelist import KNOWN_VALUES

logger = logging.getLogger(__name__)

# Colonnes dont l'absence change réellement une réponse : win_probability vide rend
# tout calcul pondéré partiel, partner vide n'empêche aucune analyse chiffrée.
_WATCHED_COLUMNS = {
    "win_probability": "Rend le montant pondéré incalculable pour la ligne",
    "weighted_amount": "Découle de win_probability",
    "partner": "Information de contexte, sans effet sur les montants",
    "funding_source": "Utilisée comme dimension d'analyse",
    "buyer": "Identifie le client dans les listes et alertes",
}


def _looks_like_another_column(field: str, value: str) -> str:
    """Repère la faute de saisie la plus fréquente : une valeur correcte, mais mise
    dans la mauvaise colonne (« AMI » est un opp_type valide, pas un statut)."""
    for other_field, known in KNOWN_VALUES.items():
        if other_field == field:
            continue
        if any(str(value).strip().lower() == k.lower() for k in known):
            return other_field
    return ""


def rejected_rows() -> list:
    """Lignes écartées au dernier chargement, regroupées par cause."""
    summary = get_last_refresh_summary() or {}
    grouped: dict = {}
    for issue in summary.get("issues", []):
        key = (issue.get("field", "?"), issue.get("value", ""))
        entry = grouped.setdefault(key, {
            "colonne": key[0],
            "valeur": key[1],
            "nb_lignes": 0,
            "lignes": [],
            "diagnostic": "",
        })
        entry["nb_lignes"] += 1
        entry["lignes"].append(issue.get("row"))

    for entry in grouped.values():
        autre = _looks_like_another_column(entry["colonne"], entry["valeur"])
        if autre:
            entry["diagnostic"] = (
                f"« {entry['valeur']} » est une valeur valide de « {autre} » — "
                f"probable erreur de colonne à la saisie."
            )
        else:
            entry["diagnostic"] = (
                f"« {entry['valeur']} » n'existe pas dans la liste blanche de "
                f"« {entry['colonne']} » — à corriger dans le Sheet, ou à ajouter à la "
                f"liste si la valeur est légitime."
            )
    return sorted(grouped.values(), key=lambda e: -e["nb_lignes"])


def missing_values() -> list:
    """Taux de valeurs manquantes sur les colonnes qui comptent."""
    df = get_dataframe()
    if df is None or df.empty:
        return []
    total = len(df)
    result = []
    for column, effet in _WATCHED_COLUMNS.items():
        if column not in df.columns:
            continue
        manquantes = int(df[column].isna().sum())
        if manquantes:
            result.append({
                "colonne": column,
                "nb_manquantes": manquantes,
                "part": manquantes / total,
                "consequence": effet,
            })
    return sorted(result, key=lambda r: -r["part"])


def report() -> dict:
    """Rapport complet, tel que renvoyé par GET /data/quality."""
    summary = get_last_refresh_summary() or {}
    rejets = rejected_rows()
    return {
        "lignes_chargees": summary.get("total_rows", 0),
        "lignes_rejetees": summary.get("skipped", 0),
        "rejets": rejets,
        "valeurs_manquantes": missing_values(),
    }


def quality_dataframe() -> pd.DataFrame:
    """Le même rapport à plat, pour être projeté dans DuckDB et interrogé par un
    dashboard DAC (voir dac/dashboards/qualite.yml) — même chemin que les données
    métier, donc toujours cohérent avec le dernier chargement."""
    lignes = []
    for rejet in rejected_rows():
        lignes.append({
            "categorie": "Ligne rejetée",
            "sujet": f"{rejet['colonne']} = {rejet['valeur']}",
            "nb": rejet["nb_lignes"],
            "part": None,
            "detail": rejet["diagnostic"],
        })
    for manque in missing_values():
        lignes.append({
            "categorie": "Valeur manquante",
            "sujet": manque["colonne"],
            "nb": manque["nb_manquantes"],
            "part": manque["part"],
            "detail": manque["consequence"],
        })
    return pd.DataFrame(
        lignes, columns=["categorie", "sujet", "nb", "part", "detail"])
