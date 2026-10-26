"""Le raccourci « Arrêter DevoTeam Dashboard » (scripts/stop.bat, scripts/stop.ps1).

Vérifié en conditions réelles avant d'être figé ici : l'application tournant sous
Docker avec le modèle chargé (4,4 Go), le raccourci arrête les trois conteneurs,
libère 8000/8321/8322 et décharge le modèle ; un processus Python leurre sur le port
5173 est arrêté, un programme étranger sur le port 8321 est NOMMÉ et laissé en vie.

Ces tests gardent les choix qui ne se voient pas à la lecture d'un écran : ce que le
script a le droit d'arrêter, et ce qu'il doit laisser tourner.
"""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
STOP_BAT = RACINE / "scripts" / "stop.bat"
STOP_PS1 = RACINE / "scripts" / "stop.ps1"
RACCOURCIS = RACINE / "scripts" / "create_shortcut.ps1"


def _lignes_de_commande(texte: str) -> list[str]:
    return [l for l in texte.splitlines()
            if not l.strip().upper().startswith("REM") and not l.strip().startswith("#")]


def test_le_lanceur_d_arret_porte_des_fins_de_ligne_windows():
    """En LF, un .bat échoue en silence sous cmd.exe (voir tests/test_docker.py)."""
    contenu = STOP_BAT.read_bytes()
    assert b"\r\n" in contenu
    assert contenu.count(b"\n") == contenu.count(b"\r\n")


def test_le_lanceur_d_arret_n_affiche_que_de_l_ascii():
    lignes = STOP_BAT.read_bytes().decode("utf-8").splitlines()
    fautives = [l for l in lignes if l.strip().lower().startswith("echo") and any(ord(c) > 127 for c in l)]
    assert not fautives, fautives[:3]


def test_les_messages_powershell_sont_en_ascii():
    """Ils s'affichent dans la même fenêtre cmd.exe que ceux du .bat."""
    lignes = STOP_PS1.read_bytes().decode("utf-8-sig").splitlines()
    fautives = [l for l in lignes if "Write-Host" in l and any(ord(c) > 127 for c in l)]
    assert not fautives, fautives[:3]


def test_les_conteneurs_sont_arretes_et_supprimes():
    commande = "\n".join(_lignes_de_commande(STOP_BAT.read_text(encoding="utf-8")))
    assert "docker compose down" in commande
    assert "stop.ps1" in commande


def test_docker_desktop_et_ollama_restent_lances():
    """Choix fait avec l'utilisateur : arrêter l'application, pas la plateforme.
    Relancer reste alors une affaire de secondes, et Ollama ne pèse presque rien
    une fois son modèle déchargé."""
    commandes = "\n".join(_lignes_de_commande(
        STOP_BAT.read_text(encoding="utf-8") + STOP_PS1.read_text(encoding="utf-8-sig"))).lower()
    assert "docker desktop stop" not in commandes
    assert "ollama app" not in commandes
    assert "taskkill" not in commandes


def test_seuls_les_processus_de_l_application_peuvent_etre_arretes():
    """Sous Docker, les ports appartiennent au moteur de Docker Desktop : un script
    qui arrêterait « ce qui occupe le port » casserait Docker lui-même."""
    script = STOP_PS1.read_text(encoding="utf-8-sig")
    assert "$processusDeLApplication = 'python', 'pythonw', 'uvicorn', 'dac', 'bruin', 'node'" in script
    assert "$processusDeLApplication -contains" in script
    assert "8000, 8321, 8322, 5173" in script


def test_le_modele_est_decharge_par_l_api_et_non_par_la_ligne_de_commande():
    """`ollama stop` relance l'application Ollama si elle ne tournait pas — l'exact
    contraire d'un arrêt. L'API, elle, se contente d'échouer si Ollama est absent."""
    script = STOP_PS1.read_text(encoding="utf-8-sig")
    assert "keep_alive = 0" in script
    assert "/api/ps" in script
    assert "ollama stop" not in script.lower()


def test_les_scripts_powershell_portent_un_bom():
    """Sans BOM, PowerShell 5.1 lit le fichier en ANSI : les accents des noms et
    descriptions de raccourcis sortaient en charabia (« rechargAc A� chaud »),
    constaté sur les raccourcis du Bureau."""
    for chemin in (STOP_PS1, RACCOURCIS):
        assert chemin.read_bytes().startswith(b"\xef\xbb\xbf"), chemin.name


def test_le_raccourci_d_arret_est_cree_avec_une_icone_distincte():
    contenu = RACCOURCIS.read_text(encoding="utf-8-sig")
    assert "Nom = 'Arrêter DevoTeam Dashboard.lnk'" in contenu
    assert "scripts\\stop.bat" in contenu
    assert "shell32.dll,27" in contenu  # icône marche/arrêt de Windows


def test_les_raccourcis_natifs_ne_sont_crees_que_s_il_y_a_une_installation_native():
    """Sur un poste installé par Docker seul, ils n'affichaient que des erreurs ;
    chaque exécution de ce script les recréait après qu'on les eut supprimés."""
    contenu = RACCOURCIS.read_text(encoding="utf-8-sig")
    assert contenu.count("Natif = $true") == 2
    assert "$installationNative = Test-Path (Join-Path $racine '.venv\\Scripts\\python.exe')" in contenu
    assert "if ($r.Natif -and -not $installationNative)" in contenu


def test_les_messages_de_lancement_designent_le_raccourci_d_arret():
    for chemin in (RACINE / "INSTALLER.bat", RACINE / "scripts" / "start_docker.bat"):
        assert '"Arreter DevoTeam Dashboard"' in chemin.read_text(encoding="utf-8"), chemin.name
