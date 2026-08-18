"""Construit et exécute une requête sur le DataFrame en mémoire (backend/data_store.py)
à partir d'une intention validée. Remplace l'ancienne couche SQL/MySQL — même
contrat d'entrée (intent dict) et de sortie (list[dict]) qu'avant, donc
response_builder.py et le générateur de graphiques n'ont pas besoin de changer.

Simplification par rapport à la version MySQL : plus de vues pré-agrégées à
choisir ni de repli "la vue ne supporte pas ce filtre" — pandas groupe
uniformément sur le DataFrame complet quelle que soit la combinaison
filtre/dimension/métrique.
"""
import datetime

import pandas as pd

from .data_store import get_dataframe

INT_COLS = {"deadline_year", "days_remaining", "id"}
FLOAT_COLS = {"budget", "financial_offer", "weighted_amount", "win_probability"}
VALID_OPS = {"<", ">", "<=", ">=", "=", "between"}

# Une valeur de metric détermine SA PROPRE agrégation, indépendamment du champ
# "aggregation" de l'intention (déjà le comportement de l'ancienne couche SQL —
# budget est toujours sommé, win_probability toujours moyenné, etc.).
METRIC_AGG = {
    "budget": ("budget", "sum"),
    "financial_offer": ("financial_offer", "sum"),
    "weighted_amount": ("weighted_amount", "sum"),
    "nb_opportunities": (None, "count"),
    "win_probability": ("win_probability", "mean"),
}

RAW_TABLE_COLUMNS = [
    "country", "practice", "status", "buyer", "budget",
    "financial_offer", "win_probability", "weighted_amount", "days_remaining", "deadline",
]


def _cast(col: str, val):
    if col in INT_COLS:
        return int(val)
    if col in FLOAT_COLS:
        return float(val)
    return val


def _apply_filters(df: pd.DataFrame, filters: dict, range_filters: dict, exclude_statuses: list) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)

    for col, val in filters.items():
        if col not in df.columns:
            continue
        if isinstance(val, (list, tuple)):
            mask &= df[col].isin([_cast(col, v) for v in val])
        else:
            mask &= df[col] == _cast(col, val)

    if exclude_statuses and "status" in df.columns:
        mask &= ~df["status"].isin(exclude_statuses)

    for col, rule in range_filters.items():
        if col not in df.columns:
            continue
        op = rule.get("op", "<")
        value = rule.get("value")
        if op not in VALID_OPS:
            continue
        if op == "between":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                continue
            lo, hi = _cast(col, value[0]), _cast(col, value[1])
            mask &= df[col].between(lo, hi)
        elif op == "<":
            mask &= df[col] < _cast(col, value)
        elif op == ">":
            mask &= df[col] > _cast(col, value)
        elif op == "<=":
            mask &= df[col] <= _cast(col, value)
        elif op == ">=":
            mask &= df[col] >= _cast(col, value)
        elif op == "=":
            mask &= df[col] == _cast(col, value)

    return df[mask]


def _agg_metric(grouped, metric: str):
    col, how = METRIC_AGG.get(metric, ("budget", "sum"))
    if how == "count":
        return grouped.size()
    return grouped[col].agg(how)


def _to_records(df: pd.DataFrame) -> list:
    """Convertit un DataFrame en list[dict] JSON-compatible : NaN -> None, dates
    -> ISO — même contrat de sortie que l'ancienne couche SQL/pymysql (list[dict],
    dates en ISO 8601, valeurs manquantes en None)."""
    records = df.where(pd.notnull(df), None).to_dict("records")
    for r in records:
        for key, val in list(r.items()):
            if isinstance(val, (datetime.date, datetime.datetime, pd.Timestamp)):
                r[key] = val.isoformat() if hasattr(val, "isoformat") else str(val)
            elif isinstance(val, float) and pd.isna(val):
                r[key] = None
    return records


def build_and_execute_query(intent: dict) -> list:
    df = get_dataframe()
    if df is None or df.empty:
        return []

    dimension = intent.get("dimension", "")
    metric = intent.get("metric", "budget")
    filters = intent.get("filters", {})
    range_filters = intent.get("range_filters", {})
    chart_type = intent.get("chart_type", "")
    exclude_statuses = intent.get("exclude_statuses") or []
    limit = int(intent.get("limit") or 0)

    # Le scatter a besoin de plusieurs mesures par opportunité (budget, probabilité
    # de gain, montant pondéré) — jamais une seule mesure agrégée par dimension,
    # donc il emprunte le même chemin "lignes brutes" que use_raw_table/range_filters.
    use_raw = intent.get("use_raw_table", False) or bool(range_filters) or chart_type == "scatter"

    filtered = _apply_filters(df, filters, range_filters, exclude_statuses)

    if chart_type == "heatmap" and dimension:
        secondary = "country" if dimension == "practice" else "practice"
        grouped = filtered.groupby([dimension, secondary])
        values = _agg_metric(grouped, metric)
        result = values.reset_index(name=metric)
        return _to_records(result)

    if use_raw:
        result = filtered[RAW_TABLE_COLUMNS].sort_values("days_remaining", ascending=True)
        if limit > 0:
            result = result.head(limit)
        return _to_records(result)

    if not dimension:
        col, how = METRIC_AGG.get(metric, ("budget", "sum"))
        if how == "count":
            value = len(filtered)
        elif filtered.empty:
            value = None
        else:
            value = filtered[col].agg(how)
        alias = metric if metric != "nb_opportunities" else "nb_opportunities"
        return _to_records(pd.DataFrame([{alias: value}]))

    grouped = filtered.groupby(dimension)
    metric_values = _agg_metric(grouped, metric)
    nb_opportunities = grouped.size()

    # Colonnes construites une par une (pas un seul dict littéral) : quand
    # metric == "budget", une clé "budget" littérale entrerait en collision avec la
    # clé metric et écraserait silencieusement la valeur voulue.
    result = pd.DataFrame({dimension: metric_values.index})
    result[metric] = metric_values.values
    result["nb_opportunities"] = nb_opportunities.reindex(metric_values.index).values
    if "budget" not in result.columns:
        result["budget"] = grouped["budget"].agg("sum").reindex(metric_values.index).values

    if dimension == "deadline_month":
        result = result.sort_values(dimension, ascending=True)
    else:
        result = result.sort_values(metric, ascending=False, na_position="last")

    if limit > 0:
        result = result.head(limit)

    return _to_records(result)
