"""Trois familles de contraintes que la question énonçait et que la requête perdait.

Toutes constatées sur les vraies données, toutes du même genre : le mot est lu, puis
jeté, et la réponse porte sur autre chose que ce qui était demandé.

  - EXCLUSION inversée. « budget par pays hors Tunisie » posait `country = Tunisie`
    et répondait 34 530 000 DT — le budget DE la Tunisie — quand la question en
    demande le complément (69 370 001). Idem pour « tout sauf Risk Advisory »
    (50 930 000 rendu au lieu de 52 970 001). La négation n'était traitée que pour le
    statut ; sur les autres colonnes, elle devenait un filtre positif.
  - BORNE chiffrée perdue. « budget entre 100 000 et 500 000 » et « budget supérieur
    à 500 000 » renvoyaient le portefeuille entier. Seul « moins de N jours » était
    reconnu.
  - CARDINALITÉ confondue avec un volume. « combien de clients différents » répondait
    229, le nombre d'opportunités, là où la réponse est 84.
"""
import duckdb
import pytest

from backend.db_layer import build_and_execute_query
from backend.intent_refiner import (
    _bornes_chiffrees, _norm, refine_intent, try_followup_parse,
)
from backend.sql_builder import build_sql

BASE_DUCKDB = "dac/data/devoteam.db"


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "kpi_card", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


def _valeur(intent):
    """La valeur renvoyée par CHAQUE moteur, qui doivent s'accorder."""
    lignes = build_and_execute_query(intent)
    pandas = lignes[0].get(intent["metric"]) if lignes else None
    with duckdb.connect(BASE_DUCKDB, read_only=True) as con:
        sql = con.execute(build_sql(intent)).fetchone()[0]
    return pandas, sql


# --- Exclusions ------------------------------------------------------------

def test_une_valeur_niee_devient_une_exclusion_pas_un_filtre():
    resultat = refine_intent("budget par pays hors Tunisie",
                             _intention(dimension="country", filters={"country": "Tunisie"}))
    assert "country" not in resultat["filters"], "la valeur niée restait un filtre positif"
    assert resultat["exclude_filters"]["country"] == ["Tunisie"]


@pytest.mark.parametrize("question,colonne,valeur", [
    ("tout sauf Risk Advisory", "practice", "Risk Advisory"),
    ("budget hors Data Management", "practice", "Data Management"),
])
def test_les_autres_colonnes_aussi(question, colonne, valeur):
    resultat = refine_intent(question, _intention(filters={colonne: valeur}))
    assert resultat["exclude_filters"][colonne] == [valeur]


def test_sans_negation_la_valeur_reste_un_filtre():
    resultat = refine_intent("budget pour Risk Advisory",
                             _intention(filters={"practice": "Risk Advisory"}))
    assert resultat["filters"]["practice"] == "Risk Advisory"
    assert not resultat.get("exclude_filters")


def test_l_exclusion_donne_bien_le_complement():
    exclu = _intention(exclude_filters={"country": ["Tunisie"]})
    inclus = _intention(filters={"country": "Tunisie"})
    tout = _intention()

    p_exclu, s_exclu = _valeur(exclu)
    p_inclus, s_inclus = _valeur(inclus)
    p_tout, _ = _valeur(tout)

    assert p_exclu == s_exclu and p_inclus == s_inclus, "les deux moteurs divergent"
    assert abs((p_exclu + p_inclus) - p_tout) < 0.01, (
        "exclu + inclus doit reconstituer le total — sinon des lignes se perdent"
    )
    assert p_exclu != p_inclus, "le symptôme d'origine : l'exclusion rendait l'inclusion"


# --- Bornes chiffrées ------------------------------------------------------

@pytest.mark.parametrize("question,attendu", [
    ("budget supérieur à 500000", {"budget": {"op": ">", "value": 500000.0}}),
    ("opportunités de plus de 2 millions", {"budget": {"op": ">", "value": 2000000.0}}),
    ("budget entre 100000 et 500000", {"budget": {"op": "between", "value": [100000.0, 500000.0]}}),
    ("offres à plus de 80% de probabilité", {"win_probability": {"op": ">", "value": 0.8}}),
])
def test_les_bornes_enoncees_sont_appliquees(question, attendu):
    assert _bornes_chiffrees(_norm(question), "budget") == attendu


def test_une_borne_en_jours_reste_a_la_regle_des_echeances():
    # « moins de 30 jours » a sa propre règle, qui borne aussi le passé à 0 : la
    # détection générique ne doit pas la doubler.
    assert _bornes_chiffrees(_norm("budget des offres à moins de 30 jours"), "budget") == {}


def test_une_question_sans_borne_n_en_recoit_aucune():
    assert _bornes_chiffrees(_norm("budget par pays"), "budget") == {}


def test_les_deux_moteurs_appliquent_la_meme_borne():
    intent = _intention(range_filters={"budget": {"op": "between", "value": [100000, 500000]}})
    pandas, sql = _valeur(intent)
    assert pandas == sql


def test_une_borne_sur_montant_pondere_n_est_pas_ignoree_par_le_sql():
    # `weighted_amount` manquait à la liste des colonnes bornables de sql_builder :
    # pandas appliquait la borne, le SQL non, et les deux moteurs répondaient deux
    # chiffres différents à la même question.
    intent = _intention(metric="weighted_amount",
                        range_filters={"weighted_amount": {"op": ">", "value": 100000}})
    assert "weighted_amount >" in build_sql(intent)
    pandas, sql = _valeur(intent)
    assert pandas == sql


# --- Cardinalité -----------------------------------------------------------

@pytest.mark.parametrize("question,axe", [
    ("combien de clients différents", "buyer"),
    ("combien de pays", "country"),
    ("combien de practices", "practice"),
    ("combien de partenaires", "partner"),
])
def test_combien_de_x_compte_les_valeurs_distinctes(question, axe):
    resultat = refine_intent(question, _intention(metric="nb_opportunities"))
    # `count_distinct` porte LA COLONNE comptée ; `dimension` reste libre pour le
    # regroupement. Les confondre faisait dériver la question dès la première suite.
    assert resultat["count_distinct"] == axe
    assert not resultat["dimension"], "sans regroupement demandé, l'axe reste vide"
    # Un seul nombre à afficher : l'arbitre de forme ne doit pas le convertir en
    # répartition.
    assert resultat["chart_type"] == "kpi_card"


def test_un_regroupement_ne_change_pas_ce_qui_est_compte():
    """« combien de clients différents » puis « par practice ».

    Avec un simple drapeau, `count_distinct` comptait la `dimension` : la suite
    écrasait l'axe et l'application répondait 3 — le nombre de practices — là où la
    question portait sur les clients distincts de chacune (23 / 59 / 52).
    """
    depart = refine_intent("combien de clients différents", _intention(metric="nb_opportunities"))
    suite = try_followup_parse("par practice", depart)

    assert suite is not None, "la retouche doit être reconnue"
    assert suite["count_distinct"] == "buyer", "on compte toujours des clients"
    assert suite["dimension"] == "practice", "regroupés par practice"


def test_le_regroupement_donne_bien_les_clients_par_practice():
    intent = _intention(metric="nb_opportunities", count_distinct="buyer",
                        dimension="practice", chart_type="bar")
    lignes = build_and_execute_query(intent)
    par_practice = {r["practice"]: r["nb_opportunities"] for r in lignes}

    with duckdb.connect(BASE_DUCKDB, read_only=True) as con:
        sql = {r[0]: r[1] for r in con.execute(build_sql(intent)).fetchall()}

    assert par_practice == sql, "les deux moteurs divergent"
    # Chaque practice compte moins de clients que le total : sinon c'est qu'on
    # dénombre autre chose.
    assert all(0 < v < 84 for v in par_practice.values()), par_practice


def test_le_libelle_dit_ce_qui_est_compte():
    from backend.response_builder import build_data_response

    intent = _intention(metric="nb_opportunities", count_distinct="buyer",
                        dimension="practice", chart_type="bar")
    message = build_data_response(intent, [{"practice": "Risk Advisory", "nb_opportunities": 52}])
    assert "client" in message.lower()
    assert "nombre d'opportunités" not in message.lower(), (
        "« Nombre d'opportunités par practice : 3 » était faux sur ce qui est compté"
    )


def test_le_comptage_distinct_donne_le_meme_nombre_dans_les_deux_moteurs():
    intent = refine_intent("combien de clients différents", _intention(metric="nb_opportunities"))
    lignes = build_and_execute_query(intent)
    pandas = lignes[0]["nb_opportunities"]
    with duckdb.connect(BASE_DUCKDB, read_only=True) as con:
        sql = con.execute(build_sql(intent)).fetchone()[0]
    assert pandas == sql
    assert pandas < 362, "un comptage distinct ne peut pas égaler le nombre de lignes"


def test_combien_d_opportunites_reste_un_volume():
    # La règle ne doit pas transformer TOUT « combien de » en cardinalité.
    resultat = refine_intent("combien d'opportunités", _intention(metric="nb_opportunities"))
    assert not resultat.get("count_distinct")


def test_l_exclusion_est_annoncee_dans_la_reponse():
    """Le chiffre était juste, la phrase muette sur le périmètre.

    « budget par pays hors Tunisie » affichait 69 370 001 DT sans dire que la Tunisie
    avait été retirée — or c'est exactement ce sur quoi portait la question.
    """
    from backend.response_builder import build_data_response

    intent = _intention(dimension="country", chart_type="bar",
                        exclude_filters={"country": ["Tunisie"]})
    message = build_data_response(intent, [{"country": "France", "budget": 1000}])
    assert "hors" in message and "Tunisie" in message
