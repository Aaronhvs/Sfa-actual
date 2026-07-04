from __future__ import annotations

import json

import httpx

from sfa.domain.ranking_explanation_ports import (
    RankingExplanationEvidenceDTO,
    RankingExplanationWriteResultDTO,
)


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
            short_text=short[:280],
            long_text=long[:1800],
            bullets=bullets[:4],
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
            "Eres el analista editorial de SFA para publico hispanohablante. "
            "Tu trabajo no es repetir la tabla: debes explicar por que el ranking tiene sentido "
            "futbolisticamente usando solo el JSON de evidencia. "
            "Prioriza contexto y justificacion: aparicion en partidos, goles/asistencias en varios juegos, "
            "hat tricks si existen, partidos de mayor peso, rival/fase, bonus de veterano/promesa, recorrido "
            "y eventos con multiplicadores altos. "
            "No inventes datos, records historicos, rivales ni marcadores no presentes en la evidencia. "
            "Evita frases genericas como 'el motor pondera rival, fase y minuto' "
            "salvo que expliques un caso concreto. "
            "No menciones IDs, hashes, JSON ni nombres internos de campos. "
            "short_text debe ser una frase editorial potente de maximo 230 caracteres. "
            "long_text debe tener 2 parrafos breves: primero el argumento principal, segundo los hechos que lo sostienen. "
            "bullets debe contener 3 o 4 razones concretas, no resumenes de columnas. "
            "Devuelve exclusivamente JSON valido con keys: short_text, long_text, bullets."
        )
        payload = {
            "model": self._model,
            "instructions": prompt,
            "input": json.dumps(evidence.evidence, ensure_ascii=False, sort_keys=True),
            "max_output_tokens": self._max_output_tokens,
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
        short_text = str(parsed.get("short_text") or "")[:280]
        long_text = str(parsed.get("long_text") or "")[:1800]
        bullets_raw = parsed.get("bullets") or []
        bullets = [str(item) for item in bullets_raw if str(item).strip()][:4]
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
