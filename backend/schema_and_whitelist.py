"""
Contrat de données pour le générateur de dashboards.
Ce fichier est la SOURCE UNIQUE DE VÉRITÉ pour :
  - les colonnes/dimensions/métriques que le LLM a le droit d'utiliser (whitelist)
  - les valeurs catégorielles réelles connues (pour la résolution fuzzy des filtres)

Source de données : Google Sheet chargé en mémoire via pandas (voir
backend/data_store.py) — plus de base de données ni de schéma SQL à valider ; les
colonnes du DataFrame sont fixes (DATA_COLUMNS dans data_store.py) et
correspondent directement aux dimensions/métriques listées ci-dessous.
"""

# ---- Dimensions et métriques valides pour le JSON intermédiaire ----
# Ce sont les seules valeurs que le LLM peut mettre dans "metric" / "dimension" / "filters"
VALID_METRICS = ["budget", "financial_offer", "weighted_amount", "nb_opportunities", "win_probability"]
VALID_DIMENSIONS = ["country", "practice", "status", "deadline_month", "deadline_year", "funding_source", "opp_type"]
VALID_FILTERS = [
    "country", "practice", "status", "funding_source", "opp_type", "partner",
    "deadline_month", "deadline_year",
]
VALID_CHART_TYPES = ["bar", "line", "pie", "table", "kpi_card", "area", "scatter", "heatmap", "funnel"]
VALID_AGGREGATIONS = ["sum", "avg", "count"]

# ---- Valeurs catégorielles réelles (pour que le LLM/validateur sache ce qui existe) ----
KNOWN_VALUES = {
    "practice": ["Digital Transformation", "Risk Advisory", "Data Management"],
    "opp_type": ["AO", "DP", "AMI", "Consultation", "Prospection", "Gré à gré", "Avant-vente"],
    "status": [
        "Lead", "Opportunité détectée", "En cours de qualification", "Complément d'information",
        "En cours de préparation", "Propal shortlistée", "Manif shortlistée", "Manifestation remise",
        "Offre remise", "Offre gagnée", "Offre perdue", "Offre signée", "Non shortlisté",
        "Infructueux", "NO GO", "Hors scope",
    ],
}
