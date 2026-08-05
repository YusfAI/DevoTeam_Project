from backend.llm import parse_user_query
import json

prompts = [
    "Montre-moi le budget par pays pour Risk Advisory",
    "Je veux la répartition des opportunités par practice",
    "Quel est notre budget pour les offres gagnées ?",
    "Donne-moi le nombre d'opportunités par type",
    "Affiche le budget total pour Data Management par mois",
    "Quel est le chiffre d'affaires des offres perdues par pays ?",
    "Montre moi le KPI du budget de Digital Transformation",
    "Fais un camembert des opportunités par source de financement",
    "Quel est le total des offres remportées ?",
    "Affiche moi un truc chelou qui ne veut rien dire avec des djkazhdkja"
]

for p in prompts:
    print(f"\n--- {p} ---")
    try:
        intent = parse_user_query(p)
        print(json.dumps(intent, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Erreur propre récupérée: {e}")
