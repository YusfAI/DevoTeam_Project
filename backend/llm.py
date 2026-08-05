import os
import json
from groq import Groq
from .schema_and_whitelist import (
    VALID_METRICS, VALID_DIMENSIONS, VALID_CHART_TYPES, VALID_AGGREGATIONS, KNOWN_VALUES
)
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from .intent_refiner import try_rule_based_parse, refine_intent

load_dotenv()

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


class DashboardIntent(BaseModel):
    goal: str = ""
    metric: str = ""
    dimension: str = ""
    filters: dict[str, str] = {}
    range_filters: dict[str, dict] = {}
    chart_type: str = "bar"
    aggregation: str = "sum"
    use_raw_table: bool = False
    is_conversation: bool = False
    limit: int = 0


client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def _normalize_categorical(column: str, value: str) -> str | None:
    if column not in KNOWN_VALUES:
        return str(value)

    known = KNOWN_VALUES[column]
    if value in known:
        return value

    value_lower = str(value).lower().strip()
    aliases = STATUS_ALIASES if column == "status" else PRACTICE_ALIASES if column == "practice" else {}

    if value_lower in aliases:
        return aliases[value_lower]

    for alias, canonical in aliases.items():
        if alias in value_lower or value_lower in alias:
            return canonical

    for candidate in known:
        c_lower = candidate.lower()
        if value_lower in c_lower or c_lower in value_lower:
            return candidate

    return None


def _load_db_context() -> dict:
    try:
        from .db import get_connection
        ctx = {}
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT country FROM opportunities ORDER BY country")
                ctx["countries"] = [r["country"] for r in cur.fetchall()]
        return ctx
    except Exception:
        return {"countries": []}


def parse_user_query(query: str) -> dict:
    ruled = try_rule_based_parse(query)
    if ruled and ruled.get("metric") and not ruled.get("is_conversation"):
        return refine_intent(query, ruled)

    db_ctx = _load_db_context()
    examples = """
EXEMPLES (copie la logique, pas les valeurs inventées) :

User: "budget par pays pour Risk Advisory"
→ {"goal":"Budget par pays — Risk Advisory","metric":"budget","dimension":"country","filters":{"practice":"Risk Advisory"},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "combien d'opportunités gagnées ?"
→ {"goal":"Nombre d'offres gagnées","metric":"nb_opportunities","dimension":"","filters":{"status":"Offre gagnée"},"range_filters":{},"chart_type":"kpi_card","aggregation":"count","use_raw_table":false,"is_conversation":false}

User: "liste des opportunités qui expirent dans moins de 7 jours"
→ {"goal":"Opportunités urgentes","metric":"budget","dimension":"","filters":{},"range_filters":{"days_remaining":{"op":"<","value":7}},"chart_type":"table","aggregation":"sum","use_raw_table":true,"is_conversation":false}

User: "répartition par practice"
→ {"goal":"Répartition par practice","metric":"nb_opportunities","dimension":"practice","filters":{},"range_filters":{},"chart_type":"pie","aggregation":"sum","use_raw_table":false,"is_conversation":false}

User: "bonjour"
→ {"goal":"","metric":"","dimension":"","filters":{},"range_filters":{},"chart_type":"bar","aggregation":"sum","use_raw_table":false,"is_conversation":true}
"""

    system_prompt = f"""Tu es un parseur d'intentions pour un dashboard commercial DevoTeam.
Tu NE réponds PAS à l'utilisateur. Tu extrais UNIQUEMENT les paramètres SQL/chart à partir de sa question.

RÈGLES ABSOLUES :
- Ne jamais inventer de chiffres, de résultats ou d'analyses.
- Ne produire AUCUN texte explicatif pour l'utilisateur (pas de message, pas de commentaire).
- Si la question demande des données → remplir metric + chart_type. is_conversation = false.
- Si c'est une salutation ou hors sujet (pas de demande de données) → metric = "" et is_conversation = true.
- Toujours mapper les termes vague vers les valeurs EXACTES listées ci-dessous.

COLONNES metric autorisées : {VALID_METRICS}
  budget = CA, montant, chiffre ; nb_opportunities = nombre, volume, combien ;
  financial_offer = offre ; weighted_amount = pondéré ; win_probability = proba, chance

COLONNES dimension autorisées : {VALID_DIMENSIONS} ("" si total global ou KPI)

chart_type : {VALID_CHART_TYPES}
  bar = comparaison ; pie = répartition ; line = évolution ; kpi_card = un seul chiffre ; table = liste détaillée

aggregation : {VALID_AGGREGATIONS}

VALEURS EXACTES EN BASE (utilise-les telles quelles dans filters) :
{json.dumps(KNOWN_VALUES, ensure_ascii=False)}

MAPPING FR → filters :
- "gagné/gagnées/remporté" → status "Offre gagnée"
- "perdu/perdue" → status "Offre perdue"
- "signé" → status "Offre signée"
- "Data" → practice "Data Management"
- "Risk" → practice "Risk Advisory"
- "Digital" → practice "Digital Transformation"

range_filters (colonnes numériques : days_remaining, deadline_year, budget, win_probability) :
Format : {{"colonne": {{"op": "<"|">"|"<="|">="|"=", "value": nombre}}}}

use_raw_table = true si l'utilisateur veut une LISTE d'opportunités (noms, détails), pas un graphique agrégé.

limit = nombre entier si l'utilisateur demande un "top N" ou "N premiers" (sinon 0).

PAYS DISPONIBLES EN BASE : {db_ctx.get("countries", [])}

{examples}

Réponds en JSON strict avec exactement ces clés :
goal, metric, dimension, filters, range_filters, chart_type, aggregation, use_raw_table, is_conversation, limit
"""

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    response_text = chat_completion.choices[0].message.content
    print(f"--- DEBUG GROQ RAW ---\n{response_text}\n----------------------")

    try:
        intent_data = json.loads(response_text)
        intent = DashboardIntent(**intent_data)

        if intent.is_conversation or not intent.metric:
            return refine_intent(query, intent.model_dump())

        if intent.metric not in VALID_METRICS:
            m = intent.metric.lower()
            if "budget" in m or "ca" in m or "montant" in m or "chiffre" in m:
                intent.metric = "budget"
            elif "nb" in m or "count" in m or "nombre" in m or "volume" in m:
                intent.metric = "nb_opportunities"
            elif "offer" in m or "offre" in m:
                intent.metric = "financial_offer"
            elif "pond" in m or "weight" in m:
                intent.metric = "weighted_amount"
            elif "prob" in m or "chance" in m:
                intent.metric = "win_probability"
            else:
                intent.metric = "budget"

        if intent.dimension and intent.dimension not in VALID_DIMENSIONS:
            d = intent.dimension.lower()
            if "countr" in d or "pays" in d:
                intent.dimension = "country"
            elif "mois" in d or "month" in d:
                intent.dimension = "deadline_month"
            elif "ann" in d or "year" in d:
                intent.dimension = "deadline_year"
            elif "prac" in d:
                intent.dimension = "practice"
            elif "stat" in d:
                intent.dimension = "status"
            elif "financ" in d or "source" in d:
                intent.dimension = "funding_source"
            elif "type" in d:
                intent.dimension = "opp_type"
            else:
                intent.dimension = ""

        if intent.chart_type not in VALID_CHART_TYPES:
            intent.chart_type = "kpi_card" if not intent.dimension else "bar"

        valid_filters = {}
        for k, v in intent.filters.items():
            if k in KNOWN_VALUES:
                normalized = _normalize_categorical(k, v)
                if normalized:
                    valid_filters[k] = normalized
            else:
                valid_filters[k] = str(v)
        intent.filters = valid_filters
        intent.limit = int(intent.limit or 0)

        return refine_intent(query, intent.model_dump())

    except ValidationError as e:
        print(f"Validation Error: {e}")
        raise ValueError(
            "Je n'ai pas pu interpréter votre demande. "
            "Essayez par exemple : « budget par pays pour Risk Advisory » ou « offres gagnées par mois »."
        )
    except json.JSONDecodeError:
        raise ValueError("Erreur de parsing de la demande. Veuillez reformuler votre question.")
