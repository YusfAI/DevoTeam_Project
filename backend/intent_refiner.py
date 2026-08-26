"""Post-process and rule-based pre-parse to improve intent accuracy."""

import re
import unicodedata
from datetime import date
from typing import Optional

from .business_rules import (
    HOT_DEAL_MIN_PROBABILITY, HOT_DEAL_STATUSES, SUBMITTED_STATUSES, choose_chart_type,
)
from .schema_and_whitelist import VALID_METRICS, VALID_DIMENSIONS, KNOWN_VALUES
from .alerts import EXCLUDED_STATUSES


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


# "offre(s)"/"opportunité(s)" doit précéder "pondéré..." de près (0-2 mots entre les
# deux) — exclut "montant pondéré", qui n'a ni "offre" ni "opportunité" à proximité.
_WEIGHTED_OFFER_PATTERN = re.compile(r"\b(?:offres?|opportunit\w*)\s+(?:\w+\s+){0,2}ponder")

# « affaire chaude » est l'autre nom de la même chose : une offre déjà remise, très
# probable, dont la décision n'est pas tombée. Deux termes pour un seul concept —
# ils doivent donc résoudre vers la MÊME définition, sinon la même question donnerait
# deux chiffres selon le mot employé.
_HOT_DEAL_PATTERN = re.compile(r"\b(?:affaires?|deals?|opportunit\w*)\s+(?:[\w'-]+\s+){0,2}chaud")

# « ajoute le budget par pays » : compléter le tableau de bord affiché, pas le
# remplacer. Le verbe ne change RIEN à l'analyse demandée — même métrique, même axe,
# mêmes filtres — seulement la façon dont le résultat rejoint l'écran. D'où un
# simple drapeau porté par l'intention, plutôt qu'un chemin de composition distinct.
_APPEND_PATTERN = re.compile(r"\b(?:ajoute\w*|rajoute\w*|joins?|complete\w*)\b")

# « offres remises » est un terme MÉTIER, pas le statut du même nom. Le statut décrit
# l'état courant : une offre partie chez le client et gagnée depuis n'y figure plus.
# Sans cette règle, la question « combien d'offres a-t-on remises ? » répondait 4 —
# le nombre d'offres encore en attente de décision — quand la vue d'ensemble en
# affiche 57. Deux chiffres différents pour la même question, selon qu'on la pose au
# chat ou qu'on la lise sur le dashboard : c'est précisément ce que ce projet évite.
#
# Le pluriel n'est pas exigé (« combien d'offre remise ») mais « offre remise »
# employé au singulier avec un déterminant défini (« le statut offre remise ») reste
# rare, et la levée d'ambiguïté par le nombre serait fragile.
# Jusqu'à trois mots peuvent s'intercaler : « combien d'offres A-T-ON remises ». La
# classe intermédiaire inclut l'apostrophe et le trait d'union, sans quoi « a-t-on »
# ne compterait pas pour un mot et la tournure la plus naturelle de la question
# passerait à côté de la règle.
_SUBMITTED_OFFER_PATTERN = re.compile(
    r"\b(?:offres?|opportunit\w*|dossiers?)\s+(?:[\w'-]+\s+){0,3}(?:remis\w*|depose\w*|soumis\w*)"
)


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


# Tables plutôt que cascades de `if` : les mêmes formulations servent à détecter la
# métrique ET à savoir quels mots de la demande ont été compris (voir
# try_followup_parse). Deux listes séparées auraient fini par diverger.
_METRIC_PHRASES = [
    (("combien", "nombre", "volume", "nb", "count"), "nb_opportunities"),
    (("proba", "probabilite", "chance"), "win_probability"),
    (("offre financiere", "financial offer"), "financial_offer"),
    (("pondere", "weighted"), "weighted_amount"),
    (("budget", "ca", "chiffre", "montant"), "budget"),
]

_DIMENSION_PHRASES = [
    (("par pays", "par country"), "country"),
    (("par practice", "par metier"), "practice"),
    (("par statut", "par status"), "status"),
    (("par mois", "evolution", "mensuel"), "deadline_month"),
    (("par an", "par annee"), "deadline_year"),
    (("par type",), "opp_type"),
    (("par source", "financement"), "funding_source"),
]


def _phrase_pattern(phrase: str) -> str:
    """Une phrase courte est ancrée des DEUX côtés. Sans ça « ca » (pour « CA »,
    le chiffre d'affaires) se retrouvait dans « camembert » et dans « carte de
    chaleur » : demander un camembert basculait silencieusement la métrique sur le
    budget. Les phrases plus longues restent ancrées au début seulement, pour
    continuer d'attraper les accords (« pondéré » → « pondérée »).
    """
    escaped = re.escape(phrase.strip())
    return r"\b" + escaped + (r"\b" if len(phrase.strip()) <= 3 else "")


def _match_phrase(q: str, table: list) -> tuple[str | None, str]:
    """(valeur, texte trouvé dans la question) — le texte sert à vérifier ensuite
    que la demande a été comprise en entier."""
    for phrases, valeur in table:
        for phrase in phrases:
            found = re.search(_phrase_pattern(phrase), q)
            if found:
                return valeur, found.group(0)
    return None, ""


def _detect_metric(q: str) -> str | None:
    return _match_phrase(q, _METRIC_PHRASES)[0]


def _detect_dimension(q: str) -> str | None:
    return _match_phrase(q, _DIMENSION_PHRASES)[0]


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
    if any(w in q for w in ("camembert", "repartition", "part de", "pourcentage", "proportion")):
        return "pie"
    if any(w in q for w in ("evolution", "tendance", "courbe")):
        # "évolution"/"tendance" n'implique une courbe que sur un axe temporel — sur une
        # dimension non temporelle (ex: "évolution par pays", très inhabituel), une courbe
        # n'a pas de sens (rien à ordonner sur l'axe X) ; on laisse retomber sur "bar".
        if not dimension or dimension in ("deadline_month", "deadline_year"):
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
# Ajustements sur le dashboard courant
#
# « en camembert », « top 5 », « enlève le filtre » ne sont pas des questions :
# ce sont des retouches de la question précédente. Les traiter comme des questions
# neuves faisait perdre le contexte — « par pays » repartait sur le nombre
# d'opportunités alors que la question d'avant portait sur le budget — et
# consommait un appel au modèle (quota gratuit ~16 requêtes/minute) pour un
# changement que le code sait appliquer seul, instantanément.
#
# GARDE-FOU CENTRAL : une retouche hérite en silence de tout le contexte précédent.
# Si un seul mot de la demande n'a pas été compris ici, l'hériter reviendrait à
# répondre à une autre question que celle posée — « budget par pays au Maroc pour
# Data Management » serait servie avec le filtre « Risk Advisory » de la question
# d'avant. On exige donc que CHAQUE mot porteur de sens ait été consommé par une
# règle ; au moindre reliquat, on rend la main au chemin normal (LLM + validation).
# ---------------------------------------------------------------------------

# Formes nommées explicitement par l'utilisateur. La forme demandée reste ensuite
# soumise à choose_chart_type : demander un camembert sur 19 pays donne des barres,
# avec l'explication affichée sous le graphique.
_FOLLOWUP_CHARTS = [
    (("camembert", "secteurs"), "pie"),
    (("histogramme", "barres", "barre"), "bar"),
    (("courbe", "lignes"), "line"),
    (("aire",), "area"),
    (("tableau", "liste"), "table"),
    (("nuage de points", "nuage"), "scatter"),
    (("entonnoir",), "funnel"),
    (("carte de chaleur", "heatmap"), "heatmap"),
]

# Retire TOUS les filtres : « remets tout », « sur l'ensemble du portefeuille ».
_RESET_FILTERS = (
    "sans filtre", "sans les filtres", "sans aucun filtre",
    "enleve les filtres", "enleve le filtre", "enleve tous les filtres",
    "retire les filtres", "retire le filtre", "annule les filtres",
    "tout le portefeuille", "ensemble du portefeuille",
    "remets tout", "sans restriction",
)

# Mots sans effet sur le sens d'une retouche : leur présence dans le reliquat ne
# doit pas faire échouer la vérification de couverture.
_FOLLOWUP_STOPWORDS = {
    "le", "la", "les", "l", "de", "du", "des", "un", "une", "d", "et", "ou",
    "en", "au", "aux", "a", "sur", "pour", "par", "avec", "dans", "ce", "cet",
    "cette", "ca", "c", "est", "moi", "me", "nous", "y", "s", "n", "je", "tu",
    "montre", "montres", "affiche", "affiches", "donne", "donnes", "mets", "met",
    "passe", "change", "changer", "fais", "fait", "refais", "plutot", "maintenant",
    "juste", "seulement", "uniquement", "aussi", "encore", "toujours", "alors",
    # Verbes d'ajout : ils pilotent la façon d'appliquer le résultat, pas son
    # contenu, et ne doivent donc pas faire échouer la vérification de couverture.
    "ajoute", "ajoutes", "ajouter", "rajoute", "rajouter", "complete", "completer",
    "puis", "ensuite", "svp", "stp", "merci", "voir", "graphique", "graphe",
    "dashboard", "tableau de bord", "practice", "plait", "il", "sous", "forme",
}

# Seconde barrière, moins fine que la couverture mot à mot mais immédiate : une
# retouche est courte par nature.
_MAX_FOLLOWUP_LENGTH = 60

_FOLLOWUP_KEYS = ("metric", "dimension", "filters", "range_filters", "chart_type",
                  "aggregation", "use_raw_table", "limit", "exclude_statuses")


def _compose_goal(intent: dict) -> str:
    """Titre reconstruit à partir de l'intention retouchée. Reprendre la phrase de
    l'utilisateur donnerait « En camembert » comme titre de dashboard ; garder
    l'ancien titre laisserait croire que la retouche n'a pas été prise en compte."""
    from .labels import DIMENSION_LABELS, FILTER_LABELS, METRIC_LABELS

    titre = METRIC_LABELS.get(intent.get("metric", ""), intent.get("metric", "")).capitalize()
    dimension = intent.get("dimension")
    if dimension:
        titre += " par " + DIMENSION_LABELS.get(dimension, dimension).lower()

    valeurs = []
    for colonne, valeur in (intent.get("filters") or {}).items():
        if isinstance(valeur, (list, tuple)):
            valeurs.append(" vs ".join(str(v) for v in valeur))
        else:
            valeurs.append(str(valeur))
        FILTER_LABELS.get(colonne, colonne)  # libellés disponibles si besoin d'enrichir
    if valeurs:
        titre += " — " + ", ".join(valeurs)
    return titre or "Analyse"


def try_followup_parse(query: str, previous_intent: dict | None) -> dict | None:
    """Applique une retouche courte à l'intention précédente. Renvoie None dès que la
    demande n'est pas intégralement reconnue comme une retouche — l'appelant passe
    alors par le chemin normal (LLM + validation stricte), jamais par une supposition.
    """
    if not previous_intent or not previous_intent.get("metric"):
        return None
    if previous_intent.get("is_conversation"):
        return None

    q = _norm(query).strip()
    if not q or len(q) > _MAX_FOLLOWUP_LENGTH:
        return None

    intent = {k: previous_intent[k] for k in _FOLLOWUP_KEYS if k in previous_intent}
    intent["filters"] = dict(intent.get("filters") or {})
    intent["range_filters"] = dict(intent.get("range_filters") or {})
    intent["is_conversation"] = False

    reste = " " + q + " "
    touche = False

    def consomme(texte: str) -> None:
        nonlocal reste
        if texte:
            reste = reste.replace(texte, " ")

    for mot in _RESET_FILTERS:
        if mot in reste:
            intent["filters"] = {}
            intent["range_filters"] = {}
            consomme(mot)
            touche = True

    chart, texte = _match_phrase(reste, _FOLLOWUP_CHARTS)
    if chart:
        intent["chart_type"] = chart
        intent["use_raw_table"] = chart == "table"
        consomme(texte)
        touche = True

    # Filtres nommés : practice et statut ont des valeurs canoniques connues, donc
    # résolubles ici sans risque. Un pays ne l'est pas (liste dynamique, hors de
    # portée de ce module) — une demande qui en nomme un échouera à la vérification
    # de couverture et repartira vers le LLM, qui sait la résoudre.
    poses_ici = set()
    practice = _detect_practice(reste)
    if practice:
        intent["filters"]["practice"] = practice
        poses_ici.add("practice")
        for cle in PRACTICE_MAP:
            if cle in reste:
                consomme(cle)
                break
        touche = True

    statut = _detect_status(reste)
    if statut:
        intent["filters"]["status"] = statut
        poses_ici.add("status")
        for cle in STATUS_MAP:
            if cle in reste:
                consomme(cle)
                break
        touche = True

    dimension, texte = _match_phrase(reste, _DIMENSION_PHRASES)
    if dimension:
        intent["dimension"] = dimension
        consomme(texte)
        # Grouper PAR une colonne sur laquelle on filtre déjà ne produirait qu'une
        # seule barre : le filtre devient redondant avec l'axe et doit sauter. On
        # épargne les filtres à plusieurs valeurs — « compare France et Maroc » veut
        # précisément cet axe ET cette restriction — et ceux que la demande vient de
        # poser elle-même, qui sont voulus.
        valeur = intent["filters"].get(dimension)
        if (dimension not in poses_ici and valeur is not None
                and not isinstance(valeur, (list, tuple))):
            del intent["filters"][dimension]
        touche = True

    metric, texte = _match_phrase(reste, _METRIC_PHRASES)
    if metric:
        intent["metric"] = metric
        consomme(texte)
        touche = True

    m_top = re.search(r"top\s*(\d+)|(\d+)\s*premiers?", reste)
    if m_top:
        intent["limit"] = int(m_top.group(1) or m_top.group(2))
        consomme(m_top.group(0))
        touche = True

    if not touche:
        return None

    # Vérification de couverture : tout mot restant est un mot qu'on n'a PAS compris.
    for mot in re.findall(r"[a-z0-9]+", reste):
        if mot not in _FOLLOWUP_STOPWORDS:
            return None

    intent["goal"] = _compose_goal(intent)
    return intent


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

    # Détecté ici plutôt que dans le seul parseur de retouches : « ajoute … » doit
    # être compris qu'il passe par le modèle ou par le chemin déterministe.
    if _APPEND_PATTERN.search(q):
        intent["append"] = True

    if not intent.get("limit"):
        m_top = re.search(r"top\s*(\d+)|(\d+)\s*premier", q)
        if m_top:
            intent["limit"] = int(m_top.group(1) or m_top.group(2))

    # "offre(s)/opportunité(s) pondérée(s)" est un terme métier défini explicitement :
    # probabilité de gain >= 80 % ET statut "Offre remise" — jamais "montant pondéré"
    # (le metric weighted_amount, ex. "montant pondéré par pays"), qui ne doit pas
    # déclencher ce filtre. D'où l'exigence que "offre"/"opportunité" précède "pondéré"
    # de près : ça exclut "montant pondéré", où aucun des deux mots n'apparaît avant.
    # Ce n'est qu'un filtre — le type d'affichage (table/KPI/graphique) reste piloté
    # normalement par le reste de la question, jamais forcé ici.
    if _WEIGHTED_OFFER_PATTERN.search(q) or _HOT_DEAL_PATTERN.search(q):
        intent.setdefault("filters", {})
        intent["filters"]["status"] = list(HOT_DEAL_STATUSES)
        intent.setdefault("range_filters", {})
        intent["range_filters"]["win_probability"] = {
            "op": ">=", "value": HOT_DEAL_MIN_PROBABILITY,
        }

    # « offres remises » = toutes celles effectivement déposées, y compris gagnées et
    # perdues depuis (business_rules.SUBMITTED_STATUSES). Placé APRÈS la règle des
    # offres pondérées, qui est plus spécifique et vise un tout autre périmètre.
    # Filtrer sur `status` lève au passage l'exclusion par défaut des affaires
    # perdues — ce qui est voulu : une offre perdue a bien été remise.
    elif _SUBMITTED_OFFER_PATTERN.search(q):
        intent.setdefault("filters", {})
        intent["filters"]["status"] = list(SUBMITTED_STATUSES)

    # Ce que les MOTS de la question demandent. La forme retenue est ensuite validée
    # contre la forme réelle des données par choose_chart_type, en fin de fonction :
    # « répartition par pays » appelle bien un camembert, mais il y a 19 pays.
    dimension = intent.get("dimension", "")
    if any(w in q for w in ("camembert", "repartition", "pourcentage", "proportion")):
        if dimension:
            intent["chart_type"] = "pie"
    if any(w in q for w in ("liste", "lister", "detail")):
        intent["use_raw_table"] = True
        intent["chart_type"] = "table"

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

    # Arbitrage final de la forme, une fois métrique, dimension, filtres et limite
    # tous connus — c'est seulement à ce stade qu'on peut mesurer la cardinalité
    # réelle et savoir si la forme demandée sert encore la question.
    if not intent.get("is_conversation") and intent.get("metric"):
        chart, raison = choose_chart_type(intent)
        intent["chart_type"] = chart
        intent["chart_type_reason"] = raison

    return intent
