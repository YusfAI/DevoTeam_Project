"""scripts/test_fonctionnel.py — le script qui prouve que les chiffres sont justes.

Deux propriétés tenues ici, trouvées en le faisant tourner pour de vrai contre
l'installation Docker :

- une question qui dépasse le délai ne doit PAS faire planter tout le script :
  un TimeoutError nu (requête acceptée, réponse trop lente — un modèle qui démarre
  à froid, par exemple) n'était pas rattrapé, et perdait le résultat de toutes les
  questions déjà passées ainsi que la section des tableaux de bord qui suit ;
- l'adresse de l'application et celle de DAC sont réglables par variable
  d'environnement, condition nécessaire pour exécuter ce script DEPUIS L'INTÉRIEUR
  du conteneur backend (ce que fait INSTALLER.bat) sans avoir besoin d'un Python
  local sur le poste de destination.
"""
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = RACINE / "scripts"

sys.path.insert(0, str(SCRIPTS))
import test_fonctionnel as tf  # noqa: E402


def _nettoyer():
    tf._reussis.clear()
    tf._echoues.clear()
    tf._ignores.clear()


def test_un_timeout_est_rapporte_en_echec_pas_une_exception_non_geree(monkeypatch):
    """Panne réellement rencontrée en testant l'installation Docker de bout en
    bout : une question lente faisait planter tout le script avec une trace
    Python, perdant le résultat des huit questions déjà passées avec succès."""
    _nettoyer()

    def _leve_timeout(question):
        raise TimeoutError("timed out")

    monkeypatch.setattr(tf, "_appeler", _leve_timeout)

    # Ne doit lever AUCUNE exception — c'est précisément ce qui manquait.
    tf.controler("Question lente", "une question quelconque", 42)

    assert tf._reussis == []
    assert len(tf._echoues) == 1
    libelle, detail = tf._echoues[0]
    assert libelle == "Question lente"
    assert "temps" in detail


def test_url_erreur_est_toujours_geree_aussi(monkeypatch):
    """Le cas déjà couvert avant ce correctif ne doit pas régresser."""
    import urllib.error

    _nettoyer()
    monkeypatch.setattr(tf, "_appeler",
                        lambda q: (_ for _ in ()).throw(urllib.error.URLError("refusé")))

    tf.controler("Question", "une question", 1)

    assert len(tf._echoues) == 1


def test_les_adresses_sont_reglables_par_variable_d_environnement(monkeypatch):
    """Sans ça, lancer ce script DEPUIS le conteneur backend (INSTALLER.bat, pour
    ne plus exiger de Python local) ne pourrait jamais joindre DAC : 127.0.0.1
    depuis l'intérieur du conteneur backend désigne CE conteneur, pas dac-light,
    qui vit dans un conteneur séparé et n'est joignable que par son nom de
    service sur le réseau Docker."""
    import importlib

    monkeypatch.setenv("TEST_API_URL", "http://backend-interne:9999")
    monkeypatch.setenv("TEST_DAC_URL", "http://dac-light:8321")
    importlib.reload(tf)
    try:
        assert tf.API == "http://backend-interne:9999"
        assert tf.DAC == "http://dac-light:8321"
    finally:
        monkeypatch.delenv("TEST_API_URL", raising=False)
        monkeypatch.delenv("TEST_DAC_URL", raising=False)
        importlib.reload(tf)  # remet les valeurs par défaut pour les tests suivants


def test_les_adresses_par_defaut_restent_localhost():
    # Sans variable d'environnement — le cas natif, ou l'exécution depuis l'hôte
    # contre les ports Docker publiés — les deux adresses par défaut n'ont pas
    # changé depuis l'ajout des variables d'environnement.
    assert tf.API == "http://127.0.0.1:8000"
    assert tf.DAC == "http://127.0.0.1:8321"
