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
from .business_rules import (
    FUNNEL_STAGE_ORDER, ISSUE_DIMENSION, LOST_STATUSES,
    heatmap_secondary_dimension, hot_deal_sql, issue_sql,
)


def _question_targets_status(intent: dict) -> bool:
    """La question porte-t-elle explicitement sur un statut ?

    Seul un FILTRE sur `status` lève l'exclusion par défaut des affaires perdues :
    l'utilisateur a nommé le statut qui l'intéresse, lui renvoyer un résultat vide
    serait absurde.

    Une simple répartition PAR statut (dimension = status) ne la lève pas : le
    graphique doit rester cohérent avec le total affiché juste au-dessus, sans quoi
    les barres ne se réconcilieraient plus avec le KPI — c'est exactement le défaut
    de lisibilité qu'on a corrigé ailleurs avec le regroupement « Autres ».
    """
    return "status" in (intent.get("filters") or {})

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

# Métriques pour lesquelles une moyenne est une demande légitime : des montants.
_MOYENNABLES = {"budget", "financial_offer", "weighted_amount"}

# Colonnes numériques qu'une question peut borner (« budget supérieur à 500 000 »,
# « probabilité de plus de 80 % »). Elles ne sont pas des filtres d'égalité, d'où
# leur absence de VALID_FILTERS — mais elles doivent être acceptées ici, sinon la
# borne est appliquée par pandas et ignorée par le SQL.
# `deadline` y figure pour « offres remises » (échéance déjà passée) et pour toute
# question bornée dans le temps. Sa valeur est une date ISO, rendue comme un
# littéral texte : DuckDB la compare sans conversion explicite.
_COLONNES_BORNABLES = {"days_remaining", "win_probability", "budget",
                       "financial_offer", "weighted_amount", "deadline"}

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


def _moyenne_demandee(intent) -> bool:
    """La question demande-t-elle explicitement une moyenne ?

    Vaut pour une intention (dict) comme pour son seul champ. Le mot était ignoré :
    « budget moyen par pays » renvoyait la somme sous une étiquette de moyenne.
    """
    if isinstance(intent, dict):
        return intent.get("aggregation") == "avg"
    return intent == "avg"


def _agg_kind(metric: str, intent=None) -> str:
    """« sum » si les valeurs affichées s'additionnent (budget sommé, comptage),
    « mean » sinon (probabilité de gain, ou montant explicitement moyenné). Détermine
    si la traîne d'un graphique peut être regroupée dans « Autres » : additionner des
    sommes a du sens, moyenner des moyennes non."""
    if metric == "win_probability":
        return "mean"
    return "mean" if _moyenne_demandee(intent) else "sum"

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

    # « Affaire chaude » : déjà remise OU probabilité >= 80 %. La condition est
    # parenthésée par `hot_deal_sql` — sans quoi son OR absorberait les AND qui
    # suivent et le périmètre de la question disparaîtrait en silence.
    if intent.get("hot_deals"):
        conditions.append(hot_deal_sql())

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
        # `financial_offer` et `weighted_amount` manquaient à cette liste : une borne
        # posée sur eux était appliquée par pandas et ignorée par le SQL. Les deux
        # moteurs auraient répondu deux chiffres différents à la même question —
        # exactement la divergence que tout ce module cherche à empêcher.
        if column not in VALID_FILTERS and column not in _COLONNES_BORNABLES:
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

    # Exclusions sur une colonne AUTRE que le statut : « budget par pays hors
    # Tunisie », « tout sauf Risk Advisory ». Elles n'existaient pas, et le mot de
    # négation était simplement ignoré : la valeur partait en filtre POSITIF et la
    # réponse donnait exactement l'inverse de la question — 34 530 000 DT (le budget
    # de la Tunisie) pour « hors Tunisie », dont la vraie valeur est 69 370 001.
    for column, value in (intent.get("exclude_filters") or {}).items():
        if column not in VALID_FILTERS:
            continue
        valeurs = value if isinstance(value, (list, tuple)) else [value]
        valeurs = [v for v in valeurs if v is not None]
        if not valeurs:
            continue
        litteraux = ", ".join(_literal(column, v) for v in valeurs)
        # `IS NULL OR NOT IN` : en SQL, `colonne NOT IN (...)` est FAUX quand la
        # colonne est vide, ce qui écarterait aussi les lignes sans valeur — or
        # « hors Tunisie » les concerne tout autant.
        conditions.append(f"({column} IS NULL OR {column} NOT IN ({litteraux}))")

    excluded = list(intent.get("exclude_statuses") or [])

    # Exclusion par défaut des affaires perdues. Elle s'ajoute à toute exclusion déjà
    # demandée (ex. « opportunités urgentes », qui écarte aussi les statuts clos).
    #
    # Elle est LEVÉE si la question filtre elle-même sur le statut : demander « la
    # liste des offres perdues » doit renvoyer ces offres, pas un tableau vide. Le
    # défaut sert à ne pas gonfler les totaux, jamais à rendre une donnée inatteignable.
    if not _question_targets_status(intent):
        excluded += [s for s in LOST_STATUSES if s not in excluded]

    if excluded:
        values = ", ".join(_literal("status", s) for s in excluded)
        conditions.append(f"status NOT IN ({values})")

    return " AND ".join(conditions) if conditions else "1 = 1"


def _metric_expr(metric: str, intent=None) -> str:
    """Expression SQL de la métrique, moyenne comprise.

    Le passage à AVG ne concerne que les montants : un comptage moyen n'a pas de
    sens sans préciser moyen sur quoi, et la probabilité de gain est déjà une
    moyenne. Le même arbitrage qu'en pandas (db_layer._agregation) — les deux
    moteurs doivent répondre le même chiffre à la même question.
    """
    if _moyenne_demandee(intent) and metric in _MOYENNABLES:
        return f"AVG({metric})"
    return METRIC_SQL.get(metric, METRIC_SQL["budget"])


def build_sql(intent: dict) -> str:
    """SQL DuckDB correspondant à l'intention, adapté au type de graphique."""
    # Un comptage de valeurs distinctes court-circuite tout le reste : la question
    # ne demande ni répartition ni graphique, seulement combien il en existe.
    compte = intent.get("count_distinct")
    if compte in VALID_DIMENSIONS:
        axe = intent.get("dimension") or ""
        where = _where_clause(intent)
        if axe in VALID_DIMENSIONS and axe != compte:
            # Regroupé : « combien de clients distincts PAR practice ». L'alias reste
            # `nb_opportunities`, comme pour tout comptage — c'est ce que le reste de
            # la chaîne (widgets, message) sait lire.
            return ("SELECT {axe}, COUNT(DISTINCT {compte}) AS nb_opportunities\n"
                    "FROM {table}\nWHERE {where}\nGROUP BY {axe}\n"
                    "ORDER BY nb_opportunities DESC"
                    .format(axe=axe, compte=compte, table=TABLE, where=where))
        return ("SELECT COUNT(DISTINCT {}) AS value\nFROM {}\nWHERE {}"
                .format(compte, TABLE, where))

    metric = intent.get("metric") or "budget"
    if metric not in VALID_METRICS:
        metric = "budget"
    dimension = intent.get("dimension") or ""
    if dimension and dimension not in VALID_DIMENSIONS:
        dimension = ""
    chart_type = intent.get("chart_type") or "bar"
    limit = int(intent.get("limit") or 0)
    where = _where_clause(intent)
    expr = _metric_expr(metric, intent)

    if chart_type == "funnel":
        return funnel_sql(intent, cumulative=True)

    if chart_type == "heatmap" and dimension:
        secondary = heatmap_secondary_dimension(dimension)
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

    # « issue » se calcule depuis le statut au lieu de se lire dans une colonne. Le
    # GROUP BY reprend l'expression ENTIÈRE : DuckDB accepte l'alias en ORDER BY mais
    # pas en GROUP BY, et s'y fier casse la requête à l'exécution.
    groupe = issue_sql() if dimension == ISSUE_DIMENSION else dimension

    order = f"{dimension} ASC" if dimension == "deadline_month" else f"{metric} DESC"
    sql = (
        f"SELECT {groupe} AS {dimension}, {expr} AS {metric}\n"
        f"FROM {TABLE}\nWHERE {where}\n"
        f"GROUP BY {groupe}\n"
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

    # L'issue n'a que trois valeurs par construction — gagnée, perdue, en attente.
    # Il n'y a donc jamais de traîne à regrouper, et passer par le plafond de
    # lisibilité serait pire qu'inutile : cette branche-là reconstruit sa requête en
    # citant la colonne, or `issue` n'en est pas une.
    if dimension == ISSUE_DIMENSION:
        return sql

    # Plafond de lisibilité. Le reste est REGROUPÉ dans « Autres » plutôt que jeté :
    # un simple LIMIT ferait disparaître des lignes sans le dire, et le total affiché
    # en KPI ne correspondrait plus à la somme des barres (constaté : 6,58 MDT d'écart
    # sur « budget par pays », 9 pays sur 21 absents du graphique).
    if _agg_kind(metric, intent) != "sum":
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
