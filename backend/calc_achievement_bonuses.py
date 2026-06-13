"""
Dispara calculate-achievement-bonuses para todas las competiciones con logros.
"""
import urllib.request, json

BASE = "http://localhost:8000/api/v1/scoring/achievements/calculate-bonuses"
SEASON = "2024"
RV = 3

competitions = [
    (1,   "La Liga"),
    (3,   "Premier League"),
    (6,   "Bundesliga"),
    (7,   "Serie A"),
    (9,   "Ligue 1"),
    (10,  "Champions League"),
    (253, "Europa League"),
    (254, "Conference League"),
    (90,  "FA Cup"),
    (256, "EFL Cup"),
    (22,  "Copa del Rey"),
    (94,  "Coppa Italia"),
    (96,  "Coupe de France"),
    (92,  "DFB-Pokal"),
]

for comp_id, name in competitions:
    body = json.dumps({"season": SEASON, "competition_id": comp_id, "rules_version_id": RV}).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        result = json.load(r)
        print(f"  queued  {name:<22}  task={result['task_id'][:8]}...")

print("\nTodas en cola. Esperar logs del worker.")
