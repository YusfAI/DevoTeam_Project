"""Libellés FR partagés entre les dashboards DAC et les réponses texte du chat."""

# Unité des montants. Elle ne peut pas accompagner le nombre dans Bruin DAC — le
# schéma refuse `suffix`/`unit`/`prefix` sur une valeur, et son format `currency`
# impose le `$` de son formateur d3. Elle vit donc sur les libellés (nom de KPI,
# titre d'axe, en-tête de colonne), où elle se lit tout aussi bien sans empêcher le
# nombre de rester un nombre.
DEVISE = "DT"

# Métriques exprimées en argent, par opposition à un comptage ou à un pourcentage.
MONETARY_METRICS = {"budget", "financial_offer", "weighted_amount"}


def with_unit(label: str, metric: str) -> str:
    """« Budget » -> « Budget (DT) », mais « Nombre d'opportunités » inchangé."""
    return "%s (%s)" % (label, DEVISE) if metric in MONETARY_METRICS else label

METRIC_LABELS = {
    "budget": "budget",
    "financial_offer": "offre financière",
    "weighted_amount": "montant pondéré",
    "nb_opportunities": "nombre d'opportunités",
    "win_probability": "probabilité de gain moyenne",
}

DIMENSION_LABELS = {
    "country": "pays",
    "practice": "practice",
    "status": "statut",
    "deadline_month": "mois d'échéance",
    "deadline_year": "année d'échéance",
    "funding_source": "source de financement",
    "opp_type": "type d'opportunité",
}

FILTER_LABELS = {
    "country": "pays",
    "practice": "practice",
    "status": "statut",
    "funding_source": "source de financement",
    "opp_type": "type",
    "partner": "partenaire",
    "deadline_month": "mois d'échéance",
    "deadline_year": "année d'échéance",
}
