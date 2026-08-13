import asyncio
import csv
import difflib
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from sfa.domain.scoring_ports import (
    ClubEloIdentityDTO,
    ClubEloRatingDTO,
    ClubEloSourceDTO,
)

CLUBELO_BASE_URL = "http://api.clubelo.com"
MAX_SNAPSHOT_LOOKBACK_DAYS = 3

CLUBELO_NAME_MAP: dict[str, str] = {
    "AEK": "AEK Athens FC",
    "Alkmaar": "AZ Alkmaar",
    "Arda": "Arda Kardzhali",
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
    "Leonesa": "Cultural Leonesa",
    "Levski": "Levski Sofia",
    "Lincoln": "Lincoln Red Imps FC",
    "M Tel Aviv": "Maccabi Tel Aviv",
    "Magdeburg": "1. FC Magdeburg",
    "Malmoe": "Malmo FF",
    "Neman Grodno": "Neman",
    "Omonia": "Omonia Nicosia",
    "Paphos": "Pafos",
    "Polissya Zhytomyr": "Polessya",
    "RFS": "R\u012bgas FS",
    "Rapid Wien": "Rapid Vienna",
    "Rijeka": "HNK Rijeka",
    "Rakow": "Rak\u00f3w Cz\u0119stochowa",
    "Razgrad": "Ludogorets",
    "Santander": "Racing Santander",
    "Shamrock": "Shamrock Rovers",
    "Sheffield Weds": "Sheffield Wednesday",
    "SS Virtus": "Virtus",
    "St Gillis": "Union St. Gilloise",
    "Steaua": "FCSB",
    "Trnava": "Spartak Trnava",
    "Vardar": "Vardar Skopje",
    "Wolfsberg": "Wolfsberger AC",
    "Young Boys": "BSC Young Boys",
    "Zrinjski Mostar": "Zrinjski",
    "Forest": "Nottingham Forest",
    "Gijon": "Sporting Gijon",
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


ClubEloEntry = ClubEloRatingDTO

CLUBELO_HISTORY_IDENTITIES: dict[str, ClubEloIdentityDTO] = {
    "Cardiff": ClubEloIdentityDTO("Cardiff", "Cardiff", "ENG"),
    "Eldense": ClubEloIdentityDTO("Eldense", "Eldense", "ESP"),
    "SSV Jahn Regensburg": ClubEloIdentityDTO(
        "SSV Jahn Regensburg",
        "Regensburg",
        "GER",
    ),
}


class ClubEloProvider:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def fetch_snapshot(self, date_str: str) -> ClubEloSourceDTO:
        requested_date = date.fromisoformat(date_str)
        last_exc: Exception | None = None
        for offset in range(MAX_SNAPSHOT_LOOKBACK_DAYS + 1):
            candidate = requested_date - timedelta(days=offset)
            try:
                source = await self._fetch_source(candidate.isoformat())
                if source.ratings:
                    return source
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_exc = exc
        raise RuntimeError(
            f"No ClubElo snapshot available for {date_str} or the previous "
            f"{MAX_SNAPSHOT_LOOKBACK_DAYS} days"
        ) from last_exc

    async def fetch_history(self, clubelo_identifier: str) -> ClubEloSourceDTO:
        return await self._fetch_source(quote(clubelo_identifier, safe=""))

    def get_history_identity(self, sfa_team_name: str) -> ClubEloIdentityDTO | None:
        return CLUBELO_HISTORY_IDENTITIES.get(sfa_team_name)

    async def _fetch_source(self, path: str) -> ClubEloSourceDTO:
        url = f"{CLUBELO_BASE_URL}/{path}"
        last_exc: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=False,
        ) as client:
            for attempt in range(2):
                try:
                    response = await client.get(url)
                    if response.is_redirect:
                        raise RuntimeError("ClubElo redirects are not allowed")
                    if response.status_code == 404:
                        payload = response.content
                    else:
                        response.raise_for_status()
                        payload = response.content
                    return ClubEloSourceDTO(
                        source_reference=url,
                        fetched_at=datetime.now(timezone.utc),
                        payload_sha256=hashlib.sha256(payload).hexdigest(),
                        ratings=tuple(_parse_csv(response.text)),
                    )
                except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                    last_exc = exc
                    retryable = (
                        isinstance(exc, httpx.TimeoutException)
                        or exc.response.status_code == 429
                        or exc.response.status_code >= 500
                    )
                    if not retryable or attempt == 1:
                        raise
                    await asyncio.sleep(2)
        raise RuntimeError("ClubElo request failed") from last_exc

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


def _parse_csv(text: str) -> list[ClubEloRatingDTO]:
    reader = csv.DictReader(io.StringIO(text))
    entries: list[ClubEloRatingDTO] = []
    for row in reader:
        try:
            entries.append(
                ClubEloRatingDTO(
                    club_name=row["Club"],
                    country=row["Country"],
                    level=int(row["Level"]),
                    elo=float(row["Elo"]),
                    valid_from=_parse_date(row.get("From")),
                    valid_to=_parse_date(row.get("To")),
                )
            )
        except (KeyError, ValueError):
            continue
    return entries


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)
