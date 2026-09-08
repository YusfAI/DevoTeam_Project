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
import pandas as pd

logger = logging.getLogger(__name__)

# dac/data/devoteam.db — chemin référencé par dac/.bruin.yml (connexion duckdb).
DUCKDB_PATH = Path(__file__).resolve().parent.parent / "dac" / "data" / "devoteam.db"

TABLE_NAME = "opportunities"
QUALITY_TABLE = "data_quality"

# DuckDB autorise SOIT plusieurs lecteurs SOIT un seul écrivain sur un fichier :
# si un `bruin query` (lecture, lancé par DAC) est en cours pile au moment du
# rafraîchissement, l'ouverture en écriture échoue sur un verrou. Ces requêtes sont
# courtes (~400 ms), donc quelques tentatives espacées suffisent à passer entre deux.
# En cas d'échec complet, on garde simplement l'ancien fichier : les dashboards
# affichent des données d'un cycle plus anciennes, jamais une base corrompue ou vide.
_MAX_ATTEMPTS = 5
_RETRY_DELAY_SECONDS = 1.0


# Colonnes dont le type doit rester temporel MÊME quand aucune ligne n'a de valeur.
#
# DuckDB devine le type d'une colonne pandas depuis les valeurs qu'elle contient.
# Une colonne entièrement à None (aucune date n'a pu être lue sur le Sheet — un
# format inattendu, par exemple) ne lui laisse rien à examiner, et il retombe sur
# INTEGER. Chaque requête qui compare ensuite la colonne à une date échoue :
#   Binder Error: Cannot compare values of type INTEGER and type DATE
# alors que le DataFrame pandas, lui, n'a jamais eu de problème — `deadline` y vaut
# simplement None, une valeur que pandas comme le reste de l'application savent déjà
# traiter. Le défaut n'existe que dans cette projection, jamais dans la source.
_COLONNES_TOUJOURS_DATE = ("deadline", "created_date")


def _typer_les_dates(df):
    """Copie de `df` où les colonnes de `_COLONNES_TOUJOURS_DATE` sont forcées en
    type date, y compris si toutes leurs valeurs sont None.

    Une copie, jamais une modification en place : `df` est le DataFrame PARTAGÉ que
    `db_layer.py` continue d'interroger pendant l'export — le muter ici serait un
    effet de bord sur la vraie source de vérité pour un besoin qui n'appartient qu'à
    cette projection DuckDB.
    """
    df = df.copy()
    for colonne in _COLONNES_TOUJOURS_DATE:
        if colonne in df.columns:
            df[colonne] = pd.to_datetime(df[colonne]).dt.date
    return df


def export_dataframe(df) -> bool:
    """Réécrit la table opportunities dans le fichier DuckDB. Renvoie True si
    l'export a réussi, False si le verrou n'a jamais pu être obtenu (non bloquant
    pour l'application : seuls les dashboards DAC en dépendent)."""
    if df is None:
        return False

    df = _typer_les_dates(df)

    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(_MAX_ATTEMPTS):
        try:
            con = duckdb.connect(str(DUCKDB_PATH))
            try:
                # CREATE OR REPLACE plutôt que DELETE+INSERT : atomique du point de
                # vue d'un lecteur, et reprend automatiquement le schéma du DataFrame
                # (pas de définition de colonnes à maintenir en double ici).
                con.execute(f"CREATE OR REPLACE TABLE {TABLE_NAME} AS SELECT * FROM df")

                # Le rapport de qualité voyage avec les données : écrit dans la même
                # transaction, il décrit forcément le chargement qu'on vient de faire
                # — impossible d'afficher un rapport décalé d'un cycle.
                from .data_quality import quality_dataframe
                qdf = quality_dataframe()
                con.execute(f"CREATE OR REPLACE TABLE {QUALITY_TABLE} AS SELECT * FROM qdf")
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
