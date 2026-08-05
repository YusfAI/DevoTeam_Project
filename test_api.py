import requests
import json

try:
    print("Sending request 1...")
    res = requests.post("http://127.0.0.1:8001/dashboard", json={"query": "Affiche moi le budget total par pays en barres"})
    print(res.status_code)
    print(json.dumps(res.json(), indent=2))
    
    print("\nSending request 2 (should be cached)...")
    res2 = requests.post("http://127.0.0.1:8001/dashboard", json={"query": "Affiche moi le budget total par pays en barres"})
    print(res2.status_code)
    print(json.dumps(res2.json(), indent=2))
except Exception as e:
    print(f"Failed to connect to API: {e}")
