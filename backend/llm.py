import os
import json
import logging
import difflib
import re
from datetime import date
from typing import Optional, Union

from groq import Groq, GroqError
from .schema_and_whitelist import (
    VALID_METRICS, VALID_DIMENSIONS, VALID_CHART_TYPES, VALID_FILTERS, KNOWN_VALUES
)
from pydantic import BaseModel, ValidationError, field_validator
from dotenv import load_dotenv
from .intent_refiner import try_rule_based_parse, refine_intent

load_dotenv()

logger = logging.getLogger("devoteam.llm")

# Synonymes métier FR → valeurs exactes en base
STATUS_ALIASES = {
    "gagné": "Offre gagnée", "gagnée": "Offre gagnée", "gagnes": "Offre gagnée",
    "gagnées": "Offre gagnée", "remporté": "Offre gagnée", "remportée": "Offre gagnée",
    "signé": "Offre signée", "signée": "Offre signée",
    "perdu": "Offre perdue", "perdue": "Offre perdue", "perdus": "Offre perdue",
    "perdues": "Offre perdue",
    "remis": "Offre remise", "remise": "Offre remise",
    "lead": "Lead", "qualification": "En cours de qualification",
    "shortlist": "Propal shortlistée", "shortlistée": "Propal shortlistée",
    "no go": "NO GO", "nogo": "NO GO",
}

PRACTICE_ALIASES = {
    "data": "Data Management", "data management": "Data Management",
    "risk": "Risk Advisory", "risk advisory": "Risk Advisory",
    "digital": "Digital Transformation", "transformation": "Digital Transformation",
    "dt": "Digital Transformation",
}

# Mots-clés utilisés pour rattraper un metric/dimension mal formé par le LLM
# (synonymes déjà enseignés dans le prompt système) — jamais pour inventer une valeur,
# seulement pour mapper vers une des valeurs whitelistées ci-dessus.
METRIC_KEYWORDS = {
    "budget": ("budget", "ca", "montant", "chiffre"),
    "nb_opportunities": ("nb", "count", "nombre", "volume"),
    "financial_offer": ("offer", "offre"),
    "weighted_amount": ("pond", "weight"),
    "win_probability": ("prob", "chance"),
}

DIMENSION_KEYWORDS = {
    "country": ("countr", "pays"),
    "deadline_month": ("mois", "month"),
    "deadline_year": ("ann", "year"),
    "practice": ("prac",),
    "status": ("stat",),
    "funding_source": ("financ", "source"),
    "opp_type": ("type",),
}


class DashboardIntent(BaseModel):
    goal: str = ""
    metric: str = ""
    dimension: str = ""
    filters: dict[str, Union[str, list[str]]] = {}
    range_filters: dict[str, dict] = {}
    chart_type: str = "bar"
    aggregation: str = "sum"
    use_raw_table: bool = False
    is_conversation: bool = False
    limit: int = 0

    @field_validator("filters")
    @classmethod
    def _check_filter_keys(cls, v: dict) -> dict:
        unknown = [k for k in v if k not in VALID_FILTERS]
        if unknown:
            raise ValueError(f"Filtre(s) non supporté(s) : {', '.join(unknown)}")
        return v


client = Groq(api_key=os.getenv("GROQ_API_KEY"))

_DB_CONTEXT_CACHE: Optional[dict] = None


class IntentUnclear(ValueError):
    """Levée quand une valeur du LLM ne peut pas être rattachée en confiance à une valeur connue.

    Ce n'est jamais rattrapé par un défaut deviné (ex: 'budget' par défaut) — l'appelant
    doit renvoyer une demande de clarification à l'utilisateur plutôt que de répondre
    à une question différente de celle posée.
    """


def _fuzzy_match(value: str, known: list[str], aliases: Optional[dict] = None) -> Optional[str]:
    """Résout `value` vers une entrée exacte de `known`, en tentant : exact, alias,
    sous-chaîne bidirectionnelle, puis correspondance approchée (difflib). Ne retourne
    jamais une valeur absente de `known` — retourne None si rien ne correspond en confiance.
    """
    if not known:
        return None
    if value in known:
        return value

    value_lower = str(value).lower().strip()
    aliases = aliases or {}

    if value_lower in aliases:
        return aliases[value_lower]
    for alias, canonical in aliases.items():
        if alias in value_lower or value_lower in alias:
            return canonical

    lower_known = [c.lower() for c in known]
    for candidate, c_lower in zip(known, lower_known):
        if value_lower in c_lower or c_lower in value_lower:
            return candidate

    close = difflib.get_close_matches(value_lower, lower_known, n=1, cutoff=0.72)
    if close:
        return known[lower_known.index(close[0])]
    return None


def _resolve_metric(raw: str) -> str:
    if raw in VALID_METRICS:
        return raw
    low = raw.lower()
    for canonical, keywords in METRIC_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return canonical
    raise IntentUnclear(
        f"Je ne suis pas sûr de la métrique demandée (« {raw} »). Précisez par exemple : "
        "budget, nombre d'opportunités, offre financière, montant pondéré ou probabilité de gain."
    )


def _resolve_dimension(raw: str) -> str:
    if raw in VALID_DIMENSIONS:
        return raw
    low = raw.lower()
    for canonical, keywords in DIMENSION_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return canonical
    raise IntentUnclear(
        f"Je ne reconnais pas l'axe d'analyse « {raw} ». Axes possibles : pays, practice, "
        "statut, mois, année, source de financement, type d'opportunité."
    )


def _filter_source(key: str, db_ctx: dict) -> tuple[list, dict]:
    if key == "practice":
        return KNOWN_VALUES["practice"], PRACTICE_ALIASES
    if key == "opp_type":
        return KNOWN_VALUES["opp_type"], {}
    if key == "status":
        return KNOWN_VALUES["status"], STATUS_ALIASES
    if key == "country":
        return db_ctx.get("countries", []), {}
    if key == "funding_source":
        return db_ctx.get("funding_sources", []), {}
    if key == "partner":
        return db_ctx.get("partners", []), {}
    return [], {}


def _resolve_one_filter_value(key: str, value: str, known: list[str], aliases: dict) -> Optional[str]:
    if not known:
        # Liste de référence indisponible (ex: DB injoignable) — on accepte la valeur
        # telle quelle plutôt que de bloquer toute requête filtrée sur cette colonne.
        return str(value)
    return _fuzzy_match(str(value), known, aliases)


def _resolve_filter_value(key: str, value, db_ctx: dict):
    """Résout une valeur de filtre — simple (égalité) ou liste (comparaison,
    ex: filters={"country": ["France","Maroc"]}). Une liste renvoie une liste
    résolue dans le même ordre ; si un ou plusieurs éléments ne correspondent à
    rien de connu, lève IntentUnclear en les nommant tous (jamais un silencieux
    "on garde ce qui matche").
    """
    known, aliases = _filter_source(key, db_ctx)

    if isinstance(value, list):
        resolved = []
        unresolved = []
        for item in value:
            match = _resolve_one_filter_value(key, item, known, aliases)
            if match is None:
                unresolved.append(str(item))
            else:
                resolved.append(match)
        if unresolved:
            raise IntentUnclear(
                f"Valeur(s) « {', '.join(unresolved)} » non reconnue(s) pour le filtre « {key} »."
            )
        return resolved

    match = _resolve_one_filter_value(key, value, known, aliases)
    if match is None:
        raise IntentUnclear(f"Valeur « {value} » non reconnue pour le filtre « {key} ».")
    return match


def _load_db_context() -> dict:
    global _DB_CONTEXT_CACHE
    if _DB_CONTEXT_CACHE is not None:
        return _DB_CONTEXT_CACHE
    try:
        from .db import get_connection
        ctx = {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT country FROM opportunities ORDER BY country")
                ctx["countries"] = [r["country"] for r in cur.fetchall()]
                cur.execute(
                    "SELECT DISTINCT funding_source FROM opportunities "
                    "WHERE funding_source IS NOT NULL ORDER BY funding_source"
                )
                ctx["funding_sources"] = [r["funding_source"] for r in cur.fetchall()]
                cur.execute(
                    "SELECT DISTINCT partner FROM opportunities WHERE partner IS NOT NULL ORDER BY partner"
                )
                ctx["partners"] = [r["partner"] for r in cur.fetchall()]
        _DB_CONTEXT_CACHE = ctx
        return ctx
    except Exception:
        logger.warning("Contexte DB indisponible, poursuite sans listes de référence.", exc_info=True)
        return {"countries": [], "funding_sources": [], "partners": []}


def _unclear_intent(message: str) -> dict:
    return {
        "goal": "", "metric": "", "dimension": "", "filters": {}, "range_filters": {},
        "chart_type": "bar", "aggregation": "sum", "use_raw_table": False,
        "is_conversation": True, "limit": 0, "clarification": message,
    }


# "en X" / "au X" / "aux X" : forme française typique d'un complément de lieu
# (pays) qui n'est pas dans le vocabulaire fixe (practice/status) du parseur
# déterministe — donc jamais extrait par lui.
_LOCATION_PATTERN = re.compile(r"\b(?:en|au|aux)\s+[a-zàâäéèêëïîôöùûüç' -]{3,30}", re.IGNORECASE)

# Signale une requête de comparaison ("compare X vs Y") — le parseur rapide n'a
# aucune notion de filtre à valeurs multiples, il ne doit jamais y prétendre
# répondre seul (voir _augment_rule_based_result).
_COMPARISON_WORDS = ("compar", " vs ", " versus ", " contre ")


def _augment_rule_based_result(query: str, ruled: dict, db_ctx: dict) -> Optional[dict]:
    """`try_rule_based_parse` ne connaît que practice/status/metric/dimension par
    mots-clés fixes — il n'a pas accès à la liste (dynamique, en DB) des pays, ni à
    la notion de comparaison (filtre à plusieurs valeurs). Une requête comme
    "budget en atlantis" obtient donc `metric="budget"` avec grande confiance et un
    `filters={}` vide, silencieux sur le complément de lieu qu'elle contient ; une
    requête comme "compare le budget France vs Maroc" ne capturerait, avec la même
    confiance mal placée, que le premier pays trouvé. On rattrape les deux cas ici :
    si un unique pays connu est nommé, on l'ajoute comme filtre ; dans tout cas
    ambigu (mot de comparaison, plusieurs pays cités, ou complément de lieu ne
    correspondant à aucun pays connu), on ne fait pas confiance au parseur rapide —
    on renvoie None pour forcer le passage par le LLM + la validation stricte.
    """
    q_lower = f" {query.lower()} "

    if any(w in q_lower for w in _COMPARISON_WORDS):
        return None

    matched_countries = [c for c in db_ctx.get("countries", []) if c.lower() in q_lower]
    if len(matched_countries) == 1:
        ruled.setdefault("filters", {})
        ruled["filters"].setdefault("country", matched_countries[0])
        return ruled
    if len(matched_countries) > 1:
        return None

    if not ruled.get("filters") and _LOCATION_PATTERN.search(query):
        return None

    return ruled


def _context_block(previous_intent: Optional[dict]) -> str:
    if not previous_intent:
        return ""
    keys = ("goal", "metric", "dimension", "filters", "chart_type", "aggregation", "range_filters", "use_raw_table")
    context = {k: previous_intent[k] for k in keys if k in previous_intent}
    return f"""
CONTEXTE DE LA QUESTION PRÉCÉDENTE (celle juste avant, dans cette même conversation) :
{json.dumps(context, ensure_ascii=False)}
Si la nouvelle question est une suite qui ne fait qu'ajuster ce contexte (ex: change juste un filtre
ou une dimension sans tout repréciser), hérite du reste de ce contexte. Si la nouvelle question est
indépendante, ignore ce contexte.
"""


def parse_user_query(query: str, previous_intent: Optional[dict] = None) -> dict:
    db_ctx = _load_db_context()
    today = date.today()

    if previous_intent is None:
        # Le parseur rapide n'a aucune notion de contexte conversationnel — lui faire
        # confiance sur un fragment de suite ("et pour le Maroc ?") serait risqué.
        # Dès qu'il y a un contexte à prendre en compte, on passe systématiquement par le LLM.
        ruled = try_rule_based_parse(query)
        if ruled and ruled.get("metric") and not ruled.get("is_conversation"):
            ruled = _augment_rule_based_result(query, ruled, db_ctx)
            if ruled is not None:
                return refine_intent(query, ruled, today=today)

    examples = """
EXEMPLES (copie la logique, pas les valeurs inventées) :

User: "budget par pays pour Risk Advisory"
→ {"goal":"Budget par pays — Risk Advisory","metric":"budget","dimension":"country","filters":{"practice":"Risk Advisory"},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "combien d'opportunités gagnées ?"
→ {"goal":"Nombre d'offres gagnées","metric":"nb_opportunities","dimension":"","filters":{"status":"Offre gagnée"},"range_filters":{},"chart_type":"kpi_card","aggregation":"count","use_raw_table":false,"is_conversation":false}

User: "liste des opportunités qui expirent dans moins de 7 jours"
→ {"goal":"Opportunités urgentes","metric":"budget","dimension":"","filters":{},"range_filters":{"days_remaining":{"op":"between","value":[0,7]}},"chart_type":"table","aggregation":"sum","use_raw_table":true,"is_conversation":false}

User: "répartition par practice"
→ {"goal":"Répartition par practice","metric":"nb_opportunities","dimension":"practice","filters":{},"range_filters":{},"chart_type":"pie","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "compare le budget entre la France et le Maroc"
→ {"goal":"Budget — France vs Maroc","metric":"budget","dimension":"country","filters":{"country":["France","Maroc"]},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: (contexte précédent : budget par pays pour Risk Advisory) "et pour Data Management ?"
→ {"goal":"Budget par pays — Data Management","metric":"budget","dimension":"country","filters":{"practice":"Data Management"},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "bonjour"
→ {"goal":"","metric":"","dimension":"","filters":{},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":true}

User: "montre-moi l'entonnoir de vente"
→ {"goal":"Entonnoir de vente","metric":"nb_opportunities","dimension":"status","filters":{},"range_filters":{},"chart_type":"funnel","aggregation":"count","use_raw_table":false,"is_conversation":false}

User: "y a-t-il un lien entre le budget et la probabilité de gain ?"
→ {"goal":"Budget vs probabilité de gain","metric":"budget","dimension":"","filters":{},"range_filters":{},"chart_type":"scatter","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "carte de chaleur du budget par pays et practice"
→ {"goal":"Budget par pays et practice","metric":"budget","dimension":"country","filters":{},"range_filters":{},"chart_type":"heatmap","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "évolution du budget en aire"
→ {"goal":"Évolution du budget","metric":"budget","dimension":"deadline_month","filters":{},"range_filters":{},"chart_type":"area","aggregation":"sum","use_raw_table":false,"is_conversation":false}
"""

    system_prompt = f"""Tu es un parseur d'intentions pour un dashboard commercial DevoTeam.
Tu NE réponds PAS à l'utilisateur. Tu extrais UNIQUEMENT les paramètres SQL/chart à partir de sa question.

RÈGLES ABSOLUES :
- Ne jamais inventer de chiffres, de résultats ou d'analyses.
- Ne produire AUCUN texte explicatif pour l'utilisateur (pas de message, pas de commentaire).
- Si la question demande des données → remplir metric + chart_type. is_conversation = false.
- Si c'est une salutation ou hors sujet (pas de demande de données) → metric = "" et is_conversation = true.
- Toujours mapper les termes vague vers les valeurs EXACTES listées ci-dessous.
- N'invente JAMAIS de calcul de date : si une période relative n'est pas claire (ex. "récemment"),
  laisse deadline_month/deadline_year de côté plutôt que de deviner une date.
- Si la question porte sur un LIEN, une CORRÉLATION, une RELATION ou demande si deux mesures
  "vont ensemble" (ex: "le budget influence-t-il les chances de gagner ?", "lien entre X et Y") →
  chart_type = "scatter", metric = "budget", dimension = "". Ce n'est JAMAIS un kpi_card : un seul
  chiffre moyen ne répond pas à une question de corrélation, il faut le nuage de points par opportunité.

COLONNES metric autorisées : {VALID_METRICS}
  budget = CA, montant, chiffre ; nb_opportunities = nombre, volume, combien ;
  financial_offer = offre ; weighted_amount = pondéré ; win_probability = proba, chance

COLONNES dimension autorisées : {VALID_DIMENSIONS} ("" si total global ou KPI)

chart_type : {VALID_CHART_TYPES}
  bar = comparaison ; pie = répartition (≤ 6 catégories) ; line = évolution ; area = évolution
  (accent visuel, même donnée que line) ; kpi_card = un seul chiffre ; table = liste détaillée ;
  funnel = entonnoir de vente par étape du pipeline (dimension forcée à "status", ne pas t'en soucier) ;
  scatter = corrélation entre deux mesures (toujours budget vs probabilité de gain — laisse dimension="") ;
  heatmap = intensité croisée entre une dimension (ex: pays) et practice

aggregation : ['sum', 'avg', 'count']

VALEURS EXACTES EN BASE (utilise-les telles quelles dans filters) :
{json.dumps(KNOWN_VALUES, ensure_ascii=False)}

MAPPING FR → filters :
- "gagné/gagnées/remporté" → status "Offre gagnée"
- "perdu/perdue" → status "Offre perdue"
- "signé" → status "Offre signée"
- "Data" → practice "Data Management"
- "Risk" → practice "Risk Advisory"
- "Digital" → practice "Digital Transformation"

Pour COMPARER plusieurs valeurs d'une même colonne (ex: "compare la France et le Maroc"), mets une
LISTE de valeurs dans filters au lieu d'une seule : {{"country": ["France", "Maroc"]}}.

DATE DU JOUR : {today.isoformat()}
Pour une période relative que tu comprends clairement (ex. "ce mois-ci", "l'année dernière"), tu peux
remplir directement filters.deadline_month ("YYYY-MM") ou filters.deadline_year ("YYYY") à partir de la
date du jour — mais ne le fais QUE si tu es sûr du calcul, sinon laisse ce filtre de côté.

range_filters (colonnes numériques : days_remaining, deadline_year, budget, win_probability, ou
deadline_month au format "YYYY-MM") :
Format simple : {{"colonne": {{"op": "<"|">"|"<="|">="|"=", "value": valeur}}}}
Format intervalle : {{"colonne": {{"op": "between", "value": [debut, fin]}}}}
IMPORTANT pour days_remaining : "urgentes" / "expire dans moins de N jours" signifie une échéance
encore À VENIR, jamais déjà passée (days_remaining peut être négatif pour une deadline dépassée).
Utilise TOUJOURS {{"op": "between", "value": [0, N]}} pour ce cas, jamais {{"op": "<", "value": N}} seul.

use_raw_table = true si l'utilisateur veut une LISTE d'opportunités (noms, détails), pas un graphique agrégé.

limit = nombre entier si l'utilisateur demande un "top N" ou "N premiers" (sinon 0).

PAYS DISPONIBLES EN BASE : {db_ctx.get("countries", [])}
SOURCES DE FINANCEMENT EN BASE : {db_ctx.get("funding_sources", [])}

{examples}
{_context_block(previous_intent)}
Réponds en JSON strict avec exactement ces clés :
goal, metric, dimension, filters, range_filters, chart_type, aggregation, use_raw_table, is_conversation, limit
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"},
            temperature=0.0,
        )
    except GroqError:
        logger.exception("Appel Groq en échec pour la requête %r", query)
        raise ValueError("Service IA temporairement indisponible. Merci de réessayer dans un instant.")

    response_text = chat_completion.choices[0].message.content
    logger.debug("Réponse brute Groq : %s", response_text)

    try:
        intent_data = json.loads(response_text)
        intent = DashboardIntent(**intent_data)
    except ValidationError as e:
        logger.warning("Validation Pydantic échouée : %s", e)
        raise ValueError(
            "Je n'ai pas pu interpréter votre demande. "
            "Essayez par exemple : « budget par pays pour Risk Advisory » ou « offres gagnées par mois »."
        )
    except json.JSONDecodeError:
        raise ValueError("Erreur de parsing de la demande. Veuillez reformuler votre question.")

    if intent.is_conversation or not intent.metric:
        return refine_intent(query, intent.model_dump(), today=today)

    try:
        intent.metric = _resolve_metric(intent.metric)
        if intent.dimension:
            intent.dimension = _resolve_dimension(intent.dimension)
        if intent.chart_type not in VALID_CHART_TYPES:
            intent.chart_type = "kpi_card" if not intent.dimension else "bar"

        resolved_filters = {}
        for k, v in intent.filters.items():
            resolved_filters[k] = _resolve_filter_value(k, v, db_ctx)
        intent.filters = resolved_filters
        intent.limit = int(intent.limit or 0)
    except IntentUnclear as e:
        logger.info("Intention ambiguë pour %r : %s", query, e)
        return _unclear_intent(str(e))

    return refine_intent(query, intent.model_dump(), today=today)
