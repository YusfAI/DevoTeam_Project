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
# pyrefly: ignore [missing-import]
from .response_builder import build_data_response, get_help_message, extract_metric_value, format_metric_value
# pyrefly: ignore [missing-import]
from .alerts import get_upcoming_deadline_opportunities, run_daily_alert_check_if_needed
# pyrefly: ignore [missing-import]
from .data_store import get_dataframe, refresh_dataframe
# pyrefly: ignore [missing-import]
from .duckdb_export import export_dataframe
# pyrefly: ignore [missing-import]
from .dac_composer import write_generated_dashboard

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
    _scheduler.add_job(_refresh_data_and_invalidate_cache, id="startup_data_refresh")
    _scheduler.add_job(run_daily_alert_check_if_needed, id="startup_deadline_alert")
    _scheduler.add_job(_refresh_data_and_invalidate_cache, "interval", minutes=15, id="data_refresh_periodic")
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

# Cache des specs déjà générées (clé = hash de l'intention) — en mémoire plutôt
# qu'en base : régénérer une spec depuis le DataFrame déjà en mémoire est rapide
# (plus de round-trip SQL à éviter), donc le bénéfice d'un cache persistant entre
# redémarrages est marginal. Vidé à chaque rafraîchissement du DataFrame (voir
# _refresh_data_and_invalidate_cache) puisque les données sous-jacentes ont pu
# changer entre-temps — une spec calculée sur l'ancien contenu serait fausse.
_dashboard_cache: dict[str, dict] = {}


def get_cached_dashboard(intent_hash: str):
    return _dashboard_cache.get(intent_hash)

def save_to_cache(intent_hash: str, vega_spec: dict):
    _dashboard_cache[intent_hash] = vega_spec

def log_request(prompt: str, intent: dict):
    logger.info("Requête dashboard : %r -> %s", prompt, json.dumps(intent, ensure_ascii=False))

def _refresh_data_and_invalidate_cache() -> dict:
    summary = refresh_dataframe()
    _dashboard_cache.clear()
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
            return {"vega_spec": None, "cached": False, "ai_message": ai_message}

        data = build_and_execute_query(intent)
        ai_message = build_data_response(intent, data)
        goal = intent.get("goal", "")

        # Dashboard multi-widgets répondant à la question (backend/dac_composer.py),
        # affiché en iframe par le frontend. Jamais bloquant : si la génération ou
        # l'écriture échoue, on renvoie quand même la réponse classique (message +
        # graphique unique) plutôt que de faire échouer toute la requête.
        try:
            dac_dashboard = write_generated_dashboard(request.query, intent)
        except Exception:
            logger.exception("Génération du dashboard DAC en échec pour %r", request.query)
            dac_dashboard = None

        base = {"cached": False, "ai_message": ai_message, "goal": goal,
                "intent": intent, "dac_dashboard": dac_dashboard}

        is_table = intent.get("use_raw_table") or bool(intent.get("range_filters")) or intent.get("chart_type") == "table"

        if is_table:
            return {**base, "vega_spec": None, "table_rows": data}

        if intent.get("chart_type") == "kpi_card":
            metric = intent.get("metric", "budget")
            kpi_value = extract_metric_value(data[0], metric) if data else None
            return {
                **base,
                "vega_spec": None,
                "kpi_value": kpi_value,
                "kpi_value_formatted": format_metric_value(kpi_value, metric),
                "kpi_label": goal,
            }

        intent_hash = hashlib.sha256(json.dumps(intent, sort_keys=True).encode('utf-8')).hexdigest()
        cached_spec = get_cached_dashboard(intent_hash)

        if cached_spec:
            return {**base, "cached": True, "vega_spec": cached_spec, "table_rows": data}

        spec = build_vega_spec(intent, data)
        save_to_cache(intent_hash, spec)

        return {**base, "vega_spec": spec, "table_rows": data}

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
    return _refresh_data_and_invalidate_cache()


# Doit rester la DERNIÈRE route déclarée : sert le build React (frontend/dist) sur "/"
# et les assets hashés sous "/assets/...". Les routes API explicites ci-dessus sont
# résolues en premier ; ce montage ne gère que ce qu'aucune route API ne matche.
app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
