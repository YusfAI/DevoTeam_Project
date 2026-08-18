"""Alertes deadline : opportunités actives dont l'échéance tombe dans les prochains
jours. days_remaining est recalculé à chaque chargement du DataFrame (voir
data_store.py) directement depuis deadline — jamais une valeur qui pourrait
dater d'un chargement précédent."""
import json
import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .data_store import get_dataframe
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

# Anti-doublon de l'alerte quotidienne (voir run_daily_alert_check_if_needed) —
# un petit fichier JSON local plutôt qu'une table MySQL, puisqu'il n'y a plus de
# base de données. Même sémantique : une ligne (date de dernière exécution) par job.
_SCHEDULER_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "scheduler_state.json"


def get_upcoming_deadline_opportunities(days: int = ALERT_WINDOW_DAYS) -> list:
    """Opportunités actives dont la deadline tombe entre aujourd'hui et +days jours
    (bornes incluses), triées par urgence croissante."""
    df = get_dataframe()
    if df is None or df.empty:
        return []

    mask = df["days_remaining"].between(0, days) & ~df["status"].isin(EXCLUDED_STATUSES)
    result = df.loc[mask, ["id", "country", "practice", "buyer", "status", "deadline", "budget", "days_remaining"]]
    result = result.sort_values("days_remaining", ascending=True)
    result = result.rename(columns={"days_remaining": "days_left"})

    records = result.where(result.notnull(), None).to_dict("records")
    for r in records:
        if hasattr(r["deadline"], "isoformat"):
            r["deadline"] = r["deadline"].isoformat()
    return records


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
        logger.exception("Alertes deadline : échec de la lecture des données, vérification annulée.")
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


def _read_scheduler_state() -> dict:
    try:
        with open(_SCHEDULER_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_scheduler_state(state: dict) -> None:
    _SCHEDULER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SCHEDULER_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _already_ran_today(job_name: str) -> bool:
    state = _read_scheduler_state()
    return state.get(job_name) == date.today().isoformat()


def _mark_ran_today(job_name: str) -> None:
    state = _read_scheduler_state()
    state[job_name] = date.today().isoformat()
    _write_scheduler_state(state)


def run_daily_alert_check_if_needed() -> int:
    """Point d'entrée idempotent : à appeler à la fois par le cron 8h ET au démarrage
    du serveur. Si le digest du jour a déjà été envoyé (ex: le serveur était éteint à
    8h et redémarre à 10h — le cron a été manqué, cet appel de démarrage rattrape),
    ne renvoie jamais un deuxième email le même jour."""
    job_name = "daily_deadline_alert"
    try:
        if _already_ran_today(job_name):
            logger.info("Alertes deadline : déjà vérifiées aujourd'hui, rien à faire.")
            return 0
    except Exception:
        logger.exception(
            "Alertes deadline : échec de la vérification anti-doublon — on continue "
            "quand même plutôt que de bloquer l'alerte sur un problème de suivi."
        )

    count = run_daily_alert_check()

    try:
        _mark_ran_today(job_name)
    except Exception:
        logger.exception("Alertes deadline : échec de l'enregistrement de l'exécution du jour.")

    return count
