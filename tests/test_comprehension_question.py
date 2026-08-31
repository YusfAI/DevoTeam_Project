"""Ce que la question dit doit se retrouver dans la réponse — entièrement.

Quatre façons de perdre une partie de la demande, chacune constatée sur les vraies
données :

  - la NÉGATION inversée : « budget des offres non gagnées » renvoyait
    30 080 000 DT, c'est-à-dire exactement le budget des offres GAGNÉES. Une
    réponse fausse et retournée, la pire des deux.
  - la CONJONCTION perdue : « offres gagnées et perdues » ne portait que sur les
    gagnées, sans le dire.
  - un mot AVALÉ par un autre : `\\bcount` (sans borne à droite) reconnaissait
    « country », si bien que « budget by country » répondait 229 — un comptage —
    sous le libellé « Budget ».
  - un COMPLÉMENT ignoré : « budget pour Data Management en Islande » rendait le
    budget de toute la practice, la garde sur les lieux inconnus ne se déclenchant
    que lorsqu'aucun autre filtre n'existait.
"""
import pytest

from backend.intent_refiner import (
    _axe_incompris, _detect_dimension, _detect_metric, _norm,
    _statuts_de_la_question, refine_intent, try_rule_based_parse,
)


def _clarification_axe(question: str):
    """Le message renvoyé par le garde-fou d'axe, ou None s'il laisse passer."""
    normalisee = _norm(question)
    return _axe_incompris(normalisee, _detect_dimension(normalisee) or "")


def _intention(**surcharges):
    base = {
        "goal": "", "metric": "budget", "dimension": "", "filters": {},
        "range_filters": {}, "chart_type": "bar", "aggregation": "sum",
        "use_raw_table": False, "is_conversation": False, "limit": 0,
    }
    base.update(surcharges)
    return base


# --- Négation ---------------------------------------------------------------

@pytest.mark.parametrize("question", [
    "budget des offres non gagnées",
    "budget des offres autres que gagnées",
    "budget hors offres gagnées",
    "budget des offres sauf gagnées",
])
def test_une_negation_exclut_au_lieu_de_filtrer(question):
    retenus, exclus = _statuts_de_la_question(_norm(question))
    assert "Offre gagnée" in exclus, "le statut nié était retenu comme filtre"
    assert "Offre gagnée" not in retenus


def test_sans_negation_le_statut_reste_un_filtre():
    retenus, exclus = _statuts_de_la_question(_norm("budget des offres gagnées"))
    assert retenus == ["Offre gagnée"] and not exclus


def test_la_negation_fait_autorite_sur_le_modele():
    # Le modèle proposait filters.status = « Offre gagnée » pour une question qui
    # demandait précisément l'inverse. Le code tranche.
    resultat = refine_intent("budget des offres non gagnées",
                             _intention(filters={"status": "Offre gagnée"}))
    assert resultat["filters"].get("status") is None
    assert "Offre gagnée" in resultat["exclude_statuses"]


def test_le_parseur_rapide_exclut_aussi():
    resultat = try_rule_based_parse("budget des offres non gagnées") or {}
    assert "Offre gagnée" in (resultat.get("exclude_statuses") or [])
    assert "status" not in (resultat.get("filters") or {})


# --- Conjonction ------------------------------------------------------------

def test_deux_statuts_nommes_sont_tous_les_deux_retenus():
    retenus, _ = _statuts_de_la_question(_norm("offres gagnées et perdues par pays"))
    assert set(retenus) == {"Offre gagnée", "Offre perdue"}


def test_le_parseur_rapide_pose_une_liste_de_statuts():
    filtres = (try_rule_based_parse("offres gagnées et perdues par pays") or {}).get("filters", {})
    assert isinstance(filtres.get("status"), list)
    assert set(filtres["status"]) == {"Offre gagnée", "Offre perdue"}


# --- Un mot ne doit pas en avaler un autre --------------------------------

@pytest.mark.parametrize("question,metrique", [
    ("budget by country", "budget"),      # « count » ne doit pas manger « country »
    ("budget par country", "budget"),
    ("combien d'opportunités", "nb_opportunities"),
    ("camembert du budget", "budget"),    # « ca » ne doit pas manger « camembert »
    ("carte de chaleur du budget", "budget"),
])
def test_la_metrique_n_est_pas_capturee_par_un_mot_voisin(question, metrique):
    assert _detect_metric(_norm(question)) == metrique


@pytest.mark.parametrize("question,accord", [
    ("offres pondérées", "weighted_amount"),   # accord au pluriel toujours reconnu
    ("offre pondérée", "weighted_amount"),
    ("montant pondéré", "weighted_amount"),
])
def test_les_accords_restent_reconnus(question, accord):
    assert _detect_metric(_norm(question)) == accord


@pytest.mark.parametrize("question,axe", [
    ("budget by country", "country"),
    ("budget by practice", "practice"),
    ("budget par pays", "country"),
])
def test_l_axe_est_reconnu_en_francais_comme_en_anglais(question, axe):
    assert _detect_dimension(_norm(question)) == axe


# --- Rien ne doit échapper au garde-fou par un détour de forme -------------

def test_un_axe_ecrit_en_ponctuation_est_quand_meme_signale():
    # « budget par ../../etc/passwd » ne présentait AUCUN jeton au motif, qui ne
    # retenait que des lettres — la question repartait donc avec le total du
    # portefeuille, sans un mot. Le silence était la faille, pas la traversée de
    # chemin (inoffensive : la whitelist ne laisse passer aucune colonne inconnue).
    message = _clarification_axe("budget par ../../etc/passwd")
    assert message and "n'existe pas" in message


def test_le_garde_fou_vaut_aussi_en_anglais():
    assert _clarification_axe("budget by unicorn")


@pytest.mark.parametrize("question", [
    "budget par pays",
    "budget par pays, pour Risk Advisory",   # ponctuation collée à l'axe
    "budget par exemple",                     # locution, pas un axe
])
def test_les_questions_claires_passent_toujours(question):
    assert _clarification_axe(question) is None


@pytest.mark.parametrize("brut", [
    "budget\tpar\rpays",      # copier-coller depuis un tableur
    "budget  par   pays",     # espaces multiples
    "budget par pays\x07",    # caractère de contrôle résiduel
])
def test_un_espacement_inhabituel_ne_fait_pas_perdre_l_axe(brut):
    # Les tables de phrases contiennent des espaces littéraux : une tabulation entre
    # « par » et « pays » suffisait à rendre l'axe invisible, et le total du
    # portefeuille repartait comme réponse.
    assert _detect_dimension(_norm(brut)) == "country"
