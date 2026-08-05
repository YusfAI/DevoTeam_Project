from backend.db_layer import build_and_execute_query
intent = {
    "dimension": "country",
    "metric": "budget",
    "chart_type": "bar",
    "filters": {"practice": "Risk Advisory"}
}
results = build_and_execute_query(intent)
print(f"Results for intent: {results}")

intent2 = {
    "dimension": "practice",
    "metric": "nb_opportunities",
    "chart_type": "pie",
    "filters": {}
}
results2 = build_and_execute_query(intent2)
print(f"Results for intent2: {results2}")
