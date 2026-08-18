"""Pont entre le DataFrame en mémoire (data_store.py) et le fichier DuckDB que
Bruin/DAC interrogent en SQL.

L'application garde pandas comme source de vérité pour le chat et les alertes ;
DuckDB n'est qu'une PROJECTION en lecture seule de ce même DataFrame, réécrite à
chaque rafraîchissement, parce que DAC ne sait interroger que des connexions SQL
(voir dac/.bruin.yml). Aucun code applicatif ne lit jamais depuis DuckDB.
"""
import logging
import time
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

# dac/data/devoteam.db — chemin référencé par dac/.bruin.yml (connexion duckdb).
DUCKDB_PATH = Path(__file__).resolve().parent.parent / "dac" / "data" / "devoteam.db"

TABLE_NAME = "opportunities"

# DuckDB autorise SOIT plusieurs lecteurs SOIT un seul écrivain sur un fichier :
# si un `bruin query` (lecture, lancé par DAC) est en cours pile au moment du
# rafraîchissement, l'ouverture en écriture échoue sur un verrou. Ces requêtes sont
# courtes (~400 ms), donc quelques tentatives espacées suffisent à passer entre deux.
# En cas d'échec complet, on garde simplement l'ancien fichier : les dashboards
# affichent des données d'un cycle plus anciennes, jamais une base corrompue ou vide.
_MAX_ATTEMPTS = 5
_RETRY_DELAY_SECONDS = 1.0


def export_dataframe(df) -> bool:
    """Réécrit la table opportunities dans le fichier DuckDB. Renvoie True si
    l'export a réussi, False si le verrou n'a jamais pu être obtenu (non bloquant
    pour l'application : seuls les dashboards DAC en dépendent)."""
    if df is None:
        return False

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(_MAX_ATTEMPTS):
        try:
            con = duckdb.connect(str(DUCKDB_PATH))
            try:
                # CREATE OR REPLACE plutôt que DELETE+INSERT : atomique du point de
                # vue d'un lecteur, et reprend automatiquement le schéma du DataFrame
                # (pas de définition de colonnes à maintenir en double ici).
                con.execute(f"CREATE OR REPLACE TABLE {TABLE_NAME} AS SELECT * FROM df")
            finally:
                # Fermeture immédiate : garder la connexion ouverte bloquerait les
                # lectures de DAC jusqu'au prochain rafraîchissement.
                con.close()
            logger.info("Export DuckDB : %d ligne(s) écrite(s) dans %s.", len(df), DUCKDB_PATH.name)
            return True
        except duckdb.IOException:
            if attempt == _MAX_ATTEMPTS - 1:
                logger.warning(
                    "Export DuckDB : fichier verrouillé après %d tentatives — les dashboards "
                    "DAC garderont les données du cycle précédent.", _MAX_ATTEMPTS,
                )
                return False
            time.sleep(_RETRY_DELAY_SECONDS)
        except Exception:
            logger.exception("Export DuckDB : échec inattendu de l'écriture.")
            return False

    return False
