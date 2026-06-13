"""
Registra los logros de la temporada 2025 via API.
Ejecutar dentro del container: python /code/register_achievements_2025.py

Datos inferidos de fixtures en DB (stage=final/semi/quarter/round_of_16).
Ligas domésticas: asignadas manualmente según contexto de temporada.
"""
import urllib.request, urllib.error, json

BASE = "http://localhost:8000/api/v1/scoring/achievements"
SEASON = "2025"
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
            print(f"  OK  {competition_name:<26} {phase:<15} team={team_id:>5} → id={result['achievement_id']}")
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        if "already exists" in body_err or "duplicate" in body_err.lower() or e.code == 409:
            print(f"  DUP {competition_name:<26} {phase:<15} team={team_id:>5} (ya existe)")
        else:
            print(f"  ERR {competition_name:<26} {phase:<15} team={team_id:>5} → {e.code}: {body_err}")


achievements = [
    # ── Ligas domésticas ──────────────────────────────────────────────────────
    # La Liga  (infered: Barcelona dominant - Yamal, Raphinha; Atletico Copa del Rey)
    (1, 1,   "champion",  "La Liga"),       # Barcelona
    (1, 2,   "runner_up", "La Liga"),       # Real Madrid
    (1, 3,   "top_4",     "La Liga"),       # Atletico Madrid
    (1, 5,   "top_4",     "La Liga"),       # Villarreal
    # Premier League  (Arsenal: CL final + EFL Cup; Liverpool: strong season)
    (3, 42,  "champion",  "Premier League"),  # Arsenal
    (3, 41,  "runner_up", "Premier League"),  # Liverpool
    (3, 43,  "top_4",     "Premier League"),  # Manchester City
    (3, 44,  "top_4",     "Premier League"),  # Chelsea
    # Bundesliga  (Bayern: DFB-Pokal winner + CL semi; Stuttgart: DFL-Supercup winner)
    (6, 61,  "champion",  "Bundesliga"),    # Bayern München
    (6, 69,  "runner_up", "Bundesliga"),    # VfB Stuttgart
    (6, 62,  "top_4",     "Bundesliga"),    # Bayer Leverkusen
    (6, 67,  "top_4",     "Bundesliga"),    # RB Leipzig
    # Serie A  (Napoli: Supercoppa; Lazio: Coppa Italia winner)
    (7, 79,  "champion",  "Serie A"),       # Napoli
    (7, 80,  "runner_up", "Serie A"),       # Inter
    (7, 81,  "top_4",     "Serie A"),       # Atalanta
    (7, 82,  "top_4",     "Serie A"),       # Juventus
    # Ligue 1  (PSG: CL winner + Trophée des Champions; Monaco strong)
    (9, 99,  "champion",  "Ligue 1"),       # Paris Saint Germain
    (9, 101, "runner_up", "Ligue 1"),       # Monaco
    (9, 100, "top_4",     "Ligue 1"),       # Marseille
    (9, 106, "top_4",     "Ligue 1"),       # Lens (Coupe de France winner)

    # ── Champions League ──────────────────────────────────────────────────────
    # Final: PSG 1-0 Arsenal  |  Semis: PSG>Bayern, Arsenal>Atletico
    # Quarters: PSG>Liverpool, Arsenal>Sporting CP, Atletico>Barcelona, Bayern>Real Madrid
    # R16: Liverpool>Galatasaray, Bayern>Atalanta, Barcelona>Newcastle, Atletico>Tottenham
    #       Arsenal>Leverkusen, Real Madrid>Man City, PSG>Chelsea, Sporting CP>Bodo/Glimt
    (10, 99,   "winner",        "Champions League"),  # Paris Saint Germain
    (10, 42,   "runner_up",     "Champions League"),  # Arsenal
    (10, 61,   "semi_final",    "Champions League"),  # Bayern München
    (10, 3,    "semi_final",    "Champions League"),  # Atletico Madrid
    (10, 41,   "quarter_final", "Champions League"),  # Liverpool
    (10, 139,  "quarter_final", "Champions League"),  # Sporting CP
    (10, 1,    "quarter_final", "Champions League"),  # Barcelona
    (10, 2,    "quarter_final", "Champions League"),  # Real Madrid
    (10, 4703, "round_of_16",   "Champions League"),  # Galatasaray
    (10, 81,   "round_of_16",   "Champions League"),  # Atalanta
    (10, 45,   "round_of_16",   "Champions League"),  # Newcastle
    (10, 57,   "round_of_16",   "Champions League"),  # Tottenham
    (10, 62,   "round_of_16",   "Champions League"),  # Bayer Leverkusen
    (10, 43,   "round_of_16",   "Champions League"),  # Manchester City
    (10, 44,   "round_of_16",   "Champions League"),  # Chelsea
    (10, 4693, "round_of_16",   "Champions League"),  # Bodo/Glimt

    # ── Europa League ─────────────────────────────────────────────────────────
    # Final: SC Freiburg > Aston Villa  |  Semis: Freiburg>Forest, Villa>Braga
    # Quarters: Braga>Betis, Villa>Bologna, Freiburg>Celta, Forest>Porto
    # R16: Bologna>Roma, Villa>Lille, Porto>Stuttgart, Betis>Panathinaikos
    #       Forest>Midtjylland, Freiburg>Genk, Braga>Ferencvarosi, Celta>Lyon
    (253, 65,   "winner",        "Europa League"),  # SC Freiburg
    (253, 46,   "runner_up",     "Europa League"),  # Aston Villa
    (253, 47,   "semi_final",    "Europa League"),  # Nottingham Forest
    (253, 7245, "semi_final",    "Europa League"),  # SC Braga
    (253, 87,   "quarter_final", "Europa League"),  # Bologna
    (253, 6,    "quarter_final", "Europa League"),  # Real Betis
    (253, 7,    "quarter_final", "Europa League"),  # Celta Vigo
    (253, 7231, "quarter_final", "Europa League"),  # FC Porto
    (253, 83,   "round_of_16",   "Europa League"),  # AS Roma
    (253, 103,  "round_of_16",   "Europa League"),  # Lille
    (253, 69,   "round_of_16",   "Europa League"),  # VfB Stuttgart
    (253, 7276, "round_of_16",   "Europa League"),  # Panathinaikos
    (253, 4702, "round_of_16",   "Europa League"),  # FC Midtjylland
    (253, 8523, "round_of_16",   "Europa League"),  # Genk
    (253, 7229, "round_of_16",   "Europa League"),  # Ferencvarosi TC
    (253, 104,  "round_of_16",   "Europa League"),  # Lyon

    # ── Conference League ─────────────────────────────────────────────────────
    # Final: Crystal Palace > Rayo Vallecano  |  Semis: Palace>Shakhtar, Rayo>Strasbourg
    # Quarters: Rayo>AEK Athens, Strasbourg>Mainz, Shakhtar>AZ Alkmaar, Palace>Fiorentina
    (254, 52,   "winner",        "Conference League"),  # Crystal Palace
    (254, 8,    "runner_up",     "Conference League"),  # Rayo Vallecano
    (254, 143,  "semi_final",    "Conference League"),  # Shakhtar Donetsk
    (254, 105,  "semi_final",    "Conference League"),  # Strasbourg
    (254, 7587, "quarter_final", "Conference League"),  # AEK Athens FC
    (254, 66,   "quarter_final", "Conference League"),  # FSV Mainz 05
    (254, 7233, "quarter_final", "Conference League"),  # AZ Alkmaar
    (254, 84,   "quarter_final", "Conference League"),  # Fiorentina

    # ── UEFA Super Cup ────────────────────────────────────────────────────────
    # Final: PSG > Tottenham
    (255, 99,  "winner",    "UEFA Super Cup"),   # Paris Saint Germain
    (255, 57,  "runner_up", "UEFA Super Cup"),   # Tottenham

    # ── Community Shield ──────────────────────────────────────────────────────
    # Final: Crystal Palace > Liverpool
    (257, 52,  "winner",    "Community Shield"),  # Crystal Palace
    (257, 41,  "runner_up", "Community Shield"),  # Liverpool

    # ── DFL-Supercup ──────────────────────────────────────────────────────────
    # Final: VfB Stuttgart > Bayern München
    (258, 69,  "winner",    "DFL-Supercup"),     # VfB Stuttgart
    (258, 61,  "runner_up", "DFL-Supercup"),     # Bayern München

    # ── Supercoppa Italiana ───────────────────────────────────────────────────
    # Final: Napoli > Bologna  |  Semis: Napoli>AC Milan, Bologna>Inter
    (259, 79,  "winner",     "Supercoppa Italiana"),  # Napoli
    (259, 87,  "runner_up",  "Supercoppa Italiana"),  # Bologna
    (259, 86,  "semi_final", "Supercoppa Italiana"),  # AC Milan
    (259, 80,  "semi_final", "Supercoppa Italiana"),  # Inter

    # ── Trophée des Champions ─────────────────────────────────────────────────
    # Final: PSG > Marseille
    (260, 99,  "winner",    "Trophée des Champions"),  # Paris Saint Germain
    (260, 100, "runner_up", "Trophée des Champions"),  # Marseille

    # ── Supercopa de España ───────────────────────────────────────────────────
    # Final: Barcelona > Real Madrid  |  Semis: Barcelona>Athletic, Real Madrid>Atletico
    (23, 1,  "winner",     "Supercopa de España"),  # Barcelona
    (23, 2,  "runner_up",  "Supercopa de España"),  # Real Madrid
    (23, 4,  "semi_final", "Supercopa de España"),  # Athletic Club
    (23, 3,  "semi_final", "Supercopa de España"),  # Atletico Madrid

    # ── Copa del Rey ──────────────────────────────────────────────────────────
    # Final: Atletico Madrid > Real Sociedad  |  Semis: Atletico>Barcelona, RealSoc>Athletic
    # Quarters: Atletico>Betis, RealSoc>Alaves, Barcelona>Albacete, Athletic>Valencia
    (22, 3,  "winner",        "Copa del Rey"),  # Atletico Madrid
    (22, 11, "runner_up",     "Copa del Rey"),  # Real Sociedad
    (22, 1,  "semi_final",    "Copa del Rey"),  # Barcelona
    (22, 4,  "semi_final",    "Copa del Rey"),  # Athletic Club
    (22, 6,  "quarter_final", "Copa del Rey"),  # Real Betis
    (22, 15, "quarter_final", "Copa del Rey"),  # Alaves
    (22, 12, "quarter_final", "Copa del Rey"),  # Valencia

    # ── FA Cup ────────────────────────────────────────────────────────────────
    # Final: Chelsea > Manchester City  |  Semis: Chelsea>Leeds, ManCity>Southampton
    # Quarters: ManCity>Liverpool, Chelsea>PortVale, Southampton>Arsenal, Leeds>WestHam
    (90, 44, "winner",        "FA Cup"),  # Chelsea
    (90, 43, "runner_up",     "FA Cup"),  # Manchester City
    (90, 60, "semi_final",    "FA Cup"),  # Southampton
    (90, 8396, "semi_final",  "FA Cup"),  # Leeds
    (90, 41, "quarter_final", "FA Cup"),  # Liverpool
    (90, 42, "quarter_final", "FA Cup"),  # Arsenal
    (90, 54, "quarter_final", "FA Cup"),  # West Ham

    # ── EFL Cup ───────────────────────────────────────────────────────────────
    # Final: Arsenal > Manchester City  |  Semis: Arsenal>Chelsea, ManCity>Newcastle
    # Quarters: Arsenal>Crystal Palace, ManCity>Brentford, Newcastle>Fulham, Chelsea>Cardiff
    (256, 42, "winner",        "EFL Cup"),  # Arsenal
    (256, 43, "runner_up",     "EFL Cup"),  # Manchester City
    (256, 45, "semi_final",    "EFL Cup"),  # Newcastle
    (256, 44, "semi_final",    "EFL Cup"),  # Chelsea
    (256, 52, "quarter_final", "EFL Cup"),  # Crystal Palace
    (256, 50, "quarter_final", "EFL Cup"),  # Brentford
    (256, 51, "quarter_final", "EFL Cup"),  # Fulham

    # ── DFB-Pokal ─────────────────────────────────────────────────────────────
    # Final: Bayern > Stuttgart  |  Semis: Bayern>Leverkusen, Stuttgart>Freiburg
    # Quarters: Bayern>Leipzig, Leverkusen>St.Pauli, Stuttgart>Holstein Kiel, Freiburg>Hertha
    (92, 61, "winner",        "DFB-Pokal"),  # Bayern München
    (92, 69, "runner_up",     "DFB-Pokal"),  # VfB Stuttgart
    (92, 62, "semi_final",    "DFB-Pokal"),  # Bayer Leverkusen
    (92, 65, "semi_final",    "DFB-Pokal"),  # SC Freiburg
    (92, 67, "quarter_final", "DFB-Pokal"),  # RB Leipzig

    # ── Coppa Italia ──────────────────────────────────────────────────────────
    # Final: Lazio > Inter  |  Semis: Lazio>Atalanta, Inter>Como
    # Quarters: Inter>Torino, Atalanta>Juventus, Como>Napoli, Lazio>Bologna
    (94, 85, "winner",        "Coppa Italia"),  # Lazio
    (94, 80, "runner_up",     "Coppa Italia"),  # Inter
    (94, 81, "semi_final",    "Coppa Italia"),  # Atalanta
    (94, 88, "semi_final",    "Coppa Italia"),  # Como
    (94, 79, "quarter_final", "Coppa Italia"),  # Napoli
    (94, 87, "quarter_final", "Coppa Italia"),  # Bologna
    (94, 82, "quarter_final", "Coppa Italia"),  # Juventus

    # ── Coupe de France ───────────────────────────────────────────────────────
    # Final: Lens > Nice  |  Semis: Lens>Toulouse, Nice>Strasbourg
    # Quarters: Lens>Lyon, Nice>Lorient, Strasbourg>Reims, Toulouse>Marseille
    (96, 106, "winner",        "Coupe de France"),  # Lens
    (96, 102, "runner_up",     "Coupe de France"),  # Nice
    (96, 108, "semi_final",    "Coupe de France"),  # Toulouse
    (96, 105, "semi_final",    "Coupe de France"),  # Strasbourg
    (96, 100, "quarter_final", "Coupe de France"),  # Marseille
    (96, 104, "quarter_final", "Coupe de France"),  # Lyon
    (96, 114, "quarter_final", "Coupe de France"),  # Reims
]

print(f"Registrando {len(achievements)} logros para season={SEASON}...\n")
for comp_id, team_id, phase, comp_name in achievements:
    post(comp_id, team_id, phase, comp_name)

print(f"\nListo. Total={len(achievements)}")
