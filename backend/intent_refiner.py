"""Post-process and rule-based pre-parse to improve intent accuracy."""

import re
import unicodedata
from .schema_and_whitelist import VALID_METRICS, VALID_DIMENSIONS, KNOWN_VALUES


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
        range_filters["days_remaining"] = {"op": "<", "value": int(m_days.group(1))}
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


def refine_intent(query: str, intent: dict) -> dict:
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

    if intent.get("metric") == "nb_opportunities":
        intent["aggregation"] = "count"
    elif intent.get("metric") == "win_probability":
        intent["aggregation"] = "avg"
    else:
        intent.setdefault("aggregation", "sum")

    intent.setdefault("limit", 0)
    return intent
