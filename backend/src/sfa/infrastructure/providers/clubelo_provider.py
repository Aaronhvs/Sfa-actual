import csv
import difflib
import io
import re
import unicodedata
from dataclasses import dataclass

import httpx

CLUBELO_BASE_URL = "http://api.clubelo.com"

CLUBELO_NAME_MAP: dict[str, str] = {
    "AEK": "AEK Athens FC",
    "Alkmaar": "AZ Alkmaar",
    "Ararat": "Ararat-Armenia",
    "Beer-Sheva": "Hapoel Beer Sheva",
    "Bueyueksehir": "Ba\u015fak\u015fehir",
    "CFR Cluj": "CFR 1907 Cluj",
    "Craiova": "Universitatea Craiova",
    "Differdang": "FC Differdange 03",
    "Dundee United": "Dundee Utd",
    "Duesseldorf": "Fortuna D\u00fcsseldorf",
    "Haecken": "BK Hacken",
    "Hamrun": "Hamrun Spartans",
    "Holstein": "Holstein Kiel",
    "Ilves Tampere": "Ilves",
    "Karabakh Agdam": "Qarabag",
    "Karlsruhe": "Karlsruher SC",
    "Kuopio": "KuPS",
    "Larnaca": "AEK Larnaca",
    "Lech": "Lech Poznan",
    "Levski": "Levski Sofia",
    "Lincoln": "Lincoln Red Imps FC",
    "M Tel Aviv": "Maccabi Tel Aviv",
    "Magdeburg": "1. FC Magdeburg",
    "Malmoe": "Malmo FF",
    "Neman Grodno": "Neman",
    "Omonia": "Omonia Nicosia",
    "Paphos": "Pafos",
    "RFS": "R\u012bgas FS",
    "Rapid Wien": "Rapid Vienna",
    "Rijeka": "HNK Rijeka",
    "Santander": "Racing Santander",
    "Shamrock": "Shamrock Rovers",
    "Sheffield Weds": "Sheffield Wednesday",
    "SS Virtus": "Virtus",
    "St Gillis": "Union St. Gilloise",
    "Trnava": "Spartak Trnava",
    "Vardar": "Vardar Skopje",
    "Wolfsberg": "Wolfsberger AC",
    "Young Boys": "BSC Young Boys",
    "Zrinjski Mostar": "Zrinjski",
    "Bielefeld": "Arminia Bielefeld",
    "Bayern": "Bayern München",
    "Basel": "FC Basel 1893",
    "Bradford City": "Bradford",
    "Braunschweig": "Eintracht Braunschweig",
    "Brugge": "Club Brugge KV",
    "Cambridge": "Cambridge United",
    "Cardiff City": "Cardiff",
    "Cottbus": "Energie Cottbus",
    "Dresden": "Dynamo Dresden",
    "Entella": "Virtus Entella",
    "Exeter": "Exeter City",
    "FC Kobenhavn": "FC Copenhagen",
    "Halle": "Hallescher FC",
    "Hamburg": "Hamburger SV",
    "Hertha": "Hertha BSC",
    "Hull": "Hull City",
    "Kairat": "Kairat Almaty",
    "Kobenhavn": "FC Copenhagen",
    "Koeln": "1. FC Köln",
    "Legia": "Legia Warszawa",
    "Malmo": "Malmo FF",
    "Mansfield": "Mansfield Town",
    "Olympiakos": "Olympiakos Piraeus",
    "Oxford": "Oxford United",
    "PSV": "PSV Eindhoven",
    "Regensburg": "SSV Jahn Regensburg",
    "Roma": "AS Roma",
    "Rostock": "Hansa Rostock",
    "Salzburg": "Red Bull Salzburg",
    "Shakhtar": "Shakhtar Donetsk",
    "Shrewsbury": "Shrewsbury Town",
    "Stoke": "Stoke City",
    "Troyes": "Estac Troyes",
    "Union SG": "Union St. Gilloise",
    "Viktoria Plzen": "Plzen",
    "Vicenza": "Vicenza Virtus",
    "Wigan Athletic": "Wigan",
    "Wycombe Wanderers": "Wycombe",
    "Paris SG": "Paris Saint-Germain",
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Atletico": "Atletico Madrid",
    "Sociedad": "Real Sociedad",
    "Bilbao": "Athletic Club",
    "Dortmund": "Borussia Dortmund",
    "Leverkusen": "Bayer Leverkusen",
    "Gladbach": "Borussia Monchengladbach",
    "Wolfsburg": "VfL Wolfsburg",
    "Hannover": "Hannover 96",
    "Koln": "FC Koln",
    "Nurnberg": "FC Nurnberg",
    "Frankfurt": "Eintracht Frankfurt",
    "Schalke": "Schalke 04",
    "Stuttgart": "VfB Stuttgart",
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
        candidates = list(dict.fromkeys((
            CLUBELO_NAME_MAP.get(clubelo_name, clubelo_name),
            clubelo_name,
        )))
        for candidate in candidates:
            if candidate in sfa_team_names:
                return candidate

        normalized_lookup = _unique_lookup(sfa_team_names, _normalize_name)
        for candidate in candidates:
            match = normalized_lookup.get(_normalize_name(candidate))
            if match is not None:
                return match

        core_lookup = _unique_lookup(sfa_team_names, _core_name)
        for candidate in candidates:
            core = _core_name(candidate)
            if core and (match := core_lookup.get(core)) is not None:
                return match

        normalized_sfa = {
            _normalize_name(team_name): team_name
            for team_name in sfa_team_names
        }
        for candidate in candidates:
            matches = difflib.get_close_matches(
                _normalize_name(candidate),
                list(normalized_sfa),
                n=2,
                cutoff=0.88,
            )
            if len(matches) == 1:
                return normalized_sfa[matches[0]]
        return None


_CORE_TOKENS = {
    "ac", "afc", "as", "cd", "cf", "fc", "fk", "kv", "sc", "ssc", "sv",
    "01", "03", "07", "1893", "1899", "1924",
}


def _normalize_name(value: str) -> str:
    translations = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ß": "ss"})
    value = unicodedata.normalize("NFKD", value.translate(translations))
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().replace("&", " and ")
    value = value.replace("oe", "o").replace("ue", "u").replace("ae", "a")
    return re.sub(r"[^a-z0-9]+", "", value)


def _core_name(value: str) -> str:
    translations = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ß": "ss"})
    value = unicodedata.normalize("NFKD", value.translate(translations))
    value = "".join(char for char in value if not unicodedata.combining(char))
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    significant = [token for token in tokens if token not in _CORE_TOKENS]
    return "".join(significant)


def _unique_lookup(values: list[str], normalizer) -> dict[str, str]:
    lookup: dict[str, str] = {}
    duplicates: set[str] = set()
    for value in values:
        key = normalizer(value)
        if key in lookup:
            duplicates.add(key)
        else:
            lookup[key] = value
    for key in duplicates:
        lookup.pop(key, None)
    return lookup


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
