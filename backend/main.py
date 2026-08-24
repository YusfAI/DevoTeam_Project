import os
import json
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
from .response_builder import build_data_response, get_help_message
# pyrefly: ignore [missing-import]
from .alerts import get_upcoming_deadline_opportunities, run_daily_alert_check_if_needed
# pyrefly: ignore [missing-import]
from .data_store import get_dataframe, get_last_refresh_summary, refresh_dataframe
# pyrefly: ignore [missing-import]
from .duckdb_export import export_dataframe
# pyrefly: ignore [missing-import]
from .dac_composer import write_generated_dashboard, write_main_dashboard

logger = logging.getLogger(__name__)

# Le DataFrame (backend/data_store.py) est rafraîchi depuis le Sheet toutes les 15
# minutes, et l'alerte deadline tourne à 8h (heure serveur) sur des données déjà
# fraîches. Les deux tournent aussi une fois au démarrage : le rafraîchissement est
# de toute façon idempotent, et l'alerte email est protégée par
# run_daily_alert_check_if_needed() (ne renvoie pas un second email si la
# vérification du jour a déjà eu lieu) — un serveur resté éteint pile à 8h rattrape
# donc l'exécution manquée dès qu'il redémarre, au lieu d'attendre le lendemain.
_scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ces tâches de démarrage tournaient auparavant en bloquant ici (synchrone,
    # avant yield) : le serveur n'acceptait aucune requête HTTP tant qu'elles
    # n'étaient pas terminées. Elles tournent maintenant comme jobs "une fois,
    # immédiatement" sur le thread du scheduler, démarré juste après : le serveur
    # répond dès que la boucle est prête, ces tâches finissent en tâche de fond.
    _scheduler.add_job(_refresh_data, id="startup_data_refresh")
    _scheduler.add_job(run_daily_alert_check_if_needed, id="startup_deadline_alert")
    _scheduler.add_job(_refresh_data, "interval", minutes=15, id="data_refresh_periodic")
    _scheduler.add_job(run_daily_alert_check_if_needed, "cron", hour=8, minute=0, id="daily_deadline_alert")
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)


app = FastAPI(title="DevoTeam Dashboard", lifespan=lifespan)

# Paths
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

class ChatRequest(BaseModel):
    query: str
    previous_intent: dict | None = None

def log_request(prompt: str, intent: dict):
    logger.info("Requête dashboard : %r -> %s", prompt, json.dumps(intent, ensure_ascii=False))

def _refresh_data() -> dict:
    summary = refresh_dataframe()
    # Projection DuckDB pour les dashboards DAC (voir backend/duckdb_export.py) —
    # jamais bloquante : un échec d'export laisse l'application pleinement
    # fonctionnelle, seuls les dashboards DAC restent sur le cycle précédent.
    summary["duckdb_exported"] = export_dataframe(get_dataframe())
    return summary


@app.post("/dashboard")
async def generate_dashboard(request: ChatRequest):
    try:
        # Phase 4: Intent parsing
        intent = parse_user_query(request.query, previous_intent=request.previous_intent)

        log_request(request.query, intent)

        if intent.get("is_conversation") or not intent.get("metric"):
            ai_message = intent.get("clarification") or get_help_message()
            return {"ai_message": ai_message}

        data = build_and_execute_query(intent)
        ai_message = build_data_response(intent, data)
        goal = intent.get("goal", "")

        # Dashboard multi-widgets répondant à la question (backend/dac_composer.py),
        # affiché en iframe par le frontend. Jamais bloquant : si la génération ou
        # l'écriture échoue, on renvoie quand même la réponse classique (message +
        # graphique unique) plutôt que de faire échouer toute la requête.
        # Deux écritures, deux rôles. Le dashboard de TRAVAIL garde toujours le même
        # nom : la question le réécrit sur place, sous les yeux de l'utilisateur.
        # L'INSTANTANÉ fige le résultat de cette question précise, pour que la liste
        # déroulante puisse le rouvrir plus tard sans repasser par le modèle.
        try:
            dac_dashboard = write_main_dashboard(request.query, intent)
        except Exception:
            logger.exception("Écriture du dashboard de travail en échec pour %r", request.query)
            dac_dashboard = None

        try:
            dashboard_snapshot = write_generated_dashboard(request.query, intent)
        except Exception:
            logger.exception("Écriture de l'instantané en échec pour %r", request.query)
            dashboard_snapshot = None

        # Si le dashboard de travail n'a pas pu être écrit, on affiche l'instantané
        # plutôt que rien : l'utilisateur perd la mise à jour en place, pas sa réponse.
        if dac_dashboard is None:
            dac_dashboard = dashboard_snapshot

        # La réponse ne transporte plus de spécification de graphique : tout ce qui
        # s'affiche vient du dashboard DAC désigné par dac_dashboard. Le frontend n'a
        # besoin que du message, du titre et de l'intention (contexte multi-tour).
        return {"ai_message": ai_message, "goal": goal, "intent": intent,
                "dac_dashboard": dac_dashboard, "dashboard_snapshot": dashboard_snapshot}

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


DAC_URL = os.getenv("DAC_URL", "http://localhost:8321")


def _dac_is_reachable() -> bool:
    """Sonde le serveur de dashboards. Faite ICI et non depuis le navigateur : une
    requête directe du frontend vers le port 8321 serait bloquée par la politique
    d'origine (l'iframe, elle, n'est pas soumise à cette règle — d'où le fait qu'une
    panne de DAC se traduisait par un cadre vide et muet, sans erreur exploitable)."""
    import urllib.request
    try:
        with urllib.request.urlopen(DAC_URL, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


@app.get("/health")
async def health():
    """État des trois briques dont dépend l'affichage. Sert à distinguer une panne
    d'un simple manque de données — un dashboard vide peut venir de l'un ou de
    l'autre, et l'utilisateur n'a aucun moyen de trancher sans cette information."""
    summary = get_last_refresh_summary() or {}
    df = get_dataframe()
    dac_ok = _dac_is_reachable()
    return {
        "ok": dac_ok and df is not None and not df.empty,
        "dac": {
            "ok": dac_ok,
            "url": DAC_URL,
            "aide": None if dac_ok else (
                "Le serveur de dashboards ne répond pas. Lancez-le depuis le dossier "
                "dac/ : dac serve --dir . --port 8321 (le dossier ~/.local/bin doit "
                "être dans le PATH)."
            ),
        },
        "donnees": {
            "ok": df is not None and not df.empty,
            "lignes": 0 if df is None else len(df),
            "ignorees": summary.get("skipped", 0),
        },
    }


@app.get("/data/quality")
async def data_quality_report():
    """Ce qui a été écarté au dernier chargement et pourquoi (lignes rejetées,
    valeurs manquantes). Les mêmes chiffres alimentent le dashboard « Qualité des
    données » via DuckDB — voir backend/data_quality.py."""
    from .data_quality import report
    return report()


@app.post("/sheets/sync")
async def trigger_sheets_sync():
    """Rafraîchissement manuel des données depuis le Google Sheet, en plus du job
    automatique toutes les 15 minutes — utile pour voir un ajout/une modification
    immédiatement sans attendre le prochain passage planifié."""
    return _refresh_data()


# Doit rester la DERNIÈRE route déclarée : sert le build React (frontend/dist) sur "/"
# et les assets hashés sous "/assets/...". Les routes API explicites ci-dessus sont
# résolues en premier ; ce montage ne gère que ce qu'aucune route API ne matche.
app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
