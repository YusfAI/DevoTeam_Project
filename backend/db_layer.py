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

# Colonnes numériques (cast int ou float selon le cas)
INT_COLS   = {"deadline_year", "days_remaining"}
FLOAT_COLS = {"budget", "financial_offer", "weighted_amount", "win_probability"}
VALID_OPS  = {"<", ">", "<=", ">=", "="}

def build_and_execute_query(intent: dict) -> list:
    import datetime
    
    dimension    = intent.get("dimension", "")
    metric       = intent.get("metric", "budget")
    filters      = intent.get("filters", {})
    range_filters = intent.get("range_filters", {})
    use_raw      = intent.get("use_raw_table", False) or bool(range_filters)

    # Identification de la table/vue
    target_table = _compute_target_table(dimension, filters, use_raw)

    if target_table not in ALLOWED_TABLES:
        raise ValueError(f"Impossible d'analyser cette dimension. ({target_table})")

    allowed_cols = set(ALLOWED_TABLES[target_table]["columns"])

    # Traduction metric → colonne réelle dans la vue
    select_metric = metric
    if target_table != "opportunities":
        if metric == "budget":          select_metric = "total_budget"
        elif metric == "financial_offer": select_metric = "total_offer"
        elif metric == "weighted_amount": select_metric = "total_weighted"

    aggregation = intent.get("aggregation", "sum")

    # Pour les KPI ou listes brutes, on construit un SELECT spécial
    if use_raw or (target_table == "opportunities" and not dimension):
        if use_raw:
            # Liste brute : retourne toutes les colonnes utiles
            query = ("SELECT country, practice, status, buyer, budget, "
                     "financial_offer, win_probability, days_remaining, deadline "
                     "FROM opportunities")
        elif metric == "nb_opportunities":
            query = "SELECT COUNT(*) as nb_opportunities FROM opportunities"
        elif metric == "win_probability":
            query = "SELECT AVG(win_probability) as win_probability FROM opportunities"
        else:
            query = f"SELECT SUM({select_metric}) as {metric} FROM opportunities"
    else:
        if select_metric not in allowed_cols:
            raise ValueError(f"Métrique '{metric}' non disponible pour l'axe '{dimension}'.")
        query = f"SELECT * FROM {target_table}"

    params = []
    conditions = []

    # Filtres d'égalité
    valid_eq = {k: v for k, v in filters.items() if k in allowed_cols or target_table == "opportunities"}
    for k, v in valid_eq.items():
        conditions.append(f"{k} = %s")
        params.append(int(v) if k in INT_COLS else v)

    # Filtres de plage (range_filters)
    for col, rule in range_filters.items():
        op    = rule.get("op", "<")
        value = rule.get("value")
        if op not in VALID_OPS or col not in allowed_cols:
            continue
        conditions.append(f"{col} {op} %s")
        if col in INT_COLS:   params.append(int(value))
        elif col in FLOAT_COLS: params.append(float(value))
        else: params.append(value)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if dimension and not use_raw:
        query += f" ORDER BY {dimension} ASC"
    elif use_raw:
        query += " ORDER BY days_remaining ASC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            results = cur.fetchall()

    # Restauration du nom du metric + ISO date serialization
    for r in results:
        if select_metric != metric and select_metric in r:
            r[metric] = r[select_metric]
            del r[select_metric]
        for key, val in list(r.items()):
            if isinstance(val, (datetime.date, datetime.datetime)):
                r[key] = val.isoformat()

    return results
