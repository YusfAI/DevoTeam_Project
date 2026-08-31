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
from .response_builder import (
    build_data_response, describe_change, get_help_message, list_changes,
)
# pyrefly: ignore [missing-import]
from .alerts import get_upcoming_deadline_opportunities, run_daily_alert_check_if_needed
# pyrefly: ignore [missing-import]
from .data_store import get_dataframe, get_last_refresh_summary, refresh_dataframe
# pyrefly: ignore [missing-import]
from .duckdb_export import export_dataframe
# pyrefly: ignore [missing-import]
from .dac_composer import (
    append_to_main_dashboard, compose_widgets, write_generated_dashboard,
    write_main_dashboard,
)

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
    # Une question vide n'atteint jamais le modèle. Le parseur rapide la rejetait
    # bien, mais elle repartait alors vers Gemini — qui, n'ayant rien à interpréter,
    # inventait une demande plausible : « Top 5 des pratiques par nombre
    # d'opportunités » a été servi pour une chaîne vide. Une analyse que personne
    # n'a demandée est une hallucination comme une autre, et c'est ici qu'on
    # l'arrête, pas dans le prompt. Au passage, l'appel économisé est du quota gardé.
    if not (request.query or "").strip():
        return {"ai_message": get_help_message()}

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
        # « ajoute … » complète le tableau de bord affiché au lieu de le remplacer.
        # Renvoie None s'il n'y a rien à compléter — on retombe alors sur une
        # composition normale, ce qui est le comportement attendu quand la question
        # est la première de la session.
        ajout = False
        deja_present = False
        # Composés UNE fois : le tableau de bord de travail et l'instantané portent
        # les mêmes widgets. Les composer deux fois refaisait pour rien le comptage
        # de cardinalité qui décide entre camembert et barres.
        widgets = compose_widgets(intent)
        try:
            dac_dashboard = None
            if intent.get("append"):
                dac_dashboard, ajout = append_to_main_dashboard(request.query, intent)
                deja_present = dac_dashboard is not None and not ajout
            if dac_dashboard is None:
                dac_dashboard = write_main_dashboard(request.query, intent, widgets)
        except Exception:
            logger.exception("Écriture du dashboard de travail en échec pour %r", request.query)
            dac_dashboard = None

        try:
            dashboard_snapshot = write_generated_dashboard(request.query, intent, widgets)
        except Exception:
            logger.exception("Écriture de l'instantané en échec pour %r", request.query)
            dashboard_snapshot = None

        # Si le dashboard de travail n'a pas pu être écrit, on affiche l'instantané
        # plutôt que rien : l'utilisateur perd la mise à jour en place, pas sa réponse.
        if dac_dashboard is None:
            dac_dashboard = dashboard_snapshot

        # Une demande de suite modifie le tableau de bord affiché : le dire, sinon
        # l'utilisateur voit l'iframe se recharger sans savoir ce qui a été pris en
        # compte. La phrase vient d'une comparaison des deux intentions, jamais du
        # modèle — elle décrit ce qui a réellement changé dans les requêtes.
        entete = []
        if ajout:
            # Un ajout ne se décrit pas comme une modification : rien n'a été remplacé,
            # et comparer les deux intentions annoncerait à tort un changement d'axe.
            entete.append(f"Widget ajouté au tableau de bord — {goal or 'nouvelle vue'}.")
        elif deja_present:
            entete.append("Ce widget est déjà sur le tableau de bord — rien n'a changé.")
        changement = ("" if ajout or deja_present
                       else describe_change(request.previous_intent, intent))
        if changement:
            entete.append(changement)
        elif (not ajout
                and not deja_present
                and request.previous_intent
                and not list_changes(request.previous_intent, intent)
                and not intent.get("chart_type_reason")):
            # Demande comprise, mais sans effet : un filtre déjà posé, un axe déjà
            # affiché. Ne rien dire laisserait croire qu'elle n'a pas été reçue.
            #
            # Écartée quand une forme a été révisée : là, ce n'est pas « déjà fait »
            # mais « demandé et refusé », et la raison qui suit le dit mieux.
            entete.append(
                "Le tableau de bord affiché répond déjà à cette demande — rien n'a changé."
            )

        # Forme révisée : la raison est affichée sous le graphique, mais elle doit
        # aussi être DITE. Demander un camembert et recevoir des barres sans un mot
        # ressemble à une demande ignorée, pas à une décision motivée.
        if intent.get("chart_type_reason"):
            entete.append(intent["chart_type_reason"])

        if entete:
            ai_message = "\n\n".join(entete) + "\n\n" + ai_message


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


# 127.0.0.1 et non « localhost » : ce dernier résout d'abord en ::1 sur Windows,
# alors que DAC n'écoute que sur l'IPv4. La sonde y épuisait donc TOUT son délai
# d'attente avant de retomber sur la bonne adresse — 2,0 s mesurées contre 0,001 s
# ici, à chaque appel de /health, donc après chaque question posée.
DAC_URL = os.getenv("DAC_URL", "http://127.0.0.1:8321")

# Une sonde qui met plus longtemps que ça n'apprend plus rien d'utile : sur une
# boucle locale, un serveur en vie répond en une poignée de millisecondes.
_DAC_PROBE_TIMEOUT_SECONDS = 0.5


def _dac_is_reachable() -> bool:
    """Sonde le serveur de dashboards. Faite ICI et non depuis le navigateur : une
    requête directe du frontend vers le port 8321 serait bloquée par la politique
    d'origine (l'iframe, elle, n'est pas soumise à cette règle — d'où le fait qu'une
    panne de DAC se traduisait par un cadre vide et muet, sans erreur exploitable)."""
    import urllib.request
    try:
        with urllib.request.urlopen(DAC_URL, timeout=_DAC_PROBE_TIMEOUT_SECONDS) as response:
            return response.status == 200
    except Exception:
        return False


# DAC n'exécute pas le SQL lui-même : il le délègue au binaire `bruin`, qu'il cherche
# dans le PATH. Les deux vivent dans ~/.local/bin, que l'installeur n'ajoute PAS au
# PATH système — un DAC lancé sans cette précaution DÉMARRE normalement, répond 200,
# et fait échouer chaque widget séparément : « bruin: executable file not found ».
# `_dac_is_reachable` répondait donc « ok » devant un mur d'erreurs.
#
# La sonde ci-dessous exécute vraiment une requête. Elle est plus coûteuse, donc son
# résultat est mis en cache : ce qu'elle détecte est un problème d'installation, qui
# ne va ni apparaître ni disparaître d'une seconde à l'autre.
_DAC_QUERY_PROBE_DASHBOARD = "Qualité des données"  # versionné, donc toujours présent
_DAC_QUERY_PROBE_TIMEOUT_SECONDS = 5.0
_DAC_QUERY_PROBE_TTL_SECONDS = 60.0
_dac_query_probe_cache: tuple[float, str | None] = (0.0, None)


def _dac_query_failure() -> str | None:
    """Le message d'erreur si DAC ne sait pas exécuter ses requêtes, sinon None."""
    global _dac_query_probe_cache
    import time
    import urllib.parse
    import urllib.request

    expire_a, precedent = _dac_query_probe_cache
    if time.monotonic() < expire_a:
        return precedent

    erreur = None
    try:
        url = "%s/api/v1/dashboards/%s/data" % (
            DAC_URL, urllib.parse.quote(_DAC_QUERY_PROBE_DASHBOARD))
        requete = urllib.request.Request(
            url, b"{}", {"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(requete, timeout=_DAC_QUERY_PROBE_TIMEOUT_SECONDS) as reponse:
            widgets = (json.loads(reponse.read()) or {}).get("widgets") or {}
        for detail in widgets.values():
            if detail.get("error"):
                erreur = str(detail["error"])
                break
    except Exception:
        # Injoignable ou réponse inattendue : `_dac_is_reachable` couvre déjà ce cas
        # et le dit mieux. Cette sonde-ci ne se prononce que sur l'exécution du SQL.
        logger.debug("Sonde d'exécution DAC indisponible.", exc_info=True)

    _dac_query_probe_cache = (time.monotonic() + _DAC_QUERY_PROBE_TTL_SECONDS, erreur)
    return erreur


@app.get("/health")
async def health():
    """État des trois briques dont dépend l'affichage. Sert à distinguer une panne
    d'un simple manque de données — un dashboard vide peut venir de l'un ou de
    l'autre, et l'utilisateur n'a aucun moyen de trancher sans cette information."""
    summary = get_last_refresh_summary() or {}
    df = get_dataframe()
    dac_repond = _dac_is_reachable()
    # Répondre ne suffit pas : DAC peut être debout et incapable d'exécuter la moindre
    # requête (voir _dac_query_failure). Tant qu'on ne distinguait pas les deux, un
    # tableau de bord entièrement en erreur s'accompagnait d'un « dac ok » rassurant.
    echec_requetes = _dac_query_failure() if dac_repond else None
    dac_ok = dac_repond and not echec_requetes

    if not dac_repond:
        aide = ("Le serveur de dashboards ne répond pas. Lancez-le depuis le dossier "
                "dac/ : dac serve --dir . --port 8321 (le dossier ~/.local/bin doit "
                "être dans le PATH).")
    elif echec_requetes and "bruin" in echec_requetes.lower():
        aide = ("Le serveur de dashboards tourne mais ne trouve pas « bruin », à qui "
                "il délègue l'exécution du SQL — tous les visuels restent donc en "
                "erreur. Relancez-le avec ~/.local/bin dans le PATH : le script "
                "scripts/start_dev.bat le fait pour vous.")
    elif echec_requetes:
        aide = "Le serveur de dashboards n'exécute pas ses requêtes : %s" % echec_requetes[:200]
    else:
        aide = None

    return {
        "ok": dac_ok and df is not None and not df.empty,
        "dac": {
            "ok": dac_ok,
            "repond": dac_repond,
            "requetes_ok": dac_repond and not echec_requetes,
            "url": DAC_URL,
            "aide": aide,
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
