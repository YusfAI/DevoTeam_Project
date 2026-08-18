"""Traduit une intention DÉJÀ VALIDÉE en SQL DuckDB pour les widgets DAC.

Le LLM n'écrit jamais ce SQL : il produit seulement une intention (métrique,
dimension, filtres) bornée par la liste blanche de schema_and_whitelist.py, et
c'est ce module qui la traduit. Les noms de colonnes proviennent donc toujours de
la liste blanche, jamais de texte libre, et les valeurs de filtres ont déjà été
résolues contre les valeurs réellement présentes dans les données (llm.py::
_resolve_filter_value) avant d'arriver ici.

Pendant natif de db_layer.py : même intention en entrée, mais du SQL pour DAC
plutôt qu'une opération pandas. Les deux doivent rester d'accord — c'est vérifié
par les tests (même filtre => même total).
"""
from .schema_and_whitelist import VALID_DIMENSIONS, VALID_FILTERS, VALID_METRICS
from .vega_generator import FUNNEL_STAGE_ORDER

TABLE = "opportunities"

METRIC_SQL = {
    "budget": "SUM(budget)",
    "financial_offer": "SUM(financial_offer)",
    "weighted_amount": "SUM(weighted_amount)",
    "nb_opportunities": "COUNT(*)",
    "win_probability": "AVG(win_probability)",
}

RAW_COLUMNS = [
    "buyer", "country", "practice", "status", "deadline",
    "days_remaining", "budget", "win_probability",
]

VALID_OPS = {"<", ">", "<=", ">=", "=", "between"}

# Colonnes numériques : leurs valeurs de filtre ne doivent pas être quotées comme
# du texte (WHERE deadline_year = 2026, pas = '2026').
_NUMERIC_COLUMNS = {"budget", "financial_offer", "weighted_amount", "win_probability",
                    "days_remaining", "deadline_year"}


def _literal(column: str, value) -> str:
    """Valeur SQL sûre. Les apostrophes sont doublées — indispensable ici : les
    vraies données en contiennent (« Côte d'Ivoire », « Complément d'information »),
    et sans ce doublement la requête serait syntaxiquement cassée."""
    if column in _NUMERIC_COLUMNS:
        return str(float(value)) if "." in str(value) else str(int(float(value)))
    return "'" + str(value).replace("'", "''") + "'"


def _where_clause(intent: dict) -> str:
    conditions = []

    for column, value in (intent.get("filters") or {}).items():
        if column not in VALID_FILTERS:
            continue  # défense en profondeur : déjà rejeté en amont par Pydantic
        if isinstance(value, (list, tuple)):
            if not value:
                continue
            values = ", ".join(_literal(column, v) for v in value)
            conditions.append(f"{column} IN ({values})")
        else:
            conditions.append(f"{column} = {_literal(column, value)}")

    for column, rule in (intent.get("range_filters") or {}).items():
        if column not in VALID_FILTERS and column not in ("days_remaining", "win_probability", "budget"):
            continue
        op = (rule or {}).get("op", "<")
        value = (rule or {}).get("value")
        if op not in VALID_OPS or value is None:
            continue
        if op == "between":
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                continue
            lo, hi = _literal(column, value[0]), _literal(column, value[1])
            conditions.append(f"{column} BETWEEN {lo} AND {hi}")
        else:
            conditions.append(f"{column} {op} {_literal(column, value)}")

    excluded = intent.get("exclude_statuses") or []
    if excluded:
        values = ", ".join(_literal("status", s) for s in excluded)
        conditions.append(f"status NOT IN ({values})")

    return " AND ".join(conditions) if conditions else "1 = 1"


def _metric_expr(metric: str) -> str:
    return METRIC_SQL.get(metric, METRIC_SQL["budget"])


def build_sql(intent: dict) -> str:
    """SQL DuckDB correspondant à l'intention, adapté au type de graphique."""
    metric = intent.get("metric") or "budget"
    if metric not in VALID_METRICS:
        metric = "budget"
    dimension = intent.get("dimension") or ""
    if dimension and dimension not in VALID_DIMENSIONS:
        dimension = ""
    chart_type = intent.get("chart_type") or "bar"
    limit = int(intent.get("limit") or 0)
    where = _where_clause(intent)
    expr = _metric_expr(metric)

    if chart_type == "funnel":
        # Ordre du pipeline commercial, jamais l'ordre des valeurs : un entonnoir
        # trié par volume ne raconterait rien du parcours réel. Les statuts de
        # sortie (perdu, NO GO…) sont exclus — ce sont des sorties, pas des étapes.
        cases = "\n".join(
            f"    WHEN {_literal('status', stage)} THEN {i + 1}"
            for i, stage in enumerate(FUNNEL_STAGE_ORDER)
        )
        stages = ", ".join(_literal("status", s) for s in FUNNEL_STAGE_ORDER)
        return (
            f"SELECT status, {expr} AS {metric},\n"
            f"  CASE status\n{cases}\n  END AS etape\n"
            f"FROM {TABLE}\n"
            f"WHERE ({where}) AND status IN ({stages})\n"
            f"GROUP BY status\n"
            f"ORDER BY etape"
        )

    if chart_type == "heatmap" and dimension:
        secondary = "country" if dimension == "practice" else "practice"
        return (
            f"SELECT {dimension}, {secondary}, {expr} AS {metric}\n"
            f"FROM {TABLE}\nWHERE {where}\n"
            f"GROUP BY {dimension}, {secondary}\n"
            f"ORDER BY {metric} DESC"
        )

    if chart_type == "scatter":
        return (
            "SELECT buyer, country, practice, budget, win_probability, weighted_amount\n"
            f"FROM {TABLE}\n"
            f"WHERE ({where}) AND budget IS NOT NULL AND win_probability IS NOT NULL\n"
            "ORDER BY budget DESC"
        )

    if chart_type == "table" or intent.get("use_raw_table"):
        columns = ", ".join(RAW_COLUMNS)
        sql = f"SELECT {columns}\nFROM {TABLE}\nWHERE {where}\nORDER BY days_remaining ASC"
        # Plafond par défaut : un tableau de plusieurs centaines de lignes dans un
        # widget de dashboard n'est pas lisible, et alourdit inutilement la réponse.
        return f"{sql}\nLIMIT {limit if limit > 0 else 50}"

    if not dimension:
        return f"SELECT {expr} AS value\nFROM {TABLE}\nWHERE {where}"

    order = f"{dimension} ASC" if dimension == "deadline_month" else f"{metric} DESC"
    sql = (
        f"SELECT {dimension}, {expr} AS {metric}\n"
        f"FROM {TABLE}\nWHERE {where}\n"
        f"GROUP BY {dimension}\n"
        f"ORDER BY {order}"
    )
    if limit > 0:
        sql += f"\nLIMIT {limit}"
    elif dimension != "deadline_month":
        # Plafond de lisibilité : au-delà, un graphique catégoriel devient illisible
        # (même principe que MAX_BAR_CATEGORIES côté Vega).
        sql += "\nLIMIT 12"
    return sql
