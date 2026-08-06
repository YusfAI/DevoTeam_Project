"""
Connexion centralisée à MySQL (XAMPP en local).
TOUT le code backend doit passer par get_connection() — jamais de connexion
ad-hoc ailleurs dans le projet. Ça garde un seul point de configuration
et évite les fuites de connexions non fermées (source classique de latence).

Utilise un pool de connexions (DBUtils) : indispensable avec MySQL, contrairement
à SQLite, car ouvrir/fermer une connexion réseau à chaque requête HTTP coûte cher.
"""
import os
import threading
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
from dbutils.pooled_db import PooledDB

# Charge réellement le fichier .env situé à la racine du projet.
# Sans cet appel, os.getenv() ne lit QUE les variables d'environnement système
# et ignore silencieusement le fichier .env — piège fréquent.
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),  # XAMPP par défaut : root sans mot de passe
    "database": os.getenv("DB_NAME", "devoteam_dashboard"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
}

# Pool de connexions partagé par toute l'application. Créé paresseusement (au premier
# get_connection(), pas à l'import du module) : importer backend.db_layer/backend.main
# ne doit pas exiger une DB déjà démarrée — utile pour les tests et pour un simple
# `python -m py_compile`/import statique du code.
_pool = None
_pool_lock = threading.Lock()


def _get_pool() -> PooledDB:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = PooledDB(
                    creator=pymysql,
                    maxconnections=10,
                    mincached=2,
                    maxcached=5,
                    blocking=True,
                    **DB_CONFIG,
                )
    return _pool


def get_connection():
    """Retourne une connexion du pool. À utiliser avec 'with' pour fermeture garantie
    (la connexion revient dans le pool au lieu d'être vraiment fermée):

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    """
    return _get_pool().connection()
