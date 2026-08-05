import os
import json
from groq import Groq
from .schema_and_whitelist import VALID_METRICS, VALID_DIMENSIONS, VALID_FILTERS, VALID_CHART_TYPES, VALID_AGGREGATIONS, KNOWN_VALUES
from pydantic import BaseModel, ValidationError
from typing import Literal, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class DashboardIntent(BaseModel):
    message_explicatif: str
    goal: str
    metric: str
    dimension: str
    filters: dict[str, str] = {}          # Filtres égalité : {"status": "Offre gagnee"}
    range_filters: dict[str, dict] = {}   # Filtres plage : {"days_remaining": {"op": "<", "value": 7}}
    chart_type: str
    aggregation: str
    use_raw_table: bool = False            # True si on veut la liste brute (pas des agrégats)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def parse_user_query(query: str) -> dict:
    system_prompt = f"""
Tu es l'assistant IA Data Analyst de DevoTeam. Tu es ultra-intelligent et libre de penser. Tu connais parfaitement la logique métier commerciale.
Le client te pose une question (parfois avec des fautes ou des termes vagues). 

Ta mission est double :
1. Comprendre l'intention profonde du client et générer un `message_explicatif` (une phrase chaleureuse et professionnelle que tu vas lui répondre, lui prouvant que tu as compris sa demande métier et que tu vas lui afficher les données).
2. Fournir les paramètres stricts pour pouvoir extraire les données depuis la base de données MySQL.

**DICTIONNAIRE DE LA BASE DE DONNÉES / LOGIQUE MÉTIER OBLIGATOIRE :**
- Colonnes autorisées pour `metric` : {VALID_METRICS} (budget = CA/Montant ; nb_opportunities = Volume/Nombre ; win_probability = Chance)
- Colonnes autorisées pour `dimension` : {VALID_DIMENSIONS} (Tu peux mettre `""` s'il veut juste un total)
- Types de graphiques `chart_type` : {VALID_CHART_TYPES} (kpi_card pour un nombre simple).
- `aggregation` : {VALID_AGGREGATIONS}

**LES FILTRES EXACTS EXISTANTS EN BDD (À réconcilier si le client s'exprime mal) :**
{json.dumps(KNOWN_VALUES, ensure_ascii=False)}

Même si le prompt est mauvais, déduis la meilleure action. Si un client dit "les gagnés", mappe-le en "Offre gagnée" sur "status". S'il dit "Data", mappe sur "Data Management" sur "practice".

**NOUVEAUTÉ — FILTRES PAR PLAGE (range_filters) :**
Si l'utilisateur demande une plage ("moins de 7 jours", "supérieur à 100k", "avant 2025"), utilise `range_filters`.
Format: {{"column": {{"op": "<"|">"|"<="|">="|"=", "value": valeur_numerique}}}}
Colonnes numériques disponibles : `days_remaining`, `deadline_year`, `budget`, `win_probability`.

**NOUVEAUTÉ — LISTE BRUTE (`use_raw_table`) :**
Si l'utilisateur veut une LISTE d'opportunités individuelles (pas un graphique agrégé), mets `use_raw_table: true` et `chart_type: "table"`.

**FORMAT JSON STRICT À RESPECTER IMPÉRATIVEMENT :**
{{
    "message_explicatif": "Voici les opportunités dont l'échéance approche dans moins de 7 jours :",
    "goal": "Opportunités urgentes",
    "metric": "budget",
    "dimension": "",
    "filters": {{}},
    "range_filters": {{"days_remaining": {{"op": "<", "value": 7}}}},
    "chart_type": "table",
    "aggregation": "sum",
    "use_raw_table": true
}}
"""

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        model="llama-3.3-70b-versatile",
        response_format={"type": "json_object"},
        temperature=0.2
    )
    
    response_text = chat_completion.choices[0].message.content
    print(f"--- DEBUG GROQ RAW ---\n{response_text}\n----------------------")
    
    try:
        intent_data = json.loads(response_text)
        intent = DashboardIntent(**intent_data)
        
        # Soft Corrections de sécurité pour ne pas faire planter la BDD
        # Si le metric est vide, on le laisse vide (mode de conversation pure du LLM)
        if intent.metric and intent.metric not in VALID_METRICS:
            if "budget" in intent.metric.lower() or "ca" in intent.metric.lower(): intent.metric = "budget"
            elif "nb" in intent.metric.lower() or "count" in intent.metric.lower(): intent.metric = "nb_opportunities"
            else: intent.metric = "budget" # Default safe metric instead of crashing
            
        if intent.dimension and intent.dimension not in VALID_DIMENSIONS:
            if "countr" in intent.dimension.lower() or "pays" in intent.dimension.lower(): intent.dimension = "country"
            elif "mois" in intent.dimension.lower() or "month" in intent.dimension.lower(): intent.dimension = "deadline_month"
            elif "prac" in intent.dimension.lower(): intent.dimension = "practice"
            elif "stat" in intent.dimension.lower(): intent.dimension = "status"
            else: intent.dimension = ""
            
        if intent.chart_type not in VALID_CHART_TYPES:
            intent.chart_type = "bar" 
            
        # Filtres strict check (si un filtre est dans KNOWN_VALUES on sécurise, 
        # sinon on le garde tel quel comme 'deadline_year = 2026')
        valid_filters = {}
        for k, v in intent.filters.items():
            if k in KNOWN_VALUES:
                if v in KNOWN_VALUES[k]:
                    valid_filters[k] = v
            else:
                valid_filters[k] = str(v)
        intent.filters = valid_filters 
                
        return intent.model_dump()
        
    except ValidationError as e:
        print(f"Validation Error: {e}")
        raise ValueError(f"L'intelligence artificielle a généré une demande invalide. Essayez de simplifier ou formuler autrement votre phrase.")
    except json.JSONDecodeError:
        raise ValueError("L'IA n'a pas réussi à fournir une réponse structurée.")
