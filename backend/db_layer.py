def _compute_target_table(dimension: str, filters: dict, use_raw: bool = False) -> str:
    if use_raw:
        return "opportunities"
    if dimension == "country" and "practice" in filters:
        return "v_by_country_practice"
    elif dimension == "country":
        return "v_by_country"
    elif dimension == "practice" and "country" in filters:
        return "v_by_country_practice"
    elif dimension == "practice":
        return "v_by_practice"
    elif dimension == "status":
        return "v_by_status"
    elif dimension == "deadline_month":
        return "v_by_month"
    elif dimension == "funding_source":
        return "v_by_funding_source"
    elif not dimension:
        return "opportunities"
    return "v_by_" + dimension


from .db import get_connection
from .schema_and_whitelist import ALLOWED_TABLES

INT_COLS = {"deadline_year", "days_remaining"}
FLOAT_COLS = {"budget", "financial_offer", "weighted_amount", "win_probability"}
VALID_OPS = {"<", ">", "<=", ">=", "="}

METRIC_EXPR = {
    "budget": "SUM(budget)",
    "financial_offer": "SUM(financial_offer)",
    "weighted_amount": "SUM(weighted_amount)",
    "nb_opportunities": "COUNT(*)",
    "win_probability": "AVG(win_probability)",
}


def _view_supports_filters(view: str, filter_keys: set) -> bool:
    if view == "opportunities":
        return True
    if view not in ALLOWED_TABLES:
        return False
    allowed = set(ALLOWED_TABLES[view]["columns"])
    return filter_keys.issubset(allowed)


def _metric_sort_column(metric: str) -> str:
    return metric


def build_and_execute_query(intent: dict) -> list:
    import datetime

    dimension = intent.get("dimension", "")
    metric = intent.get("metric", "budget")
    filters = intent.get("filters", {})
    range_filters = intent.get("range_filters", {})
    use_raw = intent.get("use_raw_table", False) or bool(range_filters)
    limit = int(intent.get("limit") or 0)

    target_table = _compute_target_table(dimension, filters, use_raw)
    filter_keys = set(filters.keys()) | set(range_filters.keys())
    use_grouped = use_raw is False and (
        target_table not in ALLOWED_TABLES
        or not _view_supports_filters(target_table, filter_keys)
        or (dimension and target_table == "opportunities")
    )

    select_metric = metric
    if not use_grouped and target_table != "opportunities":
        if metric == "budget":
            select_metric = "total_budget"
        elif metric == "financial_offer":
            select_metric = "total_offer"
        elif metric == "weighted_amount":
            select_metric = "total_weighted"

    params = []
    conditions = []

    def add_conditions(allowed_cols: set):
        nonlocal params, conditions
        for k, v in filters.items():
            if k in allowed_cols or allowed_cols is None:
                conditions.append(f"{k} = %s")
                params.append(int(v) if k in INT_COLS else v)
        for col, rule in range_filters.items():
            op = rule.get("op", "<")
            value = rule.get("value")
            if op not in VALID_OPS:
                continue
            if allowed_cols is not None and col not in allowed_cols:
                continue
            conditions.append(f"{col} {op} %s")
            if col in INT_COLS:
                params.append(int(value))
            elif col in FLOAT_COLS:
                params.append(float(value))
            else:
                params.append(value)

    if use_raw:
        query = (
            "SELECT country, practice, status, buyer, budget, "
            "financial_offer, win_probability, days_remaining, deadline "
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
        if select_metric not in ALLOWED_TABLES[target_table]["columns"]:
            raise ValueError(f"Métrique '{metric}' non disponible pour l'axe '{dimension}'.")
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
