"""
Contrat de données pour le générateur de dashboards.
Ce fichier est la SOURCE UNIQUE DE VÉRITÉ pour :
  - les colonnes/tables que le LLM a le droit d'utiliser (whitelist)
  - le mapping entre noms métier (FR, ce que l'utilisateur tape) et noms techniques MySQL

Base de données : MySQL / MariaDB (base "devoteam_dashboard").
Connexion recommandée : PyMySQL ou SQLAlchemy avec l'URL
    mysql+pymysql://dashboard_user:<password>@<host>:3306/devoteam_dashboard

Toute requête SQL générée par la couche LLM doit être validée contre ALLOWED_TABLES
avant exécution. Ne jamais exécuter de SQL brut non validé.
"""

# ---- Tables et vues autorisées (whitelist stricte) ----
ALLOWED_TABLES = {
    "opportunities": {
        "columns": [
            "id", "country", "created_date", "deadline", "deadline_month",
            "deadline_year", "days_remaining", "practice", "description",
            "buyer", "opp_type", "status", "budget", "funding_source",
            "partner", "financial_offer", "win_probability", "weighted_amount",
        ],
        "type": "table",
    },
    "v_by_country": {"columns": ["country", "nb_opportunities", "total_budget", "total_offer", "total_weighted"], "type": "view"},
    "v_by_practice": {"columns": ["practice", "nb_opportunities", "total_budget", "total_offer", "total_weighted"], "type": "view"},
    "v_by_status": {"columns": ["status", "nb_opportunities", "total_budget", "total_offer"], "type": "view"},
    "v_by_month": {"columns": ["deadline_month", "nb_opportunities", "total_budget", "total_offer", "total_weighted"], "type": "view"},
    "v_by_funding_source": {"columns": ["funding_source", "nb_opportunities", "total_budget"], "type": "view"},
    "v_by_country_practice": {"columns": ["country", "practice", "nb_opportunities", "total_budget", "total_weighted"], "type": "view"},
}

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
