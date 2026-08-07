"""Post-process and rule-based pre-parse to improve intent accuracy."""

import re
import unicodedata
from datetime import date
from typing import Optional

from .schema_and_whitelist import VALID_METRICS, VALID_DIMENSIONS, KNOWN_VALUES
from .alerts import EXCLUDED_STATUSES


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


PRACTICE_MAP = {
    "data management": "Data Management",
    "data": "Data Management",
    "risk advisory": "Risk Advisory",
    "risk": "Risk Advisory",
    "digital transformation": "Digital Transformation",
    "digital": "Digital Transformation",
}

STATUS_MAP = {
    "offre gagnee": "Offre gagnée",
    "offres gagnees": "Offre gagnée",
    "gagnee": "Offre gagnée",
    "gagnees": "Offre gagnée",
    "gagne": "Offre gagnée",
    "remportee": "Offre gagnée",
    "offre perdue": "Offre perdue",
    "offres perdues": "Offre perdue",
    "perdue": "Offre perdue",
    "perdues": "Offre perdue",
    "perdu": "Offre perdue",
    "offre signee": "Offre signée",
    "signee": "Offre signée",
    "offre remise": "Offre remise",
    "en cours": "En cours de préparation",
    "lead": "Lead",
    "no go": "NO GO",
}


def _detect_practice(q: str) -> str | None:
    for key, val in PRACTICE_MAP.items():
        if key in q:
            return val
    return None


def _detect_status(q: str) -> str | None:
    for key, val in STATUS_MAP.items():
        if key in q:
            return val
    return None


def _detect_metric(q: str) -> str | None:
    if any(w in q for w in ("combien", "nombre", "volume", "nb ", "count")):
        return "nb_opportunities"
    if any(w in q for w in ("proba", "probabilite", "chance")):
        return "win_probability"
    if any(w in q for w in ("offre financiere", "financial offer")):
        return "financial_offer"
    if any(w in q for w in ("pondere", "weighted")):
        return "weighted_amount"
    if any(w in q for w in ("budget", "ca", "chiffre", "montant")):
        return "budget"
    return None


def _detect_dimension(q: str) -> str | None:
    if any(w in q for w in ("par pays", "par country", " par pays")):
        return "country"
    if "par practice" in q or "par metier" in q:
        return "practice"
    if "par statut" in q or "par status" in q:
        return "status"
    if any(w in q for w in ("par mois", "evolution", "mensuel")):
        return "deadline_month"
    if "par an" in q or "par annee" in q:
        return "deadline_year"
    if "par type" in q:
        return "opp_type"
    if "par source" in q or "financement" in q:
        return "funding_source"
    return None


def _detect_chart_type(q: str, dimension: str) -> str | None:
    if any(w in q for w in ("liste", "lister", "detail", "tableau")):
        return "table"
    if any(w in q for w in ("entonnoir", "funnel", "pipeline de vente", "pipeline commercial")):
        return "funnel"
    if any(w in q for w in ("nuage de points", "scatter", "bulles", "correlation", "correle",
                             "lien entre", "rapport entre", "en fonction de")):
        return "scatter"
    if any(w in q for w in ("carte de chaleur", "heatmap", "heat map")):
        return "heatmap"
    # \b requis : "aire" en simple sous-chaîne matcherait "faire"/"affaire"/"nécessaire".
    if re.search(r"\baire\b", q) or "area chart" in q:
        return "area"
    if any(w in q for w in ("camembert", "repartition", "part de")):
        return "pie"
    if any(w in q for w in ("evolution", "tendance", "courbe")):
        return "line"
    if any(w in q for w in ("kpi", "combien", "total", "quel est")) and not dimension:
        return "kpi_card"
    if dimension == "deadline_month":
        return "line"
    if dimension:
        return "bar"
    return None


def try_rule_based_parse(query: str) -> dict | None:
    """High-confidence parse without LLM for common French patterns."""
    q = _norm(query)
    if not q.strip():
        return None

    if q.strip() in ("bonjour", "salut", "hello", "coucou", "aide", "help"):
        return {"goal": "", "metric": "", "dimension": "", "filters": {}, "range_filters": {},
                "chart_type": "bar", "aggregation": "sum", "use_raw_table": False,
                "is_conversation": True, "limit": 0}

    metric = _detect_metric(q)
    dimension = _detect_dimension(q)
    practice = _detect_practice(q)
    status = _detect_status(q)
    chart_type = _detect_chart_type(q, dimension or "")

    use_raw = chart_type == "table" or "liste" in q
    is_data_query = bool(metric or dimension or practice or status or use_raw or "top" in q)

    if not is_data_query:
        return None

    filters = {}
    if practice:
        filters["practice"] = practice
    if status:
        filters["status"] = status

    range_filters = {}
    m_days = re.search(r"(?:moins de|<=|<|inferieur(?:e)? a)\s*(\d+)\s*jours?", q)
    if m_days:
        # "moins de N jours" signifie une échéance encore À VENIR (urgente), jamais déjà
        # passée — days_remaining < N inclurait aussi les valeurs négatives (deadlines
        # dépassées depuis longtemps), donc bornée explicitement à [0, N].
        range_filters["days_remaining"] = {"op": "between", "value": [0, int(m_days.group(1))]}
        use_raw = True
        chart_type = "table"

    limit = 0
    m_top = re.search(r"top\s*(\d+)|(\d+)\s*premier", q)
    if m_top:
        limit = int(m_top.group(1) or m_top.group(2))

    if not metric:
        metric = "nb_opportunities" if dimension else "budget"
    if not chart_type:
        chart_type = "kpi_card" if not dimension else "bar"

    goal = query.strip().capitalize()
    if goal and not goal[0].isupper():
        goal = goal[0].upper() + goal[1:]

    return {
        "goal": goal,
        "metric": metric,
        "dimension": dimension or "",
        "filters": filters,
        "range_filters": range_filters,
        "chart_type": chart_type,
        "aggregation": "count" if metric == "nb_opportunities" else "sum",
        "use_raw_table": use_raw,
        "is_conversation": False,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# Dates et périodes relatives : résolues en Python déterministe, jamais confiées
# au calcul mental du LLM (risque de dates "plausibles mais fausses").
# ---------------------------------------------------------------------------

_MONTHS_AGO_PATTERN = re.compile(r"(\d+)\s+derniers?\s+mois")


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _month_from_index(idx: int) -> tuple[int, int]:
    return idx // 12, idx % 12 + 1


def _format_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _quarter_month_range(year: int, month: int) -> tuple[int, int]:
    """Index (premier mois, dernier mois) du trimestre contenant (year, month)."""
    start_month = ((month - 1) // 3) * 3 + 1
    start_idx = _month_index(year, start_month)
    return start_idx, start_idx + 2


def _apply_relative_period(q: str, intent: dict, today: date) -> None:
    """Détecte les tournures FR de date/période relative et remplit filters/
    range_filters sur deadline_month/deadline_year. Ne fait rien si l'intention a
    déjà une valeur sur l'une de ces deux colonnes (ne jamais écraser un filtre
    explicite déjà posé, que ce soit par l'utilisateur ou par le LLM).
    """
    filters = intent.setdefault("filters", {})
    range_filters = intent.setdefault("range_filters", {})
    if "deadline_month" in filters or "deadline_year" in filters or "deadline_month" in range_filters:
        return

    today_idx = _month_index(today.year, today.month)

    m_n_months = _MONTHS_AGO_PATTERN.search(q)
    if m_n_months:
        n = int(m_n_months.group(1))
        sy, sm = _month_from_index(today_idx - n)
        range_filters["deadline_month"] = {
            "op": "between",
            "value": [_format_month(sy, sm), _format_month(today.year, today.month)],
        }
        return

    if "trimestre dernier" in q or "trimestre precedent" in q:
        cur_start_idx, _ = _quarter_month_range(today.year, today.month)
        prev_y, prev_m = _month_from_index(cur_start_idx - 3)
        start_idx, end_idx = _quarter_month_range(prev_y, prev_m)
        sy, sm = _month_from_index(start_idx)
        ey, em = _month_from_index(end_idx)
        range_filters["deadline_month"] = {"op": "between", "value": [_format_month(sy, sm), _format_month(ey, em)]}
        return

    if "ce trimestre" in q or "trimestre en cours" in q:
        start_idx, end_idx = _quarter_month_range(today.year, today.month)
        sy, sm = _month_from_index(start_idx)
        ey, em = _month_from_index(end_idx)
        range_filters["deadline_month"] = {"op": "between", "value": [_format_month(sy, sm), _format_month(ey, em)]}
        return

    if "mois dernier" in q or "mois precedent" in q:
        y, m = _month_from_index(today_idx - 1)
        filters["deadline_month"] = _format_month(y, m)
        return

    if "ce mois" in q or "du mois" in q:
        filters["deadline_month"] = _format_month(today.year, today.month)
        return

    if "annee derniere" in q or "an dernier" in q:
        filters["deadline_year"] = str(today.year - 1)
        return

    if "cette annee" in q:
        filters["deadline_year"] = str(today.year)
        return


def refine_intent(query: str, intent: dict, today: Optional[date] = None) -> dict:
    """Merge rule hints into LLM output and normalize."""
    q = _norm(query)
    hints = try_rule_based_parse(query)

    if hints and not intent.get("is_conversation") and intent.get("metric"):
        if hints.get("filters"):
            for k, v in hints["filters"].items():
                intent.setdefault("filters", {})
                if k not in intent["filters"]:
                    intent["filters"][k] = v
        if hints.get("range_filters") and not intent.get("range_filters"):
            intent["range_filters"] = hints["range_filters"]
        if hints.get("limit") and not intent.get("limit"):
            intent["limit"] = hints["limit"]
        if hints.get("use_raw_table"):
            intent["use_raw_table"] = True
            intent["chart_type"] = "table"

    if not intent.get("limit"):
        m_top = re.search(r"top\s*(\d+)|(\d+)\s*premier", q)
        if m_top:
            intent["limit"] = int(m_top.group(1) or m_top.group(2))

    dimension = intent.get("dimension", "")
    if dimension == "deadline_month" and intent.get("chart_type") == "bar":
        intent["chart_type"] = "line"
    if "camembert" in q or "repartition" in q:
        if dimension:
            intent["chart_type"] = "pie"
    if any(w in q for w in ("liste", "lister", "detail")):
        intent["use_raw_table"] = True
        intent["chart_type"] = "table"
    if any(w in q for w in ("combien", "kpi", "total")) and not dimension:
        intent["chart_type"] = "kpi_card"

    # Un entonnoir de vente n'a de sens que sur le statut (les étapes du pipeline) —
    # imposé plutôt que de compter sur le LLM pour le deviner correctement à chaque fois.
    if intent.get("chart_type") == "funnel":
        intent["dimension"] = "status"

    # Une carte de chaleur croise toujours deux dimensions (voir db_layer.py) ; si
    # aucune n'a été précisée, "country" est un choix par défaut raisonnable — grande
    # cardinalité, le plus intéressant à croiser avec les 3 practices fixes.
    if intent.get("chart_type") == "heatmap" and not intent.get("dimension"):
        intent["dimension"] = "country"

    # Le scatter affiche toujours budget × probabilité de gain × montant pondéré —
    # fixé plutôt que piloté par "metric" (voir vega_generator.py). Sans ce verrou,
    # un metric="win_probability" ferait appliquer la mise à l'échelle ×100 (destinée
    # à un pourcentage agrégé unique) sur le champ brut utilisé comme axe Y du nuage.
    if intent.get("chart_type") == "scatter":
        intent["metric"] = "budget"

    # "days_remaining < N" (ou "<=") sous-entend toujours une échéance encore À VENIR —
    # jamais déjà passée. Sans ce garde-fou déterministe, un LLM qui produit "<" au lieu
    # de "between" (l'instruction du prompt n'est pas une garantie à 100%) laisserait
    # passer des opportunités expirées depuis des semaines dans une liste "urgente".
    days_filter = intent.get("range_filters", {}).get("days_remaining")
    if days_filter and days_filter.get("op") in ("<", "<="):
        try:
            upper = float(days_filter["value"])
        except (TypeError, ValueError):
            upper = None
        if upper is not None and upper >= 0:
            intent["range_filters"]["days_remaining"] = {"op": "between", "value": [0, days_filter["value"]]}

    # Toute requête filtrant sur days_remaining porte sur l'urgence d'une échéance —
    # une opportunité déjà close (gagnée/perdue/signée...) n'a plus rien d'urgent,
    # même si sa deadline technique tombe dans la fenêtre demandée. Même règle que
    # backend/alerts.py pour les emails de rappel : une seule liste de statuts exclus,
    # jamais deux définitions différentes de "actif" selon le canal.
    if "days_remaining" in intent.get("range_filters", {}):
        intent["exclude_statuses"] = list(EXCLUDED_STATUSES)

    if intent.get("metric") == "nb_opportunities":
        intent["aggregation"] = "count"
    elif intent.get("metric") == "win_probability":
        intent["aggregation"] = "avg"
    else:
        intent.setdefault("aggregation", "sum")

    if not intent.get("is_conversation") and intent.get("metric"):
        _apply_relative_period(q, intent, today or date.today())

    intent.setdefault("limit", 0)
    return intent
