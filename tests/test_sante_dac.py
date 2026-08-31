"""Un serveur de dashboards debout n'est pas un serveur de dashboards qui marche.

DAC n'exécute pas le SQL lui-même : il le délègue au binaire `bruin`, qu'il cherche
dans le PATH. Les deux sont installés dans ~/.local/bin, que l'installeur n'ajoute
PAS au PATH système. Un DAC lancé sans cette précaution démarre normalement, répond
HTTP 200 sur sa racine, et fait échouer CHAQUE widget séparément :

    bruin query failed: exec: "bruin": executable file not found in %PATH%

La sonde de santé ne regardait que la racine. Elle annonçait donc « dac ok » devant
un tableau de bord entièrement en erreur — exactement le genre de panne muette que
cet endpoint existe pour lever.

Reproduit en conditions réelles avant d'être corrigé : DAC relancé avec un PATH
amputé répondait bien 200, et `/health` disait « ok ».
"""
import json

import pytest
from fastapi.testclient import TestClient

from backend import main


@pytest.fixture(autouse=True)
def _vider_le_cache_de_sonde():
    """La sonde met son verdict en cache : sans remise à zéro, un test hériterait
    de la réponse du précédent."""
    main._dac_query_probe_cache = (0.0, None)
    yield
    main._dac_query_probe_cache = (0.0, None)


def _sante(monkeypatch, *, repond: bool, erreur_widget: str | None):
    """État renvoyé par /health pour un DAC dans la situation décrite."""
    monkeypatch.setattr(main, "_dac_is_reachable", lambda: repond)

    class _Reponse:
        def read(self):
            widgets = {"r0-w0": {"error": erreur_widget} if erreur_widget else {"rows": [[1]]}}
            return json.dumps({"widgets": widgets}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    # La sonde importe urllib localement : c'est donc la fonction du module qu'il
    # faut remplacer, pas une référence capturée dans backend.main.
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Reponse())

    with TestClient(main.app) as client:
        return client.get("/health").json()["dac"]


def test_un_dac_qui_ne_sait_pas_executer_n_est_pas_ok(monkeypatch):
    erreur = 'bruin query failed: exec: "bruin": executable file not found in %PATH%'
    dac = _sante(monkeypatch, repond=True, erreur_widget=erreur)

    assert dac["repond"] is True, "DAC répond bien : ce n'est pas ça qui manque"
    assert dac["requetes_ok"] is False
    assert dac["ok"] is False, "« ok » annonçait le contraire de ce que voyait l'utilisateur"


def test_l_aide_indique_un_geste_a_la_portee_de_qui_lit(monkeypatch):
    """Le message s'adresse à un commercial, pas à qui a écrit l'application.

    Il disait : « il ne trouve pas « bruin », à qui il délègue l'exécution du SQL […]
    Relancez-le avec ~/.local/bin dans le PATH ». Rien là-dedans n'est actionnable
    par la personne qui a le problème sous les yeux — elle sait en revanche relancer
    le raccourci de son Bureau. Le détail technique reste dans les journaux.
    """
    erreur = 'bruin query failed: exec: "bruin": executable file not found in %PATH%'
    aide = _sante(monkeypatch, repond=True, erreur_widget=erreur)["aide"]

    assert aide
    assert "raccourci" in aide.lower(), "le message doit dire QUOI FAIRE"
    for jargon in ("bruin", "PATH", "SQL", "start_dev", ".bat"):
        assert jargon not in aide, f"« {jargon} » n'a rien à faire dans un message d'interface"


def test_un_dac_sain_reste_ok(monkeypatch):
    dac = _sante(monkeypatch, repond=True, erreur_widget=None)
    assert dac["ok"] is True and dac["requetes_ok"] is True and dac["aide"] is None


def test_un_dac_eteint_garde_son_message_d_origine(monkeypatch):
    dac = _sante(monkeypatch, repond=False, erreur_widget=None)
    assert dac["ok"] is False and dac["repond"] is False
    assert "raccourci" in dac["aide"].lower()
    assert "dac serve" not in dac["aide"], "une commande shell n'aide pas l'utilisateur"
