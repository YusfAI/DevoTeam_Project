"""Alertes deadline : opportunités actives dont l'échéance tombe dans les prochains
jours. Calculé en direct via DATEDIFF(deadline, CURDATE()) — jamais depuis la colonne
days_remaining, qui est une valeur figée à l'import des données et non relative à la
date système courante."""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .db import get_connection
from .response_builder import format_metric_value

logger = logging.getLogger(__name__)

ALERT_WINDOW_DAYS = 7

# Statuts clos : une opportunité déjà gagnée/perdue/écartée ne doit plus déclencher
# d'alerte de deadline, même si sa date d'échéance est techniquement proche.
EXCLUDED_STATUSES = [
    "Offre gagnée", "Offre perdue", "Offre signée", "Infructueux",
    "NO GO", "Hors scope", "Non shortlisté",
]

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def get_upcoming_deadline_opportunities(days: int = ALERT_WINDOW_DAYS) -> list:
    """Opportunités actives dont la deadline tombe entre aujourd'hui et +days jours
    (bornes incluses), triées par urgence croissante."""
    placeholders = ", ".join(["%s"] * len(EXCLUDED_STATUSES))
    sql = f"""
        SELECT id, country, practice, buyer, status, deadline, budget,
               DATEDIFF(deadline, CURDATE()) AS days_left
        FROM opportunities
        WHERE DATEDIFF(deadline, CURDATE()) BETWEEN 0 AND %s
          AND status NOT IN ({placeholders})
        ORDER BY days_left ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (days, *EXCLUDED_STATUSES))
            return cur.fetchall()


def _build_email_body(opportunities: list) -> str:
    lines = [
        f"{len(opportunities)} opportunité(s) active(s) avec une échéance dans les "
        f"{ALERT_WINDOW_DAYS} prochains jours :",
        "",
    ]
    for opp in opportunities:
        budget = format_metric_value(opp.get("budget"), "budget")
        lines.append(
            f"- [{opp['days_left']}j restant(s)] {opp.get('buyer') or 'Client non renseigné'} "
            f"({opp.get('country')}, {opp.get('practice')}) — échéance {opp['deadline']} — "
            f"statut : {opp.get('status')} — budget : {budget}"
        )
    lines.append("")
    lines.append("Ce rappel se répète chaque jour tant que la deadline n'est pas passée.")
    return "\n".join(lines)


def send_alert_email(opportunities: list) -> None:
    sender = os.getenv("GMAIL_SENDER")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("ALERT_RECIPIENT_EMAIL")

    if not sender or not app_password or not recipient:
        logger.warning(
            "Alertes deadline : configuration email incomplète "
            "(GMAIL_SENDER / GMAIL_APP_PASSWORD / ALERT_RECIPIENT_EMAIL) — email non envoyé."
        )
        return

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = (
        f"[DevoTeam Dashboard] {len(opportunities)} opportunité(s) à échéance "
        f"≤ {ALERT_WINDOW_DAYS} jours"
    )
    message.attach(MIMEText(_build_email_body(opportunities), "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.starttls()
        server.login(sender, app_password)
        server.sendmail(sender, [recipient], message.as_string())


def run_daily_alert_check() -> int:
    """Point d'entrée appelé par le scheduler quotidien. Renvoie le nombre
    d'opportunités concernées (0 => rien à signaler, aucun email envoyé)."""
    try:
        opportunities = get_upcoming_deadline_opportunities()
    except Exception:
        logger.exception("Alertes deadline : échec de la requête DB, vérification annulée.")
        return 0

    if not opportunities:
        logger.info("Alertes deadline : aucune opportunité active à échéance ≤ %s jours.", ALERT_WINDOW_DAYS)
        return 0

    try:
        send_alert_email(opportunities)
        logger.info("Alertes deadline : email envoyé pour %d opportunité(s).", len(opportunities))
    except Exception:
        logger.exception("Alertes deadline : échec de l'envoi de l'email.")

    return len(opportunities)
