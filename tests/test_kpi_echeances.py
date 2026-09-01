"""Les indicateurs de la section « Échéances à venir ».

La section n'affichait qu'un tableau. Un tableau répond à « lesquelles ? », mais pas
aux questions qu'on se pose AVANT de le parcourir : combien, ce que ça pèse, dans
combien de jours tombe la plus proche, et si sept jours est une semaine calme ou le
début d'une vague.

Ces tests tiennent surtout la propriété qui relie les KPI au tableau : ils comptent
la MÊME population. Un indicateur qui annoncerait 6 au-dessus d'un tableau de 4
lignes serait pire que pas d'indicateur du tout — l'utilisateur n'aurait aucun moyen
de savoir lequel des deux croire, et c'est précisément le défaut que ce projet
poursuit depuis le début.
"""
import duckdb
import pytest

from tests.test_accueil_dashboard import (
    COLONNES, _remplir, _sans_jinja, _widget, _widget_commencant_par,
)

KPI_7_JOURS = "Échéances à 7 jours"
KPI_BUDGET = "Budget en jeu (DT)"
KPI_PLUS_PROCHE = "La plus proche (jours)"
KPI_30_JOURS = "Échéances à 30 jours"


@pytest.fixture
def base():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE opportunities (%s)" % ", ".join(
        "%s %s" % (nom, type_) for nom, type_ in COLONNES))
    return con


def _opp(**champs):
    base_ = {
        "id": 1, "country": "France", "buyer": "Client", "description": "Mission",
        "practice": "Risk Advisory", "status": "Offre remise", "budget": 100000.0,
        "financial_offer": 90000.0, "win_probability": 0.5, "weighted_amount": 50000.0,
        "deadline": "2026-09-05", "deadline_month": "2026-09", "deadline_year": 2026,
        "days_remaining": 5,
    }
    base_.update(champs)
    return base_


def _valeur(con, nom):
    return con.execute(_sans_jinja(_widget(nom)["sql"])).fetchone()[0]


def _lignes_du_tableau(con):
    sql = _sans_jinja(_widget_commencant_par("Opportunités urgentes")["sql"])
    return con.execute(sql).fetchall()


# ---------------------------------------------------------------------------
# La cohérence avec le tableau
# ---------------------------------------------------------------------------

def test_le_compte_est_celui_du_tableau_qu_il_surmonte(base):
    """Le KPI et le tableau doivent décrire la même population.

    C'est la seule garantie qui compte vraiment ici : deux nombres différents pour la
    même chose, l'un au-dessus de l'autre, ne laisseraient aucun moyen de trancher.
    """
    _remplir(base, [
        _opp(days_remaining=1),
        _opp(days_remaining=3),
        _opp(days_remaining=7),
        # Hors fenêtre : au-delà des sept jours.
        _opp(days_remaining=8),
        # Échéance dépassée : elle n'est plus « à venir ».
        _opp(days_remaining=-2),
        # Close : plus rien à traiter, même si la date est proche.
        _opp(days_remaining=2, status="Offre gagnée"),
    ])

    assert _valeur(base, KPI_7_JOURS) == 3
    assert len(_lignes_du_tableau(base)) == 3


def test_le_budget_est_celui_des_memes_lignes(base):
    _remplir(base, [
        _opp(days_remaining=1, budget=200000.0),
        _opp(days_remaining=6, budget=300000.0),
        _opp(days_remaining=20, budget=999000.0),          # hors fenêtre
        _opp(days_remaining=2, budget=888000.0, status="Offre perdue"),  # close
    ])

    assert _valeur(base, KPI_BUDGET) == 500000.0


def test_la_plus_proche_est_le_minimum_des_jours_restants(base):
    _remplir(base, [
        _opp(days_remaining=6),
        _opp(days_remaining=2),
        _opp(days_remaining=4),
    ])

    assert _valeur(base, KPI_PLUS_PROCHE) == 2


def test_une_echeance_du_jour_meme_compte(base):
    """Zéro jour restant, c'est aujourd'hui — la plus urgente de toutes.

    Une borne écrite « > 0 » l'aurait écartée précisément le jour où elle compte.
    """
    _remplir(base, [_opp(days_remaining=0)])

    assert _valeur(base, KPI_7_JOURS) == 1
    assert _valeur(base, KPI_PLUS_PROCHE) == 0


# ---------------------------------------------------------------------------
# L'horizon à trente jours
# ---------------------------------------------------------------------------

def test_l_horizon_a_trente_jours_englobe_celui_de_la_semaine(base):
    """Il est là pour DONNER SA MESURE au chiffre de la semaine.

    « 4 » ne dit pas s'il faut s'inquiéter tant qu'on ignore si le mois en compte 5
    ou 40. L'un doit donc toujours contenir l'autre.
    """
    _remplir(base, [
        _opp(days_remaining=2),
        _opp(days_remaining=5),
        _opp(days_remaining=15),
        _opp(days_remaining=29),
        _opp(days_remaining=45),   # au-delà des deux fenêtres
    ])

    assert _valeur(base, KPI_7_JOURS) == 2
    assert _valeur(base, KPI_30_JOURS) == 4


def test_les_statuts_clos_sortent_des_deux_horizons(base):
    """Une seule définition de « encore ouverte », partagée avec l'email de rappel.

    Sans cela, le tableau de bord et le mail quotidien annonceraient deux nombres
    pour la même question.
    """
    from backend.alerts import EXCLUDED_STATUSES

    _remplir(base, [_opp(days_remaining=3, status=s) for s in EXCLUDED_STATUSES])

    assert _valeur(base, KPI_7_JOURS) == 0
    assert _valeur(base, KPI_30_JOURS) == 0


def test_la_liste_des_statuts_clos_vient_bien_du_code(base):
    # Recopiée à la main, elle divergerait au premier statut ajouté au Sheet.
    from backend.alerts import EXCLUDED_STATUSES

    sql = _widget(KPI_7_JOURS)["sql"]
    for statut in EXCLUDED_STATUSES:
        assert "'%s'" % statut in sql, statut


# ---------------------------------------------------------------------------
# Les filtres de la page
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", [KPI_7_JOURS, KPI_BUDGET, KPI_PLUS_PROCHE, KPI_30_JOURS])
def test_les_kpi_ignorent_la_periode_mais_suivent_la_practice(nom):
    """Même règle que le tableau qu'ils surmontent, et pour la même raison.

    Leur fenêtre se définit toute seule ; une date de fin posée à aujourd'hui les
    viderait entièrement, ce qui est le contraire de leur propos. Le filtre de
    practice, lui, doit continuer de s'appliquer — sinon le KPI et le tableau
    répondraient à deux questions différentes dès qu'on filtre la page.
    """
    sql = _widget(nom)["sql"]

    assert "filters.Date_de_debut" not in sql
    assert "filters.Date_de_fin" not in sql
    assert "filters.practice" in sql


@pytest.mark.parametrize("nom", [KPI_7_JOURS, KPI_BUDGET, KPI_PLUS_PROCHE, KPI_30_JOURS])
def test_chaque_kpi_s_explique(nom):
    # Même exigence que partout ailleurs sur la page : un indicateur sans phrase
    # laisse deviner ce qu'il compte.
    widget = _widget(nom)

    assert widget.get("description"), nom
    assert len(widget["description"]) < 100, widget["description"]


def test_les_quatre_kpi_tiennent_sur_une_ligne():
    # La grille fait douze colonnes : quatre indicateurs à trois colonnes la
    # remplissent exactement. Un cinquième repousserait le tableau d'une ligne.
    largeurs = [_widget(n)["col"]
                for n in (KPI_7_JOURS, KPI_BUDGET, KPI_PLUS_PROCHE, KPI_30_JOURS)]

    assert sum(largeurs) == 12, largeurs
