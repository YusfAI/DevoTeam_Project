import os
import json
import hashlib
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# pyrefly: ignore [missing-import]
from .llm import parse_user_query
# pyrefly: ignore [missing-import]
from .db_layer import build_and_execute_query
# pyrefly: ignore [missing-import]
from .vega_generator import build_vega_spec
from .response_builder import build_data_response, get_help_message, extract_metric_value, format_metric_value
from .db import get_connection
from .alerts import get_upcoming_deadline_opportunities, run_daily_alert_check_if_needed
from .maintenance import refresh_days_remaining
from .sheets_sync import sync_sheet_to_mysql

logger = logging.getLogger(__name__)

# Deux jobs quotidiens : days_remaining est recalculé à minuit (pour que la valeur
# affichée dans le chat/tableaux soit déjà correcte au réveil), puis l'alerte deadline
# tourne à 8h (heure serveur) sur la base de ces valeurs fraîches — assez tôt pour que
# l'équipe commerciale la voie en arrivant, sans dépendre d'un déclenchement manuel.
# Les deux tournent aussi une fois au démarrage : days_remaining est de toute façon
# idempotent (le recalculer ne fait jamais de mal), et l'alerte email est protégée
# par run_daily_alert_check_if_needed() (ne renvoie pas un second email si la
# vérification du jour a déjà eu lieu) — un serveur resté éteint pile à 8h ou minuit
# rattrape donc l'exécution manquée dès qu'il redémarre, au lieu d'attendre le lendemain.
# La synchronisation Google Sheets tourne aussi toutes les 15 minutes (+ une fois au
# démarrage) — sens unique Sheet -> MySQL, voir backend/sheets_sync.py.
_scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Les 3 tâches de démarrage tournaient auparavant en bloquant ici (synchrone,
    # avant yield) : le serveur n'acceptait aucune requête HTTP tant qu'elles
    # n'étaient pas terminées, dont jusqu'à ~1.6s pour la seule connexion à Google
    # Sheets (sync_sheet_to_mysql -> voir backend/sheets_sync.py). Elles tournent
    # maintenant comme jobs "une fois, immédiatement" sur le thread du scheduler,
    # démarré juste après : le serveur répond dès que la boucle est prête, ces
    # tâches finissent en tâche de fond en quelques secondes.
    _scheduler.add_job(refresh_days_remaining, id="startup_days_remaining_refresh")
    _scheduler.add_job(run_daily_alert_check_if_needed, id="startup_deadline_alert")
    _scheduler.add_job(sync_sheet_to_mysql, id="startup_sheets_sync")
    _scheduler.add_job(refresh_days_remaining, "cron", hour=0, minute=5, id="daily_days_remaining_refresh")
    _scheduler.add_job(run_daily_alert_check_if_needed, "cron", hour=8, minute=0, id="daily_deadline_alert")
    _scheduler.add_job(sync_sheet_to_mysql, "interval", minutes=15, id="sheets_sync_periodic")
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="DevoTeam Dashboard", lifespan=lifespan)

# Paths
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

class ChatRequest(BaseModel):
    query: str
    previous_intent: dict | None = None

def get_cached_dashboard(intent_hash: str):
    with get_connection() as conn:
         with conn.cursor() as cur:
             cur.execute("SELECT vega_spec FROM generated_dashboards WHERE intent_hash = %s", (intent_hash,))
             row = cur.fetchone()
             if row:
                 # Handle MySQL JSON which might return as dict or string
                 return json.loads(row['vega_spec']) if isinstance(row['vega_spec'], str) else row['vega_spec']
    return None

def save_to_cache(intent_hash: str, vega_spec: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
             cur.execute("INSERT IGNORE INTO generated_dashboards (intent_hash, vega_spec) VALUES (%s, %s)",
                         (intent_hash, json.dumps(vega_spec)))
        conn.commit()

def log_request(prompt: str, intent: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
             cur.execute("INSERT INTO dashboard_requests (prompt, intent_json) VALUES (%s, %s)",
                         (prompt, json.dumps(intent)))
        conn.commit()


@app.post("/dashboard")
async def generate_dashboard(request: ChatRequest):
    try:
        # Phase 4: Intent parsing
        intent = parse_user_query(request.query, previous_intent=request.previous_intent)

        log_request(request.query, intent)

        if intent.get("is_conversation") or not intent.get("metric"):
            ai_message = intent.get("clarification") or get_help_message()
            return {"vega_spec": None, "cached": False, "ai_message": ai_message}

        data = build_and_execute_query(intent)
        ai_message = build_data_response(intent, data)
        goal = intent.get("goal", "")

        is_table = intent.get("use_raw_table") or bool(intent.get("range_filters")) or intent.get("chart_type") == "table"

        if is_table:
            return {"vega_spec": None, "table_rows": data, "cached": False, "ai_message": ai_message, "goal": goal, "intent": intent}

        if intent.get("chart_type") == "kpi_card":
            metric = intent.get("metric", "budget")
            kpi_value = extract_metric_value(data[0], metric) if data else None
            return {
                "vega_spec": None,
                "kpi_value": kpi_value,
                "kpi_value_formatted": format_metric_value(kpi_value, metric),
                "kpi_label": goal,
                "cached": False,
                "ai_message": ai_message,
                "goal": goal,
                "intent": intent,
            }

        intent_hash = hashlib.sha256(json.dumps(intent, sort_keys=True).encode('utf-8')).hexdigest()
        cached_spec = get_cached_dashboard(intent_hash)

        if cached_spec:
            return {"vega_spec": cached_spec, "table_rows": data, "cached": True, "ai_message": ai_message, "goal": goal, "intent": intent}

        spec = build_vega_spec(intent, data)
        save_to_cache(intent_hash, spec)

        return {"vega_spec": spec, "table_rows": data, "cached": False, "ai_message": ai_message, "goal": goal, "intent": intent}

    except ValueError as e:
        # Expected errors (validation failed, dimension not supported, etc)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # Protect against unhandled internal crashes by returning a 500 error gracefully
        logger.exception("Erreur interne non gérée dans /dashboard")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur. Veuillez réessayer plus tard.")


@app.get("/alerts/deadlines")
async def get_deadline_alerts():
    """Lecture live (indépendante du digest email quotidien) pour le panneau d'alerte
    du frontend — mêmes règles : opportunités actives, échéance ≤ 7 jours."""
    opportunities = get_upcoming_deadline_opportunities()
    return {"opportunities": opportunities, "window_days": 7}


@app.post("/sheets/sync")
async def trigger_sheets_sync():
    """Déclenchement manuel de la synchronisation Google Sheets -> MySQL, en plus du
    job automatique toutes les 15 minutes — utile pour voir un ajout immédiatement
    sans attendre le prochain passage planifié."""
    return sync_sheet_to_mysql()


# Doit rester la DERNIÈRE route déclarée : sert le build React (frontend/dist) sur "/"
# et les assets hashés sous "/assets/...". Les routes API explicites ci-dessus sont
# résolues en premier ; ce montage ne gère que ce qu'aucune route API ne matche.
app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
