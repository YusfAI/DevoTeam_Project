from .db import get_connection
from .schema_and_whitelist import ALLOWED_TABLES

INT_COLS = {"deadline_year", "days_remaining"}
FLOAT_COLS = {"budget", "financial_offer", "weighted_amount", "win_probability"}
VALID_OPS = {"<", ">", "<=", ">=", "=", "between"}

METRIC_EXPR = {
    "budget": "SUM(budget)",
    "financial_offer": "SUM(financial_offer)",
    "weighted_amount": "SUM(weighted_amount)",
    "nb_opportunities": "COUNT(*)",
    "win_probability": "AVG(win_probability)",
}

# Vue pré-agrégée à utiliser pour chaque dimension (seules les vues qui existent réellement
# en base). Une dimension sans vue dédiée (deadline_year, opp_type) retombe explicitement
# sur "opportunities", ce qui déclenche le calcul groupé à la volée (use_grouped) plutôt que
# de fabriquer un nom de vue inexistant.
_DIMENSION_VIEWS = {
    "country": "v_by_country",
    "practice": "v_by_practice",
    "status": "v_by_status",
    "deadline_month": "v_by_month",
    "funding_source": "v_by_funding_source",
}

# Alias de colonne metric -> colonne agrégée telle que stockée dans les vues.
_VIEW_METRIC_ALIASES = {
    "budget": "total_budget",
    "financial_offer": "total_offer",
    "weighted_amount": "total_weighted",
}


def _compute_target_table(dimension: str, filters: dict, use_raw: bool = False) -> str:
    if use_raw or not dimension:
        return "opportunities"
    if dimension == "country" and "practice" in filters:
        return "v_by_country_practice"
    if dimension == "practice" and "country" in filters:
        return "v_by_country_practice"
    return _DIMENSION_VIEWS.get(dimension, "opportunities")


def _view_supports_filters(view: str, filter_keys: set) -> bool:
    if view == "opportunities":
        return True
    if view not in ALLOWED_TABLES:
        return False
    allowed = set(ALLOWED_TABLES[view]["columns"])
    return filter_keys.issubset(allowed)


def build_and_execute_query(intent: dict) -> list:
    import datetime

    dimension = intent.get("dimension", "")
    metric = intent.get("metric", "budget")
    filters = intent.get("filters", {})
    range_filters = intent.get("range_filters", {})
    chart_type = intent.get("chart_type", "")
    # Le scatter a besoin de plusieurs mesures par opportunité (budget, probabilité de
    # gain, montant pondéré) — jamais une seule mesure agrégée par dimension, donc il
    # emprunte le même chemin "lignes brutes" que use_raw_table/range_filters.
    use_raw = intent.get("use_raw_table", False) or bool(range_filters) or chart_type == "scatter"
    limit = int(intent.get("limit") or 0)

    params = []
    conditions = []

    def _cast(col: str, val):
        if col in INT_COLS:
            return int(val)
        if col in FLOAT_COLS:
            return float(val)
        return val

    def add_conditions(allowed_cols: set):
        nonlocal params, conditions
        for k, v in filters.items():
            if k in allowed_cols or allowed_cols is None:
                if isinstance(v, (list, tuple)):
                    # Filtre de comparaison ("compare France vs Maroc") -> IN (...)
                    placeholders = ", ".join(["%s"] * len(v))
                    conditions.append(f"{k} IN ({placeholders})")
                    params.extend(_cast(k, item) for item in v)
                else:
                    conditions.append(f"{k} = %s")
                    params.append(_cast(k, v))
        for col, rule in range_filters.items():
            op = rule.get("op", "<")
            value = rule.get("value")
            if op not in VALID_OPS:
                continue
            if allowed_cols is not None and col not in allowed_cols:
                continue
            if op == "between":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    continue
                conditions.append(f"{col} BETWEEN %s AND %s")
                params.append(_cast(col, value[0]))
                params.append(_cast(col, value[1]))
            else:
                conditions.append(f"{col} {op} %s")
                params.append(_cast(col, value))

    # Une carte de chaleur croise TOUJOURS deux dimensions (la dimension demandée ×
    # practice, ou × country si la dimension demandée est déjà practice) — aucune vue
    # pré-agrégée existante ne couvre ce croisement pour une dimension arbitraire, donc
    # un GROUP BY à deux colonnes dédié est nécessaire, indépendant du reste de la fonction.
    if chart_type == "heatmap" and dimension:
        secondary = "country" if dimension == "practice" else "practice"
        expr = METRIC_EXPR.get(metric, "SUM(budget)")
        query = f"SELECT {dimension}, {secondary}, {expr} AS {metric} FROM opportunities"
        add_conditions(set(ALLOWED_TABLES["opportunities"]["columns"]))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" GROUP BY {dimension}, {secondary}"

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                results = cur.fetchall()
        for r in results:
            for key, val in list(r.items()):
                if isinstance(val, (datetime.date, datetime.datetime)):
                    r[key] = val.isoformat()
        return results

    target_table = _compute_target_table(dimension, filters, use_raw)
    filter_keys = set(filters.keys()) | set(range_filters.keys())

    select_metric = _VIEW_METRIC_ALIASES.get(metric, metric) if target_table != "opportunities" else metric
    metric_available = target_table == "opportunities" or (
        target_table in ALLOWED_TABLES and select_metric in ALLOWED_TABLES[target_table]["columns"]
    )

    # Le calcul groupé à la volée (GROUP BY sur la table brute) sert de filet de sécurité
    # dès que la vue pré-agrégée ne peut pas répondre à la demande — filtre non supporté,
    # métrique absente de la vue, ou dimension sans vue dédiée. Les données restent
    # exactes dans tous les cas, seul le chemin de calcul change.
    use_grouped = use_raw is False and (
        target_table not in ALLOWED_TABLES
        or not _view_supports_filters(target_table, filter_keys)
        or not metric_available
        or (dimension and target_table == "opportunities")
    )

    if use_raw:
        query = (
            "SELECT country, practice, status, buyer, budget, "
            "financial_offer, win_probability, weighted_amount, days_remaining, deadline "
            "FROM opportunities"
        )
        add_conditions(set(ALLOWED_TABLES["opportunities"]["columns"]))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY days_remaining ASC"
        if limit > 0:
            query += f" LIMIT {limit}"

    elif use_grouped and dimension:
        expr = METRIC_EXPR.get(metric, "SUM(budget)")
        query = (
            f"SELECT {dimension}, {expr} AS {metric}, "
            f"COUNT(*) AS nb_opportunities, SUM(budget) AS budget "
            f"FROM opportunities"
        )
        add_conditions(set(ALLOWED_TABLES["opportunities"]["columns"]))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" GROUP BY {dimension}"
        if dimension == "deadline_month":
            query += f" ORDER BY {dimension} ASC"
        else:
            query += f" ORDER BY {metric} DESC"
        if limit > 0:
            query += f" LIMIT {limit}"

    elif not dimension:
        expr = METRIC_EXPR.get(metric, "SUM(budget)")
        alias = metric if metric != "nb_opportunities" else "nb_opportunities"
        query = f"SELECT {expr} AS {alias} FROM opportunities"
        add_conditions(set(ALLOWED_TABLES["opportunities"]["columns"]))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

    else:
        query = f"SELECT * FROM {target_table}"
        add_conditions(set(ALLOWED_TABLES[target_table]["columns"]))
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if dimension == "deadline_month":
            query += f" ORDER BY {dimension} ASC"
        else:
            query += f" ORDER BY {select_metric} DESC"
        if limit > 0:
            query += f" LIMIT {limit}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            results = cur.fetchall()

    for r in results:
        if not use_grouped and select_metric != metric and select_metric in r:
            r[metric] = r[select_metric]
            del r[select_metric]
        for key, val in list(r.items()):
            if isinstance(val, (datetime.date, datetime.datetime)):
                r[key] = val.isoformat()

    return results
