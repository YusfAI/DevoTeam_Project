"""La vue d'ensemble répond déjà à beaucoup de questions : autant la montrer.

Chaque question écrivait un tableau de bord neuf, même quand la page d'accueil
portait exactement la réponse. « Budget pour Risk Advisory » composait cinq widgets
alors que la vue d'ensemble affiche ce chiffre et sait se filtrer par practice.

Trois bénéfices, dont le dernier est le plus important : l'utilisateur reste sur une
page qu'il connaît ; rien n'est écrit sur le disque ; et les chiffres viennent de
widgets DÉJÀ RELUS en revue plutôt que d'une composition refaite à la volée.

Le risque symétrique est plus grave que le gain : afficher la vue d'ensemble pour une
question qu'elle ne traite PAS serait une réponse à côté. La reconnaissance est donc
étroite, et ces tests gardent surtout sa frontière.
"""
import pytest

from backend.business_rules import SUBMITTED_STATUSES
from backend.overview_match import OVERVIEW_NAME, overview_answers


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "kpi_card", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


# --- Ce que la vue d'ensemble sait faire ----------------------------------

@pytest.mark.parametrize("intention,attendu", [
    (_intention(), {}),
    (_intention(filters={"practice": "Risk Advisory"}), {"practice": "Risk Advisory"}),
    (_intention(metric="nb_opportunities", dimension="practice"), {}),
    (_intention(dimension="country"), {}),
    (_intention(metric="weighted_amount"), {}),
])
def test_les_questions_deja_traitees_reutilisent_la_page(intention, attendu):
    assert overview_answers(intention) == attendu


def test_le_filtre_de_practice_est_transmis_tel_quel():
    # La page lit ses filtres depuis la chaîne de requête : la transmettre suffit,
    # aucune écriture n'est nécessaire.
    assert overview_answers(_intention(filters={"practice": "Data Management"})) == {
        "practice": "Data Management"}


def test_les_offres_remises_sont_le_sujet_de_la_page():
    intention = _intention(metric="nb_opportunities",
                           filters={"status": list(SUBMITTED_STATUSES)})
    assert overview_answers(intention) == {}


# --- Ce qu'elle ne sait PAS faire : au moindre doute, on compose ----------

@pytest.mark.parametrize("intention,pourquoi", [
    (_intention(dimension="buyer"), "aucun widget par client sur la page"),
    (_intention(hot_deals=True), "les affaires chaudes y sont, mais pas filtrables ainsi"),
    (_intention(aggregation="avg"), "la page montre des totaux, pas des moyennes"),
    (_intention(limit=5), "aucun classement tronqué sur la page"),
    (_intention(use_raw_table=True), "une liste d'opportunités n'y figure pas"),
    (_intention(exclude_filters={"country": ["Tunisie"]}), "exclusion non exprimable"),
    (_intention(range_filters={"budget": {"op": ">", "value": 1000}}), "borne non exprimable"),
    (_intention(count_distinct="buyer"), "cardinalité absente de la page"),
    (_intention(exclude_statuses=["Offre gagnée"]), "exclusion de statut non exprimable"),
    (_intention(filters={"country": "Tunisie"}), "la page ne filtre pas par pays"),
    (_intention(filters={"practice": ["Risk Advisory", "Data Management"]}), "choix unique"),
    (_intention(filters={"status": "Offre gagnée"}), "un statut isolé n'est pas son sujet"),
    (_intention(chart_type="scatter"), "aucune corrélation sur la page"),
    (_intention(chart_type="heatmap"), "aucun croisement sur la page"),
    (_intention(append=True), "« ajoute … » complète le tableau de travail"),
    (_intention(is_conversation=True), "ce n'est pas une question de données"),
    (_intention(metric=""), "aucune métrique résolue"),
])
def test_une_question_qu_elle_ne_traite_pas_compose_un_tableau_dedie(intention, pourquoi):
    assert overview_answers(intention) is None, pourquoi


def test_le_nom_correspond_exactement_a_celui_du_fichier():
    """DAC route ses tableaux de bord par leur nom affiché, pas par leur fichier.

    Un écart d'un caractère afficherait une page vide sans qu'aucune requête échoue.
    """
    import yaml
    from pathlib import Path

    accueil = Path(__file__).resolve().parent.parent / "dac" / "dashboards" / "accueil.yml"
    assert yaml.safe_load(accueil.read_text(encoding="utf-8"))["name"] == OVERVIEW_NAME


def test_le_frontend_connait_le_meme_nom():
    # Le nom vit des deux côtés : backend pour décider, frontend pour construire
    # l'URL de l'iframe. Les laisser diverger ouvrirait une page inexistante.
    from pathlib import Path

    dac_js = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "dac.js")
    assert OVERVIEW_NAME in dac_js.read_text(encoding="utf-8")
