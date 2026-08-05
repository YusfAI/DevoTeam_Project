from backend.llm import parse_user_query

queries = [
    "C'est quoi le CA des data ?",
    "montre les revenus en france stp",
    "Quel est notre taux de réussite pour la practice risque ? "
]

for q in queries:
    print(f"\n--- {q} ---")
    try:
        res = parse_user_query(q)
        print("Success:", res)
    except Exception as e:
        print("Failed:", repr(e))
