from __future__ import annotations

import json

import httpx

from sfa.domain.ranking_explanation_ports import (
    RankingExplanationEvidenceDTO,
    RankingExplanationWriteResultDTO,
)

TEXT_REPLACEMENTS_ES = {
    "World Cup": "Mundial",
    "FIFA World Cup 2026": "Mundial 2026",
    "Algeria": "Argelia",
    "Belgium": "Bélgica",
    "Brazil": "Brasil",
    "Canada": "Canadá",
    "Cape Verde": "Cabo Verde",
    "Congo DR": "R.D. Congo",
    "Croatia": "Croacia",
    "Czechia": "Chequia",
    "Ecuador": "Ecuador",
    "Egypt": "Egipto",
    "England": "Inglaterra",
    "France": "Francia",
    "Germany": "Alemania",
    "Haiti": "Haití",
    "Iran": "Irán",
    "Iraq": "Irak",
    "Ivory Coast": "Costa de Marfil",
    "Japan": "Japón",
    "Jordan": "Jordania",
    "Korea Republic": "Corea del Sur",
    "Mexico": "México",
    "Morocco": "Marruecos",
    "Netherlands": "Países Bajos",
    "New Zealand": "Nueva Zelanda",
    "Norway": "Noruega",
    "Panama": "Panamá",
    "Qatar": "Catar",
    "Saudi Arabia": "Arabia Saudita",
    "Scotland": "Escocia",
    "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur",
    "Spain": "España",
    "Sweden": "Suecia",
    "Switzerland": "Suiza",
    "Tunisia": "Túnez",
    "Turkey": "Turquía",
    "Türkiye": "Turquía",
    "USA": "Estados Unidos",
    "United States": "Estados Unidos",
    "Uzbekistan": "Uzbekistán",
}


def _sanitize_output_text(text: str) -> str:
    result = text
    for source, target in sorted(TEXT_REPLACEMENTS_ES.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(source, target)
    return result


class DeterministicRankingExplanationWriter:
    async def write(
        self,
        evidence: RankingExplanationEvidenceDTO,
    ) -> RankingExplanationWriteResultDTO:
        data = evidence.evidence
        player = data["player"]
        comparison = data.get("comparison", {})
        top_events = data.get("top_events", [])
        match_summaries = data.get("match_summaries", [])
        breakdown = data.get("breakdown", {})

        name = player["name"]
        rank = player["rank"]
        total = round(float(player["total_pts"]), 2)
        matches = int(player.get("matches") or 0)
        goals = int(player.get("goals") or 0)
        assists = int(player.get("assists") or 0)
        ppg = comparison.get("points_per_match")
        gap = comparison.get("gap_to_leader", 0)
        b1_label = player.get("b1_bonus_label")
        b1_pts = round(float(player.get("b1_bonus_pts") or 0), 2)
        achievement = round(float(player.get("achievement_bonus_pts") or 0), 2)

        impact_parts = []
        if goals:
            impact_parts.append(f"{goals} goles")
        if assists:
            impact_parts.append(f"{assists} asistencias")
        if achievement > 0:
            impact_parts.append(f"{achievement:g} pts por recorrido")
        if b1_pts > 0 and b1_label:
            impact_parts.append(f"bonus {b1_label.lower()} de {b1_pts:g} pts")
        if not impact_parts:
            impact_parts.append("produccion acumulada en acciones de juego")

        best_event = top_events[0] if top_events else None
        best_match = match_summaries[0] if match_summaries else None
        goal_matches = [m for m in match_summaries if int(m.get("goals") or 0) > 0]
        hat_tricks = [m for m in match_summaries if int(m.get("goals") or 0) >= 3]
        event_sentence = ""
        if best_event:
            event_sentence = (
                f" Su accion mas pesada fue {best_event.get('action_type')} ante "
                f"{best_event.get('home_team')} vs {best_event.get('away_team')}, "
                f"valorada en {round(float(best_event.get('final_points') or 0), 2):g} pts."
            )
        match_sentence = ""
        if hat_tricks:
            match = hat_tricks[0]
            match_sentence = (
                f" Su partido mas llamativo fue ante {match.get('home_team')} vs {match.get('away_team')}, "
                f"donde firmo {int(match.get('goals') or 0)} goles."
            )
        elif best_match:
            match_sentence = (
                f" Su partido de mayor peso fue ante {best_match.get('home_team')} vs {best_match.get('away_team')}, "
                f"con {round(float(best_match.get('total_points') or 0), 2):g} pts."
            )

        short = (
            f"#{rank}: {name} suma {total:g} pts en {matches} partidos: "
            f"{', '.join(impact_parts[:2])}."
        )
        long = (
            f"{name} aparece en el puesto {rank} porque su puntaje no depende solo del volumen: "
            f"el motor SFA pondera rival, fase, minuto y contexto de marcador. En este scope acumula "
            f"{total:g} pts en {matches} partidos"
        )
        if ppg:
            long += f", con {ppg:g} pts por partido"
        if rank > 1 and gap:
            long += f", a {round(float(gap), 2):g} pts del lider"
        long += f". Su perfil combina {', '.join(impact_parts)}"
        if goal_matches and matches:
            long += f" y marco en {len(goal_matches)} de {matches} partidos"
        long += f".{match_sentence}{event_sentence}"

        bullets = [
            f"{total:g} puntos SFA en {matches} partidos.",
            f"Produccion directa: {goals} goles y {assists} asistencias.",
        ]
        if best_event:
            bullets.append(
                f"Evento clave: {best_event.get('action_type')} por "
                f"{round(float(best_event.get('final_points') or 0), 2):g} pts."
            )
        if hat_tricks:
            match = hat_tricks[0]
            bullets.append(
                f"Partido destacado: {int(match.get('goals') or 0)} goles en "
                f"{match.get('home_team')} vs {match.get('away_team')}."
            )
        if breakdown:
            top_action = max(breakdown.items(), key=lambda item: float(item[1].get("pts") or 0))
            top_action_points = round(float(top_action[1].get("pts") or 0), 2)
            bullets.append(f"Mayor fuente de puntos: {top_action[0]} ({top_action_points:g} pts).")

        return RankingExplanationWriteResultDTO(
            short_text=_sanitize_output_text(short)[:280],
            long_text=_sanitize_output_text(long)[:1800],
            bullets=[_sanitize_output_text(item) for item in bullets[:4]],
            variant="deterministic",
            status="fallback",
            model_name="deterministic-sfa-v1",
        )


class OpenAICompatibleRankingExplanationWriter:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        timeout_seconds: int = 20,
        max_output_tokens: int = 700,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens

    async def write(
        self,
        evidence: RankingExplanationEvidenceDTO,
    ) -> RankingExplanationWriteResultDTO:
        prompt = (
            "Eres analista de Stats Football Award (SFA). Explicas a un aficionado que no conoce "
            "el sistema por que un jugador ocupa su puesto, de forma que lo entienda y quiera "
            "discutirlo. No vendes stats: cuentas el rendimiento real del jugador y muestras por "
            "que el sistema lo valora. El criterio de fondo se dice una sola vez: SFA mide impacto "
            "real, no volumen de minutos. Espanol neutro. Directo, seguro, premium. Nunca sonar a "
            "robot ni a lista de datos. "
            "Usa solo el JSON de evidencia. No inventes goles, rivales, minutos, marcadores, records "
            "ni resultados. La distribucion de goles debe salir de top_events, match_summaries o "
            "impact_minutes. Consecuencias como clasifico, remonto o sentencio solo pueden aparecer "
            "si el JSON trae esa consecuencia de forma explicita. Si no, describe fase, minuto y "
            "marcador, pero no afirmes la consecuencia. Si el evento es goal_penalty, di de penal y "
            "no lo vendas como remate dificil: su valor esta en el momento. "
            "Solo puedes mencionar nombres propios que aparezcan en allowed_names o player.name. "
            "Si necesitas nombrar un rival, usa exactamente el nombre en espanol que aparece en el JSON. "
            "Cero jerga interna en el texto final. Prohibido escribir M1, M2, M3, M4, mvisit, xG, "
            "PSxG, multiplicador, puntos base, scope, ranking peers, knockout, score, stage, JSON. "
            "Traduce rival: si el dato indica rival fuerte, habla de rival de jerarquia; si indica "
            "rival menor, habla de rival considerado inferior frente a su seleccion, sin tono "
            "despectivo. Traduce fase: fase de grupos, ronda de eliminacion, dieciseisavos, octavos, "
            "cuartos, semifinal o final. Traduce momento: marcador empatado, iba perdiendo, minutos "
            "finales. Traduce dificultad: remate dificil. Traduce visitante: jugando de visitante. "
            "Nada de decimales crudos. Mejor 'mas de 7 de cada 10 remates' que '71.43%'. Si usas "
            "puntos SFA, redondea. Torneo en curso: no presentes cifras como definitivas; usa "
            "'hasta ahora', 'viene marcando', 'sostiene'. "
            "Anti-redundancia estricta: cada frase debe aportar un partido, un numero, un contraste "
            "o una lectura futbolera. No repitas la tesis. "
            "Constancia primero: el puesto se sostiene por el rendimiento a lo largo del torneo. La "
            "mejor escena es un ancla, no toda la historia. Para DEL y EXT mira goles, asistencias, "
            "regularidad y momentos. Para MCO mira creacion, pases clave, asistencias y participacion "
            "en goles. Para MC mira control, volumen y precision de pase, recuperaciones, duelos y "
            "rating; no menciones presion porque no existe esa metrica. Para LAT mira proyeccion "
            "ofensiva y solidez; si rindio ante rivales fuertes, ese es el gancho. Para DC, si esta "
            "arriba sin goles, recalca cortes anticipados, entradas ganadas, bloqueos y duelos; si "
            "un defensa participa en goles, tratalo como una rareza valiosa. "
            "Giro de honestidad: si un factor jugo en contra (rival inferior, local, fase temprana) "
            "y aun asi puntua alto, dilo. Si rindio contra rivales fuertes, ese debe ser el gancho. "
            "El texto no explica la formula; demuestra el principio en accion. "
            "short_text: una frase de 20 a 30 palabras, gancho puro, sin jerga. "
            "long_text: maximo 2 parrafos cortos, 90 a 120 palabras totales, sin encabezados ni "
            "vinetas. Parrafo 1: trayectoria y situacion, con una escena real si aplica. Parrafo 2: "
            "criterio, giro de honestidad si aplica y cierre discutible. "
            "bullets existe solo por compatibilidad tecnica: devuelve siempre un arreglo vacio. "
            "Devuelve exclusivamente JSON valido con keys: short_text, long_text, bullets."
        )
        payload = {
            "model": self._model,
            "instructions": prompt,
            "input": json.dumps(evidence.evidence, ensure_ascii=False, sort_keys=True),
            "reasoning": {"effort": "low"},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ranking_explanation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "short_text": {
                                "type": "string",
                                "description": "Frase editorial breve para el banner.",
                            },
                            "long_text": {
                                "type": "string",
                                "description": "Analisis editorial en maximo 2 parrafos breves.",
                            },
                            "bullets": {
                                "type": "array",
                                "minItems": 0,
                                "maxItems": 0,
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["short_text", "long_text", "bullets"],
                    },
                }
            },
            "max_output_tokens": max(self._max_output_tokens, 1200),
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        parsed = self._parse_output(data)
        short_text = _sanitize_output_text(str(parsed.get("short_text") or ""))[:280]
        long_text = _sanitize_output_text(str(parsed.get("long_text") or ""))[:1800]
        bullets_raw = parsed.get("bullets") or []
        bullets = [_sanitize_output_text(str(item)) for item in bullets_raw if str(item).strip()][:4]
        if not short_text or not long_text:
            raise ValueError("AI explanation output missing required text fields")

        usage = data.get("usage") or {}
        return RankingExplanationWriteResultDTO(
            short_text=short_text,
            long_text=long_text,
            bullets=bullets,
            variant="ai",
            status="generated",
            model_name=self._model,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
        )

    def _parse_output(self, data: dict) -> dict:
        output_text = data.get("output_text")
        if not output_text:
            chunks: list[str] = []
            for item in data.get("output", []) or []:
                for content in item.get("content", []) or []:
                    if content.get("type") == "output_text" and content.get("text"):
                        chunks.append(content["text"])
            output_text = "".join(chunks)
        if not output_text:
            raise ValueError("AI response did not include output_text")
        return json.loads(output_text)
