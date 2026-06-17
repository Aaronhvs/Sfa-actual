from __future__ import annotations

import difflib
import html
import re
import unicodedata
from datetime import date
from urllib.parse import urlparse

import httpx

from sfa.domain.scoring_ports import NationalTeamEloEntry

DEFAULT_NATIONAL_ELO_URL = "https://www.eloratings.net/"

NATIONAL_TEAM_NAME_MAP: dict[str, str] = {
    "Cape Verde": "Cape Verde Islands",
    "DR Congo": "Congo DR",
    "Iran": "IR Iran",
    "Korea Rep": "South Korea",
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "Netherlands": "Netherlands",
    "Republic of Ireland": "Ireland",
    "Turkiye": "Turkey",
    "Turkey": "Turkiye",
    "United States": "USA",
    "United States of America": "USA",
}


class NationalTeamEloProvider:
    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def fetch_snapshot(
        self,
        source_url: str | None = None,
        manual_entries: list[NationalTeamEloEntry] | None = None,
    ) -> list[NationalTeamEloEntry]:
        if manual_entries is not None:
            return manual_entries

        url = _normalize_eloratings_source_url(source_url or DEFAULT_NATIONAL_ELO_URL)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            if _is_eloratings_tsv_url(url):
                teams_response = await client.get(
                    _eloratings_teams_url(url),
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                teams_response.raise_for_status()
                source_date = response.headers.get("Last-Modified") or date.today().isoformat()
                return parse_eloratings_tsv(response.text, teams_response.text, source_date)
        return parse_national_team_elo(response.text)

    def resolve_team_name(self, source_name: str, sfa_team_names: list[str]) -> str | None:
        normalized = NATIONAL_TEAM_NAME_MAP.get(source_name, source_name)
        if normalized in sfa_team_names:
            return normalized

        normalized_lookup = {
            _normalize_name(team_name): team_name
            for team_name in sfa_team_names
        }
        direct = normalized_lookup.get(_normalize_name(normalized))
        if direct is not None:
            return direct

        matches = difflib.get_close_matches(
            _normalize_name(normalized),
            list(normalized_lookup.keys()),
            n=1,
            cutoff=0.78,
        )
        return normalized_lookup[matches[0]] if matches else None


def parse_national_team_elo(raw: str) -> list[NationalTeamEloEntry]:
    text = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text.replace(";", " "))
    source_date = _extract_source_date(text)

    entries: list[NationalTeamEloEntry] = []
    seen: set[str] = set()
    ranked_pattern = re.compile(
        r"(?:^|\s)(?P<rank>\d{1,3})\.\s+"
        r"(?:(?:\d{1,3})\.\s+)?"
        r"(?P<name>[A-Za-z][A-Za-z .&'()/-]{1,60}?)\s+"
        r"(?P<elo>\d{3,4})(?=\D|$)"
    )
    plain_pattern = re.compile(
        r"(?:^|\s)(?P<name>[A-Z][^\d]{1,60}?)\s+"
        r"(?P<elo>\d{3,4})(?=\D|$)"
    )
    for match in ranked_pattern.finditer(text):
        _append_entry(entries, seen, match.group("name"), match.group("elo"), match.group("rank"), source_date)
    if entries:
        return entries

    for match in plain_pattern.finditer(text):
        _append_entry(entries, seen, match.group("name"), match.group("elo"), None, source_date)
    return entries


def parse_eloratings_tsv(
    raw: str,
    team_dictionary_raw: str,
    source_date: str | None = None,
) -> list[NationalTeamEloEntry]:
    code_to_name = _parse_eloratings_team_dictionary(team_dictionary_raw)
    entries: list[NationalTeamEloEntry] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        fields = line.split("\t")
        if len(fields) < 4:
            continue
        rank, global_rank, code, elo_raw = fields[:4]
        if not rank.isdigit() or not global_rank.isdigit() or not elo_raw.isdigit():
            continue
        name = code_to_name.get(code)
        if name is None or name in seen:
            continue
        seen.add(name)
        entries.append(NationalTeamEloEntry(
            country_name=name,
            elo_raw=float(elo_raw),
            rank=int(global_rank),
            source_date=source_date or date.today().isoformat(),
        ))
    return entries


def _append_entry(
    entries: list[NationalTeamEloEntry],
    seen: set[str],
    raw_name: str,
    raw_elo: str,
    raw_rank: str | None,
    source_date: str,
) -> None:
    name = raw_name.strip(" .")
    if not _looks_like_team_name(name):
        return
    if name in seen:
        return
    seen.add(name)
    entries.append(NationalTeamEloEntry(
        country_name=name,
        elo_raw=float(raw_elo),
        rank=int(raw_rank) if raw_rank is not None else None,
        source_date=source_date,
    ))


def _extract_source_date(text: str) -> str:
    match = re.search(r"as of ([A-Za-z]{3} [A-Za-z]{3} \d{1,2} \d{4})", text)
    return match.group(1) if match else date.today().isoformat()


def _normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _looks_like_team_name(name: str) -> bool:
    rejected = {
        "Ratings and Statistics as of",
        "World Football Elo Ratings",
        "Rank",
        "Team",
    }
    if name in rejected:
        return False
    return any(char.isalpha() for char in name) and len(name) <= 60


def _parse_eloratings_team_dictionary(raw: str) -> dict[str, str]:
    teams: dict[str, str] = {}
    for line in raw.splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        code = fields[0]
        if code.endswith("_loc"):
            continue
        teams[code] = fields[1]
    return teams


def _normalize_eloratings_source_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc not in {"eloratings.net", "www.eloratings.net"}:
        return url
    if parsed.path in {"", "/"} or parsed.path.endswith(".tsv"):
        return url
    return f"{url.rstrip('/')}.tsv"


def _is_eloratings_tsv_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in {"eloratings.net", "www.eloratings.net"} and parsed.path.endswith(".tsv")


def _eloratings_teams_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/en.teams.tsv"
