"""Rapport de qualité des données du Google Sheet.

Le principe du projet est de ne jamais deviner : une cellule dont la valeur n'est pas
reconnue n'est jamais rattachée au hasard à une valeur voisine. Elle est remplacée
par « Non renseigné », qui n'invente rien — il DIT que la donnée manque — et la ligne
est conservée : rejeter l'opportunité entière pour une cellule fautive faisait perdre
son budget, son échéance et son client avec elle.

Ce module est la contrepartie de cette tolérance. Réparer sans tracer reviendrait à
corrompre les données en silence, exactement ce que le rejet servait à éviter :
chaque cellule remplacée est donc recensée ici, avec sa ligne, sa colonne et sa valeur
d'origine, et diagnostiquée quand la faute est reconnaissable (« AMI » saisi dans
`status` est une valeur valide d'`opp_type`).

Il ne corrige rien DANS LE SHEET : décider qu'une valeur inconnue est légitime et
doit rejoindre la liste blanche relève du métier, pas du code.
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


def repaired_cells() -> list:
    """Cellules remplacées au dernier chargement, regroupées par cause.

    Ce sont les anomalies qui, avant, coûtaient la ligne entière. Les voir groupées
    par colonne et valeur montre immédiatement s'il s'agit d'une faute isolée ou d'une
    colonne systématiquement mal remplie.
    """
    summary = get_last_refresh_summary() or {}
    grouped: dict = {}
    for repair in summary.get("repairs", []):
        key = (repair.get("field", "?"), repair.get("value", ""))
        entry = grouped.setdefault(key, {
            "colonne": key[0],
            "valeur": key[1],
            "nb_lignes": 0,
            "lignes": [],
            "diagnostic": "",
        })
        entry["nb_lignes"] += 1
        entry["lignes"].append(repair.get("row"))

    for entry in grouped.values():
        vide = not entry["valeur"]
        autre = _looks_like_another_column(entry["colonne"], entry["valeur"])
        if vide:
            entry["diagnostic"] = (
                f"« {entry['colonne']} » est vide sur ces lignes — la ligne est conservée, "
                f"la colonne marquée « Non renseigné »."
            )
        elif autre:
            entry["diagnostic"] = (
                f"« {entry['valeur']} » est une valeur valide de « {autre} » — probable "
                f"erreur de colonne à la saisie. La ligne est conservée, la colonne "
                f"« {entry['colonne']} » marquée « Non renseigné »."
            )
        else:
            entry["diagnostic"] = (
                f"« {entry['valeur']} » n'existe pas dans la liste blanche de "
                f"« {entry['colonne']} » — à corriger dans le Sheet, ou à ajouter à la "
                f"liste si la valeur est légitime. La ligne est conservée en attendant."
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
    reparations = repaired_cells()
    return {
        "lignes_chargees": summary.get("total_rows", 0),
        "lignes_rejetees": summary.get("skipped", 0),
        "cellules_reparees": sum(e["nb_lignes"] for e in reparations),
        "rejets": rejets,
        "reparations": reparations,
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
    for reparation in repaired_cells():
        lignes.append({
            "categorie": "Cellule réparée",
            "sujet": f"{reparation['colonne']} = {reparation['valeur'] or '(vide)'}",
            "nb": reparation["nb_lignes"],
            "part": None,
            "detail": reparation["diagnostic"],
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
