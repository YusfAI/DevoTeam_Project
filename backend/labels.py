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


# Seule « offre financière » est féminine parmi les métriques moyennables — d'où
# « offre financière moyenne » là où le budget donne « budget moyen ». Un accord
# faux se remarque immédiatement dans un titre de graphique.
_METRIQUES_FEMININES = {"financial_offer"}


def metric_label(metric: str, aggregation: str = "") -> str:
    """Libellé de la métrique, moyenne comprise.

    Une somme et une moyenne portaient jusqu'ici le MÊME nom : « budget par pays »
    s'affichait à l'identique que le chiffre soit un total ou une moyenne, ce qui
    rendait l'écart impossible à voir. Le libellé dit désormais laquelle des deux
    on regarde — c'est la moitié visible de la correction, l'autre étant le calcul.
    """
    base = METRIC_LABELS.get(metric, metric)
    if aggregation != "avg" or metric not in MONETARY_METRICS:
        return base
    return "%s %s" % (base, "moyenne" if metric in _METRIQUES_FEMININES else "moyen")

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
    "buyer": "client",
    "partner": "partenaire",
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
    "buyer": "client",
    # Bornées par range_filters plutôt que par une égalité, mais elles apparaissent
    # dans les mêmes phrases : sans libellé, « win_probability >= 0.8 » s'affichait
    # tel quel dans le titre d'un tableau de bord.
    "win_probability": "probabilité de gain",
    "days_remaining": "jours restants",
}


# Pluriel des axes, pour les libellés qui dénombrent (« nombre de clients
# distincts »). « client » + « distincts » donnait « client distincts » ; « pays »
# est déjà pluriel et ne prend pas de s.
_AXES_PLURIELS = {"country": "pays", "practice": "practices", "status": "statuts",
                  "buyer": "clients", "partner": "partenaires",
                  "opp_type": "types d'opportunité",
                  "funding_source": "sources de financement"}


def distinct_label(dimension: str) -> str:
    """« buyer » -> « nombre de clients distincts »."""
    pluriel = _AXES_PLURIELS.get(dimension, DIMENSION_LABELS.get(dimension, dimension))
    return "nombre de %s distincts" % pluriel
