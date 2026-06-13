"""
Registra los logros de la temporada 2024 via API.
Ejecutar dentro del container: python /code/register_achievements.py
"""
import urllib.request, urllib.error, json, sys

BASE = "http://localhost:8000/api/v1/scoring/achievements"
SEASON = "2024"
RV = 3


def post(competition_id, team_id, phase, competition_name):
    body = json.dumps({
        "competition_id": competition_id,
        "team_id": team_id,
        "season": SEASON,
        "phase": phase,
        "rules_version_id": RV,
        "competition_name": competition_name,
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            result = json.load(r)
            print(f"  OK  {competition_name:<22} {phase:<15} team={team_id} → id={result['achievement_id']}")
    except urllib.error.HTTPError as e:
        print(f"  ERR {competition_name:<22} {phase:<15} team={team_id} → {e.code}: {e.read().decode()}")


achievements = [
    # ── Ligas domésticas ──────────────────────────────────────────────────
    # La Liga
    (1, 1,   "champion",  "La Liga"),
    (1, 2,   "runner_up", "La Liga"),
    (1, 3,   "top_4",     "La Liga"),
    (1, 4,   "top_4",     "La Liga"),
    # Premier League
    (3, 41,  "champion",  "Premier League"),
    (3, 42,  "runner_up", "Premier League"),
    (3, 43,  "top_4",     "Premier League"),
    (3, 44,  "top_4",     "Premier League"),
    # Bundesliga
    (6, 61,  "champion",  "Bundesliga"),
    (6, 62,  "runner_up", "Bundesliga"),
    (6, 63,  "top_4",     "Bundesliga"),
    (6, 64,  "top_4",     "Bundesliga"),
    # Serie A
    (7, 79,  "champion",  "Serie A"),
    (7, 80,  "runner_up", "Serie A"),
    (7, 81,  "top_4",     "Serie A"),
    (7, 82,  "top_4",     "Serie A"),
    # Ligue 1
    (9, 99,  "champion",  "Ligue 1"),
    (9, 100, "runner_up", "Ligue 1"),
    (9, 101, "top_4",     "Ligue 1"),
    (9, 102, "top_4",     "Ligue 1"),

    # ── Champions League ──────────────────────────────────────────────────
    (10, 99,  "winner",       "Champions League"),  # PSG
    (10, 80,  "semi_final",   "Champions League"),  # Inter (final)
    (10, 42,  "semi_final",   "Champions League"),  # Arsenal
    (10, 1,   "semi_final",   "Champions League"),  # Barcelona
    (10, 46,  "quarter_final","Champions League"),  # Aston Villa
    (10, 61,  "quarter_final","Champions League"),  # Bayern München
    (10, 64,  "quarter_final","Champions League"),  # Borussia Dortmund
    (10, 2,   "quarter_final","Champions League"),  # Real Madrid
    (10, 3,   "round_of_16", "Champions League"),   # Atletico Madrid
    (10, 62,  "round_of_16", "Champions League"),   # Bayer Leverkusen
    (10, 132, "round_of_16", "Champions League"),   # Benfica
    (10, 140, "round_of_16", "Champions League"),   # Club Brugge KV
    (10, 135, "round_of_16", "Champions League"),   # Feyenoord
    (10, 103, "round_of_16", "Champions League"),   # Lille
    (10, 41,  "round_of_16", "Champions League"),   # Liverpool
    (10, 130, "round_of_16", "Champions League"),   # PSV Eindhoven

    # ── Europa League ─────────────────────────────────────────────────────
    (253, 57,   "winner",       "Europa League"),   # Tottenham
    (253, 55,   "semi_final",   "Europa League"),   # Man Utd (final)
    (253, 4,    "semi_final",   "Europa League"),   # Athletic Club
    (253, 4693, "semi_final",   "Europa League"),   # Bodo/Glimt
    (253, 63,   "quarter_final","Europa League"),   # Eintracht Frankfurt
    (253, 85,   "quarter_final","Europa League"),   # Lazio
    (253, 104,  "quarter_final","Europa League"),   # Lyon
    (253, 7211, "quarter_final","Europa League"),   # Rangers
    (253, 83,   "round_of_16", "Europa League"),    # AS Roma
    (253, 7233, "round_of_16", "Europa League"),    # AZ Alkmaar
    (253, 7219, "round_of_16", "Europa League"),    # Ajax
    (253, 4695, "round_of_16", "Europa League"),    # FCSB
    (253, 409,  "round_of_16", "Europa League"),    # Fenerbahce
    (253, 7208, "round_of_16", "Europa League"),    # Olympiakos
    (253, 7227, "round_of_16", "Europa League"),    # Plzen
    (253, 11,   "round_of_16", "Europa League"),    # Real Sociedad

    # ── Conference League ─────────────────────────────────────────────────
    (254, 44,   "winner",       "Conference League"),   # Chelsea
    (254, 6,    "semi_final",   "Conference League"),   # Real Betis (final)
    (254, 7505, "semi_final",   "Conference League"),   # Djurgardens IF
    (254, 84,   "semi_final",   "Conference League"),   # Fiorentina
    (254, 4700, "quarter_final","Conference League"),   # Celje
    (254, 7277, "quarter_final","Conference League"),   # Jagiellonia
    (254, 7507, "quarter_final","Conference League"),   # Legia Warszawa
    (254, 7284, "quarter_final","Conference League"),   # Rapid Vienna

    # ── Copas domésticas mayores ──────────────────────────────────────────
    (90,  52, "winner", "FA Cup"),          # Crystal Palace
    (90,  43, "runner_up", "FA Cup"),       # Manchester City
    (256, 41, "winner", "EFL Cup"),         # Liverpool
    (256, 45, "runner_up", "EFL Cup"),      # Newcastle
    (22,  1,  "winner", "Copa del Rey"),    # Barcelona
    (22,  2,  "runner_up", "Copa del Rey"), # Real Madrid
    (94,  86, "winner", "Coppa Italia"),    # AC Milan
    (94,  87, "runner_up", "Coppa Italia"), # Bologna
    (96,  99, "winner", "Coupe de France"), # PSG
    (96,  114,"runner_up", "Coupe de France"), # Reims
    (92,  69, "winner", "DFB-Pokal"),       # VfB Stuttgart
    (92,  1987,"runner_up", "DFB-Pokal"),   # Arminia Bielefeld
]

print(f"Registrando {len(achievements)} logros...\n")
for comp_id, team_id, phase, comp_name in achievements:
    post(comp_id, team_id, phase, comp_name)

print("\nListo.")
