import os
import json
import logging
import difflib
import re
import time
from datetime import date
from typing import Optional, Union

from google import genai
from google.genai import types as genai_types
from google.genai.errors import APIError, ClientError, ServerError
from .schema_and_whitelist import (
    VALID_METRICS, VALID_DIMENSIONS, VALID_CHART_TYPES, VALID_FILTERS, KNOWN_VALUES
)
from pydantic import BaseModel, ValidationError, field_validator
from dotenv import load_dotenv
from .intent_refiner import try_followup_parse, try_rule_based_parse, refine_intent

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
    # "client"/"buyer"/"acheteur" désignent tous la colonne buyer. "lead" est le mot
    # qu'emploie l'équipe pour la même chose dans le tableau des affaires chaudes.
    "buyer": ("client", "buyer", "acheteur", "lead", "compte"),
    "partner": ("partenaire", "partner"),
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


# "-latest" plutôt qu'une version épinglée (ex: gemini-2.5-flash) : Google déprécie et
# retire des modèles sans préavis particulier (déjà vécu avec Groq/llama-3.3-70b-versatile,
# retiré du service entre deux sessions) — un alias "-latest" reste pointé vers un modèle
# valide même si Google fait tourner sa gamme, au prix de ne pas figer le comportement.
#
# "flash-lite" plutôt que "flash" : mesuré empiriquement sur le quota gratuit — la variante
# "flash" (gemini-flash-latest, alias vers gemini-3.7-flash au moment du test) est plafonnée
# à 5 requêtes/minute, beaucoup trop bas pour un chat interactif (quelques messages suffisent
# à l'épuiser) ; "flash-lite" tient ~16 requêtes/minute sur le même compte gratuit, largement
# suffisant ici puisque c'est le schéma + la validation Pydantic qui garantissent la précision,
# pas la taille du modèle (qualité d'extraction vérifiée équivalente sur les mêmes requêtes).
GEMINI_MODEL = "gemini-flash-lite-latest"

_GEMINI_MAX_ATTEMPTS = 3  # 1 essai + 2 retries sur surcharge transitoire (503)
_GEMINI_RETRY_DELAY_SECONDS = 1.5

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


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


def _libelle(colonne: str) -> str:
    """Le nom FRANÇAIS d'une colonne, pour les messages destinés à l'utilisateur.

    « Valeur « Atlantide » non reconnue pour le filtre « country » » mêlait une
    phrase française et une clé technique anglaise. Les libellés existaient déjà
    (labels.FILTER_LABELS) ; ils n'étaient simplement pas appliqués ici.
    """
    from .labels import DIMENSION_LABELS, FILTER_LABELS
    return FILTER_LABELS.get(colonne) or DIMENSION_LABELS.get(colonne) or colonne


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


# Ce que le modèle renvoie quand la question demande une répartition selon quelque
# chose qui n'existe pas dans les données. Un marqueur explicite plutôt qu'une chaîne
# vide : "" veut dire « aucune répartition demandée » (un KPI global est alors la
# bonne réponse), et confondre les deux faisait répondre le total du portefeuille à
# « budget par couleur de cheveux ».
DIMENSION_INCONNUE = "__inconnu__"

AXES_DISPONIBLES = ("pays, practice, statut, client, partenaire, mois, année, "
                    "source de financement, type d'opportunité")


def _resolve_dimension(raw: str) -> str:
    if raw in VALID_DIMENSIONS:
        return raw
    if raw == DIMENSION_INCONNUE:
        raise IntentUnclear(
            "Cette répartition n'existe pas dans les données. Axes disponibles : "
            f"{AXES_DISPONIBLES}."
        )
    low = raw.lower()
    for canonical, keywords in DIMENSION_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return canonical
    raise IntentUnclear(
        f"Je ne reconnais pas l'axe d'analyse « {raw} ». Axes possibles : {AXES_DISPONIBLES}."
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
    if key == "buyer":
        return db_ctx.get("buyers", []), {}
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
                "Valeur(s) « %s » non reconnue(s) pour « %s »."
                % (", ".join(unresolved), _libelle(key))
            )
        return resolved

    match = _resolve_one_filter_value(key, value, known, aliases)
    if match is None:
        raise IntentUnclear(
            "Valeur « %s » non reconnue pour « %s »." % (value, _libelle(key)))
    return match


# Une seule définition du contexte vide : les deux sorties de secours de
# `_load_db_context` (données absentes, chargement en échec) doivent porter les
# mêmes clés que le cas nominal, sinon un `.get()` oublié ailleurs lève un KeyError
# exactement le jour où les données manquent.
_EMPTY_DB_CONTEXT = {
    "countries": [], "funding_sources": [], "partners": [], "buyers": [], "years": [],
}


def _verifier_periode(filters: dict, db_ctx: dict) -> None:
    """Refuse une période entièrement hors des données plutôt que de l'ignorer.

    « budget en 2030 » renvoyait le portefeuille complet, tous exercices confondus :
    la contrainte disparaissait de la requête mais restait dans la question, donc la
    réponse avait toutes les apparences d'y répondre. Une année PARTIELLEMENT couverte
    passe normalement — c'est seulement quand il ne reste rien à montrer qu'on parle.
    """
    annees_connues = db_ctx.get("years") or []
    if not annees_connues:
        return  # Données indisponibles : on ne bloque pas sur une liste vide.

    demandees = filters.get("deadline_year")
    if demandees is None:
        return
    if not isinstance(demandees, list):
        demandees = [demandees]

    hors_perimetre = []
    for annee in demandees:
        try:
            valeur = int(str(annee).strip())
        except (TypeError, ValueError):
            continue  # Valeur illisible : ce n'est pas à ce garde-fou de la juger.
        if valeur not in annees_connues:
            hors_perimetre.append(str(valeur))

    if hors_perimetre and len(hors_perimetre) == len(demandees):
        couverture = (f"{annees_connues[0]}" if len(annees_connues) == 1
                      else f"{annees_connues[0]} à {annees_connues[-1]}")
        raise IntentUnclear(
            f"Aucune donnée pour {', '.join(hors_perimetre)}. Les échéances connues vont "
            f"de {couverture}."
        )


def _load_db_context() -> dict:
    # Pas de cache ici (contrairement à avant, où c'était une vraie requête réseau
    # MySQL qu'on ne voulait pas refaire à chaque appel) : le DataFrame lui-même est
    # déjà mis en cache et rafraîchi périodiquement par data_store.py, donc dériver
    # ces listes à chaque appel est instantané (opération en mémoire) et reste
    # toujours à jour avec le dernier chargement du Sheet, sans jamais devenir périmé.
    try:
        from .data_store import get_dataframe
        df = get_dataframe()
        if df is None or df.empty:
            return _EMPTY_DB_CONTEXT.copy()
        return {
            "countries": sorted(df["country"].dropna().unique().tolist()),
            "funding_sources": sorted(df["funding_source"].dropna().unique().tolist()),
            "partners": sorted(df["partner"].dropna().unique().tolist()),
            "buyers": sorted(df["buyer"].dropna().unique().tolist()),
            # Années réellement couvertes par les données. Sert à refuser une période
            # hors périmètre plutôt qu'à répondre le portefeuille entier : « budget en
            # 2030 » ne doit pas renvoyer le total de tous les exercices confondus.
            "years": sorted({int(a) for a in df["deadline_year"].dropna().unique().tolist()}),
        }
    except Exception:
        logger.warning("Contexte des données indisponible, poursuite sans listes de référence.", exc_info=True)
        return _EMPTY_DB_CONTEXT.copy()


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

# « pour le client X », « chez le partenaire Y » : une désignation explicite d'entité
# que le parseur rapide ne sait pas résoudre. Quand elle ne correspond à aucun nom
# connu, mieux vaut le modèle et sa validation stricte qu'une réponse muette sur le
# complément.
_DESIGNATION_PATTERN = re.compile(
    r"\b(?:client|acheteur|partenaire|compte|lead)\s+[\w'&.-]{2,}", re.IGNORECASE
)


def _entites_nommees(q_lower: str, connues: list) -> list:
    """Les noms de `connues` cités dans la question.

    La comparaison est ancrée sur des frontières de mots : sans ça, un client nommé
    « CDC » se reconnaîtrait à l'intérieur de n'importe quel mot le contenant, et une
    question sans rapport se retrouverait filtrée sur lui. Les noms très courts sont
    écartés pour la même raison — le risque de collision y dépasse le service rendu.
    """
    trouves = []
    for nom in connues:
        nom_bas = str(nom).lower().strip()
        if len(nom_bas) < 3:
            continue
        if re.search(r"(?<![\w])%s(?![\w])" % re.escape(nom_bas), q_lower):
            trouves.append(nom)
    return trouves


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

    # La condition portait sur « aucun filtre du tout » : « budget pour Data
    # Management en Islande » avait déjà son filtre de practice, la garde ne se
    # déclenchait donc pas et le complément de lieu disparaissait sans un mot — le
    # budget de la practice entière repartait comme celui de l'Islande. Ce qui
    # compte n'est pas qu'un filtre existe, c'est qu'aucun ne réponde AU LIEU cité.
    if "country" not in (ruled.get("filters") or {}) and _LOCATION_PATTERN.search(query):
        return None

    # Même raisonnement que pour les pays, appliqué aux clients et aux partenaires :
    # le parseur rapide ne connaît pas ces listes (96 clients, 13 partenaires) et
    # rendait « budget pour le client ASIN » avec un `filters` vide — donc le budget
    # de TOUT le portefeuille présenté comme celui d'un client. Un nom reconnu
    # devient un filtre ; une désignation explicite qui ne correspond à rien de connu
    # repasse par le modèle et sa validation stricte, qui saura le dire.
    for colonne, cle_ctx in (("buyer", "buyers"), ("partner", "partners")):
        trouves = _entites_nommees(q_lower, db_ctx.get(cle_ctx, []))
        if len(trouves) == 1:
            ruled.setdefault("filters", {})
            ruled["filters"].setdefault(colonne, trouves[0])
            return ruled
        if len(trouves) > 1:
            return None

    if not ruled.get("filters") and _DESIGNATION_PATTERN.search(query):
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

    # Retouche du dashboard courant (« en camembert », « top 5 », « enlève le filtre ») :
    # l'intention précédente est reprise et modifiée, ce que le code fait mieux qu'un
    # appel au modèle — le contexte est conservé exactement, sans risque de le voir
    # réinterprété, et sans consommer le quota. Rendu None dès que la demande n'est
    # pas une retouche reconnue : on repasse alors par le chemin normal.
    if previous_intent is not None:
        suite = try_followup_parse(query, previous_intent)
        if suite is not None:
            logger.info("Retouche appliquée sans appel au modèle : %r", query)
            return refine_intent(query, suite, today=today)

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

User: "liste des offres pondérées"
→ {"goal":"Offres pondérées","metric":"budget","dimension":"","filters":{},"range_filters":{"win_probability":{"op":">=","value":0.8}},"chart_type":"table","aggregation":"sum","use_raw_table":true,"is_conversation":false}

User: "budget moyen par pays"
→ {"goal":"Budget moyen par pays","metric":"budget","dimension":"country","filters":{},"range_filters":{},"chart_type":"bar","aggregation":"avg","use_raw_table":false,"is_conversation":false}

User: "top 5 des clients par budget"
→ {"goal":"Top 5 des clients par budget","metric":"budget","dimension":"buyer","filters":{},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "montant pondéré par pays"
→ {"goal":"Montant pondéré par pays","metric":"weighted_amount","dimension":"country","filters":{},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":false}
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
  buyer = client, acheteur, lead, compte ; partner = partenaire ;
  funding_source = source de financement ; opp_type = type d'opportunité
  N'utilise "" QUE si la question ne demande vraiment aucune répartition. Si elle demande
  une répartition selon quelque chose qui ne figure PAS dans cette liste, mets
  dimension = "__inconnu__" — ne réponds jamais un total global à la place.

aggregation : "avg" dès que la question demande une MOYENNE ("moyen", "moyenne", "en moyenne").
  "sum" sinon pour un montant, "count" pour nb_opportunities. Une moyenne et une somme ne
  répondent pas à la même question : ne les confonds jamais.

chart_type : {VALID_CHART_TYPES} — choisis selon le JOB de la question, pas selon des mots-clés isolés :
  - Un seul chiffre demandé, sans dimension (« combien », « quel est », « total ») → kpi_card
  - Comparer une magnitude entre catégories (« par pays », « par statut »…) → bar (le défaut sûr)
  - Proportion / part du total explicitement demandée (« répartition », « part de »,
    « pourcentage », « quelle proportion ») ET la dimension a peu de valeurs (≤ 6) → pie
    (jamais pie si la question demande juste une comparaison sans notion de proportion — bar reste le défaut)
  - Tendance dans le temps → line (dimension = deadline_month/deadline_year) ; area = même chose
    en plus visuel, seulement si "aire"/"area" est explicitement demandé
  - Liste détaillée d'opportunités individuelles (« liste », « détail », « tableau ») → table,
    use_raw_table = true
  - Entonnoir de vente / pipeline par étape → funnel (dimension forcée à "status", ne pas t'en soucier)
  - Corrélation entre deux mesures numériques (« lien entre X et Y », « est-ce que X influence Y »)
    → scatter (toujours budget vs probabilité de gain — laisse dimension="", JAMAIS kpi_card pour
    une question de corrélation : un seul chiffre moyen n'y répond pas)
  - Intensité croisée entre une dimension (ex: pays) et practice → heatmap
  N'invente jamais un chart_type "pour faire joli" — s'il n'y a pas de signal clair dans la question,
  reste sur le défaut (bar si dimension posée, kpi_card sinon).

aggregation : ['sum', 'avg', 'count']

VALEURS EXACTES EN BASE (utilise-les telles quelles dans filters) :
{json.dumps(KNOWN_VALUES, ensure_ascii=False)}

MAPPING FR → filters :
- "gagné/gagnées/remporté" → status "Offre gagnée"
- "perdu/perdue" → status "Offre perdue"
- "signé" → status "Offre signée"
- "pour/chez le client X", "le compte X", "le lead X" → filters.buyer = "X"
- "avec le partenaire Y", "en partenariat avec Y" → filters.partner = "Y"
- "Data" → practice "Data Management"
- "Risk" → practice "Risk Advisory"
- "Digital" → practice "Digital Transformation"
- "offre(s)/opportunité(s) pondérée(s)" et "affaire(s) chaude(s)" (jamais "montant pondéré",
  qui désigne le metric weighted_amount) → range_filters.win_probability = {{"op": ">=",
  "value": 0.8}} et RIEN D'AUTRE. Le statut ne joue AUCUN rôle dans cette définition :
  n'ajoute jamais filters.status ici. Définition métier fixe, ne dépend pas du contexte.

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

    # ServerError (5xx) = surcharge côté Google, transitoire — observé empiriquement en
    # pratique, une ou deux tentatives suffisent presque toujours. ClientError 429 = quota
    # épuisé : Google indique lui-même un délai de reprise de plusieurs dizaines de
    # secondes, donc retenter tout de suite ne servirait à rien — message dédié à la place.
    response = None
    for attempt in range(_GEMINI_MAX_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=query,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            break
        except ServerError:
            if attempt == _GEMINI_MAX_ATTEMPTS - 1:
                logger.exception("Appel Gemini en échec (surcharge persistante) pour la requête %r", query)
                raise ValueError("Service IA temporairement indisponible. Merci de réessayer dans un instant.")
            logger.warning("Gemini surchargé (503), nouvelle tentative %d/%d...", attempt + 1, _GEMINI_MAX_ATTEMPTS)
            time.sleep(_GEMINI_RETRY_DELAY_SECONDS)
        except ClientError as e:
            logger.exception("Appel Gemini en échec (429/quota) pour la requête %r", query)
            if getattr(e, "code", None) == 429:
                raise ValueError(
                    "Trop de questions posées en peu de temps (quota IA atteint). "
                    "Merci de patienter une minute avant de réessayer."
                )
            raise ValueError("Service IA temporairement indisponible. Merci de réessayer dans un instant.")
        except APIError:
            logger.exception("Appel Gemini en échec pour la requête %r", query)
            raise ValueError("Service IA temporairement indisponible. Merci de réessayer dans un instant.")

    response_text = response.text
    logger.debug("Réponse brute Gemini : %s", response_text)

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
            # Une clé de filtre hors périmètre passait jusqu'ici sans bruit : aucune
            # liste de référence n'existe pour elle, donc sa valeur était acceptée
            # telle quelle puis ignorée en aval — la réponse portait alors sur tout
            # le portefeuille en prétendant être filtrée.
            if k not in VALID_FILTERS:
                raise IntentUnclear(
                    "Je ne peux pas filtrer sur « %s ». Filtres disponibles : %s."
                    % (_libelle(k), AXES_DISPONIBLES)
                )
            resolved_filters[k] = _resolve_filter_value(k, v, db_ctx)
        intent.filters = resolved_filters
        _verifier_periode(resolved_filters, db_ctx)
        intent.limit = int(intent.limit or 0)
    except IntentUnclear as e:
        logger.info("Intention ambiguë pour %r : %s", query, e)
        return _unclear_intent(str(e))

    return refine_intent(query, intent.model_dump(), today=today)
