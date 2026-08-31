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

# Les noms EXACTS des champs `name:` de dac/dashboards/ — DAC route par nom affiché.
# Produits par scripts/generate_accueil.py ; un écart d'un caractère ouvrirait une
# page vide sans qu'aucune requête n'échoue (tests/test_sections_accueil.py le garde).
OVERVIEW_NAME = "Vue d'ensemble commerciale"
SECTION_CHAUDES = "Affaires chaudes"
SECTION_SANTE = "Santé du portefeuille"
SECTION_PIPELINE = "Pipeline commercial"
SECTION_URGENCES = "Échéances à venir"

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
# (métrique, axe) -> LA SECTION qui porte la réponse. L'axe vide signifie « un
# chiffre unique ». Router vers la bonne section plutôt que vers la page d'accueil
# évite à l'utilisateur d'avoir à chercher où la réponse se trouve.
#
# CHAQUE ENTRÉE EST PROUVÉE, jamais supposée : un widget de la section doit rendre
# EXACTEMENT le nombre et les lignes que le chat vient d'annoncer. Ce n'est pas une
# précaution théorique — la première version de cette table était écrite de mémoire,
# et cinq de ses huit entrées désignaient une page qui répond à une AUTRE question :
#
#   « budget par pays »      -> Santé du portefeuille, qui n'a aucun widget par pays
#   « budget par practice »  -> accueil, dont le budget vaut 75,4 M (offres remises)
#   « combien d'offres »     -> accueil, qui en affiche 147 quand le chat en dit 229
#   « offres par practice »  -> même écart de population
#   « offres par statut »    -> l'entonnoir, cumulatif, 12 étapes contre 13 statuts
#
# Le piège est toujours le même : la métrique et l'axe coïncident, le PÉRIMÈTRE non.
# « Offres remises » compte les statuts déposés dont l'échéance est passée ; le chat
# compte le portefeuille actif. Les deux sont justes, ils ne répondent pas à la même
# question — et la page contredisait alors la phrase qu'on venait de lire.
#
# tests/test_reutilisation_fidele.py exécute les deux moteurs et refuse toute entrée
# dont les résultats diffèrent. Pour en ajouter une, ajoutez-la et lancez ce test :
# s'il passe, la section répond vraiment.
_REPONSES = {
    ("budget", ""): SECTION_SANTE,
    ("weighted_amount", ""): SECTION_SANTE,
    ("financial_offer", ""): SECTION_SANTE,
}


def _sans_periode(filters: dict) -> dict:
    return {k: v for k, v in (filters or {}).items() if k not in ("deadline_year", "deadline_month")}


def overview_answers(intent: dict) -> dict | None:
    """La SECTION qui répond et les filtres à lui passer, ou None si aucune ne répond.

    Le retour est `{"dashboard": <nom>, "filters": {...}}`. Les filtres d'un tableau
    de bord DAC vivent dans la chaîne de requête : l'afficher filtré ne demande donc
    aucune écriture.
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

    section = _REPONSES.get((intent.get("metric"), intent.get("dimension") or ""))
    if section is None:
        return None

    # Une valeur de practice multiple n'est pas exprimable : le filtre de la page est
    # une liste déroulante à choix unique.
    practice = _sans_periode(filtres).get("practice")
    if isinstance(practice, (list, tuple)):
        return None

    return {"dashboard": section, "filters": {"practice": practice} if practice else {}}
