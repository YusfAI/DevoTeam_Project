# -*- coding: utf-8 -*-
"""La feuille est-elle accessible en LECTURE et en ÉCRITURE ?

Employée par l'assistant pour attendre que le partage soit fait, plutôt que
d'échouer dessus. C'est l'étape qui bloque le plus d'installations, et la seule
qui dépende d'un geste fait ailleurs — dans l'interface de Google Sheets.

Sort avec 0 si tout va bien, 1 sinon, et affiche une ligne lisible dans les deux
cas : l'assistant la reprend telle quelle.

L'écriture est réellement tentée, en réécrivant la cellule A1 avec sa propre
valeur. Un partage en Lecteur laisse la lecture fonctionner et n'échoue qu'au
premier enregistrement — c'est-à-dire au premier usage réel.
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
        feuille = data_store._get_worksheet()
        valeurs = feuille.get_all_values()
    except Exception as e:
        message = str(e)
        if "PERMISSION_DENIED" in message or "403" in message:
            print("Acces refuse : la feuille n'est pas partagee avec le compte de service.")
        elif "404" in message or "not found" in message.lower():
            print("Feuille introuvable : verifier l'identifiant et le nom de l'onglet.")
        else:
            print("Feuille inaccessible : %s" % message[:120])
        return 1

    if not valeurs:
        print("La feuille est vide — pas meme une ligne d'en-tete.")
        return 1

    try:
        feuille.update_acell("A1", valeurs[0][0])
    except Exception as e:
        print("Lecture possible, ECRITURE refusee (%s) — repartager en Editeur."
              % str(e)[:80])
        return 1

    print("%d ligne(s) lues, ecriture autorisee." % (len(valeurs) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
