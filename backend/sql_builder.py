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
from .business_rules import FUNNEL_STAGE_ORDER

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

# Au-delà, un graphique catégoriel devient illisible. La traîne est regroupée dans
# « Autres » (voir build_sql) et non supprimée, pour que le total reste vérifiable.
MAX_CATEGORIES = 12


def funnel_sql(intent: dict, cumulative: bool = True, conversion: bool = False) -> str:
    """SQL de l'entonnoir de vente, reconstruit depuis un INSTANTANÉ de statuts.

    Point clé : `status` est l'état COURANT d'une opportunité, pas son historique —
    chaque opportunité n'apparaît que dans un seul statut. Compter les opportunités
    par statut ne produit donc pas un entonnoir : rien ne garantit que les volumes
    décroissent, et diviser deux comptages voisins donnait des « taux de conversion »
    supérieurs à 100 % (jusqu'à 800 % mesurés), c'est-à-dire dénués de sens.

    La reconstruction correcte s'appuie sur une propriété du pipeline : une
    opportunité arrivée à « Offre gagnée » a nécessairement franchi toutes les étapes
    précédentes. On cumule donc depuis la fin — « nombre ayant ATTEINT au moins cette
    étape » — ce qui décroît par construction et redonne un vrai entonnoir. Le taux
    de passage devient alors le rapport de deux cumuls consécutifs, borné à 100 %.

    Les statuts de SORTIE (perdu, NO GO, infructueux…) restent exclus : ce sont des
    sorties du pipeline, pas des étapes que chaque opportunité traverse.
    """
    where = _where_clause(intent)
    cases = "\n".join(
        f"    WHEN {_literal('status', stage)} THEN {i + 1}"
        for i, stage in enumerate(FUNNEL_STAGE_ORDER)
    )
    stages = ", ".join(_literal("status", s) for s in FUNNEL_STAGE_ORDER)

    base = (
        f"WITH etapes AS (\n"
        f"  SELECT status, COUNT(*) AS nb,\n"
        f"    CASE status\n{cases}\n    END AS rang\n"
        f"  FROM {TABLE}\n"
        f"  WHERE ({where}) AND status IN ({stages})\n"
        f"  GROUP BY status\n"
        f"),\n"
        f"cumul AS (\n"
        f"  SELECT status, rang,\n"
        f"    SUM(nb) OVER (ORDER BY rang DESC ROWS UNBOUNDED PRECEDING) AS atteint\n"
        f"  FROM etapes\n"
        f")\n"
    )

    if conversion:
        return base + (
            "SELECT status,\n"
            "  atteint * 1.0 / NULLIF(LAG(atteint) OVER (ORDER BY rang), 0) AS taux\n"
            "FROM cumul\nORDER BY rang"
        )
    if not cumulative:
        return base + "SELECT status, atteint FROM cumul ORDER BY rang"
    return base + "SELECT status, atteint AS nb_opportunities FROM cumul ORDER BY rang"


def _agg_kind(metric: str) -> str:
    """« sum » si les valeurs de la métrique s'additionnent (budget, comptage),
    « mean » sinon (probabilité de gain). Détermine si la traîne d'un graphique peut
    être regroupée : additionner des sommes a du sens, moyenner des moyennes non."""
    return "mean" if metric == "win_probability" else "sum"

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
        return funnel_sql(intent, cumulative=True)

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

    # Un "top N" demandé par l'utilisateur DOIT tronquer : il a explicitement demandé
    # les N premiers, regrouper le reste trahirait sa question.
    if limit > 0:
        return f"{sql}\nLIMIT {limit}"

    # Une dimension temporelle n'est jamais plafonnée : l'axe est chronologique, en
    # couper la fin amputerait la tendance au lieu de l'alléger.
    if dimension == "deadline_month":
        return sql

    # Plafond de lisibilité. Le reste est REGROUPÉ dans « Autres » plutôt que jeté :
    # un simple LIMIT ferait disparaître des lignes sans le dire, et le total affiché
    # en KPI ne correspondrait plus à la somme des barres (constaté : 6,58 M€ d'écart
    # sur « budget par pays », 9 pays sur 21 absents du graphique).
    if _agg_kind(metric) != "sum":
        # Une moyenne de moyennes n'a pas de sens statistique : sur ce type de métrique
        # (probabilité de gain), on tronque honnêtement au lieu d'inventer un agrégat.
        return f"{sql}\nLIMIT {MAX_CATEGORIES}"

    head = MAX_CATEGORIES - 1
    return (
        f"WITH agg AS (\n"
        f"  SELECT {dimension} AS dim, {expr} AS val\n"
        f"  FROM {TABLE}\n  WHERE {where}\n  GROUP BY {dimension}\n"
        f"),\n"
        f"ranked AS (SELECT dim, val, ROW_NUMBER() OVER (ORDER BY val DESC) AS rn FROM agg)\n"
        f"SELECT dim AS {dimension}, val AS {metric}, 0 AS is_autres FROM ranked WHERE rn <= {head}\n"
        f"UNION ALL\n"
        f"SELECT 'Autres', SUM(val), 1 FROM ranked WHERE rn > {head} HAVING COUNT(*) > 0\n"
        # « Autres » épinglé en dernier plutôt que classé par valeur : ce n'est pas une
        # catégorie réelle, la voir se ranger 5e induirait en erreur.
        f"ORDER BY is_autres, {metric} DESC"
    )
