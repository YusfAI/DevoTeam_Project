import json
from backend.vega_generator import build_vega_spec

def test_bar():
    intent = {
        "goal": "Budget par pays",
        "metric": "budget",
        "dimension": "country",
        "chart_type": "bar",
        "aggregation": "sum"
    }
    data = [
        {"country": "France", "budget": 1000000},
        {"country": "UK", "budget": 500000},
        {"country": "Germany", "budget": None} # Testing NULL
    ]
    spec = build_vega_spec(intent, data)
    print("Bar Spec:", json.dumps(spec, indent=2))

def test_pie():
    intent = {
        "goal": "Répartition par practice",
        "metric": "nb_opportunities",
        "dimension": "practice",
        "chart_type": "pie",
        "aggregation": "sum"
    }
    data = [
        {"practice": "Risk Advisory", "nb_opportunities": 10},
        {"practice": "Data Management", "nb_opportunities": 20}
    ]
    spec = build_vega_spec(intent, data)
    print("Pie Spec:", json.dumps(spec, indent=2))

if __name__ == "__main__":
    test_bar()
    test_pie()
    print("All tests passed.")
