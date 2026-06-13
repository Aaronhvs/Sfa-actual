import csv
import difflib
import io
from dataclasses import dataclass

import httpx

CLUBELO_BASE_URL = "http://api.clubelo.com"

CLUBELO_NAME_MAP: dict[str, str] = {
    "Paris SG": "Paris Saint-Germain",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Atletico": "Atletico Madrid",
    "Sociedad": "Real Sociedad",
    "Bilbao": "Athletic Club",
    "Dortmund": "Borussia Dortmund",
    "Leverkusen": "Bayer Leverkusen",
    "Gladbach": "Borussia Monchengladbach",
    "Wolfsburg": "Wolfsburg",
    "Hannover": "Hannover 96",
    "Koln": "FC Koln",
    "Nurnberg": "FC Nurnberg",
    "Frankfurt": "Eintracht Frankfurt",
    "Schalke": "Schalke 04",
    "Stuttgart": "VfB Stuttgart",
    "Hertha": "Hertha Berlin",
    "Newcastle": "Newcastle United",
    "Brighton": "Brighton & Hove Albion",
    "Spurs": "Tottenham Hotspur",
    "Wolves": "Wolverhampton Wanderers",
    "Leicester": "Leicester City",
    "Nottm Forest": "Nottingham Forest",
    "Sheffield Utd": "Sheffield United",
    "Luton": "Luton Town",
    "Burnley": "Burnley",
    "Brentford": "Brentford",
    "Fulham": "Fulham",
    "Bournemouth": "Bournemouth",
    "Sevilla": "Sevilla",
    "Villarreal": "Villarreal",
    "Betis": "Real Betis",
    "Celta": "Celta Vigo",
    "Osasuna": "Osasuna",
    "Getafe": "Getafe",
    "Almeria": "Almeria",
    "Girona": "Girona",
    "Las Palmas": "Las Palmas",
    "Alaves": "Deportivo Alaves",
    "Vallecano": "Rayo Vallecano",
    "Cadiz": "Cadiz",
    "Udinese": "Udinese",
    "Monza": "Monza",
    "Frosinone": "Frosinone",
    "Cagliari": "Cagliari",
    "Salernitana": "Salernitana",
    "Verona": "Hellas Verona",
    "Lecce": "Lecce",
    "Genoa": "Genoa",
    "Empoli": "Empoli",
    "Sassuolo": "Sassuolo",
    "Spezia": "Spezia",
    "Cremonese": "Cremonese",
    "Lens": "RC Lens",
    "Rennes": "Stade Rennais",
    "Marseille": "Olympique de Marseille",
    "Lyon": "Olympique Lyonnais",
    "Lille": "LOSC Lille",
    "Nantes": "FC Nantes",
    "Nice": "OGC Nice",
    "Strasbourg": "RC Strasbourg",
    "Montpellier": "Montpellier HSC",
    "Reims": "Stade de Reims",
    "Metz": "FC Metz",
    "Lorient": "FC Lorient",
    "Brest": "Stade Brestois",
    "Clermont": "Clermont Foot",
    "Ajaccio": "AC Ajaccio",
    "Auxerre": "AJ Auxerre",
    "Toulouse": "Toulouse FC",
    "RB Leipzig": "RB Leipzig",
    "Augsburg": "FC Augsburg",
    "Freiburg": "SC Freiburg",
    "Hoffenheim": "TSG 1899 Hoffenheim",
    "Mainz": "1. FSV Mainz 05",
    "Bochum": "VfL Bochum",
    "Heidenheim": "1. FC Heidenheim",
    "Darmstadt": "SV Darmstadt 98",
    "Union Berlin": "Union Berlin",
    "Werder": "Werder Bremen",
}


@dataclass(frozen=True)
class ClubEloEntry:
    club_name: str
    country: str
    level: int
    elo: float


class ClubEloProvider:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def fetch_snapshot(self, date_str: str) -> list[ClubEloEntry]:
        url = f"{CLUBELO_BASE_URL}/{date_str}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
        return _parse_csv(response.text)

    def resolve_team_name(self, clubelo_name: str, sfa_team_names: list[str]) -> str | None:
        normalized = CLUBELO_NAME_MAP.get(clubelo_name, clubelo_name)
        if normalized in sfa_team_names:
            return normalized
        matches = difflib.get_close_matches(normalized, sfa_team_names, n=1, cutoff=0.75)
        return matches[0] if matches else None


def _parse_csv(text: str) -> list[ClubEloEntry]:
    reader = csv.DictReader(io.StringIO(text))
    entries: list[ClubEloEntry] = []
    for row in reader:
        try:
            entries.append(
                ClubEloEntry(
                    club_name=row["Club"],
                    country=row["Country"],
                    level=int(row["Level"]),
                    elo=float(row["Elo"]),
                )
            )
        except (KeyError, ValueError):
            continue
    return entries
