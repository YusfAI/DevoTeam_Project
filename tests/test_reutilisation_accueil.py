"""Les sections répondent déjà à beaucoup de questions : autant les montrer.

Chaque question écrivait un tableau de bord neuf, même quand la page d'accueil
portait exactement la réponse. « Budget pour Risk Advisory » composait cinq widgets
alors que la vue d'ensemble affiche ce chiffre et sait se filtrer par practice.

Trois bénéfices, dont le dernier est le plus important : l'utilisateur reste sur une
page qu'il connaît ; rien n'est écrit sur le disque ; et les chiffres viennent de
widgets DÉJÀ RELUS en revue plutôt que d'une composition refaite à la volée.

La réponse désigne LA SECTION qui porte le chiffre, pas seulement la page d'accueil :
ouvrir la vue d'ensemble pour une question de pipeline obligerait à chercher où la
réponse se trouve, ce qui annulerait le bénéfice.

Le risque symétrique est plus grave que le gain : afficher la vue d'ensemble pour une
question qu'elle ne traite PAS serait une réponse à côté. La reconnaissance est donc
étroite, et ces tests gardent surtout sa frontière.
"""
import pytest

from backend.business_rules import SUBMITTED_STATUSES
from backend.overview_match import OVERVIEW_NAME, SECTION_SANTE, overview_answers


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "kpi_card", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


# --- Ce que la vue d'ensemble sait faire ----------------------------------

@pytest.mark.parametrize("intention,section,filtres", [
    (_intention(), SECTION_SANTE, {}),
    (_intention(filters={"practice": "Risk Advisory"}), SECTION_SANTE,
     {"practice": "Risk Advisory"}),
    (_intention(metric="weighted_amount"), SECTION_SANTE, {}),
    (_intention(metric="financial_offer"), SECTION_SANTE, {}),
])
def test_les_questions_deja_traitees_reutilisent_la_page(intention, section, filtres):
    assert overview_answers(intention) == {"dashboard": section, "filters": filtres}


def test_le_filtre_de_practice_est_transmis_tel_quel():
    # La page lit ses filtres depuis la chaîne de requête : la transmettre suffit,
    # aucune écriture n'est nécessaire.
    assert overview_answers(_intention(filters={"practice": "Data Management"})) == {
        "dashboard": SECTION_SANTE, "filters": {"practice": "Data Management"}}


def test_le_compte_des_offres_remises_n_est_pas_celui_de_la_page():
    """Piège de périmètre, et non de métrique.

    Le KPI « Offres remises » de l'accueil compte les statuts déposés DONT L'ÉCHÉANCE
    EST PASSÉE — 147 sur les vraies données. Le chat, lui, compte le portefeuille
    actif : 229. Même métrique, même axe, deux populations. Y renvoyer afficherait un
    nombre différent de celui qu'on vient d'annoncer.
    """
    intention = _intention(metric="nb_opportunities",
                           filters={"status": list(SUBMITTED_STATUSES)})
    assert overview_answers(intention) is None


# --- Ce qu'elle ne sait PAS faire : au moindre doute, on compose ----------

@pytest.mark.parametrize("intention,pourquoi", [
    (_intention(dimension="buyer"), "aucun widget par client sur la page"),
    # Les trois entrées ci-dessous ONT ÉTÉ retirées de la table après vérification :
    # chacune désignait une page qui répond à une autre question. Elles restent ici
    # pour que les y remettre par mégarde fasse échouer un test plutôt que d'envoyer
    # l'utilisateur sur une page qui le contredit.
    (_intention(dimension="country"),
     "aucun widget par pays sur la santé du portefeuille"),
    (_intention(metric="nb_opportunities", dimension="practice"),
     "l'accueil compte les offres remises, pas le portefeuille actif"),
    (_intention(metric="nb_opportunities", dimension="status"),
     "l'entonnoir est cumulatif : 12 étapes contre 13 statuts"),
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


def test_chaque_section_citee_existe_vraiment():
    """DAC route ses tableaux de bord par leur nom affiché, pas par leur fichier.

    Un écart d'un caractère afficherait une page vide sans qu'aucune requête échoue.
    Le routage ne vaut donc que si CHAQUE nom qu'il peut renvoyer existe sur disque.
    """
    import yaml
    from pathlib import Path

    from backend.overview_match import _REPONSES

    dossier = Path(__file__).resolve().parent.parent / "dac" / "dashboards"
    existants = {yaml.safe_load(f.read_text(encoding="utf-8"))["name"]
                 for f in dossier.glob("*.yml")}

    for section in set(_REPONSES.values()):
        assert section in existants, section


def test_le_frontend_connait_le_meme_nom():
    # Le nom vit des deux côtés : backend pour décider, frontend pour construire
    # l'URL de l'iframe. Les laisser diverger ouvrirait une page inexistante.
    from pathlib import Path

    dac_js = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "dac.js")
    assert OVERVIEW_NAME in dac_js.read_text(encoding="utf-8")
