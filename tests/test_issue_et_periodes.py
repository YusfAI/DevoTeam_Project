"""L'issue d'une offre remise, et les périodes exprimées en mois nommés.

Trois questions que le métier pose souvent y répondaient mal, chacune pour une
raison différente :

- « Sur le total des offres remises, combien gagnées, perdues, en attente » recevait
  une répartition par statut BRUT — cinq lignes au lieu de trois, les gagnées
  coupées en deux et les perdues noyées dans le reste.
- « Combien d'offres remises » comptait 167 dans le chat et 147 sur le tableau de
  bord : le chat ne regardait que le statut, sans la borne d'échéance que la règle
  métier impose depuis toujours.
- « Entre novembre 2025 et à date actuelle » perdait purement et simplement la
  période : aucune tournure ne la reconnaissait, et la réponse portait sur tout le
  portefeuille sans que rien ne signale la moitié de question ignorée.

Ces tests tiennent les trois corrections, et surtout la propriété qui les relie :
les deux moteurs — pandas pour le chat, SQL pour les widgets — doivent toujours
rendre le MÊME chiffre.
"""
from datetime import date

import duckdb
import pandas as pd
import pytest

from backend import db_layer
from backend.business_rules import (
    ISSUE_DIMENSION, ISSUE_LOST, ISSUE_PENDING, ISSUE_WON, SUBMITTED_STATUSES,
    issue_sql,
)
from backend.intent_refiner import refine_intent
from backend.sql_builder import build_sql
from tests.test_accueil_dashboard import COLONNES, _opportunite

# Une date de référence fixe : « à date actuelle » doit donner le même résultat en
# janvier et en décembre, sinon le test dirait tantôt vrai tantôt faux.
AUJOURD_HUI = date(2026, 8, 31)


def _df(lignes):
    """Les lignes d'essai, avec `deadline` en objet `date`.

    Les vraies données en portent : la laisser en texte ferait passer le test là où
    l'application lèverait un TypeError en comparant la colonne à une borne.
    """
    lignes = [_opportunite(**l) for l in lignes]
    for ligne in lignes:
        if isinstance(ligne["deadline"], str):
            ligne["deadline"] = date.fromisoformat(ligne["deadline"])
    return pd.DataFrame(lignes)


def _valeur(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


def _duckdb_avec(df):
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE opportunities (%s)" % ", ".join(
        "%s %s" % (nom, type_) for nom, type_ in COLONNES))
    for ligne in df.to_dict("records"):
        con.execute("INSERT INTO opportunities VALUES (%s)"
                    % ", ".join("?" for _ in COLONNES),
                    [_valeur(ligne[nom]) for nom, _ in COLONNES])
    return con


def _intention(question, **brut):
    """L'intention telle que le pipeline la produit, dictionnaires NEUFS à chaque
    appel — les partager ferait fuir les filtres d'une question dans la suivante."""
    base = {"metric": "nb_opportunities", "dimension": "", "aggregation": "count",
            "filters": {}, "range_filters": {}, "use_raw_table": False, "limit": 0}
    base.update(brut)
    return refine_intent(question, base, today=AUJOURD_HUI)


def _les_deux_moteurs(question, lignes, **brut):
    """(réponse du chat, réponse du SQL) sur les mêmes lignes."""
    df = _df(lignes)
    intent = _intention(question, **brut)
    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(db_layer, "get_dataframe", lambda: df)
        chat = db_layer.build_and_execute_query(intent)
    finally:
        monkey.undo()
    sql = _duckdb_avec(df).execute(build_sql(intent)).fetchall()
    return intent, chat, sql


# Un jeu couvrant les trois issues ET les deux côtés de la borne d'échéance.
LIGNES = [
    # Remises, échéance passée : elles comptent.
    {"status": "Offre gagnée", "days_remaining": -40,
     "deadline": "2025-11-10", "deadline_month": "2025-11", "deadline_year": 2025},
    {"status": "Offre signée", "days_remaining": -30,
     "deadline": "2025-12-10", "deadline_month": "2025-12", "deadline_year": 2025},
    {"status": "Offre perdue", "days_remaining": -20,
     "deadline": "2026-01-10", "deadline_month": "2026-01"},
    {"status": "Offre remise", "days_remaining": -10,
     "deadline": "2026-02-10", "deadline_month": "2026-02"},
    {"status": "En attente du plan de charge", "days_remaining": 0,
     "deadline": "2026-08-31", "deadline_month": "2026-08"},
    # Remise au statut, mais échéance ENCORE À VENIR : pas encore remise.
    {"status": "Offre remise", "days_remaining": 45,
     "deadline": "2026-10-15", "deadline_month": "2026-10"},
    # Jamais déposée : hors périmètre quoi qu'il arrive.
    {"status": "Lead", "days_remaining": -5,
     "deadline": "2026-03-10", "deadline_month": "2026-03"},
]


# ---------------------------------------------------------------------------
# La borne d'échéance sur « offres remises »
# ---------------------------------------------------------------------------

def test_une_offre_dont_l_echeance_n_est_pas_passee_n_est_pas_encore_remise():
    """La règle du tableau de bord, désormais appliquée aussi par le chat.

    Le statut dit qu'une offre EST partie chez le client ; l'échéance dit QUAND.
    Sans cette borne, le chat annonçait 167 offres remises quand le tableau de bord
    juste à côté en affichait 147 — deux nombres pour un même terme métier selon
    l'endroit où l'on pose la question.
    """
    intent, chat, sql = _les_deux_moteurs("combien d'offres a-t-on remises ?", LIGNES)

    # Cinq lignes remises ET échues ; la sixième attend encore son échéance.
    assert chat == [{"nb_opportunities": 5}]
    assert sql == [(5,)]


def test_la_borne_s_ecrit_sur_deadline_et_non_sur_l_urgence():
    """`days_remaining` porte partout ailleurs la sémantique de l'URGENCE.

    L'employer ici déclenchait deux garde-fous écrits pour elle : la borne « <= 0 »
    devenait « entre 0 et 0 », et les statuts clos étaient exclus — ce qui vidait
    « offres remises » des gagnées et des perdues, précisément celles qu'elle compte.
    """
    intent = _intention("combien d'offres a-t-on remises ?")

    assert intent["range_filters"]["deadline"] == {
        "op": "<=", "value": AUJOURD_HUI.isoformat()}
    assert "days_remaining" not in intent["range_filters"]
    assert not intent.get("exclude_statuses")


def test_une_borne_deja_posee_n_est_jamais_ecrasee():
    """« Offres remises en mars » vise une fenêtre précise.

    La borne par défaut la remplacerait si elle s'appliquait sans condition, et la
    question deviendrait inposable : toute période demandée sur les offres remises
    retomberait sur « depuis toujours jusqu'à aujourd'hui ».
    """
    from backend.intent_refiner import _borner_aux_offres_deja_remises

    intent = {"range_filters": {"deadline": {"op": "between",
                                             "value": ["2026-03-01", "2026-03-31"]}}}
    _borner_aux_offres_deja_remises(intent, AUJOURD_HUI)

    assert intent["range_filters"]["deadline"] == {
        "op": "between", "value": ["2026-03-01", "2026-03-31"]}


# ---------------------------------------------------------------------------
# L'axe « issue »
# ---------------------------------------------------------------------------

def test_l_issue_donne_trois_cas_et_non_les_statuts_bruts():
    intent, chat, sql = _les_deux_moteurs(
        "Sur le total des offres remises, combien d'offres gagnées, perdues, "
        "et en attente ?", LIGNES, dimension="status")

    assert intent["dimension"] == ISSUE_DIMENSION
    par_issue = {r[ISSUE_DIMENSION]: r["nb_opportunities"] for r in chat}
    assert par_issue == {ISSUE_WON: 2, ISSUE_LOST: 1, ISSUE_PENDING: 2}
    # Les deux moteurs, sur les mêmes lignes, rangent chaque offre dans la même case.
    assert sorted(sql) == sorted((k, v) for k, v in par_issue.items())


def test_l_issue_impose_le_perimetre_des_offres_remises():
    """Les trois cas ne veulent rien dire sur une opportunité jamais déposée.

    Un « Lead » n'est ni gagné, ni perdu, ni « en attente » d'une décision du client :
    le compter en attente gonflerait la seule case que le commercial regarde.
    """
    intent = _intention("combien gagnées, perdues et en attente ?")

    assert intent["filters"]["status"] == list(SUBMITTED_STATUSES)
    assert intent["range_filters"]["deadline"]["op"] == "<="


def test_une_question_sur_les_seules_gagnees_reste_un_comptage():
    """Un marqueur ne suffit pas : il en faut deux.

    Sans cette exigence, « combien d'offres gagnées ? » — un simple nombre — serait
    devenu une répartition en trois parts.
    """
    intent = _intention("combien d'offres gagnées ?")

    assert intent["dimension"] != ISSUE_DIMENSION


def test_les_deux_moteurs_partagent_une_seule_definition_de_l_issue():
    # Le SQL des widgets et la colonne pandas viennent tous deux de business_rules.
    # Si quelqu'un réécrivait l'un des deux à la main, ce test le dirait.
    assert "Offre gagnée" in issue_sql() and "Offre signée" in issue_sql()
    assert ISSUE_WON in issue_sql() and ISSUE_LOST in issue_sql()


# ---------------------------------------------------------------------------
# Les périodes en mois nommés
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question,attendu", [
    ("budget entre novembre 2025 et à date actuelle", ["2025-11", "2026-08"]),
    ("budget entre novembre 2025 et aujourd'hui", ["2025-11", "2026-08"]),
    ("budget depuis janvier 2026", ["2026-01", "2026-08"]),
    ("budget entre mars 2026 et juin 2026", ["2026-03", "2026-06"]),
    # L'ordre inverse est une faute de saisie plus probable qu'une période vide.
    ("budget entre juin 2026 et mars 2026", ["2026-03", "2026-06"]),
])
def test_une_periode_en_mois_nommes_est_reconnue(question, attendu):
    intent = _intention(question, metric="budget", aggregation="sum")

    assert intent["range_filters"]["deadline_month"] == {
        "op": "between", "value": attendu}


def test_un_mois_seul_filtre_ce_mois_la():
    intent = _intention("budget en mars 2026", metric="budget", aggregation="sum")

    assert intent["filters"]["deadline_month"] == "2026-03"


def test_l_annee_absente_vaut_l_annee_en_cours():
    intent = _intention("budget entre mars et juin", metric="budget", aggregation="sum")

    assert intent["range_filters"]["deadline_month"] == {
        "op": "between", "value": ["2026-03", "2026-06"]}


def test_la_periode_traverse_les_deux_moteurs():
    """Le défaut d'origine : la période était appliquée nulle part.

    Une borne reconnue mais posée sur une colonne qu'un seul moteur accepte serait
    tout aussi grave — appliquée par pandas, ignorée par le SQL, elle ferait
    diverger le message du chat et les graphiques pour une question identique.
    """
    intent, chat, sql = _les_deux_moteurs(
        "combien d'offres a-t-on remises entre novembre 2025 et à date actuelle ?",
        LIGNES)

    # Les cinq offres remises et échues tombent toutes dans la fenêtre ; celle de
    # 2026-10 en est dehors ET pas encore échue.
    assert chat == [{"nb_opportunities": 5}]
    assert sql == [(5,)]


def test_une_tournure_relative_reste_reconnue():
    # Les mois nommés passent en tête ; ils ne doivent pas masquer l'existant.
    intent = _intention("budget des 3 derniers mois", metric="budget", aggregation="sum")

    assert intent["range_filters"]["deadline_month"] == {
        "op": "between", "value": ["2026-05", "2026-08"]}
