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
    # « Non renseigné » n'est pas une valeur du Sheet : c'est ce que le chargement
    # inscrit quand la cellule est vide ou illisible, plutôt que de perdre la ligne
    # entière (voir data_store.UNKNOWN). Listée ici pour rester filtrable — « montre
    # les opportunités sans practice » est une question légitime.
    "practice": ["Digital Transformation", "Risk Advisory", "Data Management", "Non renseigné"],
    "opp_type": ["AO", "DP", "AMI", "Consultation", "Prospection", "Gré à gré", "Avant-vente",
                 "Non renseigné"],
    # « En attente du plan de charge » figure sur 8 lignes du Sheet et a été confirmé
    # comme un statut légitime : une étape réelle du pipeline, pas une faute de saisie.
    # « Non renseigné » recueille les lignes dont la colonne statut contient en fait un
    # type d'opportunité (AMI, DP) — voir data_store._normalize_status.
    "status": [
        "Lead", "Opportunité détectée", "En cours de qualification", "Complément d'information",
        "En cours de préparation", "Propal shortlistée", "Manif shortlistée", "Manifestation remise",
        "Offre remise", "En attente du plan de charge", "Offre gagnée", "Offre perdue",
        "Offre signée", "Non shortlisté", "Infructueux", "NO GO", "Hors scope", "Non renseigné",
    ],
}
