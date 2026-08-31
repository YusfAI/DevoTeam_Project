"""Une retouche doit changer ce qu'elle annonce, et rien d'autre.

Trois défauts constatés en enchaînant des questions comme le fait un utilisateur :

  - « en somme » après « budget moyen par pays » n'était pas reconnu comme une
    retouche. La demande repartait vers le modèle, qui la lisait comme une question
    autonome : l'axe « pays » disparaissait et il restait un chiffre unique.
  - « par practice » après « affaires chaudes » annonçait « axe : aucun → practice »
    puis réaffichait exactement la même liste plate — la liste brute héritée
    court-circuitait le regroupement dans les deux moteurs. Le message promettait un
    changement qui n'avait pas lieu.
  - le récit du changement ignorait l'agrégation, les bornes et les exclusions : une
    retouche qui ne touchait qu'eux s'annonçait « rien n'a changé ».

Et un quatrième, sur la carte de chaleur : le second axe était écrit en dur, si bien
qu'un croisement par practice s'annonçait « practice × practice ».
"""
import pytest

from backend.business_rules import heatmap_secondary_dimension
from backend.intent_refiner import try_followup_parse
from backend.response_builder import list_changes


def _precedent(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "country", "filters": {},
        "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


# --- L'agrégation est une retouche ----------------------------------------

@pytest.mark.parametrize("retouche,attendu", [
    ("en somme", "sum"), ("au total", "sum"), ("en moyenne", "avg"), ("moyenne", "avg"),
])
def test_passer_du_total_a_la_moyenne_est_une_retouche(retouche, attendu):
    suite = try_followup_parse(retouche, _precedent(aggregation="avg" if attendu == "sum" else "sum"))
    assert suite is not None, "la retouche n'a pas été reconnue et repart vers le modèle"
    assert suite["aggregation"] == attendu


def test_changer_l_agregation_ne_detruit_pas_l_axe():
    # Le symptôme exact : « en somme » renvoyait un chiffre unique, sans axe.
    suite = try_followup_parse("en somme", _precedent(aggregation="avg"))
    assert suite["dimension"] == "country"
    assert suite["metric"] == "budget"


# --- Un axe demandé annule la liste brute ---------------------------------

def test_demander_un_axe_annule_la_liste_brute_heritee():
    suite = try_followup_parse("par practice",
                               _precedent(dimension="", use_raw_table=True, chart_type="table"))
    assert suite["dimension"] == "practice"
    assert suite["use_raw_table"] is False, "la liste plate aurait court-circuité le regroupement"
    assert suite["chart_type"] != "table"


def test_mais_un_tableau_explicitement_demande_est_respecte():
    suite = try_followup_parse("par practice en tableau",
                               _precedent(dimension="", use_raw_table=False))
    assert suite["dimension"] == "practice"
    assert suite["use_raw_table"] is True


# --- Le récit du changement est complet -----------------------------------

def test_le_changement_d_agregation_est_annonce():
    changements = list_changes(_precedent(aggregation="avg"), _precedent(aggregation="sum"))
    assert changements, "une retouche réelle s'annonçait « rien n'a changé »"
    assert "moyenne" in changements[0] and "total" in changements[0]


def test_les_bornes_ajoutees_sont_annoncees():
    apres = _precedent(range_filters={"win_probability": {"op": ">=", "value": 0.8}})
    assert list_changes(_precedent(), apres)


def test_les_exclusions_ajoutees_sont_annoncees():
    apres = _precedent(exclude_statuses=["Offre gagnée"])
    changements = list_changes(_precedent(), apres)
    assert changements and "Offre gagnée" in changements[0]


def test_une_intention_identique_n_annonce_rien():
    assert list_changes(_precedent(), _precedent()) == []


# --- Le croisement de la carte de chaleur ---------------------------------

def test_la_carte_de_chaleur_croise_toujours_deux_axes_differents():
    for axe in ("country", "practice", "status", "buyer"):
        assert heatmap_secondary_dimension(axe) != axe, (
            f"« {axe} × {axe} » ne croise rien du tout"
        )
