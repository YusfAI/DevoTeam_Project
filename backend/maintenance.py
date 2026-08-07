"""Tâches de maintenance quotidiennes sur les données (indépendantes des alertes)."""
import logging

from .db import get_connection

logger = logging.getLogger(__name__)


def refresh_days_remaining() -> int:
    """Recalcule days_remaining = DATEDIFF(deadline, CURDATE()) pour chaque ligne.

    Recalculer depuis la deadline réelle (plutôt que décrémenter servilement -1)
    est idempotent et se rattrape tout seul si le job a été manqué un jour (ex:
    serveur éteint) — un simple `days_remaining - 1` accumulerait une dérive
    silencieuse à chaque interruption.
    """
    sql = "UPDATE opportunities SET days_remaining = DATEDIFF(deadline, CURDATE())"
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                affected = cur.execute(sql)
            conn.commit()
    except Exception:
        logger.exception("Rafraîchissement de days_remaining : échec de la mise à jour.")
        return 0

    logger.info("days_remaining recalculé pour %d opportunité(s).", affected)
    return affected
