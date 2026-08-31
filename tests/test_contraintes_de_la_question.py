"""Toute contrainte énoncée doit se retrouver dans la requête exécutée.

Trois contraintes disparaissaient en chemin, et la réponse portait alors sur le
portefeuille entier tout en gardant l'apparence d'une réponse à la question :

  - le STATUT au pluriel. La table n'énumérait « signée » qu'au singulier, si bien
    que « budget des offres signées » ET « budget des offres NON signées »
    renvoyaient tous deux 103 900 001 DT — deux réponses fausses, identiques, à deux
    questions opposées. Les vraies valeurs : 13 080 000 et 90 820 001.
  - l'ANNÉE existante. Le garde-fou refusait déjà « en 2030 » (hors données) ; « en
    2026 » était tout aussi ignoré, mais en silence : 103 900 001 DT tous exercices
    confondus au lieu des 74 540 001 de l'exercice demandé.
  - l'URGENCE. « liste des opportunités urgentes » rendait les 229 opportunités
    actives au lieu des 6 qui tombent dans la semaine.
"""
import pytest

from backend.alerts import ALERT_WINDOW_DAYS
from backend.intent_refiner import _norm, _statuts_de_la_question, refine_intent


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


# --- Le statut, dans toutes ses formes ------------------------------------

@pytest.mark.parametrize("question,attendu", [
    ("budget des offres signées", "Offre signée"),
    ("budget des offres signée", "Offre signée"),
    ("budget des offres gagnées", "Offre gagnée"),
    ("budget des offres perdues", "Offre perdue"),
])
def test_un_statut_est_reconnu_quel_que_soit_son_accord(question, attendu):
    retenus, _ = _statuts_de_la_question(_norm(question))
    assert attendu in retenus


@pytest.mark.parametrize("question,attendu", [
    ("budget des offres non signées", "Offre signée"),
    ("budget des offres non gagnées", "Offre gagnée"),
])
def test_la_negation_vaut_aussi_au_pluriel(question, attendu):
    retenus, exclus = _statuts_de_la_question(_norm(question))
    assert attendu in exclus and attendu not in retenus


def test_deux_questions_opposees_ne_donnent_pas_le_meme_perimetre():
    # Le symptôme le plus net du défaut : les deux répondaient 103 900 001 DT, le
    # portefeuille entier. Le MÊME statut doit désormais apparaître des deux côtés,
    # mais dans deux rôles opposés — retenu ici, exclu là.
    retenus_positif, exclus_positif = _statuts_de_la_question(_norm("budget des offres signées"))
    retenus_negatif, exclus_negatif = _statuts_de_la_question(_norm("budget des offres non signées"))

    assert retenus_positif == ["Offre signée"] and not exclus_positif
    assert exclus_negatif == ["Offre signée"] and not retenus_negatif


def test_offres_remises_reste_un_terme_metier_et_non_le_statut():
    """« offres remises » désigne TOUTES celles effectivement déposées.

    Y compris celles gagnées ou perdues depuis — c'est le sens que lui donne
    l'équipe, et il est volontairement distinct du statut « Offre remise », qui ne
    décrit que l'état courant. La règle vit dans `refine_intent`
    (`_SUBMITTED_OFFER_PATTERN`), pas dans la table des statuts : c'est pourquoi
    cette table, elle, ne doit PAS reconnaître la tournure.
    """
    retenus, exclus = _statuts_de_la_question(_norm("combien d'offres remises"))
    assert not retenus and not exclus

    resultat = refine_intent("combien d'offres remises", _intention(metric="nb_opportunities"))
    statuts = resultat["filters"]["status"]
    assert isinstance(statuts, list) and len(statuts) > 1, (
        "le terme métier couvre plusieurs statuts, pas le seul « Offre remise »"
    )


# --- L'année demandée ------------------------------------------------------

def test_une_annee_citee_devient_un_filtre():
    resultat = refine_intent("budget par pays en 2026", _intention(dimension="country"))
    assert resultat["filters"].get("deadline_year") == "2026"


def test_le_filtre_pose_par_le_modele_fait_autorite():
    # Une comparaison (« 2025 et 2026 ») pose une LISTE : ce code ne doit pas
    # l'écraser par une année unique.
    resultat = refine_intent("compare le budget de 2025 et 2026",
                             _intention(filters={"deadline_year": ["2025", "2026"]}))
    assert resultat["filters"]["deadline_year"] == ["2025", "2026"]


def test_une_question_sans_annee_ne_recoit_aucun_filtre_d_annee():
    resultat = refine_intent("budget par pays", _intention(dimension="country"))
    assert "deadline_year" not in resultat["filters"]


# --- L'urgence -------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "liste des opportunités urgentes",
    "quelles offres sont urgentes",
    "les dossiers pressés",
])
def test_urgent_borne_l_echeance(question):
    bornes = refine_intent(question, _intention())["range_filters"]
    assert bornes.get("days_remaining") == {"op": "between", "value": [0, ALERT_WINDOW_DAYS]}, (
        "sans cette borne, la question rendait tout le portefeuille actif"
    )


def test_l_urgence_du_chat_est_celle_des_alertes_email():
    # Une seule définition de l'urgence, quel que soit le canal : le chat et le
    # digest quotidien ne doivent jamais annoncer deux nombres différents.
    bornes = refine_intent("opportunités urgentes", _intention())["range_filters"]
    assert bornes["days_remaining"]["value"][1] == ALERT_WINDOW_DAYS


# --- Une question vide n'est pas une question ------------------------------

@pytest.mark.parametrize("vide", ["", "   ", "\t\n"])
def test_une_question_vide_ne_produit_jamais_d_analyse(vide):
    """Elle repartait vers le modèle, qui inventait une demande plausible.

    Constaté : une chaîne vide a reçu « Top 5 des pratiques par nombre
    d'opportunités » — une analyse que personne n'avait demandée. C'est une
    hallucination comme une autre, et elle s'arrête dans le code, pas dans le prompt.
    """
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        reponse = client.post("/dashboard", json={"query": vide})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert "analyser uniquement" in corps["ai_message"], "une analyse a été inventée"
    # Aucune analyse ne doit accompagner le message : ni tableau de bord, ni intention.
    assert not corps.get("dac_dashboard")
    assert not corps.get("intent")


def test_une_question_absente_est_refusee_par_le_contrat_d_api():
    """`query: str` est requis : l'absence de champ n'est pas une question vide.

    422 est ici la bonne réponse — une requête malformée, pas une demande à laquelle
    répondre par de l'aide.
    """
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        assert client.post("/dashboard", json={"query": None}).status_code == 422
        assert client.post("/dashboard", json={}).status_code == 422
