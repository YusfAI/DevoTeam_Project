import os
import json
import hashlib
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# pyrefly: ignore [missing-import]
from .llm import parse_user_query
# pyrefly: ignore [missing-import]
from .db_layer import build_and_execute_query
# pyrefly: ignore [missing-import]
from .vega_generator import build_vega_spec
from .db import get_connection

app = FastAPI(title="DevoTeam Dashboard")

# Paths
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

class ChatRequest(BaseModel):
    query: str

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

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found in frontend directory")


@app.post("/dashboard")
async def generate_dashboard(request: ChatRequest):
    try:
        # Phase 4: Intent parsing
        intent = parse_user_query(request.query)
        
        # Phase 6: Logger l'historique
        log_request(request.query, intent)
        
        ai_message = intent.get("message_explicatif", "Voici votre analyse :")
        
        # Test conversationnel : si pas de metric, le LLM dit juste bonjour ou autre
        if not intent.get("metric"):
            return {"vega_spec": None, "cached": False, "ai_message": ai_message}
        
        # Phase 6: Check Cache
        intent_hash = hashlib.sha256(json.dumps(intent, sort_keys=True).encode('utf-8')).hexdigest()
        cached_spec = get_cached_dashboard(intent_hash)
        if cached_spec:
            return {"vega_spec": cached_spec, "cached": True, "ai_message": ai_message}
        
        # Phase 3: DB execution
        data = build_and_execute_query(intent)
        
        is_table = intent.get("use_raw_table") or bool(intent.get("range_filters")) or intent.get("chart_type") == "table"
        
        if is_table:
            # For list queries, skip Vega-Lite and send raw rows to frontend
            return {"vega_spec": None, "table_rows": data, "cached": False, "ai_message": ai_message}
        
        # Phase 2: Vega generation
        spec = build_vega_spec(intent, data)
        
        # Save to Cache
        save_to_cache(intent_hash, spec)
        
        return {"vega_spec": spec, "cached": False, "ai_message": ai_message}
        
    except ValueError as e:
        # Expected errors (validation failed, dimension not supported, etc)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Protect against unhandled internal crashes by returning a 500 error gracefully
        print(f"Server error: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur. Veuillez réessayer plus tard.")
