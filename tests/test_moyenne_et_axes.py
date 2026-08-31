"""Deux corrections que seule une confrontation aux vrais chiffres révèle.

1. « budget moyen par pays » renvoyait la SOMME sous une étiquette de moyenne :
   34 530 000 DT affichés pour la Tunisie là où la moyenne vaut 466 622 DT. Le
   champ `aggregation` existait dans l'intention mais aucun des deux moteurs ne le
   lisait — chacun déduisait l'agrégation de la seule métrique.

2. `buyer` et `partner` étaient absents de la whitelist alors que les colonnes
   existent. « budget par client » repartait donc sans dimension, et le total du
   portefeuille sortait comme réponse.

Les deux moteurs — pandas pour le chat, SQL pour les widgets — sont vérifiés
ensemble : c'est leur divergence qui ferait réapparaître deux chiffres pour une
même question.
"""
import pandas as pd
import pytest

from backend.db_layer import _agregation, build_and_execute_query
from backend.intent_refiner import refine_intent
from backend.labels import DIMENSION_LABELS, metric_label
from backend.schema_and_whitelist import VALID_DIMENSIONS, VALID_FILTERS
from backend.sql_builder import build_sql


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "country", "filters": {},
        "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


# --- La moyenne est lue, calculée et nommée -------------------------------

@pytest.mark.parametrize("question", [
    "budget moyen par pays",
    "quelle est la moyenne du budget par pays",
    "budget par pays en moyenne",
])
def test_le_mot_moyenne_bascule_l_agregation(question):
    assert refine_intent(question, _intention())["aggregation"] == "avg"


def test_sans_le_mot_l_agregation_reste_une_somme():
    assert refine_intent("budget par pays", _intention())["aggregation"] == "sum"


def test_les_deux_moteurs_appliquent_la_meme_moyenne():
    intention = _intention(aggregation="avg")
    # Moteur SQL (widgets du tableau de bord).
    assert "AVG(budget)" in build_sql(intention)
    # Moteur pandas (réponse du chat).
    assert _agregation("budget", intention) == ("budget", "mean")


def test_la_moyenne_ne_deborde_pas_sur_les_comptages():
    # « nombre moyen d'opportunités » n'a pas de sens sans préciser moyen sur quoi ;
    # et la probabilité de gain est DÉJÀ une moyenne.
    assert _agregation("nb_opportunities", {"aggregation": "avg"})[1] == "count"
    assert _agregation("win_probability", {"aggregation": "avg"})[1] == "mean"


def test_le_libelle_distingue_la_moyenne_de_la_somme():
    assert metric_label("budget", "avg") == "budget moyen"
    assert metric_label("budget", "sum") == "budget"
    # Accord en genre : « offre financière » est féminine.
    assert metric_label("financial_offer", "avg") == "offre financière moyenne"
    # Un comptage ne prend pas la marque : « nombre d'opportunités moyen » serait faux.
    assert metric_label("nb_opportunities", "avg") == "nombre d'opportunités"


def test_la_moyenne_calculee_sur_de_vraies_donnees():
    # Le cœur du défaut : c'est en comparant au chiffre réel qu'il s'est vu.
    resultat = build_and_execute_query(_intention(aggregation="avg"))
    if not resultat:
        pytest.skip("Données indisponibles (le Sheet n'est pas joignable).")
    par_pays = {r["country"]: r["budget"] for r in resultat}
    somme = build_and_execute_query(_intention(aggregation="sum"))
    par_pays_somme = {r["country"]: r["budget"] for r in somme}
    for pays, moyenne in par_pays.items():
        assert moyenne <= par_pays_somme[pays] + 1e-6, (
            f"{pays} : la « moyenne » ({moyenne}) dépasse la somme "
            f"({par_pays_somme[pays]}) — c'est la somme qui a été renvoyée."
        )
    assert any(par_pays[p] < par_pays_somme[p] for p in par_pays), (
        "aucun pays ne distingue moyenne et somme : l'agrégation n'a pas été appliquée"
    )


# --- Client et partenaire sont des axes à part entière --------------------

@pytest.mark.parametrize("axe", ["buyer", "partner"])
def test_les_colonnes_reelles_sont_interrogeables(axe):
    assert axe in VALID_DIMENSIONS, f"{axe} existe dans les données mais pas au menu"
    assert axe in DIMENSION_LABELS, f"{axe} n'a pas de libellé français"


def test_le_client_est_aussi_filtrable():
    # « budget pour le client ASIN » répondait 103 900 001 DT — le portefeuille
    # entier — faute de pouvoir filtrer sur cette colonne.
    assert "buyer" in VALID_FILTERS


@pytest.mark.parametrize("question,attendu", [
    ("budget par client", "buyer"),
    ("budget par acheteur", "buyer"),
    ("top 5 des clients par budget", "buyer"),
    ("budget par partenaire", "partner"),
])
def test_les_formulations_courantes_trouvent_l_axe(question, attendu):
    assert refine_intent(question, _intention(dimension=""))["dimension"] == attendu


def test_le_sql_groupe_bien_par_client():
    sql = build_sql(_intention(dimension="buyer"))
    assert "buyer" in sql and "GROUP BY" in sql


def test_la_forte_cardinalite_des_clients_reste_lisible():
    # 96 clients : sans regroupement, le graphique serait illisible. La traîne est
    # regroupée dans « Autres » plutôt que supprimée, pour que le total reste juste.
    sql = build_sql(_intention(dimension="buyer"))
    assert "Autres" in sql, "les clients au-delà du plafond disparaîtraient du total"
