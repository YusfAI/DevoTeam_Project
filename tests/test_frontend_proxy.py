"""Le serveur de développement doit router vers l'API tout ce que le frontend appelle.

Un préfixe oublié dans le proxy Vite ne casse rien au démarrage : le serveur renvoie
simplement l'index.html du SPA à la place de la réponse JSON, et l'appelant reçoit
« Unexpected token '<', "<!doctype "... is not valid JSON ». C'est arrivé en ajoutant
`GET /hot-deals` sur un préfixe neuf — l'endpoint marchait, le proxy l'ignorait.

Ces tests confrontent trois fichiers qui doivent rester d'accord : les appels de
`src/api.js`, les préfixes de `vite.config.js`, et les routes de `backend/main.py`.
"""
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
API_JS = RACINE / "frontend" / "src" / "api.js"
VITE_CONFIG = RACINE / "frontend" / "vite.config.js"
MAIN_PY = RACINE / "backend" / "main.py"


def _chemins_appeles() -> set:
    """Les chemins passés à fetch() dans la couche API du frontend."""
    source = API_JS.read_text(encoding="utf-8")
    return set(re.findall(r"fetch\(\s*['\"](/[^'\"]*)['\"]", source))


def _prefixes_proxy() -> set:
    """Les clés de `server.proxy` dans la configuration Vite."""
    source = VITE_CONFIG.read_text(encoding="utf-8")
    bloc = source[source.index("proxy: {"):]
    bloc = bloc[:bloc.index("}")]
    return set(re.findall(r"['\"](/[^'\"]*)['\"]\s*:", bloc))


def _routes_backend() -> set:
    source = MAIN_PY.read_text(encoding="utf-8")
    return set(re.findall(r"@app\.(?:get|post|put|delete)\(\s*['\"](/[^'\"]*)['\"]", source))


def test_every_call_the_frontend_makes_is_proxied():
    appels = _chemins_appeles()
    prefixes = _prefixes_proxy()
    assert appels, "aucun fetch trouvé dans api.js — le test ne vérifierait plus rien"

    non_routes = [c for c in appels if not any(c == p or c.startswith(p + "/") for p in prefixes)]
    assert not non_routes, (
        "chemins appelés par le frontend et absents du proxy Vite : %s. "
        "Le serveur de développement leur répondra l'index.html du SPA." % non_routes
    )


def test_every_call_the_frontend_makes_exists_in_the_backend():
    # L'autre moitié du contrat : un proxy correct vers une route inexistante donne
    # un 404 tout aussi silencieux côté interface.
    appels = _chemins_appeles()
    routes = _routes_backend()

    inconnus = [c for c in appels if c not in routes]
    assert not inconnus, "chemins appelés par le frontend et absents de main.py : %s" % inconnus


def test_the_static_mount_stays_last():
    """Le montage statique attrape tout : déclaré avant une route d'API, il la masque.

    C'est le pendant côté production du problème de proxy — l'appel renverrait là
    encore l'index.html au lieu du JSON attendu.
    """
    source = MAIN_PY.read_text(encoding="utf-8")
    montage = source.index('app.mount("/"')
    derniere_route = max(m.start() for m in re.finditer(r"@app\.(?:get|post|put|delete)\(", source))
    assert derniere_route < montage, (
        "une route d'API est déclarée après le montage statique : elle sera masquée."
    )
