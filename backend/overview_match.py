# -*- coding: utf-8 -*-
"""Quand la vue d'ensemble répond déjà à la question posée.

Chaque question écrivait un tableau de bord neuf, même lorsque la page d'accueil
portait exactement la réponse. « Combien d'offres remises pour Risk Advisory ? »
générait cinq widgets alors que la vue d'ensemble affiche ce chiffre en haut à
gauche et sait se filtrer par practice — il suffisait de la montrer.

Trois bénéfices, et le troisième est le plus important :
  - l'utilisateur reste sur une page qu'il connaît, au lieu d'en découvrir une par
    question ;
  - rien n'est écrit sur le disque, donc rien à purger ni à faire relire à DAC ;
  - les chiffres viennent des widgets DÉJÀ RELUS en revue, pas d'une composition
    reconstruite à la volée. Une réponse dont on sait qu'elle est juste vaut mieux
    qu'une réponse qu'il faut revérifier.

La correspondance est volontairement ÉTROITE. Un doute doit conduire à composer un
tableau de bord dédié : afficher la vue d'ensemble pour une question qu'elle ne
traite pas serait une réponse à côté — exactement le défaut que ce projet combat.
"""
from .business_rules import SUBMITTED_STATUSES

# Le nom EXACT du champ `name:` de dac/dashboards/accueil.yml — DAC route par nom.
OVERVIEW_NAME = "Vue d'ensemble commerciale"

# Les filtres que la page sait porter. Toute autre restriction demandée par la
# question la disqualifie : la vue d'ensemble ne saurait pas l'appliquer, et
# l'afficher quand même donnerait des chiffres plus larges que ce qui est demandé.
# `status` y figure à titre CONDITIONNEL : la page ne porte pas de filtre de statut,
# mais son sujet principal EST un statut — les offres remises. Un filtre qui désigne
# exactement cet ensemble est donc déjà appliqué par la page ; tout autre statut la
# disqualifie. La valeur est vérifiée plus bas, la clé seule ne suffit pas.
_FILTRES_PORTES = {"practice", "deadline_year", "deadline_month", "status"}

# Ce que la page répond réellement, en (métrique, axe). L'axe vide signifie « un
# chiffre unique ». Cette liste est tenue à la main plutôt que déduite du YAML :
# un widget peut exister sans que la page réponde à la question pour autant, et se
# tromper ici coûte une réponse fausse.
_REPONSES = {
    # Q1 et Q3 : les offres remises et leur issue.
    ("nb_opportunities", ""),
    ("nb_opportunities", "practice"),
    ("nb_opportunities", "status"),
    ("budget", ""),
    ("budget", "practice"),
    ("budget", "country"),
    ("weighted_amount", ""),
    ("financial_offer", ""),
}


def _sans_periode(filters: dict) -> dict:
    return {k: v for k, v in (filters or {}).items() if k not in ("deadline_year", "deadline_month")}


def overview_answers(intent: dict) -> dict | None:
    """Les filtres à passer à la vue d'ensemble si elle répond, sinon None.

    Le retour est un dictionnaire prêt pour la chaîne de requête de DAC : la page
    lit ses filtres depuis l'URL, donc l'afficher filtrée ne demande aucune écriture.
    """
    if not intent or intent.get("is_conversation") or not intent.get("metric"):
        return None

    # Une demande de LISTE, de corrélation ou d'ajout veut autre chose que la page
    # d'accueil : elle n'y figure pas.
    if intent.get("use_raw_table") or intent.get("append"):
        return None
    if intent.get("chart_type") in ("scatter", "heatmap", "table"):
        return None

    # Un périmètre que la page ne sait pas reproduire : bornes chiffrées, exclusions,
    # comptage distinct, affaires chaudes filtrées autrement, moyenne.
    if intent.get("range_filters") or intent.get("exclude_filters"):
        return None
    if intent.get("count_distinct") or intent.get("hot_deals"):
        return None
    if intent.get("aggregation") == "avg" or intent.get("limit"):
        return None
    if intent.get("exclude_statuses"):
        return None

    filtres = intent.get("filters") or {}
    if any(cle not in _FILTRES_PORTES for cle in filtres):
        return None

    # Un filtre de statut n'est pas porté par la page — SAUF s'il désigne exactement
    # les offres remises, qui sont son sujet principal.
    statut = filtres.get("status")
    if statut is not None and sorted(statut if isinstance(statut, list) else [statut]) != sorted(SUBMITTED_STATUSES):
        return None

    if (intent.get("metric"), intent.get("dimension") or "") not in _REPONSES:
        return None

    # Une valeur de practice multiple n'est pas exprimable : le filtre de la page est
    # une liste déroulante à choix unique.
    practice = _sans_periode(filtres).get("practice")
    if isinstance(practice, (list, tuple)):
        return None

    return {"practice": practice} if practice else {}
