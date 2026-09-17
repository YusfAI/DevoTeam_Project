# -*- coding: utf-8 -*-
"""La feuille est-elle lisible avec la clé API renseignée dans .env ?

Employée par l'assistant pour attendre que le partage soit fait, plutôt que
d'échouer dessus. C'est l'étape qui bloque le plus d'installations, et la seule
qui dépende d'un geste fait ailleurs — dans l'interface de Google Sheets.

Sort avec 0 si tout va bien, 1 sinon, et affiche une ligne lisible dans les deux
cas : l'assistant la reprend telle quelle.

Lecture seule : une clé API Google ne permet jamais l'écriture, il n'y a donc
rien à prouver de ce côté-là — seulement que la feuille est bien partagée en
« Lecteur — toute personne disposant du lien », sans quoi l'API répond 403.
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(RACINE / ".env")
        from backend import data_store
    except ImportError as e:
        print("Dependances Python pas encore installees (%s)." % e)
        return 1

    try:
        valeurs = data_store.fetch_sheet_values()
    except Exception as e:
        message = str(e)
        if "403" in message:
            print("Acces refuse : la feuille n'est pas partagee en Lecteur, toute personne disposant du lien.")
        elif "404" in message:
            print("Feuille introuvable : verifier l'identifiant et le nom de l'onglet.")
        elif "400" in message:
            print("Cle API refusee : verifier GOOGLE_SHEETS_API_KEY et que l'API Sheets est activee.")
        else:
            print("Feuille inaccessible : %s" % message[:120])
        return 1

    if not valeurs:
        print("La feuille est vide — pas meme une ligne d'en-tete.")
        return 1

    print("%d ligne(s) lues." % (len(valeurs) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
