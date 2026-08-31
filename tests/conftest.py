import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _aucun_effet_sur_la_production(monkeypatch, tmp_path):
    """Aucun test ne doit toucher aux données réelles. Garde-fou global.

    Deux fichiers de tests démarrent l'application avec `TestClient`, ce qui exécute
    son cycle de vie complet : le planificateur y est lancé et programme
    `_refresh_data`, qui appelle le Google Sheet ET réécrit la base DuckDB que DAC
    est en train de servir.

    Constaté : `pytest tests/test_sante_dac.py` suffisait à modifier
    `dac/data/devoteam.db`. Les données s'en trouvaient identiques — le Sheet n'avait
    pas bougé —, donc rien ne cassait et rien ne le signalait. Il suffisait pourtant
    d'un Sheet momentanément incohérent pendant un `pytest` pour corrompre ce que
    l'utilisateur regardait à l'écran, sans qu'aucun test n'échoue.

    Trois effets de bord sont neutralisés ici plutôt que dans chaque test, parce que
    c'est le genre de précaution qu'on oublie d'ajouter au test suivant :
      - l'export DuckDB écrit dans un dossier temporaire ;
      - le rafraîchissement depuis le Sheet ne part pas (pas de réseau, pas de quota
        consommé, et surtout pas de réécriture des colonnes calculées du Sheet) ;
      - le digest d'alerte quotidien n'est pas envoyé.

    Les tests qui veulent EXERCER ces chemins les remplacent eux-mêmes : ce
    remplacement-ci a lieu avant, et `monkeypatch` restaure tout après chaque test.
    """
    from backend import duckdb_export, main

    monkeypatch.setattr(duckdb_export, "DUCKDB_PATH", tmp_path / "devoteam_test.db")
    monkeypatch.setattr(main, "_refresh_data", lambda: {"total_rows": 0, "skipped": 0})
    monkeypatch.setattr(main, "run_daily_alert_check_if_needed", lambda: None)
