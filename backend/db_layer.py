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

from .business_rules import (
    ISSUE_DIMENSION, LOST_STATUSES, heatmap_secondary_dimension, hot_deal_mask,
    issue_series,
)
from .data_store import get_dataframe

INT_COLS = {"deadline_year", "days_remaining", "id"}
# `deadline` porte des objets `datetime.date`, jamais du texte : comparer la colonne
# à une chaîne ISO lève un TypeError au lieu de filtrer. La borne arrive pourtant
# toujours en ISO, seule forme qui traverse le JSON de l'intention.
DATE_COLS = {"deadline"}
FLOAT_COLS = {"budget", "financial_offer", "weighted_amount", "win_probability"}
VALID_OPS = {"<", ">", "<=", ">=", "=", "between"}

# Agrégation PAR DÉFAUT de chaque métrique : un montant se somme, une probabilité se
# moyenne, des opportunités se comptent. C'est le défaut, plus la règle absolue qu'elle
# était : une question qui demande explicitement une moyenne (« budget moyen par
# pays ») la reçoit — voir `_agregation`. Ignorer ce mot faisait afficher une somme
# sous une étiquette de moyenne, à un facteur 74 près.
METRIC_AGG = {
    "budget": ("budget", "sum"),
    "financial_offer": ("financial_offer", "sum"),
    "weighted_amount": ("weighted_amount", "sum"),
    "nb_opportunities": (None, "count"),
    "win_probability": ("win_probability", "mean"),
}


def _agregation(metric: str, intent: dict) -> tuple:
    """(colonne, opération pandas) en tenant compte de l'agrégation demandée.

    Seule "avg" peut surcharger le défaut, et jamais pour un comptage : « nombre
    moyen d'opportunités » n'a pas de sens sans préciser moyen SUR QUOI, et la
    probabilité de gain est déjà une moyenne.
    """
    col, how = METRIC_AGG.get(metric, ("budget", "sum"))
    if how == "sum" and (intent or {}).get("aggregation") == "avg":
        return col, "mean"
    return col, how

RAW_TABLE_COLUMNS = [
    "country", "practice", "status", "buyer", "budget",
    "financial_offer", "win_probability", "weighted_amount", "days_remaining", "deadline",
]


def _cast(col: str, val):
    if col in DATE_COLS and isinstance(val, str):
        return datetime.date.fromisoformat(val)
    if col in INT_COLS:
        return int(val)
    if col in FLOAT_COLS:
        return float(val)
    return val


def _apply_filters(df: pd.DataFrame, filters: dict, range_filters: dict,
                   exclude_statuses: list, exclude_filters: dict | None = None,
                   hot_deals: bool = False) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)

    # « Affaire chaude » : déjà remise OU probabilité >= 80 %. Une RÉUNION, que les
    # filtres de l'intention — tous combinés par ET — ne savent pas exprimer. La
    # définition vit dans business_rules, une seule fois pour les deux moteurs.
    if hot_deals:
        mask &= hot_deal_mask(df)

    for col, val in filters.items():
        if col not in df.columns:
            continue
        if isinstance(val, (list, tuple)):
            mask &= df[col].isin([_cast(col, v) for v in val])
        else:
            mask &= df[col] == _cast(col, val)

    # Exclusions sur une colonne autre que le statut (« hors Tunisie », « sauf Risk
    # Advisory »). Même règle que dans sql_builder._where_clause, et pour la même
    # raison : sans elle, le mot de négation était ignoré et la valeur partait en
    # filtre POSITIF — la réponse donnait alors l'inverse exact de la question.
    for col, val in (exclude_filters or {}).items():
        if col not in df.columns:
            continue
        valeurs = val if isinstance(val, (list, tuple)) else [val]
        valeurs = [_cast(col, v) for v in valeurs if v is not None]
        if not valeurs:
            continue
        # Les lignes SANS valeur restent : « hors Tunisie » les concerne aussi.
        mask &= ~df[col].isin(valeurs)

    # Exclusion par défaut des affaires perdues, identique à celle du SQL des widgets
    # (sql_builder._where_clause) : sans cette symétrie, le message du chat et les
    # graphiques annonceraient deux totaux différents pour la même question.
    # Levée si la question filtre elle-même sur le statut — voir _question_targets_status.
    excluded = list(exclude_statuses or [])
    if "status" not in filters:
        excluded += [s for s in LOST_STATUSES if s not in excluded]

    if excluded and "status" in df.columns:
        mask &= ~df["status"].isin(excluded)

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


def _agg_metric(grouped, metric: str, intent: dict | None = None):
    col, how = _agregation(metric, intent or {})
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
    exclude_filters = intent.get("exclude_filters") or {}
    hot_deals = bool(intent.get("hot_deals"))
    limit = int(intent.get("limit") or 0)

    # Le scatter a besoin de plusieurs mesures par opportunité (budget, probabilité
    # de gain, montant pondéré) — jamais une seule mesure agrégée par dimension, donc
    # il emprunte le même chemin "lignes brutes" que use_raw_table.
    #
    # La présence d'un range_filter ne déclenche PLUS ce chemin. Elle le faisait, et
    # les deux moteurs divergeaient : sql_builder groupait « affaires chaudes par
    # practice » comme demandé pendant que pandas renvoyait la liste brute — le
    # graphique et le message du chat ne racontaient donc pas la même chose pour une
    # question identique. Le souhait d'une liste s'exprime par use_raw_table ou
    # chart_type == "table", jamais par le seul fait de borner une valeur.
    use_raw = intent.get("use_raw_table", False) or chart_type in ("table", "scatter")

    filtered = _apply_filters(df, filters, range_filters, exclude_statuses,
                              exclude_filters, hot_deals)

    # « issue » n'existe pas dans les données : elle se calcule depuis le statut.
    # La colonne est ajoutée APRÈS le filtrage — la calculer avant reviendrait à la
    # faire porter sur des lignes que la question écarte. La définition vient de
    # business_rules, la même que celle du SQL, pour que les deux moteurs ne puissent
    # pas ranger une offre dans deux cases différentes.
    if ISSUE_DIMENSION in (dimension, intent.get("secondary_dimension")):
        filtered = filtered.assign(**{ISSUE_DIMENSION: issue_series(filtered)})

    # « combien de clients différents » : une CARDINALITÉ, pas un volume. Placé avant
    # tout le reste — la question ne demande ni répartition, ni liste, ni graphique.
    compte = intent.get("count_distinct")
    if compte and compte in filtered.columns:
        if dimension and dimension in filtered.columns:
            # Regroupé : « combien de clients distincts PAR practice ».
            distincts = filtered.groupby(dimension)[compte].nunique()
            return _to_records(distincts.reset_index(name="nb_opportunities"))
        return _to_records(pd.DataFrame([{"nb_opportunities": int(filtered[compte].nunique())}]))

    if chart_type == "heatmap" and dimension:
        secondary = heatmap_secondary_dimension(dimension)
        grouped = filtered.groupby([dimension, secondary])
        values = _agg_metric(grouped, metric, intent)
        result = values.reset_index(name=metric)
        return _to_records(result)

    if use_raw:
        result = filtered[RAW_TABLE_COLUMNS].sort_values("days_remaining", ascending=True)
        if limit > 0:
            result = result.head(limit)
        return _to_records(result)

    if not dimension:
        col, how = _agregation(metric, intent)
        if how == "count":
            value = len(filtered)
        elif filtered.empty:
            value = None
        else:
            value = filtered[col].agg(how)
        alias = metric if metric != "nb_opportunities" else "nb_opportunities"
        return _to_records(pd.DataFrame([{alias: value}]))

    grouped = filtered.groupby(dimension)
    metric_values = _agg_metric(grouped, metric, intent)
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
