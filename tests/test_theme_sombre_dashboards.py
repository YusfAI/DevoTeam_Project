"""Le mode sombre des tableaux de bord, et son repli.

Le mode sombre ne couvrait que le chat : le tableau de bord, servi en iframe par
DAC, restait blanc à côté d'un chat noir. Un thème DAC est une carte de valeurs
fixes appliquée au lancement du serveur — il n'existe aucune bascule dans le
fichier — donc le mode sombre passe par un SECOND serveur, sur le port 8322.

Ce second processus est FACULTATIF par construction, et ces tests tiennent surtout
ce point : quand il manque, le tableau de bord reste affiché en clair. Faire dépendre
l'affichage d'un confort serait un mauvais échange, et c'est exactement le genre de
dépendance qui casse une démonstration sur une machine où l'on a oublié un raccourci.
"""
import pathlib

import yaml

RACINE = pathlib.Path(__file__).resolve().parent.parent
THEME_CLAIR = RACINE / "dac" / "themes" / "devoteam.yml"
THEME_SOMBRE = RACINE / "dac" / "themes" / "devoteam-dark.yml"
TOKENS = RACINE / "frontend" / "src" / "styles" / "tokens.css"


def test_le_theme_sombre_existe_et_se_charge():
    doc = yaml.safe_load(THEME_SOMBRE.read_text(encoding="utf-8"))

    assert doc["name"] == "devoteam-dark"
    assert doc["extends"] == "bruin"


def test_le_theme_sombre_couvre_les_memes_jetons_que_le_clair():
    """Un jeton oublié retomberait sur la valeur CLAIRE du thème intégré.

    Le défaut serait silencieux : la page s'afficherait, avec une surface blanche au
    milieu d'un fond noir, et rien dans les journaux ne le signalerait.
    """
    clair = yaml.safe_load(THEME_CLAIR.read_text(encoding="utf-8"))["tokens"]
    sombre = yaml.safe_load(THEME_SOMBRE.read_text(encoding="utf-8"))["tokens"]

    assert set(sombre) == set(clair), set(clair).symmetric_difference(sombre)


def test_la_palette_sombre_n_est_pas_la_palette_claire():
    """Le mode sombre est SÉLECTIONNÉ pas à pas, jamais obtenu par inversion.

    Recopier les teintes claires sur un fond noir casse à la fois le contraste et la
    séparation en vision daltonienne — c'est le principe posé dans tokens.css, et il
    doit valoir aussi pour les graphiques servis par DAC.
    """
    clair = yaml.safe_load(THEME_CLAIR.read_text(encoding="utf-8"))["tokens"]
    sombre = yaml.safe_load(THEME_SOMBRE.read_text(encoding="utf-8"))["tokens"]

    for i in range(1, 9):
        cle = "chart-%d" % i
        assert sombre[cle] != clair[cle], cle


def test_les_valeurs_sombres_viennent_bien_des_jetons_de_l_application():
    """Le thème DAC et le CSS de l'application ne doivent pas diverger.

    C'est la même garantie que pour le thème clair : deux fichiers qui décrivent la
    même palette finissent par se contredire dès qu'on n'en modifie qu'un.
    """
    css = TOKENS.read_text(encoding="utf-8")
    sombre = yaml.safe_load(THEME_SOMBRE.read_text(encoding="utf-8"))["tokens"]

    # Le bloc `:root[data-theme="dark"]` porte les valeurs de référence.
    bloc = css[css.index(':root[data-theme="dark"]'):]
    for cle_theme, cle_css in [("background", "--surface-page"),
                               ("surface", "--surface-card"),
                               ("text-primary", "--text-primary"),
                               ("text-secondary", "--text-secondary"),
                               ("text-muted", "--text-muted")]:
        attendu = bloc.split(cle_css + ":")[1].split(";")[0].strip()
        assert sombre[cle_theme].lower() == attendu.lower(), cle_theme


def test_les_lanceurs_demarrent_le_serveur_sombre():
    """Sans cela, le thème sombre n'aurait jamais de serveur à interroger."""
    for nom in ("start_dev.bat", "start_prod.bat"):
        contenu = (RACINE / "scripts" / nom).read_text(encoding="utf-8",
                                                       errors="surrogateescape")
        assert "--port 8322" in contenu, nom
        assert "devoteam-dark.yml" in contenu, nom
        # Le serveur clair reste lancé EN PREMIER : c'est lui qui porte l'affichage
        # par défaut, et le sombre ne doit jamais retarder son démarrage.
        assert contenu.index("--port 8321") < contenu.index("--port 8322"), nom


def test_le_frontend_retombe_sur_le_serveur_clair(monkeypatch):
    """Le repli, écrit côté frontend : racine absente -> serveur clair.

    Vérifié sur la source plutôt qu'en exécutant le JavaScript : ce qui compte est
    que l'URL par défaut reste celle du serveur clair, et que le paramètre de racine
    soit facultatif.
    """
    js = (RACINE / "frontend" / "src" / "dac.js").read_text(encoding="utf-8")

    assert "export function dacDashboardUrl(name, filters, racine)" in js
    # `racine || DAC_BASE_URL` : c'est CE `||` qui porte le repli.
    assert "racine || DAC_BASE_URL" in js
    assert "DAC_DARK_BASE_URL" in js


def test_le_serveur_sombre_ne_conditionne_pas_la_sante_generale():
    """Son absence n'est pas une panne.

    Si elle comptait dans `ok`, l'application afficherait « serveur injoignable » —
    et masquerait le tableau de bord — parce qu'un confort manque.
    """
    source = (RACINE / "backend" / "main.py").read_text(encoding="utf-8")

    # `dac_ok` se calcule à partir du SEUL serveur clair : la sonde du sombre n'entre
    # dans aucun des deux termes.
    ligne_ok = next(l for l in source.splitlines()
                    if l.strip().startswith("dac_ok = "))
    assert "sombre" not in ligne_ok, ligne_ok

    # Et il est bien rapporté, sinon le frontend n'aurait aucun moyen de le choisir.
    assert '"sombre_url": DAC_DARK_URL if _dac_dark_is_reachable() else None' in source


# ---------------------------------------------------------------------------
# Le serveur sombre doit savoir CALCULER, pas seulement répondre
# ---------------------------------------------------------------------------

def test_un_serveur_sombre_qui_repond_mais_ne_calcule_pas_n_est_pas_propose(monkeypatch):
    """La panne réellement rencontrée, en test.

    Un DAC lancé dans un environnement fautif démarre normalement, sert ses pages, et
    fait échouer CHAQUE widget séparément — « bruin query failed: exit status
    0xc0000142 » sur les 28 widgets, pendant que la sonde le déclarait disponible.

    Le proposer dans cet état ferait basculer le mode sombre sur un mur d'erreurs,
    alors que le serveur clair juste à côté fonctionne : l'exact contraire du repli
    que ce second serveur est censé garantir.
    """
    from backend import main

    main._dac_query_probe_cache.clear()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _reponse_vide())
    monkeypatch.setattr(main, "_dac_query_failure",
                        lambda racine=None: "bruin query failed: exit status 0xc0000142")

    assert main._dac_dark_is_reachable() is False


def test_un_serveur_sombre_qui_calcule_est_propose(monkeypatch):
    from backend import main

    main._dac_query_probe_cache.clear()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _reponse_vide())
    monkeypatch.setattr(main, "_dac_query_failure", lambda racine=None: None)

    assert main._dac_dark_is_reachable() is True


class _reponse_vide:
    """Un gestionnaire de contexte minimal, suffisant pour la sonde de présence."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"{}"
