"""Replay a previously captured snapshot; writes local report artifacts only."""

import argparse
import asyncio
import csv
import hashlib
import json
from pathlib import Path

from sfa.core.dependencies import get_player_position_audit_use_case


def longitudinal_markdown(data: dict) -> str:
    profiles = [(player, profile) for player in data["catalog"] for profile in player["longitudinal"]]
    profiles.sort(key=lambda item: (-item[1]["recent"]["observations"], item[0]["name"],
                                    item[1]["recent"]["context"]["team_id"],
                                    item[1]["recent"]["context"]["competition_id"]))
    result = (
        "# Perfiles posicionales SFA: vista previa longitudinal\n\n"
        f"Corte: {data['profile_as_of']}. Política: `{data['longitudinal_policy_version']}`.\n\n"
        "Se conservan perfiles de temporada y recientes por jugador, equipo y competición. "
        "La vista reciente usa hasta diez titularidades observadas en 180 días, incluidas las no interpretables. "
        "Sin inventario completo, la cobertura sigue desconocida. Son candidatos, no asignaciones publicadas.\n\n"
        f"- Contextos con titularidades conservadas: {data['summary']['longitudinal_contexts']}.\n"
        f"- Contextos con principal reciente sustentada en la muestra: "
        f"{data['summary']['longitudinal_recent_primary']}.\n"
        f"- Propuestas estabilizadas de rol/categoría/lado: {data['summary']['longitudinal_change_proposals']}.\n\n"
        "Los porcentajes describen titularidades interpretadas, no minutos ni todos los partidos del jugador. "
        "Datos muestra válidas/seleccionadas; las no interpretables no se sustituyen por partidos antiguos.\n\n"
        "| Jugador | Equipo / competición (IDs) | Actual efectiva | Ubicación inicial: temporada | Reciente | "
        "Secundarias | Datos | Cambio |\n"
        "|---|---|---|---|---|---|---:|---|\n"
    )

    def label(profile: dict) -> str:
        primary = profile["primary_position"]
        frequency = next((f for f in profile["position_distribution"] if f["value"] == primary), None)
        if frequency is None:
            return f"Sin predominio ({profile['observations']} observaciones)"
        return f"{profile['label']} · {frequency['share']:.0%}"

    for player, preview in profiles:
        recent = preview["recent"]
        context = recent["context"]
        secondary = ", ".join(f"{f['value']} {f['share']:.0%}" for f in recent["secondary_positions"]) or "—"
        changes = [p for p in preview["proposals"] if p["state"] in {"switch_pending", "change_proposed"}]
        change = "; ".join(f"{p['dimension']}: {p['incumbent']} → {p['candidate']} ({p['state']})"
                           for p in changes) or "—"
        name = player["name"].replace("|", "\\|")
        effective = "/".join(preview["legacy_effective_positions"]) or "—"
        candidate = label(recent) + (" †" if preview["candidate_comparison"] == "differs_from_legacy" else "")
        result += (f"| {name} | {context['team_id']} / {context['competition_id']} | {effective} | "
                   f"{label(preview['season'])} | {candidate} | {secondary} | "
                   f"{recent['observations']}/{recent['selected_starts']} | {change} |\n")
    return result + (
        "\nEsta distribución describe slots iniciales, no determina por sí sola la función habitual del futbolista. "
        "La categoría SFA y el rol táctico se calculan por separado: 40 % DM + 40 % CM suma 80 % MC, "
        "sin convertirlo en 80 % CM. La lateralidad se mide dentro del rol; los lados mixtos y los datos "
        "laterales insuficientes tienen motivos diferentes en el JSON/CSV.\n\n"
        "Una principal requiere ≥3 observaciones y ≥2/3 de respaldo. Las secundarias requieren ≥2 y ≥20 %. "
        "Las propuestas de cambio usan un buffer de ocho, mínimo seis válidas, ≥75 %, margen ≥20 puntos "
        "y dos cortes por partidos distintos, reproducidos por fecha, no por orden de descarga. "
        "Ninguna propuesta modifica posiciones aceptadas ni eventos puntuados. † Indica que el candidato "
        "difiere de la posición efectiva legacy, que se conserva y no se presenta como verificación.\n\n"
        "Los suplentes aparecen en el registro de apariciones del JSON; no reciben por inferencia el rol "
        "del jugador sustituido. Las correcciones explícitas generan una nueva revisión conservando la anterior.\n\n"
        f"Snapshot SHA-256: `{data['snapshot_sha256']}`. Reproducción offline; cero escrituras en producción.\n"
    )


def summary_markdown(data: dict) -> str:
    summary = data["summary"]
    acquisition = data.get("acquisition")
    acquisition_note = (
        f"Adquisición previa: {acquisition['lineup_calls']} consultas de alineaciones y "
        f"{acquisition['status_calls']} consultas de cuota. La reproducción posterior es offline.\n\n"
    ) if acquisition else "Origen: captura de caché existente; reproducción offline.\n\n"
    text = (
        "# Simulación de posiciones SFA\n\n"
        f"Temporada física: {data['season']}. Captura: {data['captured_at']}.\n\n"
        "Se ejecutó el primer hito del spec 0065: interpretación de alineaciones y auditoría offline. "
        "Todos los resultados son candidatos de posición inicial, no posiciones verificadas para publicar.\n\n"
        + acquisition_note
        +
        f"- Catálogo inventariado: **{summary['catalog_players']:,} jugadores**.\n"
        f"- Con evidencia utilizable en caché: **{summary['players_with_cached_evidence']} jugadores**.\n"
        f"- Sin evidencia utilizable: **{summary['players_without_cached_evidence']:,} jugadores**.\n"
        f"- Partidos de la temporada: {summary['season_fixtures']}; con caché: {summary['cached_season_fixtures']}.\n"
        f"- XI interpretables: {summary['valid_team_lineups']}; excluidos: {summary['invalid_team_lineups']}.\n"
        f"- Observaciones de casilla: {summary['slot_observations']}.\n"
        f"- Observaciones que difieren de la posición efectiva actual: "
        f"**{summary['projection_discrepancy_observations']}**. No son errores confirmados.\n"
        f"- Contextos elegibles para publicación: **{summary['eligible_contexts']}**.\n\n"
        "## Qué muestran las alineaciones\n\n"
        "| Jugador | Partido | Rol inicial | Lado | Candidato SFA | Posición efectiva actual |\n"
        "|---|---:|---|---|---|---|\n"
    )
    for item in data["observations"]:
        if item["differs_from_legacy_effective"] or item["role"] == "AM":
            name = (item["name"] or f"External ID {item['external_id']}").replace("|", "\\|")
            text += (f"| {name} | {item['fixture_id']} | {item['role']} | {item['side']} | "
                     f"{item['sfa_position'] or 'indeterminado'} | {item['legacy_effective_position'] or '—'} |\n")
    return text + (
        "\n## Límites y continuidad\n\n"
        "Los dibujos ausentes de las 12 plantillas acordadas quedan excluidos; no se convierten "
        "a otra formación. Las plantillas tienen pruebas sintéticas, todavía no una evaluación "
        "de exactitud deportiva.\n\n"
        "La base actual no permite reconstruir un inventario fiable de titularidades. La cobertura "
        "permanece desconocida, aunque un jugador acumulara tres observaciones. Los umbrales piloto "
        "de 3 partidos, 2/3 de soporte y 60 % de cobertura no son una probabilidad de acierto. "
        "Las observaciones de casilla no equivalen a posiciones verificadas.\n\n"
        "LD/LI se distinguen mediante FB + RIGHT/LEFT; ambos proyectan LAT. WB/WM y W/AM mantienen "
        "ambigüedad. La posición inicial no representa todos los minutos ni las acciones del partido.\n\n"
        "La siguiente fase requiere conservar alineaciones antes de que caduquen, registrar titularidades "
        "y validar más equipos, ligas y dibujos. Permanecen pendientes la integración continua, las "
        "asignaciones verificadas, la simulación de puntos y la publicación transaccional del spec 0065.\n\n"
        "No se escribieron datos en producción. La reproducción no hace llamadas al proveedor. "
        "La exportación inicial usó SQL READ ONLY y Redis solo SCAN/GET. La reproducción usa archivos locales; "
        "comprueba que el hash de entrada no cambie.\n\n"
        f"Snapshot SHA-256: `{data['snapshot_sha256']}`.\n"
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of", help="Timezone-aware cutoff for longitudinal profiles; defaults to snapshot capture")
    args = parser.parse_args()
    before = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()
    result = await get_player_position_audit_use_case(args.snapshot).execute(as_of=args.as_of)
    if hashlib.sha256(args.snapshot.read_bytes()).hexdigest() != before:
        raise RuntimeError("Snapshot changed while auditing")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "position-report.json").write_text(result.report_json + "\n", encoding="utf-8")
    data = json.loads(result.report_json)
    with (args.output / "position-catalog.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "external_id", "name", "position", "position_source", "status"])
        writer.writeheader()
        for player in data["catalog"]:
            writer.writerow({key: player[key] for key in writer.fieldnames})
    with (args.output / "position-observations.csv").open("w", newline="", encoding="utf-8-sig") as file:
        fields = ["player_id", "external_id", "name", "fixture_id", "team_id", "role", "side", "sfa_position",
                  "role_quality", "side_quality", "stored_position", "legacy_effective_position",
                  "differs_from_legacy_effective"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for observation in data["observations"]:
            writer.writerow({key: observation[key] for key in fields})
    (args.output / "position-summary.md").write_text(
        summary_markdown(data), encoding="utf-8",
    )
    (args.output / "position-profiles.md").write_text(longitudinal_markdown(data), encoding="utf-8")
    with (args.output / "position-profiles.csv").open("w", newline="", encoding="utf-8-sig") as file:
        fields = ["player_id", "name", "team_id", "competition_id", "season", "window", "as_of", "label",
                  "primary_position", "primary_role", "primary_side", "side_reason", "observations",
                  "selected_starts", "excluded_starts", "window_basis", "start_coverage", "freshness",
                  "secondary_positions", "candidate_only", "meets_evidence_gates"]
        fields += ["legacy_effective_positions", "candidate_comparison"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for player in data["catalog"]:
            for preview in player["longitudinal"]:
                for window in ("season", "recent"):
                    profile = preview[window]
                    row = {key: profile.get(key) for key in fields}
                    row.update(player_id=player["id"], name=player["name"], **{
                        key: profile["context"][key] for key in ("team_id", "competition_id", "season")})
                    row["secondary_positions"] = json.dumps(profile["secondary_positions"], ensure_ascii=False)
                    row["legacy_effective_positions"] = "/".join(preview["legacy_effective_positions"])
                    row["candidate_comparison"] = preview["candidate_comparison"]
                    writer.writerow(row)
    print(json.dumps(data["summary"], ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
