"""Une question mal comprise doit le DIRE, jamais répondre autre chose.

Le contrôle anti-hallucination du projet ne couvrait qu'un seul axe : la VALEUR
d'un filtre. « budget en Atlantide » demandait bien une précision, mais quatre
autres façons de sortir du périmètre passaient sans un mot, et le total du
portefeuille repartait comme réponse :

  - un axe d'analyse inexistant  (« budget par couleur de cheveux »)
  - un axe réel mais absent de la whitelist (« budget par client »)
  - une période hors des données (« budget en 2030 »)
  - une mesure que les données ne portent pas (« taux de réussite »)

Le pire de ces cas restait « budget pour le client ASIN : 103 900 001 DT » — un
chiffre juste, présenté comme la réponse à une question qu'il ne concerne pas.
Ces tests interdisent le retour de chacun.
"""
import pytest

from backend.intent_refiner import refine_intent


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


def _clarification(question, **surcharges):
    resultat = refine_intent(question, _intention(**surcharges))
    return resultat.get("clarification")


# --- Axe d'analyse inexistant ---------------------------------------------

def test_un_axe_qui_n_existe_pas_est_signale():
    message = _clarification("budget par couleur de cheveux")
    assert message, "la question repartait avec le total du portefeuille"
    assert "couleur" in message
    # Le refus ne sert à rien s'il ne dit pas ce qui EST possible.
    assert "pays" in message and "client" in message


def test_l_axe_compris_ne_declenche_rien():
    assert _clarification("budget par pays", dimension="country") is None


@pytest.mark.parametrize("question", [
    "budget par pays, par exemple",          # locution, pas un axe
    "budget par rapport au pipeline",        # locution
    "top 5 des clients par budget",          # « par budget » = critère de tri
])
def test_les_tournures_en_par_qui_ne_designent_pas_un_axe(question):
    assert _clarification(question, dimension="buyer") is None


# --- Période hors des données ---------------------------------------------

def test_une_annee_absente_des_donnees_est_signalee():
    message = _clarification("budget par pays en 2030", dimension="country")
    assert message and "2030" in message
    # Dire ce qui manque ne suffit pas : il faut dire ce qu'on couvre.
    assert "2025" in message or "2026" in message


def test_une_annee_absurde_annoncee_comme_telle_est_signalee():
    # Hors de la plage 1800-2199, donc reconnue par le mot « année » qui la précède.
    assert "3000" in (_clarification("budget pour l'année 3000") or "")


def test_un_montant_a_quatre_chiffres_n_est_pas_pris_pour_une_annee():
    assert _clarification("opportunités au-dessus de 3000 DT") is None


def test_une_seule_annee_couverte_suffit_a_traiter_la_question():
    # « compare 2025 et 2030 » garde tout son sens sur 2025 : on ne bloque que si
    # AUCUNE des années citées n'est dans les données.
    assert _clarification("compare le budget de 2025 et 2030") is None


# --- Mesure indisponible ---------------------------------------------------

def test_le_taux_de_reussite_est_refuse_et_reoriente():
    message = _clarification("taux de réussite par practice", dimension="practice")
    assert message, "la question était silencieusement rabattue sur un comptage"
    # Un refus utile nomme la solution de repli.
    assert "probabilité de gain" in message


def test_la_probabilite_de_gain_reste_une_question_valable():
    assert _clarification("probabilité de gain moyenne par practice",
                          metric="win_probability", dimension="practice") is None
