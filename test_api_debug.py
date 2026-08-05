import requests

queries = [
    "C'est quoi le CA des data ?",
    "Affiche le volume d'affaires remportées par mois",
    "montre les revenus en france stp",
    "Quel est notre taux de réussite pour la practice risque ? ",
    "Combien on a d'opportunités en ce moment ?",
    "Fais moi un camembert des statuts pour voir où on en est."
]

for q in queries:
    print(f"\n--- {q} ---")
    try:
        res = requests.post("http://127.0.0.1:8001/dashboard", json={"query": q})
        if res.status_code != 200:
            print(f"ERROR {res.status_code}: {res.json()}")
        else:
            data = res.json()
            if "vega_spec" in data:
                print("SUCCESS: Vega Spec returned")
                print("Data length:", len(data["vega_spec"]["data"]["values"]))
            if "ai_message" in data:
                print("AI:", data["ai_message"])
    except Exception as e:
        print("Crash:", e)
